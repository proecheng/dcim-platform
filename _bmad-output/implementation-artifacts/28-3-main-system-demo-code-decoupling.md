# Story 28.3: 主系统代码与 Demo 编码解耦

**Epic:** 28 - Demo 系统解耦与数据隔离
**优先级:** P1
**状态:** ready-for-dev
**创建时间:** 2026-03-05
**Story 来源:** Epic 28, Architecture V4.0.0 Section 20, docs/demo-system-audit.md

---

## 用户故事

**As a** 开发者
**I want** 主系统业务服务不硬编码 demo 特定的设备编码和楼层规则
**So that** 非 demo 环境中这些服务能正常工作，且新增设备能被正确匹配

---

## 业务价值

- **可维护性提升**: 消除主系统对 demo 数据的硬编码依赖，降低维护成本
- **部署灵活性**: 支持纯生产环境部署，无需携带 demo 相关代码
- **扩展性增强**: 新增设备和楼层时无需修改硬编码规则
- **代码清晰度**: 明确分离 demo 逻辑与业务逻辑

---

## 验收标准 (AC)

### AC1: 点位匹配引擎解耦

**Given** `point_device_matcher.py` 的 `LEGACY_MAPPING_RULES` 包含 20+ 条硬编码 demo 设备码
**When** 重构点位匹配引擎
**Then**
- `LEGACY_MAPPING_RULES` 从 `point_device_matcher.py` 移除
- 迁移到 `backend/app/demo/data/legacy_mapping.py`
- 主系统仅保留通用的 `derive_point_prefix()` 和 `identify_point_usage()` 算法

### AC2: Demo 规则注册机制

**Given** Demo 模块需要使用 legacy 映射规则
**When** Demo 模块初始化
**Then**
- Demo 模块通过注册机制将 legacy 规则注入匹配引擎（可选）
- 注册机制支持动态添加/移除规则（按来源标识）
- 主系统在 demo 禁用时不加载这些规则
- Demo 关闭时自动卸载注册的规则

### AC3: 楼层列表动态查询

**Given** `device_sync.py` 硬编码楼层列表 `["F1", "F2", "F3", "F4"]`
**When** 重构设备同步服务
**Then**
- 楼层列表从数据库 Floor 表动态查询
- 移除所有硬编码楼层字符串
- 支持任意数量和命名的楼层

### AC4: 回路推断规则参数化

**Given** `device_sync.py` 硬编码回路名称 `"C-CH-01"`, `"C-AC-01"` 等
**When** 重构回路推断逻辑
**Then**
- 回路推断规则参数化
- 从 DistributionCircuit 表动态匹配
- 移除所有硬编码回路字符串

### AC5: building_points.py 迁移

**Given** `building_points.py` 包含 demo 特定的点位定义
**When** 重构目录结构
**Then**
- `backend/app/data/building_points.py` 移动到 `backend/app/demo/data/building_points.py`
- 主系统不再直接导入此文件
- Demo 模块内部使用此文件
- 验证以下文件不再导入 building_points.py:
  - `app/services/point_device_matcher.py`
  - `app/services/device_sync.py`
  - `app/api/v1/*.py` (所有 API 路由)
- 仅允许 `app/demo/` 目录下的文件导入

### AC6: Demo 禁用测试

**Given** Demo 功能已解耦
**When** 在 demo 禁用状态下运行后端测试
**Then**
- 所有主系统服务无 ImportError，包括:
  - `app/services/point_device_matcher.py`
  - `app/services/device_sync.py`
  - `app/services/ingest_pipeline.py`
  - `app/api/v1/device.py`
  - `app/api/v1/point.py`
- 核心业务逻辑测试通过（至少 90% 通过率）
- 无 demo 相关的硬编码错误
- 测试覆盖率不低于重构前水平

---

## 技术设计

### 1. 架构概览

```
主系统 (app/services/)
├── point_device_matcher.py  [通用算法]
│   ├── derive_point_prefix()
│   ├── identify_point_usage()
│   └── MatcherRegistry (新增)
└── device_sync.py  [参数化逻辑]
    ├── get_floors_from_db()
    └── match_circuit_from_db()

Demo 模块 (app/demo/)
├── data/
│   ├── legacy_mapping.py  [Demo 特定规则]
│   └── building_points.py  [Demo 点位定义]
└── lifecycle.py
    └── register_demo_rules()  [注册机制]
```

### 2. 点位匹配引擎重构

#### 2.1 当前问题

`point_device_matcher.py` 包含硬编码规则：

```python
LEGACY_MAPPING_RULES = {
    "UPS-01-AI-01": {"device_code": "UPS-01", "point_type": "AI"},
    "AC-01-AI-01": {"device_code": "AC-01", "point_type": "AI"},
    # ... 20+ 条硬编码规则
}
```

#### 2.2 重构方案

**主系统 (point_device_matcher.py):**

```python
from threading import RLock
from functools import lru_cache
from typing import Dict, Optional, Set

class MatcherRegistry:
    """点位匹配规则注册表（线程安全）"""
    _rules: Dict[str, Dict] = {}
    _lock = RLock()
    _registered_sources: Set[str] = set()  # 跟踪注册来源

    @classmethod
    def register(cls, rules: Dict[str, Dict], source: str = "default"):
        """注册自定义规则

        Args:
            rules: 规则字典
            source: 规则来源标识（用于后续卸载）
        """
        with cls._lock:
            cls._rules.update(rules)
            cls._registered_sources.add(source)

    @classmethod
    def unregister(cls, source: str):
        """卸载指定来源的规则

        Args:
            source: 规则来源标识
        """
        with cls._lock:
            # 移除该来源的所有规则
            keys_to_remove = [
                k for k, v in cls._rules.items()
                if v.get("_source") == source
            ]
            for key in keys_to_remove:
                del cls._rules[key]
            cls._registered_sources.discard(source)

    @classmethod
    def clear(cls):
        """清空所有规则（用于测试）"""
        with cls._lock:
            cls._rules.clear()
            cls._registered_sources.clear()

    @classmethod
    def get_rule(cls, point_code: str) -> Optional[Dict]:
        """获取单个规则（避免复制整个字典）"""
        with cls._lock:
            return cls._rules.get(point_code)

    @classmethod
    def has_rules(cls) -> bool:
        """检查是否有注册的规则"""
        with cls._lock:
            return len(cls._rules) > 0

def derive_point_prefix(point_code: str) -> Optional[str]:
    """通用算法：从点位编码推导设备前缀"""
    # 检查注册的规则（优化：直接获取单个规则）
    rule = MatcherRegistry.get_rule(point_code)
    if rule:
        return rule.get("device_code")

    # 通用模式匹配
    # 格式: DEVICE-XX-TYPE-YY
    parts = point_code.split("-")
    if len(parts) >= 2:
        return "-".join(parts[:2])  # 返回 DEVICE-XX

    return None

def identify_point_usage(point_code: str, point_name: str) -> str:
    """通用算法：识别点位用途

    使用多层匹配策略避免误判：
    1. 精确关键词匹配
    2. 点位编码模式匹配
    3. 排除告警/状态类点位
    """
    # 排除告警和状态类点位
    if any(keyword in point_name for keyword in ["告警", "故障", "状态", "开关"]):
        return "status"

    # 温度类点位
    if any(keyword in point_name for keyword in ["温度", "温湿度"]) or "TEMP" in point_code.upper():
        if "告警" not in point_name:  # 二次确认
            return "temperature"

    # 湿度类点位
    if "湿度" in point_name or "HUMI" in point_code.upper():
        if "告警" not in point_name:
            return "humidity"

    # 电流/电压
    if any(keyword in point_name for keyword in ["电流", "电压", "功率"]):
        return "electrical"

    # ... 更多通用模式
    return "unknown"
```

**Demo 模块 (demo/data/legacy_mapping.py):**

```python
"""Demo 环境的 Legacy 映射规则"""

# 为每个规则添加来源标记
DEMO_LEGACY_RULES = {
    "UPS-01-AI-01": {"device_code": "UPS-01", "point_type": "AI", "_source": "demo"},
    "AC-01-AI-01": {"device_code": "AC-01", "point_type": "AI", "_source": "demo"},
    "PDU-01-AI-01": {"device_code": "PDU-01", "point_type": "AI", "_source": "demo"},
    # ... 所有 demo 特定规则
}

def register_demo_rules():
    """注册 Demo 规则到主系统"""
    try:
        from app.services.point_device_matcher import MatcherRegistry
        MatcherRegistry.register(DEMO_LEGACY_RULES, source="demo")
        logger.info("✓ Demo legacy 规则注册成功")
    except Exception as e:
        logger.error(f"✗ Demo legacy 规则注册失败: {e}")
        # 不抛出异常，允许 demo 继续启动

def unregister_demo_rules():
    """卸载 Demo 规则"""
    try:
        from app.services.point_device_matcher import MatcherRegistry
        MatcherRegistry.unregister(source="demo")
        logger.info("✓ Demo legacy 规则卸载成功")
    except Exception as e:
        logger.error(f"✗ Demo legacy 规则卸载失败: {e}")
```

**Demo 生命周期 (demo/lifecycle.py):**

```python
async def demo_startup():
    """Demo 启动流程"""
    if settings.demo_enabled:
        # 注册 demo 特定规则（带错误处理）
        try:
            from app.demo.data.legacy_mapping import register_demo_rules
            register_demo_rules()
        except Exception as e:
            logger.error(f"Demo 规则注册失败: {e}")
            # 继续启动，不影响其他 demo 功能

        # ... 其他 demo 初始化

async def demo_shutdown():
    """Demo 关闭流程"""
    if settings.demo_enabled:
        # 卸载 demo 规则
        try:
            from app.demo.data.legacy_mapping import unregister_demo_rules
            unregister_demo_rules()
        except Exception as e:
            logger.error(f"Demo 规则卸载失败: {e}")
```

### 3. device_sync.py 参数化

#### 3.1 当前问题

```python
# 硬编码楼层
FLOORS = ["F1", "F2", "F3", "F4"]

# 硬编码回路
if device_type == "空调":
    circuit_code = "C-AC-01"
elif device_type == "照明":
    circuit_code = "C-CH-01"
```

#### 3.2 重构方案

```python
from functools import lru_cache
from typing import List, Optional

# 楼层列表缓存（TTL 1小时，楼层变化频率低）
@lru_cache(maxsize=1)
def _get_floors_cache_key() -> int:
    """缓存键生成器（基于时间戳）"""
    import time
    return int(time.time() / 3600)  # 每小时更新

async def get_floors_from_db(session: AsyncSession, use_cache: bool = True) -> List[str]:
    """从数据库动态查询楼层列表

    Args:
        session: 数据库会话
        use_cache: 是否使用缓存（默认 True）

    Returns:
        楼层编码列表，按 sort_order 排序
    """
    if use_cache:
        cache_key = _get_floors_cache_key()
        # 缓存逻辑由 lru_cache 处理

    result = await session.execute(
        select(Floor.floor_code)
        .order_by(Floor.sort_order)
    )
    floors = [row[0] for row in result.fetchall()]

    if not floors:
        logger.warning("数据库中没有楼层数据，返回空列表")

    return floors

async def match_circuit_from_db(
    session: AsyncSession,
    device_category: str,  # 使用 category 而非 type
    floor_code: str
) -> Optional[str]:
    """从数据库动态匹配配电回路

    Args:
        session: 数据库会话
        device_category: 设备类别（如 "hvac", "lighting", "power"）
        floor_code: 楼层编码

    Returns:
        回路编码，如果未找到返回 None

    Note:
        DistributionCircuit 表结构:
        - circuit_code: VARCHAR(50) 回路编码
        - circuit_name: VARCHAR(100) 回路名称
        - floor_id: INT 楼层ID（外键）
        - category: VARCHAR(50) 回路类别（hvac/lighting/power/other）
    """
    # 先查询楼层ID
    floor_result = await session.execute(
        select(Floor.id).where(Floor.floor_code == floor_code)
    )
    floor_row = floor_result.fetchone()
    if not floor_row:
        logger.warning(f"未找到楼层: {floor_code}")
        return None

    floor_id = floor_row[0]

    # 根据楼层ID和类别查询回路
    result = await session.execute(
        select(DistributionCircuit.circuit_code)
        .where(
            DistributionCircuit.floor_id == floor_id,
            DistributionCircuit.category == device_category
        )
        .limit(1)
    )
    row = result.fetchone()
    return row[0] if row else None

# 设备类型到回路类别的映射
DEVICE_TYPE_TO_CATEGORY = {
    "空调": "hvac",
    "精密空调": "hvac",
    "新风机": "hvac",
    "照明": "lighting",
    "UPS": "power",
    "配电柜": "power",
    "PDU": "power",
}

async def sync_devices(session: AsyncSession):
    """设备同步主流程

    从数据库动态获取楼层和回路信息，避免硬编码
    """
    # 动态获取楼层
    floors = await get_floors_from_db(session)

    if not floors:
        logger.warning("没有楼层数据，跳过设备同步")
        return

    for floor_code in floors:
        logger.info(f"同步楼层 {floor_code} 的设备")

        # 遍历需要同步的设备类型
        for device_type, category in DEVICE_TYPE_TO_CATEGORY.items():
            # 动态匹配回路
            circuit_code = await match_circuit_from_db(session, category, floor_code)

            if circuit_code:
                logger.debug(f"楼层 {floor_code} 的 {device_type} 匹配到回路: {circuit_code}")
                # ... 同步逻辑
            else:
                logger.debug(f"楼层 {floor_code} 的 {device_type} 未找到匹配回路")
```

### 4. 目录结构调整

**迁移前:**
```
backend/app/
├── data/
│   └── building_points.py  [Demo 特定]
└── services/
    ├── point_device_matcher.py  [含硬编码]
    └── device_sync.py  [含硬编码]
```

**迁移后:**
```
backend/app/
├── services/
│   ├── point_device_matcher.py  [纯通用算法]
│   └── device_sync.py  [参数化逻辑]
└── demo/
    └── data/
        ├── legacy_mapping.py  [Demo 规则]
        └── building_points.py  [Demo 点位]
```

---

## 实施步骤

### Phase 1: 点位匹配引擎重构（必须先完成）

1. **创建注册机制**
   - 在 `point_device_matcher.py` 中添加 `MatcherRegistry` 类
   - 实现线程安全的注册/卸载机制
   - 修改 `derive_point_prefix()` 支持注册规则查询

2. **迁移 Legacy 规则**
   - 创建 `backend/app/demo/data/legacy_mapping.py`
   - 将 `LEGACY_MAPPING_RULES` 移动到新文件
   - 为每个规则添加 `_source` 标记
   - 实现 `register_demo_rules()` 和 `unregister_demo_rules()` 函数

3. **集成到 Demo 生命周期**
   - 修改 `demo/lifecycle.py` 的 `demo_startup()`
   - 在 demo 启用时注册规则（带错误处理）
   - 修改 `demo_shutdown()` 卸载规则

### Phase 2: device_sync.py 参数化（依赖 Phase 1）

1. **实现动态查询函数**
   - 添加 `get_floors_from_db()` 带缓存
   - 添加 `match_circuit_from_db()`
   - 定义 `DEVICE_TYPE_TO_CATEGORY` 映射

2. **重构同步逻辑**
   - 移除硬编码楼层列表
   - 移除硬编码回路名称
   - 使用动态查询函数

### Phase 3: building_points.py 迁移（可与 Phase 2 并行）

1. **移动文件**
   - `app/data/building_points.py` → `app/demo/data/building_points.py`

2. **更新导入**
   - 全局搜索 `from app.data.building_points import`
   - 更新所有导入路径到 `app.demo.data.building_points`
   - 验证只有 demo 模块导入

### Phase 4: 测试验证（必须最后执行）

1. **Demo 禁用测试**
   - 设置 `DEMO_ENABLED=false`
   - 运行后端测试套件
   - 验证无 ImportError
   - 验证测试通过率 >= 90%

2. **Demo 启用测试**
   - 设置 `DEMO_ENABLED=true`
   - 验证 legacy 规则正常工作
   - 验证设备同步正常
   - 验证规则卸载功能

**注意:** Phase 1 必须先完成，Phase 2 和 Phase 3 可并行，Phase 4 必须最后执行。

---

## 测试策略

### 单元测试

```python
# tests/services/test_point_device_matcher.py
import pytest
from app.services.point_device_matcher import MatcherRegistry, derive_point_prefix

@pytest.fixture(autouse=True)
def clear_registry():
    """每个测试前清空注册表"""
    MatcherRegistry.clear()
    yield
    MatcherRegistry.clear()

def test_matcher_registry_thread_safe():
    """测试规则注册机制的线程安全性"""
    import threading

    def register_rules(source):
        rules = {f"TEST-{source}-AI-01": {"device_code": f"TEST-{source}", "_source": source}}
        MatcherRegistry.register(rules, source=source)

    threads = [threading.Thread(target=register_rules, args=(f"S{i}",)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert MatcherRegistry.has_rules()

def test_matcher_registry_unregister():
    """测试规则卸载功能"""
    rules1 = {"TEST-01-AI-01": {"device_code": "TEST-01", "_source": "demo"}}
    rules2 = {"TEST-02-AI-01": {"device_code": "TEST-02", "_source": "custom"}}

    MatcherRegistry.register(rules1, source="demo")
    MatcherRegistry.register(rules2, source="custom")

    # 卸载 demo 规则
    MatcherRegistry.unregister(source="demo")

    # 验证 demo 规则已移除，custom 规则保留
    assert MatcherRegistry.get_rule("TEST-01-AI-01") is None
    assert MatcherRegistry.get_rule("TEST-02-AI-01") is not None

def test_derive_point_prefix_with_registry():
    """测试带注册规则的点位匹配"""
    MatcherRegistry.register({
        "CUSTOM-99-AI-01": {"device_code": "CUSTOM-99", "_source": "test"}
    }, source="test")

    result = derive_point_prefix("CUSTOM-99-AI-01")
    assert result == "CUSTOM-99"

def test_derive_point_prefix_generic():
    """测试通用模式匹配"""
    result = derive_point_prefix("UPS-05-AI-02")
    assert result == "UPS-05"

def test_derive_point_prefix_invalid():
    """测试无效点位编码"""
    assert derive_point_prefix("INVALID") is None
    assert derive_point_prefix("") is None

async def test_get_floors_from_db_empty():
    """测试空数据库场景"""
    from app.core.database import async_session
    async with async_session() as session:
        floors = await get_floors_from_db(session, use_cache=False)
        assert isinstance(floors, list)
        assert len(floors) == 0

async def test_get_floors_from_db_sorted():
    """测试楼层排序正确性"""
    from app.core.database import async_session
    from app.models import Floor

    async with async_session() as session:
        # 创建测试数据
        floor1 = Floor(floor_code="3F", floor_name="3F", sort_order=3, site_id=1)
        floor2 = Floor(floor_code="1F", floor_name="1F", sort_order=1, site_id=1)
        floor3 = Floor(floor_code="2F", floor_name="2F", sort_order=2, site_id=1)
        session.add_all([floor1, floor2, floor3])
        await session.commit()

        floors = await get_floors_from_db(session, use_cache=False)
        assert floors == ["1F", "2F", "3F"]

async def test_match_circuit_from_db_not_found():
    """测试回路未找到场景"""
    from app.core.database import async_session
    async with async_session() as session:
        circuit = await match_circuit_from_db(session, "hvac", "NONEXISTENT")
        assert circuit is None
```

### 集成测试

```python
# tests/integration/test_demo_decoupling.py
import pytest
import os

@pytest.fixture
def demo_disabled_env(monkeypatch):
    """使用 pytest monkeypatch 隔离环境变量"""
    monkeypatch.setenv("DEMO_ENABLED", "false")
    yield
    # 自动清理

@pytest.fixture
def demo_enabled_env(monkeypatch):
    """使用 pytest monkeypatch 隔离环境变量"""
    monkeypatch.setenv("DEMO_ENABLED", "true")
    yield

async def test_demo_disabled_no_import_error(demo_disabled_env):
    """测试 demo 禁用时无导入错误"""
    # 导入主系统服务
    from app.services.point_device_matcher import derive_point_prefix
    from app.services.device_sync import get_floors_from_db

    # 验证函数可调用
    result = derive_point_prefix("TEST-01-AI-01")
    assert result is not None

async def test_demo_enabled_with_legacy_rules(demo_enabled_env):
    """测试 demo 启用时 legacy 规则生效"""
    # 清空注册表
    from app.services.point_device_matcher import MatcherRegistry
    MatcherRegistry.clear()

    # 模拟 demo 启动
    from app.demo.data.legacy_mapping import register_demo_rules
    register_demo_rules()

    # 验证 demo 规则生效
    from app.services.point_device_matcher import derive_point_prefix
    result = derive_point_prefix("UPS-01-AI-01")
    assert result == "UPS-01"

    # 清理
    from app.demo.data.legacy_mapping import unregister_demo_rules
    unregister_demo_rules()

async def test_demo_shutdown_unregisters_rules(demo_enabled_env):
    """测试 demo 关闭时卸载规则"""
    from app.services.point_device_matcher import MatcherRegistry
    from app.demo.data.legacy_mapping import register_demo_rules, unregister_demo_rules

    MatcherRegistry.clear()
    register_demo_rules()
    assert MatcherRegistry.has_rules()

    unregister_demo_rules()
    # 验证 demo 规则已卸载
    assert not MatcherRegistry.has_rules() or MatcherRegistry.get_rule("UPS-01-AI-01") is None
```

---

## 风险与缓解

### 风险 1: 现有功能回归

**风险:** 重构可能破坏现有的点位匹配和设备同步功能

**缓解:**
- 完整的单元测试覆盖
- 集成测试验证端到端流程
- 在测试环境充分验证后再部署

### 风险 2: 性能影响

**风险:** 动态数据库查询可能影响性能

**缓解:**
- 楼层列表查询结果可缓存（楼层变化频率低）
- 回路匹配可添加内存缓存
- 监控查询性能，必要时优化

### 风险 3: 迁移遗漏

**风险:** 可能遗漏某些硬编码的 demo 依赖

**缓解:**
- 全局搜索 demo 相关硬编码: `grep -r "UPS-01\|AC-01\|PDU-01\|F1\|F2\|F3\|F4\|C-CH-01\|C-AC-01" backend/app/services/`
- 全局搜索 building_points 导入: `grep -r "from app.data.building_points" backend/`
- Code review 重点检查
- Demo 禁用测试覆盖所有主要功能

### 风险 4: 回滚策略

**风险:** 如果重构后发现严重问题，需要快速回滚

**缓解:**
- 使用 Git feature branch 开发，保留回滚点
- 实施前创建数据库备份
- 使用 Feature Flag 控制新代码启用: `USE_DYNAMIC_FLOOR_QUERY=true/false`
- 灰度发布: 先在测试环境验证 1 周，再部署生产
- 保留旧代码注释，便于快速恢复

---

## 依赖关系

**前置依赖:**
- Story 28.2 (Demo 配置分离与最小化种子) - 已完成

**后续依赖:**
- Story 28.4 (Demo 数据安全卸载与标记) - 可并行

---

## 涉及文件清单

### 修改文件

1. `backend/app/services/point_device_matcher.py`
   - 添加 `MatcherRegistry` 类
   - 移除 `LEGACY_MAPPING_RULES`
   - 修改 `derive_point_prefix()` 支持注册规则

2. `backend/app/services/device_sync.py`
   - 添加 `get_floors_from_db()`
   - 添加 `match_circuit_from_db()`
   - 移除硬编码楼层和回路

3. `backend/app/demo/lifecycle.py`
   - 在 `demo_startup()` 中注册 demo 规则

### 新建文件

1. `backend/app/demo/data/legacy_mapping.py`
   - 定义 `DEMO_LEGACY_RULES`
   - 实现 `register_demo_rules()`

### 移动文件

1. `backend/app/data/building_points.py` → `backend/app/demo/data/building_points.py`

### 测试文件

1. `backend/tests/services/test_point_device_matcher.py` (新增测试)
2. `backend/tests/services/test_device_sync.py` (新增测试)
3. `backend/tests/integration/test_demo_decoupling.py` (新建)

---

## 完成定义 (DoD)

- [ ] 所有 AC 验收标准通过
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过
- [ ] Demo 禁用状态下所有主系统测试通过
- [ ] Demo 启用状态下功能正常
- [ ] 代码审查通过
- [ ] 文档更新完成
- [ ] 无遗留 TODO 或 FIXME

---

## 参考资料

- **Epic 28 文档:** `_bmad-output/planning-artifacts/epics.md`
- **架构文档:** `_bmad-output/planning-artifacts/architecture.md` Section 20
- **审查文档:** `docs/demo-system-audit.md`
- **Story 28.2:** `_bmad-output/implementation-artifacts/28-2-demo-config-separation-and-minimal-seed.md`

---

**文档版本:** v1.0
**最后更新:** 2026-03-05
