# Story 3.3: 只读模式与写入权限管理

Status: done

## Story

As a 集成工程师,
I want 新设备默认以只读模式对接,
So that 首次对接时不会误下发控制命令导致设备异常。

## Acceptance Criteria (验收标准)

1. **AC-1: 默认只读** — DataSource.write_enabled 默认为 false（已在模型中实现）
2. **AC-2: 写入权限切换 API** — PUT `/api/v1/datasources/{id}/write-permission` 切换写入权限，需要 operator 权限
3. **AC-3: 操作日志记录** — 写入权限变更时记录到 OperationLog 表（module=datasource, action=update, old_value/new_value 记录变更）
4. **AC-4: 前端写入权限列** — 数据源列表中显示"写入权限"列，使用 el-switch 切换，切换前弹出确认对话框
5. **AC-5: 后端测试** — 测试写入权限切换 API 和操作日志记录

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端写入权限 API (AC: #2, #3)
  - [ ] 1.1 在 datasources.py 新增 PUT `/{datasource_id}/write-permission` 端点
  - [ ] 1.2 记录操作日志到 OperationLog 表

- [ ] Task 2: 前端写入权限列 (AC: #4)
  - [ ] 2.1 在数据源列表中新增"写入权限"列（el-switch）
  - [ ] 2.2 切换前弹出确认对话框（开启写入权限需二次确认）

- [ ] Task 3: 前端 API (AC: #2)
  - [ ] 3.1 在 datasource.ts 新增 toggleWritePermission 函数

- [ ] Task 4: 后端测试 (AC: #5)
  - [ ] 4.1 测试切换写入权限成功
  - [ ] 4.2 测试操作日志记录
  - [ ] 4.3 测试数据源不存在返回 404

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/api/v1/datasources.py           # 修改 — 新增写入权限端点
backend/tests/test_point_import.py          # 修改 — 新增写入权限测试（或新建 test_write_permission.py）
frontend/src/api/datasource.ts              # 修改 — 新增 API
frontend/src/views/datasource/index.vue     # 修改 — 新增写入权限列
```

### 2. 后端写入权限 API

在 `backend/app/api/v1/datasources.py` 中新增（放在 points/import 之后、DELETE 之前）：

```python
from ...models.log import OperationLog
import json

@router.put("/{datasource_id}/write-permission", summary="切换数据源写入权限")
async def toggle_write_permission(
    datasource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="数据源不存在")

    old_value = obj.write_enabled
    new_value = not old_value

    await db.execute(
        update(DataSource).where(DataSource.id == datasource_id).values(
            write_enabled=new_value,
            updated_at=datetime.now(),
        )
    )

    # 记录操作日志
    log = OperationLog(
        user_id=current_user.id,
        username=current_user.username,
        module="datasource",
        action="update",
        target_type="datasource",
        target_id=datasource_id,
        target_name=obj.name,
        old_value=json.dumps({"write_enabled": old_value}),
        new_value=json.dumps({"write_enabled": new_value}),
        remark=f"{'开启' if new_value else '关闭'}写入权限",
    )
    db.add(log)
    await db.commit()

    return {"write_enabled": new_value, "message": f"写入权限已{'开启' if new_value else '关闭'}"}
```

### 3. 前端 API

在 `frontend/src/api/datasource.ts` 新增：

```typescript
export function toggleWritePermission(id: number) {
  return request.put(`/v1/datasources/${id}/write-permission`)
}
```

### 4. 前端写入权限列

在数据源列表的 `is_enabled` 列之前新增：

```vue
<el-table-column prop="write_enabled" label="写入权限" width="100">
  <template #default="{ row }">
    <el-switch
      v-model="row.write_enabled"
      @change="handleToggleWrite(row)"
      :before-change="() => confirmWriteChange(row)"
    />
  </template>
</el-table-column>
```

处理函数：

```typescript
async function confirmWriteChange(row: DataSource): Promise<boolean> {
  const action = row.write_enabled ? '关闭' : '开启'
  try {
    await ElMessageBox.confirm(
      `确定${action}数据源 "${row.name}" 的写入权限？${action === '开启' ? '开启后可下发控制命令。' : ''}`,
      '写入权限变更',
      { type: 'warning' }
    )
    return true
  } catch {
    return false
  }
}

async function handleToggleWrite(row: DataSource) {
  try {
    await toggleWritePermission(row.id)
    ElMessage.success(row.write_enabled ? '写入权限已开启' : '写入权限已关闭')
  } catch (e) {
    row.write_enabled = !row.write_enabled
    console.error('切换写入权限失败', e)
  }
}
```

### 5. 关键约束

- DataSource.write_enabled 默认已经是 false（模型中 `default=False`）
- 操作日志使用现有 OperationLog 模型，module="datasource"
- 前端切换前必须弹出确认对话框
- 需要导入 ElMessageBox

### References

- [Source: models/log.py] OperationLog 模型
- [Source: models/gateway.py] DataSource.write_enabled 字段
- [Source: epics.md#Story 3.3] Acceptance Criteria

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

