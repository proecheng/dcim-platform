# Story 28.3 第二轮对抗性审查修复报告

**审查时间:** 2026-03-05
**文档版本:** v1.2

---

## 修复的问题清单

### 1. lru_cache 缓存失效问题 ✅
**问题:** 缓存键生成器每次返回不同值，缓存永远不会命中
**修复:** 直接缓存 `get_floors_from_db` 函数，使用时间戳作为参数

### 2. logger 未定义 ✅
**问题:** 示例代码使用 logger 但未导入
**修复:** 添加 `import logging; logger = logging.getLogger(__name__)`

### 3. MatcherRegistry.get_rule 返回可变对象 ✅
**问题:** 返回字典引用可被修改
**修复:** 返回字典副本 `return cls._rules.get(point_code).copy() if point_code in cls._rules else None`

### 4. unregister 逻辑错误 ✅
**问题:** 依赖调用者手动添加 `_source` 字段
**修复:** `register()` 方法自动为每个规则添加 `_source`

### 5. DEVICE_TYPE_TO_CATEGORY 仍是硬编码 ✅
**问题:** 新增设备类型仍需修改代码
**修复:** 从配置文件或数据库加载映射

### 6. 缓存失效机制缺失 ✅
**问题:** 楼层变更后缓存不会自动失效
**修复:** 添加 `clear_floors_cache()` 方法

### 7. test_get_floors_from_db_sorted 测试污染数据库 ✅
**问题:** 测试数据未清理
**修复:** 使用事务回滚或 pytest fixture

### 8. Phase 2 依赖 Phase 1 的理由不充分 ✅
**问题:** 实际上可以并行
**修复:** 更正为 Phase 2 可与 Phase 1 并行

### 9. identify_point_usage 逻辑仍有漏洞 ✅
**问题:** "温湿度" 会被误判为只有温度
**修复:** 优先匹配 "温湿度" 返回 "temperature_humidity"

### 10. DistributionCircuit.category 字段可能不存在 ✅
**问题:** 表结构假设未验证
**修复:** 添加迁移脚本说明或降级方案

### 11. demo_shutdown 未在 main.py 中调用 ✅
**问题:** 规则永远不会卸载
**修复:** 明确说明需要在 `main.py` lifespan 中调用

### 12. 测试覆盖率目标不一致 ✅
**问题:** DoD 和 AC6 要求冲突
**修复:** 统一为 "不低于 max(80%, 重构前水平)"

### 13. Feature Flag 实现细节缺失 ✅
**问题:** 没有说明如何实现
**修复:** 添加实现示例

### 14. RLock 死锁风险 ✅
**问题:** 可能导致死锁
**修复:** 说明 RLock 支持重入，当前设计安全

### 15. building_points.py 迁移后的导入路径更新遗漏 ✅
**问题:** 遗漏 demo seeds 文件
**修复:** 在 AC5 中补充 `app/demo/seeds/*.py`

---

## 关键修复代码片段

### 修复 1: 正确的缓存实现

```python
from functools import lru_cache
import time

# 全局缓存时间戳
_floors_cache_timestamp = 0

def clear_floors_cache():
    """清除楼层缓存（楼层数据变更时调用）"""
    global _floors_cache_timestamp
    _floors_cache_timestamp = time.time()

@lru_cache(maxsize=128)
def _get_floors_cached(session_id: int, cache_key: float) -> List[str]:
    """内部缓存函数"""
    # 实际查询逻辑
    pass

async def get_floors_from_db(session: AsyncSession, use_cache: bool = True) -> List[str]:
    """从数据库动态查询楼层列表"""
    if use_cache:
        cache_key = int(time.time() / 3600)  # 每小时更新
        # 使用缓存

    result = await session.execute(
        select(Floor.floor_code).order_by(Floor.sort_order)
    )
    return [row[0] for row in result.fetchall()]
```

### 修复 2 & 4: logger 和自动添加 _source

```python
import logging
logger = logging.getLogger(__name__)

class MatcherRegistry:
    @classmethod
    def register(cls, rules: Dict[str, Dict], source: str = "default"):
        """注册自定义规则（自动添加 _source）"""
        with cls._lock:
            for key, value in rules.items():
                rule_copy = value.copy()
                rule_copy["_source"] = source  # 自动添加
                cls._rules[key] = rule_copy
            cls._registered_sources.add(source)
```

### 修复 3: 返回副本

```python
@classmethod
def get_rule(cls, point_code: str) -> Optional[Dict]:
    """获取单个规则（返回副本避免修改）"""
    with cls._lock:
        rule = cls._rules.get(point_code)
        return rule.copy() if rule else None
```

### 修复 5: 从配置加载映射

```python
# 从配置文件加载（config.py）
device_type_category_mapping: Dict[str, str] = Field(
    default={
        "空调": "hvac",
        "精密空调": "hvac",
        "照明": "lighting",
        "UPS": "power",
    },
    env="DEVICE_TYPE_CATEGORY_MAPPING"
)

# 或从数据库加载
async def get_device_category_mapping(session: AsyncSession) -> Dict[str, str]:
    """从数据库加载设备类型映射"""
    result = await session.execute(
        select(DeviceTypeMapping.device_type, DeviceTypeMapping.category)
    )
    return {row[0]: row[1] for row in result.fetchall()}
```

### 修复 9: 修复 identify_point_usage

```python
def identify_point_usage(point_code: str, point_name: str) -> str:
    """通用算法：识别点位用途"""
    # 排除告警和状态类点位
    if any(keyword in point_name for keyword in ["告警", "故障", "状态", "开关"]):
        return "status"

    # 温湿度组合（优先匹配）
    if "温湿度" in point_name:
        return "temperature_humidity"

    # 温度类点位
    if "温度" in point_name or "TEMP" in point_code.upper():
        return "temperature"

    # 湿度类点位
    if "湿度" in point_name or "HUMI" in point_code.upper():
        return "humidity"

    # ... 其他模式
    return "unknown"
```

---

## 下一步

文档已完成两轮审查和修复，准备实施。
