# Story 24.1: L1 规则引擎

**Story ID:** 24.1
**Epic:** 24 - 智能诊断核心引擎
**Status:** ready-for-dev
**Created:** 2026-03-06
**Author:** BMAD System

---

## 用户故事

As a 运维工程师,
I want 系统在告警触发时立即给出常见故障的快速诊断,
So that 我可以在1秒内获得初步故障判断，加快响应速度。

---

## 验收标准

**注意**: 本 Story 仅实现 L1 规则引擎核心功能。调度器、告警订阅、结果保存在 Story 24.2 实现。

- **Given** 管理员已在系统中配置 JSON 格式的诊断规则集（条件→结论，存储在 PostgreSQL `diagnosis_rules` 表——复用棕地已有表名）
- **When** 调用 `L1RuleEngine.match_rules(alarm_event)` 方法
- **Then** L1 引擎从内存中加载的规则集逐条匹配（规则在服务启动时从 DB 加载到内存 dict）
- **And** 匹配逻辑：先从告警关联的规则中收集所有需要的点位 ID，通过 Redis `MGET` 批量读取最新值（一次网络往返），再逐规则遍历 `conditions` 按 `logic`（AND/OR）组合判断
- **And** 匹配成功时输出结论（含根因描述、置信度、建议操作列表）
- **And** 全部匹配过程 < 1秒完成（纯内存操作，无 DB 查询）
- **And** 无规则匹配时返回 `matched: False`
- **And** 初始规则集覆盖 Top 20 高频故障中 ≥12 类（60%），由运维专家协助编写

---

## 技术实现要点

### 数据库设计

**复用棕地已有表 `diagnosis_rules`（复数形式）**。

**现有表结构**（来自 `backend/app/models/diagnosis.py`）：
- `rule_code` (String(50), unique, 规则编码)
- `name` (String(100), 规则名称)
- `description` (Text, 规则描述)
- `category` (String(30), 分类)
- `trigger_condition` (JSON, 触发条件)
- `diagnosis_logic` (JSON, 诊断逻辑)
- `priority` (Integer, 优先级，**数字越小优先级越高**，与告警级别一致：紧急=10, 重要=30, 一般=50)
- `is_enabled` (Boolean, 是否启用)
- `is_system` (Boolean, 是否系统内置)

**L1 引擎复用策略**：
- 使用 `trigger_condition` JSON 字段存储条件列表和逻辑运算符
- 使用 `diagnosis_logic` JSON 字段存储结论、置信度、建议操作
- 使用 `category` 字段存储设备类型（如 "power/ups"）
- **不需要新增字段**，完全复用现有结构

**Alembic 迁移脚本**（仅添加索引优化查询）：

```python
# 新增迁移脚本: backend/alembic/versions/xxxx_add_diagnosis_rules_indexes.py

def upgrade():
    # 添加索引加速 L1 引擎查询
    op.create_index('ix_diagnosis_rules_category_enabled', 'diagnosis_rules', ['category', 'is_enabled'])
    op.create_index('ix_diagnosis_rules_priority_enabled', 'diagnosis_rules', ['priority', 'is_enabled'], postgresql_ops={'priority': 'DESC'})

def downgrade():
    op.drop_index('ix_diagnosis_rules_priority_enabled', table_name='diagnosis_rules')
    op.drop_index('ix_diagnosis_rules_category_enabled', table_name='diagnosis_rules')
```

**规则 JSON 格式示例**（复用现有字段）：

```json
{
  "rule_code": "R001",
  "name": "UPS电池低压",
  "category": "power/ups",
  "trigger_condition": {
    "logic": "AND",
    "conditions": [
      {"point_id": "point_123", "operator": "<", "value": 44.0},
      {"point_id": "point_456", "operator": "==", "value": "ON_BATTERY"}
    ]
  },
  "diagnosis_logic": {
    "conclusion": "UPS电池组电压过低，可能需要更换电池",
    "confidence": 0.85,
    "suggested_actions": ["检查电池组内阻", "联系维保更换电池"],
    "possible_causes": ["电池老化", "充电器故障"]
  },
  "priority": 10,  # 数字越小优先级越高（紧急故障）
  "is_enabled": true
}
```

**字段映射说明**：
- `category`: 用于快速过滤设备类型（如 "power/ups", "cooling/ac"）
- `trigger_condition.logic`: AND/OR 逻辑运算符
- `trigger_condition.conditions`: 条件列表，每个条件包含 `point_id`（点位ID）、`operator`（比较运算符）、`value`（阈值）
- `diagnosis_logic.conclusion`: 诊断结论文本
- `diagnosis_logic.confidence`: 置信度 (0.0-1.0)
- `diagnosis_logic.suggested_actions`: 建议操作列表
- `priority`: 优先级，**数字越小越优先**（紧急=10, 重要=30, 一般=50）

### 内存缓存架构

```python
# backend/app/services/diagnosis/l1_engine.py

import json
import time
from typing import Dict, List
from app.models.diagnosis import DiagnosisRule
from app.core.database import async_session
from app.core.config import get_settings
from sqlalchemy import select
import redis.asyncio as aioredis

settings = get_settings()

class L1RuleEngine:
    def __init__(self, redis_client: aioredis.Redis):
        # 规则索引: {category: [DiagnosisRule, ...]}
        self.rule_index: Dict[str, List[DiagnosisRule]] = {}
        self.redis_client = redis_client

    async def load_rules(self):
        """服务启动时从 DB 加载规则到内存（使用 copy-on-write 避免竞态条件）"""
        async with async_session() as session:
            result = await session.execute(
                select(DiagnosisRule)
                .where(DiagnosisRule.is_enabled == True)
                .order_by(DiagnosisRule.priority.asc())  # 数字越小优先级越高
            )
            rules = result.scalars().all()

            # 构建新索引（不影响旧索引）
            new_index: Dict[str, List[DiagnosisRule]] = {}
            for rule in rules:
                category = rule.category or "general"
                if category not in new_index:
                    new_index[category] = []
                new_index[category].append(rule)

            # 原子替换索引（copy-on-write）
            self.rule_index = new_index

    async def match_rules(self, alarm_event: dict) -> dict:
        """
        匹配规则并返回诊断结果

        Args:
            alarm_event: {
                "device_id": "xxx",
                "device_category": "power/ups",  # 对应 category 字段
                "alarm_level": "critical",
                "point_id": "xxx"
            }

        Returns:
            {
                "matched": True/False,
                "conclusion": "...",
                "confidence": 0.85,
                "suggested_actions": [...],
                "rule_code": "R001",
                "inference_time_ms": 123
            }
        """
        start_time = time.time()

        # 1. 查找候选规则
        category = alarm_event.get("device_category", "general")
        candidate_rules = self.rule_index.get(category, [])

        if not candidate_rules:
            return {
                "matched": False,
                "conclusion": "L1未匹配到规则",
                "confidence": 0.0,
                "inference_time_ms": int((time.time() - start_time) * 1000)
            }

        # 2. 收集所有需要的点位 ID
        point_ids = set()
        for rule in candidate_rules:
            trigger_cond = rule.trigger_condition or {}
            conditions = trigger_cond.get("conditions", [])
            for condition in conditions:
                if "point_id" in condition:
                    point_ids.add(condition["point_id"])

        # 3. 批量从 Redis 读取点位值（一次 MGET）
        if point_ids:
            redis_keys = [f"point:{pid}:value" for pid in point_ids]
            values = await self.redis_client.mget(redis_keys)
            # Redis 返回 bytes 或 None，需要解码
            point_values = {}
            for pid, val in zip(point_ids, values):
                if val is not None:
                    try:
                        point_values[pid] = val.decode('utf-8') if isinstance(val, bytes) else str(val)
                    except Exception:
                        point_values[pid] = None
                else:
                    point_values[pid] = None
        else:
            point_values = {}

        # 4. 逐规则匹配
        for rule in candidate_rules:
            if self._evaluate_rule(rule, point_values):
                diagnosis_logic = rule.diagnosis_logic or {}
                return {
                    "matched": True,
                    "conclusion": diagnosis_logic.get("conclusion", "未知故障"),
                    "confidence": diagnosis_logic.get("confidence", 0.5),
                    "suggested_actions": diagnosis_logic.get("suggested_actions", []),
                    "rule_code": rule.rule_code,
                    "inference_time_ms": int((time.time() - start_time) * 1000)
                }

        # 5. 无规则匹配
        return {
            "matched": False,
            "conclusion": "L1未匹配到规则",
            "confidence": 0.0,
            "inference_time_ms": int((time.time() - start_time) * 1000)
        }

    def _evaluate_rule(self, rule: DiagnosisRule, point_values: dict) -> bool:
        """评估单条规则是否匹配"""
        trigger_cond = rule.trigger_condition or {}
        logic = trigger_cond.get("logic", "AND")
        conditions = trigger_cond.get("conditions", [])

        if not conditions:
            return False

        results = []
        for condition in conditions:
            point_id = condition.get("point_id")
            operator = condition.get("operator")
            threshold = condition.get("value")

            if not point_id or not operator or threshold is None:
                results.append(False)
                continue

            if point_id not in point_values or point_values[point_id] is None:
                results.append(False)
                continue

            try:
                current_value = float(point_values[point_id])
                threshold_value = float(threshold)
            except (ValueError, TypeError):
                # 非数字值，尝试字符串比较
                current_value = str(point_values[point_id])
                threshold_value = str(threshold)

            # 执行比较
            try:
                if operator == "<":
                    results.append(current_value < threshold_value)
                elif operator == ">":
                    results.append(current_value > threshold_value)
                elif operator == "==":
                    results.append(current_value == threshold_value)
                elif operator == "<=":
                    results.append(current_value <= threshold_value)
                elif operator == ">=":
                    results.append(current_value >= threshold_value)
                elif operator == "!=":
                    results.append(current_value != threshold_value)
                else:
                    results.append(False)
            except Exception:
                results.append(False)

        # 根据 logic 组合结果
        if logic == "AND":
            return all(results) if results else False
        elif logic == "OR":
            return any(results) if results else False
        else:
            return False
```

### 规则热更新

```python
# backend/app/services/diagnosis/rule_manager.py

import redis.asyncio as aioredis
import asyncio

class RuleManager:
    def __init__(self, l1_engine: 'L1RuleEngine', redis_client: aioredis.Redis):
        self.l1_engine = l1_engine
        self.redis_client = redis_client
        self._listener_task = None

    async def start_listener(self):
        """订阅 Redis Pub/Sub 监听规则更新事件"""
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe("diagnosis:rule_update")

        async for message in pubsub.listen():
            if message["type"] == "message":
                # 重新加载规则
                await self.l1_engine.load_rules()
                print("诊断规则已热更新")

    def start(self):
        """启动监听器（非阻塞）"""
        self._listener_task = asyncio.create_task(self.start_listener())

    async def stop(self):
        """停止监听器"""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
```

**触发机制**：管理员通过 API 修改规则后，API 端点发布 Redis 事件：

```python
# backend/app/api/v1/diagnosis.py (示例，本 Story 不实现完整 API)

@router.put("/rules/{rule_id}")
async def update_rule(rule_id: int, rule_data: dict, redis: aioredis.Redis = Depends(get_redis)):
    # 更新数据库
    # ...

    # 发布热更新事件
    await redis.publish("diagnosis:rule_update", "reload")
    return {"message": "规则已更新"}
```

### 与告警引擎集成（简化版）

**注意**: 完整的诊断调度器和并发控制在 Story 24.2 实现。本 Story 仅实现 L1 引擎核心逻辑。

```python
# backend/app/services/diagnosis/__init__.py

from .l1_engine import L1RuleEngine
from .rule_manager import RuleManager

__all__ = ["L1RuleEngine", "RuleManager"]
```

**FastAPI lifespan 集成示例**（完整实现在 Story 24.2）：

```python
# backend/app/main.py (部分代码)

from contextlib import asynccontextmanager
from app.services.diagnosis import L1RuleEngine, RuleManager
from app.core.redis import get_redis_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    redis_client = await get_redis_client()
    l1_engine = L1RuleEngine(redis_client)
    await l1_engine.load_rules()

    rule_manager = RuleManager(l1_engine, redis_client)
    rule_manager.start()

    # 将引擎实例存储到 app.state
    app.state.l1_engine = l1_engine
    app.state.rule_manager = rule_manager

    yield

    # 关闭时清理
    await rule_manager.stop()
    await redis_client.close()

app = FastAPI(lifespan=lifespan)
```

---

## 初始规则集

根据验收标准，初始规则集需覆盖 Top 20 高频故障中 ≥12 类（60%）。以下是建议的初始规则类别和示例规则。

### 规则初始化方式

通过 Alembic 数据迁移脚本初始化：

```python
# backend/alembic/versions/xxxx_init_l1_diagnosis_rules.py

from alembic import op
import sqlalchemy as sa
from datetime import datetime
import json

def upgrade():
    # 插入初始规则
    op.execute(f"""
        INSERT INTO diagnosis_rules (rule_code, name, category, trigger_condition, diagnosis_logic, priority, is_enabled, is_system, created_at, updated_at)
        VALUES
        ('R001', 'UPS电池低压', 'power/ups',
         '{json.dumps({"logic": "AND", "conditions": [{"point_id": "ups_battery_voltage", "operator": "<", "value": 44.0}, {"point_id": "ups_status", "operator": "==", "value": "ON_BATTERY"}]})}',
         '{json.dumps({"conclusion": "UPS电池组电压过低，可能需要更换电池", "confidence": 0.9, "suggested_actions": ["检查电池组内阻", "联系维保更换电池"], "possible_causes": ["电池老化", "充电器故障"]})}',
         10, true, true, '{datetime.now()}', '{datetime.now()}'),

        ('R002', 'UPS过载', 'power/ups',
         '{json.dumps({"logic": "AND", "conditions": [{"point_id": "ups_load_percent", "operator": ">", "value": 90.0}]})}',
         '{json.dumps({"conclusion": "UPS负载过高，存在过载风险", "confidence": 0.85, "suggested_actions": ["检查负载分布", "考虑扩容"], "possible_causes": ["新增设备", "负载不均"]})}',
         15, true, true, '{datetime.now()}', '{datetime.now()}')
        -- 继续添加其他 10 条规则...
    """)

def downgrade():
    op.execute("DELETE FROM diagnosis_rules WHERE is_system = true")
```

### 电力系统（4类）

1. **UPS 电池低压** (R001)
   - category: "power/ups"
   - 条件: 电池电压 < 44V AND UPS 状态 = ON_BATTERY
   - 置信度: 0.9

2. **UPS 过载** (R002)
   - category: "power/ups"
   - 条件: 负载率 > 90%
   - 置信度: 0.85

3. **PDU 过载** (R003)
   - category: "power/pdu"
   - 条件: PDU 电流 > 额定电流 * 0.9
   - 置信度: 0.85

4. **市电中断** (R004)
   - category: "power/mains"
   - 条件: 市电状态 = OFFLINE
   - 置信度: 0.95

### 暖通系统（3类）

5. **空调高温告警** (R005)
   - category: "cooling/ac"
   - 条件: 回风温度 > 设定温度 + 5°C
   - 置信度: 0.8

6. **空调制冷剂泄漏** (R006)
   - category: "cooling/ac"
   - 条件: 制冷剂压力 < 正常值 * 0.7
   - 置信度: 0.75

7. **冷却水泵故障** (R007)
   - category: "cooling/pump"
   - 条件: 水泵运行状态 = STOPPED AND 空调运行中
   - 置信度: 0.9

### 环境监测（3类）

8. **机房温度过高** (R008)
   - category: "environment/temperature"
   - 条件: 机房温度 > 28°C
   - 置信度: 0.85

9. **机房湿度异常** (R009)
   - category: "environment/humidity"
   - 条件: 湿度 < 30% OR 湿度 > 70%
   - 置信度: 0.8

10. **漏水检测** (R010)
    - category: "environment/leak"
    - 条件: 漏水传感器状态 = LEAK
    - 置信度: 0.95

### 通信与网络（2类）

11. **网关离线** (R011)
    - category: "communication/gateway"
    - 条件: 网关心跳超时 > 60 秒
    - 置信度: 0.9

12. **设备通信中断** (R012)
    - category: "communication/device"
    - 条件: 设备最后通信时间 > 300 秒
    - 置信度: 0.85

**规则编写指南**：
- 每类故障至少 1 条规则
- 规则优先级：紧急故障（10-20）> 重要故障（30-50）> 一般故障（60-100）
- 置信度：明确故障（0.9+）> 可能故障（0.7-0.9）> 疑似故障（0.5-0.7）
- **注意**: 上述规则中的 `point_id` 需要根据实际系统中的点位 ID 替换

---

## 架构参考

- **Architecture 18.2**: L1 规则引擎架构
- **Architecture 18.3**: 告警引擎 → 诊断引擎集成
- **PRD FR34-1**: L1 规则引擎需求

---

## 开发者上下文

### 棕地约束

1. **表名复数形式**: 复用已有 `diagnosis_rules` 表（复数），不要创建 `diagnosis_rule`（单数）
2. **Alembic 迁移**: 仅添加索引，不修改表结构
3. **ORM 模型**: 无需修改 `backend/app/models/diagnosis.py`
4. **Redis 客户端**: 复用棕地已有 `app.core.redis.get_redis_client()` 函数（如不存在需新建）
5. **category 长度限制**: 现有字段 `String(30)`，分类路径不要超过 30 字符

### Redis 配置

```python
# backend/app/core/redis.py (如不存在需新建)

import redis.asyncio as aioredis
from app.core.config import get_settings

settings = get_settings()

_redis_client: aioredis.Redis = None

async def get_redis_client() -> aioredis.Redis:
    """获取 Redis 客户端单例"""
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=False,  # L1 引擎需要手动解码
            max_connections=50,  # 连接池大小
            socket_timeout=5.0,  # 超时 5 秒
            socket_connect_timeout=5.0
        )
    return _redis_client

async def close_redis_client():
    """关闭 Redis 客户端"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
```

### 技术栈

- **后端**: FastAPI 0.109.0 + SQLAlchemy 2.0 (async) + Pydantic v2
- **缓存**: Redis 7 (redis.asyncio)
- **数据库**: PostgreSQL 16
- **异步**: asyncio + asyncio.PriorityQueue

### 文件结构

```
backend/
├── alembic/versions/
│   └── xxxx_add_diagnosis_rules_indexes.py  # 新建迁移（仅添加索引）
├── app/
│   ├── models/
│   │   └── diagnosis.py  # 已存在，无需修改
│   └── services/diagnosis/
│       ├── __init__.py  # 新建
│       ├── l1_engine.py  # 新建 L1 引擎
│       └── rule_manager.py  # 新建规则管理器
```

**注意**: 调度器 (`scheduler.py`) 和诊断 API (`api/v1/diagnosis.py`) 在 Story 24.2 实现。

### 性能要求

- L1 推理 < 1 秒
- Redis MGET 批量读取（一次网络往返）
- 规则匹配纯内存操作

### 测试策略

1. **单元测试**: 规则匹配逻辑
   - AND 逻辑：所有条件满足
   - OR 逻辑：至少一个条件满足
   - 空规则集：返回未匹配
   - 空条件列表：返回 False
   - Redis 返回 None：条件判断为 False
   - 非数字比较：字符串相等比较
   - 无效运算符：条件判断为 False
   - 空 category：使用 "general" 默认值

2. **集成测试**: 规则加载和匹配流程
   - 从数据库加载规则
   - 规则索引构建正确性
   - Redis 批量读取点位值
   - 完整匹配流程

3. **性能测试**:
   - 1000 条规则加载时间 < 2 秒
   - 单次推理 < 1 秒（包含 Redis 查询）
   - 并发 10 个推理请求无性能退化

4. **竞态条件测试**:
   - 规则热更新期间并发推理请求
   - 验证 copy-on-write 机制有效性

---

## FR 追溯

- **FR34-1**: L1 规则引擎

---

## 完成标准

- [ ] Alembic 迁移脚本创建并执行成功（仅添加索引）
- [ ] L1RuleEngine 类实现并通过单元测试
- [ ] RuleManager 类实现规则热更新
- [ ] 规则加载和索引构建功能完成
- [ ] 规则匹配逻辑通过单元测试（AND/OR 组合、边界情况）
- [ ] Redis 值类型转换和错误处理完整
- [ ] 性能测试通过（1000 条规则加载 < 2 秒，单次推理 < 1 秒）
- [ ] 代码审查通过

**不包含在本 Story 中**（在 Story 24.2 实现）：
- 诊断调度器和并发控制
- 告警事件订阅
- 诊断结果保存到数据库
- L2 升级逻辑

---

**Created by BMAD Method - Story Context Engine**
**Date:** 2026-03-06
