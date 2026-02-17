# Story 7-2: 机柜 U 位可视化

## Story

As a 资产管理员,
I want 查看机柜 U 位占用可视化图,
So that 我可以直观了解每个机柜的空间使用情况。

## Status: Ready for Dev

## FR 追溯
- FR56: 资产管理员可以查看机柜 U 位占用可视化图

## Acceptance Criteria

1. Given 资产管理员在机柜管理页面
   When 点击某机柜的"U位图"按钮
   Then 以可视化方式显示机柜的每个 U 位占用情况（已用/空闲）
   And 已用 U 位显示设备名称和型号
   And 多 U 设备合并显示为一个连续色块

2. Given 资产管理员在 U 位图中
   When 查看已占用的 U 位
   Then 可以看到设备名称、型号、资产编码、状态等信息（悬浮提示）
   And 不同状态的设备用不同颜色区分（使用中=蓝色、维护中=橙色、借出=黄色等）

3. Given 资产管理员在 U 位图中
   When 拖拽某设备到同一机柜内新的 U 位位置
   Then 系统校验目标位置是否有足够连续空闲 U 位且不超出机柜总 U 数
   And 校验通过后更新设备的 U 位位置
   And 自动创建"移动"生命周期记录

4. Given 资产管理员在 U 位图中
   When 拖拽设备到已被占用的位置或超出机柜范围
   Then 系统提示 U 位冲突或超出范围，拒绝操作

## 对抗性审查修复记录

### C1: CabinetUsage 接口字段与后端返回严重不匹配
前端 CabinetUsage 定义了 cabinet_code/max_power/current_power/power_usage_rate/max_weight/current_weight/weight_usage_rate，
但后端 get_cabinet_usage 只返回 cabinet_id/cabinet_name/total_u/used_u/available_u/usage_rate/u_map。
修复：Task 3 重写 CabinetUsage 接口，删除后端不返回的字段，仅保留实际返回的字段 + 新增 assets。

### C2: start_u/end_u vs u_position/u_height 字段命名不统一
前端 isUnitOccupied/getAssetAtUnit 引用 asset.start_u/end_u，但 Asset 接口和后端都用 u_position/u_height。
修复：统一使用 u_position + u_height。新增 CabinetAssetItem 接口使用 u_position/u_height，
Task 4 中所有 U 位计算改为 u_position 到 u_position + u_height - 1。设备清单表格也同步修改。

### C3: usage_rate 后端返回百分比数值，前端又乘以 100
后端 usage_rate = round((used_u / total_u * 100), 2) 已是百分比（如 23.81），
前端 (currentUsage.usage_rate * 100).toFixed(1) 又乘 100 导致显示 2381.0%。
修复：Task 4 去掉 * 100，直接 usage_rate.toFixed(1)。

### H1: row_number/column_number 前端用 el-input-number 但后端是 String
已知问题，不在本 Story 范围内修复。

### H2: move-asset 缺少 total_u 上限校验
修复：Task 2 增加校验 new_u_position >= 1 且 new_u_position + u_height - 1 <= cabinet.total_u。

### H3: move-asset 缺少认证依赖
修复：Task 2 明确使用 require_operator 依赖，current_user 填写生命周期 operator 字段。

### H4: 后端不返回 assets 数组导致现有 U 位图半残废
现有前端代码依赖 currentUsage.assets 但后端从未返回。Task 1 是修复此现有 bug。

### H5: u_map 与 assets 职责分工
修复：合并色块渲染基于 assets 数组（按 u_position + u_height 计算跨度），u_map 保留向后兼容但前端不再使用。

## 现有代码基础

| 层级 | 文件 | 行数 | 已有功能 |
|------|------|------|----------|
| 模型 | `backend/app/models/asset.py` | 187 | Cabinet(total_u, ...), Asset(cabinet_id, u_position, u_height, ...) |
| API | `backend/app/api/v1/asset.py` | ~710 | `GET /cabinets/{id}/usage` 返回 u_map + 汇总统计（缺 assets 数组） |
| Schema | `backend/app/schemas/asset.py` | 258 | CabinetResponse, AssetResponse 完整 |
| 前端页面 | `frontend/src/views/asset/cabinet.vue` | 599 | 已有基础 U 位图对话框（半残废：依赖 assets 但后端不返回） |
| 前端 API | `frontend/src/api/modules/asset.ts` | 387 | CabinetUsage 接口（字段与后端严重不匹配，需重写） |

### 后端 get_cabinet_usage 实际返回结构
```json
{
  "cabinet_id": 1, "cabinet_name": "A01",
  "total_u": 42, "used_u": 10, "available_u": 32,
  "usage_rate": 23.81,
  "u_map": { "1": {"asset_id":1, "asset_code":"SV001", "asset_name":"服务器1", "asset_type":"server"}, ... }
}
```

## 技术设计

### Task 1: 后端增强 get_cabinet_usage 返回 assets 数组（修复现有 bug + 新增数据）

修改 `backend/app/api/v1/asset.py` 的 `get_cabinet_usage` 端点（约 L194-248）：

在现有返回基础上，新增 `assets` 列表：
```python
assets_list = []
for asset in assets:
    if asset.u_position is not None and asset.u_height is not None:
        assets_list.append({
            "asset_id": asset.id,
            "asset_code": asset.asset_code,
            "asset_name": asset.asset_name,
            "asset_type": asset.asset_type.value if asset.asset_type else None,
            "model": asset.model or "",
            "brand": asset.brand or "",
            "status": asset.status.value if asset.status else None,
            "u_position": asset.u_position,
            "u_height": asset.u_height,
        })
```

返回 dict 增加 `"assets": assets_list`。保留 `u_map` 向后兼容。

### Task 2: 后端新增拖拽移动端点 PUT /cabinets/{cabinet_id}/move-asset

新增端点（路由放在 cabinets/{cabinet_id}/usage 之后）：
```
PUT /asset/cabinets/{cabinet_id}/move-asset
Body: { "asset_id": int, "new_u_position": int }
权限: require_operator
```

逻辑：
1. 校验 cabinet 存在，获取 cabinet.total_u
2. 校验 asset 存在且 asset.cabinet_id == cabinet_id
3. 校验 new_u_position >= 1 且 new_u_position + asset.u_height - 1 <= cabinet.total_u
4. 调用 `_check_u_position_conflict(db, cabinet_id, new_u_position, asset.u_height, exclude_asset_id=asset.id)`
5. 冲突则返回 400 + 冲突信息
6. 记录旧位置 old_u_position = asset.u_position
7. 更新 asset.u_position = new_u_position
8. 创建 AssetLifecycle(asset_id=asset.id, action="move", operator=current_user.username, from_location=f"U{old_u_position}", to_location=f"U{new_u_position}")
9. commit 后返回更新后的 usage 数据（复用 get_cabinet_usage 逻辑）

### Task 3: 前端更新类型定义和 API（C1/C2 修复）

修改 `frontend/src/api/modules/asset.ts`：

1. 新增 `CabinetAssetItem` 接口（U位图专用）：
```typescript
export interface CabinetAssetItem {
  asset_id: number
  asset_code: string
  asset_name: string
  asset_type: string
  model: string
  brand: string
  status: string
  u_position: number
  u_height: number
}
```

2. 重写 `CabinetUsage` 接口（删除后端不返回的字段）：
```typescript
export interface CabinetUsage {
  cabinet_id: number
  cabinet_name: string
  total_u: number
  used_u: number
  available_u: number
  usage_rate: number
  u_map: Record<string, { asset_id: number; asset_code: string; asset_name: string; asset_type: string }>
  assets: CabinetAssetItem[]
}
```

3. 新增 `moveAssetInCabinet` API：
```typescript
export function moveAssetInCabinet(cabinetId: number, data: { asset_id: number; new_u_position: number }) {
  return request.put<ResponseModel>(`/v1/asset/cabinets/${cabinetId}/move-asset`, data)
}
```

### Task 4: 前端重构 U 位图可视化（C2/C3/H5 修复 + 新功能）

重构 `frontend/src/views/asset/cabinet.vue` 的 U 位图对话框：

1. **修复 C3**: usage_rate 显示去掉 `* 100`，直接 `usage_rate.toFixed(1)`
2. **合并色块渲染**（基于 assets 数组，不再用 u_map）：
   - 构建 U 位占用数组：遍历 assets，标记每个 U 位的占用状态
   - 渲染时：遇到设备起始 U 位，渲染一个高度为 u_height 的合并色块；空闲 U 位单独渲染
   - 从顶部（42U）到底部（1U）渲染，符合实际机柜视角
3. **状态颜色区分**：
   - in_use: #409eff（蓝色）
   - maintenance: #e6a23c（橙色）
   - borrowed: #f2c037（黄色）
   - in_stock: #909399（灰色）
   - scrapped: #f56c6c（红色）
4. **设备信息展示**：色块内显示设备名称 + 型号，el-tooltip 悬浮显示完整信息
5. **修复设备清单表格**：`row.start_u`/`row.end_u` → `row.u_position`/`row.u_position + row.u_height - 1`
6. **重写 isUnitOccupied / getAssetAtUnit**：基于 u_position + u_height 计算

### Task 5: 前端实现拖拽功能

在 U 位图组件中实现 HTML5 原生拖拽（同机柜内移动）：

1. 设备色块设置 `draggable="true"`，dragstart 时记录 asset_id 和 u_height
2. 空闲 U 位作为 drop target（dragover 时 preventDefault）
3. 拖拽时高亮可放置区域（目标 U 位起向上连续空闲 ≥ u_height 个 U 位）
4. drop 时调用 `moveAssetInCabinet(cabinetId, { asset_id, new_u_position: targetU })`
5. 成功后刷新 U 位图数据（重新调用 getCabinetUsage）
6. 失败时 ElMessage.error 显示错误信息

### Task 6: 后端测试

新增 `backend/tests/test_cabinet_usage.py`：
- test_get_cabinet_usage_returns_assets: 验证返回包含 assets 数组，每个元素有 u_position/u_height/model/brand/status
- test_move_asset_success: 移动成功，验证 u_position 更新 + 生命周期记录创建
- test_move_asset_conflict: 目标位置冲突，返回 400
- test_move_asset_out_of_range: new_u_position + u_height - 1 > total_u，返回 400
- test_move_asset_wrong_cabinet: asset 不属于该机柜，返回 400/404

## 依赖

- Story 7-1（已完成）：U 位冲突校验函数 `_check_u_position_conflict`
- 现有 `update_asset` 中的位置变更检测和生命周期记录逻辑

## 测试要求

- 后端：5 测试用例覆盖 usage 查询和拖拽移动
- 前端：构建通过，无 TypeScript 错误
