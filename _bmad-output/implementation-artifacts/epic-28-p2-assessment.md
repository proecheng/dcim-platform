# Epic 28 P2 问题评估报告

**评估日期:** 2026-03-10
**评估人:** Claude (P2 Assessment)
**评估范围:** Epic 28 对抗性审查中发现的 2 个 P2 问题

---

## 评估结论

✅ **P2-1 可以接受现状** - service_new.py 未被使用，可以安全删除
⚠️ **P2-2 建议修复** - 硬编码回路规则限制系统通用性，但不影响当前功能

---

## P2-1: service.py 与 service_new.py 重复

### 问题描述

项目中同时存在两个几乎相同的文件：
- `backend/app/demo/service.py` (74K)
- `backend/app/demo/service_new.py` (73K)

### 实际使用情况

**检查结果:**

```bash
# 搜索所有导入语句
grep -r "from app.demo.service" backend/
grep -r "from .service" backend/app/demo/
```

**发现:**
- `backend/app/demo/router.py:11` - `from .service import demo_data_service`
- `backend/tests/demo/test_service.py:8` - `from app.demo.service import DemoDataService`
- `backend/tests/demo/test_integration_flow.py:8` - `from app.demo.service import DemoDataService`

**结论:**
- ✅ **service.py** 是当前使用的版本（被 router 和测试引用）
- ❌ **service_new.py** 未被任何代码引用，是遗留文件

### 文件差异

```bash
# 比较两个文件
diff backend/app/demo/service.py backend/app/demo/service_new.py
```

**差异:**
- 唯一差异是 `_clear_demo_data_safe()` 方法（我们刚刚添加到 service_new.py）
- 其他内容完全相同

### 评估结果

**影响:** 无 - service_new.py 未被使用

**建议操作:**
1. **删除 service_new.py** - 避免代码维护混淆
2. **保留 service.py** - 当前生产使用的版本

**优先级:** P2 - 代码质量问题，不影响功能

**是否需要修复:** ✅ **建议修复** - 删除未使用的文件，保持代码库整洁

---

## P2-2: device_sync.py 回路推断规则硬编码

### 问题描述

`backend/app/services/device_sync.py` 中的回路推断规则硬编码了特定的回路编码：

```python
# lines 773-790
if code.startswith("CH-"):
    return circuit_map.get("C-CH-01")  # 硬编码

if code.startswith("AC-A"):
    return circuit_map.get("C-AC-01")  # 硬编码
elif code.startswith("AC-B"):
    return circuit_map.get("C-AC-02")  # 硬编码

if code.startswith("CT-"):
    return circuit_map.get("C-CT-01")  # 硬编码

if code.startswith("AC-OUT-"):
    return circuit_map.get("C-AC-OUT-01")  # 硬编码
```

### 实际使用情况

**检查结果:**

```bash
# 搜索 device_sync 的使用
grep -r "device_sync" backend/app/services/
```

**发现:**
- `device_sync.py` - 主文件
- `diagnosis/device_sync_service.py` - 诊断系统的设备同步监听器

**使用场景:**
- 设备自动同步到配电拓扑
- 根据设备编码推断所属回路

### 影响分析

**当前环境:**
- Demo 数据使用的回路编码: `C-CH-01`, `C-AC-01`, `C-AC-02`, `C-CT-01`, `C-AC-OUT-01`
- 硬编码规则与 Demo 数据完全匹配

**非 Demo 环境:**
- 如果用户的回路编码不是 `C-CH-01`、`C-AC-01` 等，推断会失败
- 例如：用户使用 `C-CHILLER-01`、`C-HVAC-01` 等编码
- 结果：设备无法自动关联到回路，需要手动配置

**新设备类型:**
- 如果添加新设备类型（如 `HW-` 热水机组），需要修改代码添加规则
- 不支持配置驱动的规则扩展

### 评估结果

**影响:** 中等 - 限制系统通用性，但不影响当前 Demo 功能

**建议修复方案:**

**方案 1: 参数化回路规则（推荐）**
```python
# 从数据库 DistributionCircuit 表动态匹配
# 根据 circuit_code 的前缀模式推断
# 例如: C-CH-* 匹配所有冷机回路
```

**方案 2: 配置文件驱动**
```yaml
# config/circuit_inference_rules.yaml
circuit_inference_rules:
  - device_prefix: "CH-"
    circuit_pattern: "C-CH-*"
  - device_prefix: "AC-A"
    circuit_pattern: "C-AC-01"
```

**方案 3: 数据库表存储规则**
```sql
CREATE TABLE circuit_inference_rule (
    id SERIAL PRIMARY KEY,
    device_prefix VARCHAR(20),
    circuit_pattern VARCHAR(50),
    priority INT
);
```

**优先级:** P2 - 不影响核心功能，但限制系统通用性

**是否需要修复:** ⚠️ **建议修复，但不紧急**
- 当前 Demo 环境下功能正常
- 如果有真实客户部署，需要修复
- 可以作为后续优化任务

---

## 总体建议

### 立即执行（P2-1）

1. **删除 service_new.py**
   ```bash
   git rm backend/app/demo/service_new.py
   git commit -m "chore: 删除未使用的 service_new.py 文件"
   ```

### 后续优化（P2-2）

1. **创建 Epic 29 或 Story 28.5**
   - 标题: "配电回路推断规则参数化"
   - 优先级: P2
   - 描述: 将 device_sync.py 的硬编码规则改为配置驱动或数据库驱动

2. **实施时机**
   - 当有真实客户部署需求时
   - 或者在下一个 Sprint 的空闲时间

---

## 对比原始审查报告

| 问题编号 | 问题描述 | 评估结果 | 建议操作 |
|---------|---------|---------|---------|
| P2-1 | service.py 与 service_new.py 重复 | ✅ 可以接受 | 删除 service_new.py |
| P2-2 | device_sync.py 回路推断规则硬编码 | ⚠️ 建议修复 | 创建后续优化任务 |

---

## 最终结论

**P2-1:** 可以立即修复（删除未使用的文件）
**P2-2:** 可以接受现状，作为后续优化任务

**Epic 28 整体评估:**
- 核心目标已完成（数据源追踪、配置分离、is_demo 标记、安全卸载）
- P0 问题已修复
- P2 问题不影响当前功能，可以接受现状或后续优化

---

**评估完成时间:** 2026-03-10
**下一步:** 删除 service_new.py，更新 Sprint 状态
