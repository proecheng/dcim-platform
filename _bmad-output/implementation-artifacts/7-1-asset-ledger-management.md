# Story 7-1: 资产台账管理

## Story

As a 资产管理员,
I want 录入和管理设备资产信息,
So that 我可以掌握所有设备的基本信息和归属。

## Status: Ready for Dev

## FR 追溯
- FR54: 资产管理员可以录入和管理设备资产信息（SN 码、型号、厂商、保修期等）
- FR55: 资产管理员可以批量导入设备资产

## Acceptance Criteria

1. Given 资产管理员在资产管理页面
   When 点击"新增资产"
   Then 可填写 SN 码、型号、厂商、保修期、所属机柜、U 位位置等信息
   And 保存后资产出现在列表中

2. Given 资产管理员在资产管理页面
   When 点击"导入"按钮并上传 Excel 文件
   Then 系统解析 Excel 并显示预校验结果（成功/失败条数、错误详情）
   And 确认后批量创建资产记录
   And 每条导入的资产自动创建"入库"生命周期记录

3. Given 资产管理员在资产管理页面
   When 使用筛选条件（类型/厂商/状态/机柜）
   Then 列表按条件过滤显示
   And 支持关键字搜索（资产编码、名称、SN码）

4. Given 资产管理员编辑资产信息
   When 修改所属机柜或 U 位位置
   Then 系统自动校验 U 位冲突（目标位置是否已被占用）
   And 自动创建"移动"生命周期记录（已实现，仅需补充 U 位冲突校验）

5. Given 资产管理员在资产管理页面
   When 点击"导出"按钮
   Then 下载当前筛选条件下的资产列表 Excel 文件

## 对抗性审查修复记录

### C1: 前端字段名与后端 schema 全面不匹配
前端 asset.ts 使用 start_u/end_u/warranty_date/responsible_person/description，
后端 schema 使用 u_position/u_height/warranty_start+warranty_end/owner/remark+specifications。
修复：修改前端 asset.ts 类型定义和 index.vue 表单字段，对齐后端 schema 字段名。

### C2: create_asset 已实现生命周期记录创建
asset.py 第386-401行已有 action="purchase" 的 AssetLifecycle 记录创建。
修复：不重复实现。

### C3: update_asset 已实现位置变更检测和"移动"记录
asset.py 第436-488行已检测 cabinet_id/u_position 变更并创建 action="move" 记录。
修复：仅实现 U 位冲突校验（确实缺失）。

### H1: update_asset 缺少 U 位冲突校验
当前更新 u_position/u_height 时不检查目标 U 位是否已被其他资产占用。
修复：在 update_asset 和 create_asset 中添加 U 位重叠检测逻辑。

### H2: 前端 LifecycleRecord 字段名与后端不匹配
前端用 event_type/event_description/event_time，后端用 action/remark/action_date。
修复：修改前端 LifecycleRecord 接口对齐后端 LifecycleResponse。

### H3-H4: 前端 MaintenanceCreate/InventoryCreate 字段名与后端不匹配
修复：修改前端类型定义对齐后端 schema。

### H5: 前端 AssetStatistics 缺少 by_department，多了 maintenance_count
后端返回 by_department，不返回 maintenance_count。
修复：修改前端 AssetStatistics 接口，index.vue 中"维护中"改用 by_status.maintenance。

### H6: 前端分页参数 page/page_size 与后端 skip/limit 不匹配
修复：前端 getAssets 调用时转换参数 skip=(page-1)*page_size, limit=page_size。

### H7: 路由冲突 — /assets/import 和 /assets/export vs /assets/{asset_id}
修复：确保 /assets/import 和 /assets/export 路由在 /assets/{asset_id} 之前定义。

### H8: Excel 导入中机柜编码查找失败处理
修复：预校验时标记为错误行，提示"机柜编码 XXX 不存在"。

## 现有代码基础

| 层级 | 文件 | 行数 | 已有功能 |
|------|------|------|----------|
| 模型 | `backend/app/models/asset.py` | 187 | Asset, Cabinet, AssetLifecycle, MaintenanceRecord, AssetInventory 完整模型 |
| API | `backend/app/api/v1/asset.py` | 993 | 21 端点：机柜 CRUD+U位、资产 CRUD+生命周期+状态变更、维护 CRUD、盘点 CRUD、统计、过保预警 |
| Schema | `backend/app/schemas/asset.py` | 258 | 完整 schema：字段名以后端模型为准 |
| 前端页面 | `frontend/src/views/asset/index.vue` | 853 | 资产列表页（字段名与后端不匹配，需修复） |
| 前端页面 | `frontend/src/views/asset/cabinet.vue` | 591 | 机柜管理页 |
| 前端 API | `frontend/src/api/modules/asset.ts` | 349 | API 模块（类型定义与后端不匹配，需修复） |

### 关键字段映射（后端 schema 为准）

| 后端字段 | 前端当前字段 | 需修改为 |
|----------|-------------|---------|
| u_position | start_u | u_position |
| u_height | end_u | u_height |
| warranty_start | — | warranty_start |
| warranty_end | warranty_date | warranty_end |
| owner | responsible_person | owner |
| remark | description | remark |
| specifications | — | specifications |

## 技术设计

### Task 1: 修复前端类型定义对齐后端 schema（C1, H2-H5 修复）

修改 `frontend/src/api/modules/asset.ts`：
- Asset 接口：start_u/end_u → u_position/u_height，warranty_date → warranty_start + warranty_end，responsible_person → owner，description → remark
- AssetCreate/AssetUpdate：同步修改
- LifecycleRecord：event_type → action，event_description → remark，event_time → action_date，新增 from_location/to_location
- MaintenanceCreate：maintenance_description → description，maintenance_date → start_time，maintenance_person → technician，maintenance_cost → cost
- MaintenanceRecord：同步修改
- InventoryCreate：inventory_name/inventory_type → inventory_code/inventory_date
- AssetStatistics：删除 maintenance_count，新增 by_department

### Task 2: 修复前端页面对齐新类型定义

修改 `frontend/src/views/asset/index.vue`：
- 表单字段绑定：对齐 Task 1 的新字段名
- 分页参数：page/page_size 转换为 skip/limit（H6）
- 统计卡片："维护中"改用 statistics.by_status?.maintenance || 0（H5）
- 生命周期展示：使用 action/action_date/from_location/to_location（H2）

### Task 3: 后端 U 位冲突校验（H1 修复）

修改 `backend/app/api/v1/asset.py`：
- 抽取公共函数 `_check_u_position_conflict(db, cabinet_id, u_position, u_height, exclude_asset_id=None)`
- 在 create_asset 和 update_asset 中调用
- 检测 U 位范围重叠：[new_u_position, new_u_position + new_u_height) 与已有资产的 [u_position, u_position + u_height) 是否交叉
- 冲突时返回 400 + 冲突资产信息

### Task 4: 批量导入端点 `POST /asset/assets/import`

**重要：路由必须在 /assets/{asset_id} 之前定义（H7）**

新增端点，接收 Excel 文件（UploadFile）+ mode 参数（preview/confirm）：

1. 解析 Excel（openpyxl），映射列名到 AssetCreate 字段
2. 预校验（mode=preview）：
   - 必填字段检查（asset_code, asset_name, asset_type）
   - asset_code 唯一性（数据库 + Excel 内部去重）
   - cabinet_code 存在性检查（查找失败标记错误，H8）
   - U 位冲突检查
   - asset_type 枚举值校验
3. 返回校验结果：{total, success_count, error_count, errors: [{row, field, message}]}
4. 执行导入（mode=confirm）：
   - 批量创建 Asset 记录
   - 每条记录创建 AssetLifecycle（action="purchase"）
   - 事务性：全部成功或全部回滚

Excel 列映射（与后端 AssetCreate schema 字段对齐）：
| Excel 列名 | 后端字段 | 必填 |
|------------|---------|------|
| 资产编码 | asset_code | ✅ |
| 资产名称 | asset_name | ✅ |
| 资产类型 | asset_type | ✅ (枚举值) |
| 品牌 | brand | |
| 型号 | model | |
| 序列号 | serial_number | |
| 机柜编码 | → 查找 cabinet_id | |
| U位起始 | u_position | |
| 占用U数 | u_height | |
| 采购日期 | purchase_date | |
| 保修开始 | warranty_start | |
| 保修截止 | warranty_end | |
| 供应商 | supplier | |
| 负责人 | owner | |
| 部门 | department | |
| 备注 | remark | |

### Task 5: 资产导出端点 `GET /asset/assets/export`

**重要：路由必须在 /assets/{asset_id} 之前定义（H7）**

新增端点，接收与列表相同的筛选参数（asset_type, status, cabinet_id, keyword）：
- 查询资产列表（含机柜名称 JOIN）
- 生成 Excel（openpyxl），列与导入模板一致
- 返回 StreamingResponse

### Task 6: 前端导入对话框

修改 `frontend/src/views/asset/index.vue`：
- "导入"按钮绑定打开导入对话框
- 对话框：文件上传（el-upload, accept=.xlsx）、下载模板按钮、预校验结果表格、确认导入按钮
- 流程：上传 → 预校验（mode=preview）→ 展示结果 → 确认（mode=confirm）→ 刷新列表

### Task 7: 前端导出按钮 + API 补充

修改 `frontend/src/api/modules/asset.ts`：
- 新增 importAssets(file: File, mode: string) — FormData 上传
- 新增 exportAssets(params) — 下载 blob
- 新增 downloadImportTemplate() — 下载空模板

修改 `frontend/src/views/asset/index.vue`：
- 新增"导出"按钮，调用 exportAssets

### Task 8: 后端测试 `backend/tests/test_asset_import.py`

- 测试 Excel 解析和列映射
- 测试预校验（重复编码、必填缺失、U位冲突、机柜编码不存在）
- 测试导入成功后生命周期记录创建
- 测试 U 位冲突校验（create + update）
- 测试导出 Excel 生成
- 测试路由顺序（/assets/import 不被 /assets/{asset_id} 拦截）

## 依赖
- openpyxl（已安装）
- 现有 Asset/Cabinet/AssetLifecycle 模型和 API

## 估算
- Task 1-2（前端字段对齐）：约 200 行修改
- Task 3（U位冲突校验）：约 50 行新增
- Task 4（批量导入）：约 200 行新增
- Task 5（导出）：约 80 行新增
- Task 6-7（前端导入导出）：约 250 行新增/修改
- Task 8（测试）：约 150 行
