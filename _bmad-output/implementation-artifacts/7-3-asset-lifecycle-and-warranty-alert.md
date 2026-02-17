# Story 7.3: 资产生命周期与保修预警

Status: ready-for-dev

## Story

As a 资产管理员,
I want 系统自动记录资产生命周期并在保修到期前预警,
So that 我可以及时安排维保和更换。

## FR 追溯

- FR57: 系统自动记录资产生命周期事件（入库、上架、维修、下架、报废）
- FR58: 系统在保修到期前自动发送预警提醒

## Acceptance Criteria

1. Given 资产已录入系统
   When 资产状态发生变化（入库、上架、维修、下架、报废）
   Then 系统自动记录生命周期事件（时间、操作人、变更内容）

2. Given 资产有保修截止日期
   When 保修到期前 30/60/90 天
   Then 资产管理员可在保修预警面板中查看分级预警列表（被动查询模式，不含定时推送）

3. Given 资产管理员在资产详情页
   When 查看生命周期标签页
   Then 可查看完整的生命周期时间线（按时间倒序，含操作类型、操作人、位置变更、备注）

4. Given 资产管理员在资产管理页面
   When 查看保修预警面板
   Then 可按 30/60/90 天阈值查看即将过保资产列表，含剩余天数和保修状态

## 对抗性审查修复记录

### C-1: _calculate_warranty_status 返回值变更将破坏前端
前端 `index.vue` L150-153 硬编码判断 `row.warranty_status === 'expiring'`。
如果改为 `expiring_30/60/90`，所有 30-90 天内资产会 fallthrough 到 `danger`（已过保），显示红色标签。
**修复**：不修改 `_calculate_warranty_status`，保持原返回值（valid/expiring/expired/unknown）。
新增 `/warranty-alerts` 端点内部独立计算 `days_remaining` 做分组，不依赖该函数。

### C-2: Task 1 与已有代码重复
`create_asset`（L861-876）已有完整的入库生命周期记录逻辑（action="purchase"）。
**修复**：删除原 Task 1，改为验证性说明。

### H-1: 新路由可能被 {asset_id} 吞掉
`/warranty-alerts` 不以 `/assets/` 开头，与现有 `/warranty-expiring` 风格一致，不会被 `/assets/{asset_id}` 匹配。
**修复**：明确路径为 `/warranty-alerts`（无 `/assets/` 前缀）。

### H-2: complete_maintenance 维护完成后状态恢复逻辑有 bug
`complete_maintenance` 完成后将资产状态改为 `in_use`，但维护前可能是 `in_stock`。
**决定**：此为现有 bug，不在本 Story 范围内修复。在 Dev Notes 中标注。

### H-3: 无定时任务，AC #2 无法满足"自动发送预警"
**修复**：将 AC #2 降级为被动查询模式（用户打开页面时看到预警列表），不含定时推送。

### M-1: 测试覆盖不足
**修复**：增加到 7 个测试用例，补充边界值测试。

### L-1: 批量导入未记录生命周期事件
**决定**：记录为已知限制，不在本 Story 范围内修复。

### L-2: action 类型无枚举约束
**修复**：前端时间线组件对未知 action 显示通用灰色样式。

## 现有代码基础

| 层级 | 文件 | 已有功能 | 缺失 |
|------|------|----------|------|
| 模型 | `backend/app/models/asset.py` L108-123 | AssetLifecycle 模型完整 | 无缺失 |
| API | `backend/app/api/v1/asset.py` L861-876 | `create_asset` 已自动记录 action="purchase" 入库事件 | 无缺失 |
| API | `backend/app/api/v1/asset.py` L920-999 | `update_asset` 已自动记录位置变更和状态变更事件 | 无缺失 |
| API | `backend/app/api/v1/asset.py` L1110-1121 | `create_maintenance` 已自动记录 action="maintain" | 无缺失 |
| API | `backend/app/api/v1/asset.py` L1057-1078 | `GET /assets/{id}/lifecycle` 返回生命周期记录列表 | 无缺失 |
| API | `backend/app/api/v1/asset.py` L1409-1446 | `GET /warranty-expiring` 查询即将过保资产 | 缺分级预警汇总端点 |
| API | `backend/app/api/v1/asset.py` L1451-1470 | `_calculate_warranty_status()` 返回 valid/expiring/expired/unknown | 不修改，保持兼容 |
| Schema | `backend/app/schemas/asset.py` | LifecycleResponse, MaintenanceResponse 完整 | 缺 WarrantyAlertResponse |
| 前端 API | `frontend/src/api/modules/asset.ts` | getAssetLifecycle, getWarrantyExpiringAssets 已有 | 缺 getWarrantyAlerts |
| 前端页面 | `frontend/src/views/asset/index.vue` | 保修状态列（valid/expiring/expired 标签）、统计卡片 | 缺时间线组件、缺预警面板 |

### 已有的生命周期自动记录逻辑汇总

| 触发操作 | action 值 | 触发位置 |
|----------|-----------|----------|
| 创建资产 | `purchase` | `create_asset` L866-876 |
| 位置变更 | `move` | `update_asset` L942-972 |
| 状态→报废 | `scrap` | `update_asset` L979-981 |
| 状态→维护 | `maintain` | `update_asset` L982-984 |
| 状态→使用中 | `deploy` | `update_asset` L985-987 |
| 其他状态变更 | `status_change` | `update_asset` L976-977 |
| 创建维护记录 | `maintain` | `create_maintenance` L1111-1121 |
| U位拖拽移动 | `move` | `move_asset_in_cabinet` (Story 7-2) |

## 技术设计

### Task 1: 后端 — 新增 WarrantyAlertResponse schema (AC: #2, #4)

修改 `backend/app/schemas/asset.py`，在文件末尾新增：
```python
class WarrantyAlertItem(BaseModel):
    """保修预警项"""
    asset_id: int
    asset_code: str
    asset_name: str
    asset_type: Optional[str] = None
    warranty_end: str
    days_remaining: int
    status: Optional[str] = None

class WarrantyAlertResponse(BaseModel):
    """保修预警汇总"""
    within_30_days: List[WarrantyAlertItem] = []
    within_60_days: List[WarrantyAlertItem] = []
    within_90_days: List[WarrantyAlertItem] = []
    total_count: int = 0
```

### Task 2: 后端 — 新增 GET /warranty-alerts 端点 (AC: #2, #4)

修改 `backend/app/api/v1/asset.py`：

1. 在 schema import 中添加 `WarrantyAlertItem, WarrantyAlertResponse`
2. 新增端点（路径 `/warranty-alerts`，注册在 `/warranty-expiring` 之前）：

```python
@router.get("/warranty-alerts", response_model=WarrantyAlertResponse, summary="获取保修预警汇总")
async def get_warranty_alerts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """返回 30/60/90 天三个阈值的过保预警资产列表"""
    today = date.today()
    result = await db.execute(
        select(Asset).where(
            Asset.warranty_end.isnot(None),
            Asset.warranty_end >= today,
            Asset.warranty_end <= today + timedelta(days=90),
            Asset.status != AssetStatus.scrapped
        ).order_by(Asset.warranty_end.asc())
    )
    assets = result.scalars().all()

    alerts_30, alerts_60, alerts_90 = [], [], []
    for asset in assets:
        days_remaining = (asset.warranty_end - today).days
        item = WarrantyAlertItem(
            asset_id=asset.id,
            asset_code=asset.asset_code,
            asset_name=asset.asset_name,
            asset_type=asset.asset_type.value if asset.asset_type else None,
            warranty_end=asset.warranty_end.isoformat(),
            days_remaining=days_remaining,
            status=asset.status.value if asset.status else None,
        )
        if days_remaining <= 30:
            alerts_30.append(item)
        elif days_remaining <= 60:
            alerts_60.append(item)
        else:
            alerts_90.append(item)

    return WarrantyAlertResponse(
        within_30_days=alerts_30,
        within_60_days=alerts_60,
        within_90_days=alerts_90,
        total_count=len(assets),
    )
```

**注意**：不修改 `_calculate_warranty_status`，保持原返回值兼容前端。

### Task 3: 前端 — 新增保修预警 API 和类型 (AC: #4)

修改 `frontend/src/api/modules/asset.ts`，新增类型和 API 函数。

### Task 4: 前端 — 资产详情生命周期时间线组件 (AC: #3)

新增 `frontend/src/components/asset/LifecycleTimeline.vue`：
- Props: `assetId: number`
- 使用 Element Plus `<el-timeline>` 渲染
- action 颜色映射：purchase=绿, deploy=蓝, move=橙, maintain=黄, scrap=红, 其他=灰
- 空状态：`<el-empty description="暂无生命周期记录" />`

### Task 5: 前端 — 资产详情对话框增加生命周期标签页 (AC: #3)

修改 `frontend/src/views/asset/index.vue`：
- 操作列新增"详情"按钮
- 详情对话框 800px，`<el-tabs>` 含基本信息/生命周期/维护记录三个标签页

### Task 6: 前端 — 保修预警面板 (AC: #4)

修改 `frontend/src/views/asset/index.vue`：
- 统计卡片下方新增可折叠保修预警面板
- 三列布局（30天红/60天橙/90天黄）
- 无预警时显示绿色提示

### Task 7: 后端测试 (AC: #1, #2, #4)

新增 `backend/tests/api/test_asset_lifecycle_warranty.py`，7 个测试用例：
1. `test_create_asset_auto_lifecycle`: 创建资产 → 验证 purchase 记录
2. `test_update_asset_status_change_lifecycle`: 状态变更 → 验证 scrap 记录
3. `test_update_asset_location_change_lifecycle`: 位置变更 → 验证 move 记录
4. `test_warranty_alerts_grouping`: 3 个资产（15/45/75天后过保）→ 验证分组
5. `test_warranty_alerts_excludes_scrapped`: 报废资产不出现
6. `test_warranty_alerts_excludes_expired`: 已过保资产不出现
7. `test_warranty_alerts_empty`: 无预警时返回空列表

## 依赖

- Story 7-1（已完成）：资产 CRUD、AssetLifecycle 模型
- Story 7-2（已完成）：U 位可视化、move-asset 端点

## 测试要求

- 后端：7 测试用例
- 前端：`npm run build` 通过

## Dev Notes

### 关键约束
- **不修改 `_calculate_warranty_status`**：保持原返回值，前端现有保修状态列不受影响
- `/warranty-alerts` 端点内部独立计算 `days_remaining` 做分组
- Axios 拦截器 `return response.data`，API 调用直接返回 JSON body
- 前端自动导入：ref, computed, onMounted 等无需手动 import
- 2.5D 样式：资产页面已有 `@use '@/styles/mixins-25d'`，新增组件需兼容

### 已知限制（不在本 Story 范围）
- `import_assets` 批量导入不记录生命周期事件（L-1）
- `complete_maintenance` 完成后固定设为 `in_use`，不恢复维护前状态（H-2）
- 无定时告警推送机制，仅被动查询（H-3，可作为后续增强）

### Project Structure Notes
- 后端路由：`/warranty-alerts` 不以 `/assets/` 开头，与 `/warranty-expiring` 风格一致
- 前端组件：`frontend/src/components/asset/LifecycleTimeline.vue`（新建 asset 子目录）
- 测试文件：`backend/tests/api/test_asset_lifecycle_warranty.py`

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.3 L706-720]
- [Source: _bmad-output/planning-artifacts/prd.md#FR57-FR58 L802-803]
- [Source: backend/app/api/v1/asset.py#create_asset L861-876]
- [Source: backend/app/api/v1/asset.py#update_asset L885-999]
- [Source: backend/app/api/v1/asset.py#get_warranty_expiring_assets L1409-1446]
- [Source: backend/app/api/v1/asset.py#_calculate_warranty_status L1451-1470]
- [Source: frontend/src/views/asset/index.vue L147-153]

## Dev Agent Record

### Agent Model Used

（实施后填写）

### Debug Log References

### Completion Notes List

### File List
