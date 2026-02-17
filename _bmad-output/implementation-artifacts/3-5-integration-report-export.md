# Story 3.5: 对接报告导出

Status: done

## Story

As a 集成工程师,
I want 导出设备对接报告,
So that 我可以将对接结果交付给客户运维团队。

## Acceptance Criteria (验收标准)

1. **AC-1: 导出 API** — GET `/api/v1/datasources/export-report` 返回 Excel 文件流，包含所有数据源及其点位的对接报告
2. **AC-2: 设备清单 Sheet** — 第一个 Sheet "数据源清单"，包含：名称、协议类型、连接参数摘要、连接状态、最后通信时间、创建时间、启用状态
3. **AC-3: 点位映射 Sheet** — 第二个 Sheet "点位映射表"，包含：数据源名称、地址、数据类型、缩放系数、偏移量、是否干接点
4. **AC-4: 筛选参数** — 支持按 gateway_id、protocol_type、status 筛选导出范围
5. **AC-5: 前端导出按钮** — 数据源管理页面顶部新增"导出对接报告"按钮，点击后下载 Excel 文件
6. **AC-6: 后端测试** — 测试导出 API 返回有效 Excel 文件

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端导出服务 (AC: #1, #2, #3)
  - [ ] 1.1 创建 `backend/app/services/report_export.py`
  - [ ] 1.2 实现 `generate_integration_report(datasources, points)` — 生成 Excel bytes
  - [ ] 1.3 Sheet 1 "数据源清单"：名称、协议类型、连接参数、状态、最后通信时间、创建时间、启用
  - [ ] 1.4 Sheet 2 "点位映射表"：数据源名称、地址、数据类型、scale、offset、干接点

- [ ] Task 2: 后端 API 端点 (AC: #1, #4)
  - [ ] 2.1 在 `backend/app/api/v1/datasources.py` 新增 GET `/export-report` 端点
  - [ ] 2.2 查询 DataSource + DataSourcePoint，支持筛选
  - [ ] 2.3 返回 StreamingResponse（application/vnd.openxmlformats-officedocument.spreadsheetml.sheet）

- [ ] Task 3: 前端导出按钮 (AC: #5)
  - [ ] 3.1 在 `frontend/src/api/datasource.ts` 新增 exportReport 函数
  - [ ] 3.2 在数据源管理页面 header 新增"导出报告"按钮

- [ ] Task 4: 后端测试 (AC: #6)
  - [ ] 4.1 测试导出 — 生成有效 Excel（可用 openpyxl 解析验证）
  - [ ] 4.2 测试导出 — 包含正确的 Sheet 名称和列头
  - [ ] 4.3 测试导出 — 数据源和点位数据正确填充
  - [ ] 4.4 测试导出 — 无数据时返回空报告（仅表头）

- [ ] Task 5: 前端构建验证
  - [ ] 5.1 `npm run build` 构建成功

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/services/report_export.py       # 新建 — 报告生成服务
backend/app/api/v1/datasources.py           # 修改 — 新增导出端点
backend/tests/test_report_export.py         # 新建 — 测试
frontend/src/api/datasource.ts              # 修改 — 新增导出 API
frontend/src/views/datasource/index.vue     # 修改 — 新增导出按钮
```

### 2. 报告生成服务

```python
# backend/app/services/report_export.py

"""对接报告导出服务 — Story 3.5"""
import io
import json
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill


def generate_integration_report(
    datasources: list[dict],
    points: list[dict],
) -> bytes:
    """生成对接报告 Excel，返回 bytes"""
    wb = Workbook()

    # --- Sheet 1: 数据源清单 ---
    ws1 = wb.active
    ws1.title = "数据源清单"

    headers1 = ["名称", "协议类型", "连接参数", "连接状态", "最后通信时间", "创建时间", "启用状态"]
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

    for col, h in enumerate(headers1, 1):
        cell = ws1.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    for row_idx, ds in enumerate(datasources, 2):
        ws1.cell(row=row_idx, column=1, value=ds.get("name", ""))
        ws1.cell(row=row_idx, column=2, value=ds.get("protocol_type", ""))
        # 连接参数摘要
        config = ds.get("connection_config", {})
        config_summary = json.dumps(config, ensure_ascii=False) if config else ""
        ws1.cell(row=row_idx, column=3, value=config_summary)
        ws1.cell(row=row_idx, column=4, value=ds.get("status", ""))
        ws1.cell(row=row_idx, column=5, value=str(ds.get("last_communication", "") or ""))
        ws1.cell(row=row_idx, column=6, value=str(ds.get("created_at", "") or ""))
        ws1.cell(row=row_idx, column=7, value="是" if ds.get("is_enabled") else "否")

    # 自动列宽
    for col in ws1.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws1.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

    # --- Sheet 2: 点位映射表 ---
    ws2 = wb.create_sheet("点位映射表")

    headers2 = ["数据源名称", "地址", "数据类型", "缩放系数", "偏移量", "是否干接点"]
    for col, h in enumerate(headers2, 1):
        cell = ws2.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    for row_idx, pt in enumerate(points, 2):
        ws2.cell(row=row_idx, column=1, value=pt.get("datasource_name", ""))
        ws2.cell(row=row_idx, column=2, value=pt.get("address", ""))
        ws2.cell(row=row_idx, column=3, value=pt.get("data_type", ""))
        ws2.cell(row=row_idx, column=4, value=pt.get("scale", 1.0))
        ws2.cell(row=row_idx, column=5, value=pt.get("offset", 0.0))
        ws2.cell(row=row_idx, column=6, value="是" if pt.get("is_dry_contact") else "否")

    for col in ws2.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws2.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
```

### 3. 后端 API 端点

在 `backend/app/api/v1/datasources.py` 中新增（放在 list_datasources 之后、create_datasource 之前，因为路径是 `/export-report` 不含路径参数）：

```python
from fastapi.responses import StreamingResponse
from ...models.gateway import DataSourcePoint
from ...services.report_export import generate_integration_report
import io

@router.get("/export-report", summary="导出对接报告")
async def export_report(
    protocol_type: Optional[str] = Query(None),
    gateway_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    # 查询数据源
    query = select(DataSource)
    if protocol_type:
        query = query.where(DataSource.protocol_type == protocol_type)
    if gateway_id is not None:
        query = query.where(DataSource.gateway_id == gateway_id)
    if status:
        query = query.where(DataSource.status == status)
    query = query.order_by(DataSource.id)

    result = await db.execute(query)
    ds_list = result.scalars().all()

    # 构建数据源字典列表
    datasources = []
    ds_id_to_name = {}
    ds_ids = []
    for ds in ds_list:
        ds_ids.append(ds.id)
        ds_id_to_name[ds.id] = ds.name
        datasources.append({
            "name": ds.name,
            "protocol_type": ds.protocol_type,
            "connection_config": ds.connection_config,
            "status": ds.status,
            "last_communication": ds.last_communication,
            "created_at": ds.created_at,
            "is_enabled": ds.is_enabled,
        })

    # 查询点位
    points = []
    if ds_ids:
        pt_result = await db.execute(
            select(DataSourcePoint).where(DataSourcePoint.datasource_id.in_(ds_ids))
            .order_by(DataSourcePoint.datasource_id, DataSourcePoint.id)
        )
        for pt in pt_result.scalars().all():
            points.append({
                "datasource_name": ds_id_to_name.get(pt.datasource_id, ""),
                "address": pt.address,
                "data_type": pt.data_type,
                "scale": pt.scale,
                "offset": pt.offset,
                "is_dry_contact": pt.is_dry_contact,
            })

    # 生成 Excel
    excel_bytes = generate_integration_report(datasources, points)

    filename = f"integration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
```

**重要**：`/export-report` 端点必须放在 `/{datasource_id}` 之前，否则 FastAPI 会把 "export-report" 当作 datasource_id 路径参数。放在 list_datasources（GET ""）之后、create_datasource（POST ""）之前。

### 4. 前端导出 API

在 `frontend/src/api/datasource.ts` 新增：

```typescript
export function exportReport(params?: any) {
  return request.get('/v1/datasources/export-report', {
    params,
    responseType: 'blob',
  } as any)
}
```

注意：需要 responseType: 'blob' 来接收二进制文件。由于 request 封装的类型限制，可能需要 `as any`。

### 5. 前端导出按钮

在数据源管理页面的 card-header 中，"新增数据源"按钮之前新增"导出报告"按钮：

```vue
<div class="card-header">
  <span>数据源管理</span>
  <div>
    <el-button :icon="Download" @click="handleExport">导出报告</el-button>
    <el-button type="primary" :icon="Plus" @click="handleAdd">新增数据源</el-button>
  </div>
</div>
```

导出处理函数：

```typescript
import { Download } from '@element-plus/icons-vue'

async function handleExport() {
  try {
    const blob = await exportReport() as any
    const url = window.URL.createObjectURL(new Blob([blob]))
    const link = document.createElement('a')
    link.href = url
    link.download = `对接报告_${new Date().toISOString().slice(0, 10)}.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('报告导出成功')
  } catch (e) {
    console.error('导出失败', e)
    ElMessage.error('导出失败')
  }
}
```

### 6. 关键约束

- **openpyxl 已安装**: 版本 3.1.2
- **StreamingResponse**: 使用 FastAPI 的 StreamingResponse 返回文件流
- **路由顺序**: `/export-report` 必须在 `/{datasource_id}` 之前注册
- **Excel 样式**: 表头蓝色背景白色粗体，自动列宽
- **responseType blob**: 前端下载需要 blob 响应类型
- **测试**: 使用 openpyxl 解析生成的 Excel 验证内容

### References

- [Source: models/gateway.py] DataSource, DataSourcePoint 模型
- [Source: api/v1/datasources.py] 现有数据源 API
- [Source: epics.md#Story 3.5] Acceptance Criteria

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

