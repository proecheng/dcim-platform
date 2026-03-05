# Story 28.4: Demo 数据安全卸载与标记

**Epic:** Epic 28 - Demo 系统解耦与数据隔离
**Story ID:** 28-4-demo-data-safe-unload-and-tagging
**优先级:** P1（核心路径）
**估算:** 中等复杂度
**依赖:** Story 28.2（Demo 配置分离与最小化种子）
**阻塞:** 无

---

## 用户故事

**As a** 管理员,
**I want** 卸载 demo 数据时只删除 demo 创建的记录，保留我自定义的配置,
**So that** 从 demo 模式过渡到生产模式时不会丢失自定义的告警规则、配电拓扑等。

---

## 业务价值

### 问题陈述
当前 demo 数据卸载机制存在以下问题：
1. **无法区分数据来源:** 无法识别哪些记录是 demo 创建的，哪些是用户手动添加的
2. **全量删除风险:** 卸载 demo 时可能误删用户自定义的配置（告警阈值、配电拓扑、电价配置等）
3. **过渡困难:** 从 demo 环境过渡到生产环境时，用户需要重新配置所有自定义规则
4. **缺少删除预览:** 卸载前无法预知将要删除的数据量，存在误操作风险

### 解决方案
为所有核心数据表增加 `is_demo` 标记列，实现：
- **精准标记:** Demo 种子创建的记录标记为 `is_demo=True`，用户手动创建的记录为 `False`
- **选择性删除:** 卸载时仅删除 `is_demo=True` 的记录，保留用户自定义配置
- **外键级联:** 按照外键依赖顺序删除（子表→父表），避免外键约束冲突
- **删除预览:** 卸载前统计并显示将要删除的记录数量

### 预期收益
- 用户可以在 demo 环境中添加自定义配置，卸载 demo 后这些配置得以保留
- 降低从 demo 到生产环境过渡的成本
- 提升数据安全性，避免误删重要配置

---

## Acceptance Criteria

### AC-1: 数据模型增加 is_demo 列
- **Given** 以下核心数据表
- **When** 执行 Alembic 迁移
- **Then** 为以下表增加 `is_demo: Boolean` 列（默认值 `False`）：
  - **设备相关:** Device, Point
  - **空间相关:** Site, Floor, Room, Row
  - **配电相关:** Transformer, MeterPoint, DistributionPanel, DistributionCircuit, PowerDevice
  - **制冷相关:** CoolingGroup, CoolingUnit, ColdAisle
  - **告警相关:** AlarmThreshold
  - **其他:** FloorMap, ElectricityPricing
- **And** 现有数据默认标记为 `is_demo=True`（假设当前全部是 demo 数据）
- **And** 迁移脚本兼容 SQLite 和 PostgreSQL


### AC-2: Demo 种子数据标记
- **Given** Demo 种子脚本（`datacenter_seed.py`, `power_seed.py`, `cooling_seed.py`）
- **When** 创建 demo 数据
- **Then** 所有创建的记录标记 `is_demo=True`
- **And** 最小种子（`minimal_seed.py`）创建的默认 Site/Floor/Room 标记 `is_demo=False`

### AC-3: 用户手动创建数据标记
- **Given** 用户通过 API 或前端页面手动创建记录
- **When** 创建设备、点位、告警阈值等
- **Then** 新创建的记录 `is_demo=False`
- **And** 确保所有 CRUD API 在创建时正确设置 `is_demo` 字段

### AC-4: 安全卸载逻辑重构
- **Given** `backend/app/demo/service.py` 的 `unload_demo_data()` 方法
- **When** 执行卸载操作
- **Then** 按照外键依赖顺序删除 `is_demo=True` 的记录：
  1. **历史数据:** PointHistory（外键→Point）
  2. **实时数据:** PointRealtime（外键→Point）
  3. **告警阈值:** AlarmThreshold（外键→Point）
  4. **点位:** Point（外键→Device）
  5. **设备:** Device（外键→Room/Floor）
  6. **配电设备:** PowerDevice（外键→DistributionCircuit）
  7. **配电回路:** DistributionCircuit（外键→DistributionPanel）
  8. **配电柜:** DistributionPanel（外键→Floor）
  9. **变压器:** Transformer（外键→Floor）
  10. **制冷设备:** ColdAisle, CoolingUnit, CoolingGroup（外键→Floor）
  11. **空间结构:** Row（外键→Room）, Room（外键→Floor）, Floor（外键→Site）
  12. **站点:** Site（根表）
  13. **其他:** FloorMap, ElectricityPricing
- **And** 使用事务确保原子性（全部成功或全部回滚）
- **And** 删除操作使用批量删除，避免逐条查询

### AC-5: 删除预览与确认
- **Given** 卸载操作执行前
- **When** 调用 `unload_demo_data(dry_run=True)`
- **Then** 返回将要删除的记录统计
- **And** 在日志中输出详细统计信息
- **And** 前端 `DemoDataLoader.vue` 卸载确认对话框显示统计数据

### AC-6: 前端卸载确认增强
- **Given** `frontend/src/components/DemoDataLoader.vue`
- **When** 用户点击"卸载 Demo 数据"按钮
- **Then** 先调用 `/api/v1/demo/unload-preview` 获取删除统计
- **And** 显示确认对话框，列出将要删除的记录数量
- **And** 用户确认后调用 `/api/v1/demo/unload` 执行实际删除

### AC-7: API 端点实现
- **Given** 后端 API
- **When** 实现以下端点
- **Then** 提供以下接口：
  - `GET /api/v1/demo/unload-preview` — 返回删除预览统计（dry_run=True）
  - `POST /api/v1/demo/unload` — 执行实际删除操作
  - `GET /api/v1/demo/stats` — 返回当前 demo 数据统计（is_demo=True 的记录数）
- **And** 所有端点需要管理员权限（`current_user.role == "admin"`）

### AC-8: 错误处理与日志
- **Given** 卸载操作执行过程中
- **When** 遇到外键约束冲突或其他错误
- **Then** 回滚事务，保持数据一致性
- **And** 记录详细错误日志（表名、记录ID、错误原因）
- **And** 返回友好的错误提示给前端

### AC-9: 测试覆盖
- **Given** 测试套件
- **When** 运行测试
- **Then** 包含以下测试用例：
  - 测试 `is_demo=True` 的记录被正确删除
  - 测试 `is_demo=False` 的记录被保留
  - 测试外键级联删除顺序正确
  - 测试事务回滚机制
  - 测试删除预览统计准确性
  - 测试混合场景（demo 数据 + 用户数据共存）

---

## 技术实现要点

### 1. Alembic 迁移脚本

**关键点:**
- 为 17 个表批量添加 `is_demo` 列
- 现有数据默认值设为 `True`（假设当前全部是 demo 数据）
- 兼容 SQLite 和 PostgreSQL 语法
- 使用 `batch_alter_table` 确保 SQLite 兼容性

### 2. 删除顺序依赖图

按照外键依赖从子表到父表删除，确保不违反外键约束。

### 3. 批量删除优化

使用 SQLAlchemy 批量删除避免 N+1 查询问题。

### 4. 事务管理

使用异步事务确保原子性，错误时自动回滚。

---

## 涉及文件清单

### 后端文件

| 文件路径 | 变更类型 | 说明 |
|---------|---------|------|
| `backend/alembic/versions/xxxx_add_is_demo_column.py` | 新建 | Alembic 迁移脚本 |
| `backend/app/models/device.py` | 修改 | Device 增加 is_demo 列 |
| `backend/app/models/__init__.py` | 修改 | Point 增加 is_demo 列 |
| `backend/app/models/spatial.py` | 修改 | Site/Floor/Room/Row 增加 is_demo 列 |
| `backend/app/models/energy.py` | 修改 | 配电相关模型增加 is_demo 列 |
| `backend/app/models/cooling.py` | 修改 | 制冷相关模型增加 is_demo 列 |
| `backend/app/models/alarm.py` | 修改 | AlarmThreshold 增加 is_demo 列 |
| `backend/app/demo/service.py` | 重构 | 重构 unload_demo_data() 方法 |
| `backend/app/demo/seeds/*.py` | 修改 | 创建时标记 is_demo=True |
| `backend/app/seeds/minimal_seed.py` | 修改 | 创建时标记 is_demo=False |
| `backend/app/api/v1/demo.py` | 新建/修改 | 新增 API 端点 |
| `backend/tests/demo/test_unload_safe.py` | 新建 | 安全卸载测试 |

### 前端文件

| 文件路径 | 变更类型 | 说明 |
|---------|---------|------|
| `frontend/src/components/DemoDataLoader.vue` | 修改 | 卸载确认对话框增强 |
| `frontend/src/api/modules/demo.ts` | 修改 | 新增 API 方法 |

---

## 实施检查清单

### 数据模型变更
- [ ] 为 17 个表增加 `is_demo` 列
- [ ] 编写 Alembic 迁移脚本
- [ ] 测试迁移脚本（SQLite + PostgreSQL）
- [ ] 验证现有数据默认值正确

### 种子数据标记
- [ ] 修改 demo 种子脚本标记 is_demo=True
- [ ] 修改最小种子脚本标记 is_demo=False

### 卸载逻辑重构
- [ ] 实现统计方法
- [ ] 实现删除方法
- [ ] 确定外键依赖删除顺序
- [ ] 添加事务管理和错误处理
- [ ] 实现 dry_run 模式

### API 端点
- [ ] 实现 unload-preview 端点
- [ ] 实现 unload 端点
- [ ] 实现 stats 端点
- [ ] 添加管理员权限检查

### 前端增强
- [ ] 修改卸载确认对话框
- [ ] 调用 unload-preview 获取统计
- [ ] 显示删除预览信息
- [ ] 添加二次确认机制

### 测试
- [ ] 编写单元测试
- [ ] 编写集成测试
- [ ] 手动测试混合场景
- [ ] 性能测试

### 文档
- [ ] 更新 API 文档
- [ ] 更新部署文档
- [ ] 更新用户手册

---

## 验收标准总结

**Story 完成的定义:**
1. ✅ 所有 AC 通过验证
2. ✅ 单元测试覆盖率 ≥ 80%
3. ✅ 集成测试全部通过
4. ✅ 代码审查通过（无 P0/P1 问题）
5. ✅ 在 demo 和生产环境中手动测试通过
6. ✅ 文档更新完成

**关键验收点:**
- Demo 数据可以安全卸载，不影响用户自定义配置
- 卸载前有明确的删除预览和确认机制
- 外键级联删除顺序正确，无数据一致性问题
- 性能满足要求（删除 10 万条记录 < 30 秒）

---

**Story 状态:** ready-for-dev
**创建时间:** 2026-03-06
**最后更新:** 2026-03-06
