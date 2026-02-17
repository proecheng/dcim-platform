# Story 3.2: 点位批量导入与预校验

Status: done

## Story

As a 集成工程师,
I want 通过 Excel 批量导入点位配置,
So that 我可以快速完成大量点位的配置工作。

## Acceptance Criteria (验收标准)

1. **AC-1: 后端校验 API** — POST `/api/v1/datasources/{id}/points/validate` 接收 Excel 文件，同步执行预校验，返回校验报告
2. **AC-2: 后端导入 API** — POST `/api/v1/datasources/{id}/points/import` 接收 Excel 文件，校验通过后批量导入到 DataSourcePoint 表
3. **AC-3: 寄存器地址冲突检测** — 校验 Excel 内部地址重复 + 与数据库已有地址冲突
4. **AC-4: 数据类型匹配验证** — 校验 data_type 是否在允许列表内（int16/uint16/int32/uint32/float32/float64/bool/string）
5. **AC-5: 量程范围合理性检查** — scale 和 offset 为数值类型，enum_mapping 为合法 JSON
6. **AC-6: 校验报告格式** — 返回 `{total, passed, failed, errors: [{row, field, message}]}`
7. **AC-7: 文件格式校验** — 非 xlsx 文件返回 400 错误提示
8. **AC-8: 文件大小限制** — 超过 10MB 拒绝上传并提示分批导入
9. **AC-9: 前端上传组件** — 在数据源详情/编辑页面提供"导入点位"按钮，弹出上传对话框
10. **AC-10: 前端校验报告展示** — 上传后显示校验结果，通过后可一键确认导入

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端点位导入服务 (AC: #1-#6)
  - [ ] 1.1 创建 `backend/app/services/point_import.py`
  - [ ] 1.2 实现 `validate_point_excel(file, datasource_id, db)` — 解析 Excel + 校验
  - [ ] 1.3 实现 `import_point_excel(file, datasource_id, db)` — 校验 + 批量导入
  - [ ] 1.4 校验规则：地址冲突、数据类型、scale/offset 数值、enum_mapping JSON

- [ ] Task 2: 后端 API 端点 (AC: #1, #2, #7, #8)
  - [ ] 2.1 在 `backend/app/api/v1/datasources.py` 新增 validate 和 import 端点
  - [ ] 2.2 文件格式校验（仅 .xlsx）
  - [ ] 2.3 文件大小校验（≤10MB）

- [ ] Task 3: 前端 API 扩展 (AC: #9)
  - [ ] 3.1 在 `frontend/src/api/datasource.ts` 新增 validatePoints 和 importPoints 函数

- [ ] Task 4: 前端导入对话框 (AC: #9, #10)
  - [ ] 4.1 在数据源管理页面新增"导入点位"操作按钮
  - [ ] 4.2 实现导入对话框：el-upload 上传 + 校验报告展示 + 确认导入按钮

- [ ] Task 5: 后端单元测试 (AC: 全部)
  - [ ] 5.1 测试 validate — 正常 Excel 校验通过
  - [ ] 5.2 测试 validate — 地址冲突检测（Excel 内部重复）
  - [ ] 5.3 测试 validate — 地址冲突检测（与数据库已有冲突）
  - [ ] 5.4 测试 validate — 无效数据类型
  - [ ] 5.5 测试 validate — scale/offset 非数值
  - [ ] 5.6 测试 validate — 空文件/无数据行
  - [ ] 5.7 测试 import — 校验通过后批量插入
  - [ ] 5.8 测试 API — 文件格式校验（非 xlsx 返回 400）
  - [ ] 5.9 测试 API — 文件大小校验（>10MB 返回 400）

- [ ] Task 6: 前端构建验证
  - [ ] 6.1 `npm run build` 构建成功

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/services/point_import.py        # 新建 — 点位导入服务
backend/app/api/v1/datasources.py           # 修改 — 新增 validate/import 端点
backend/tests/test_point_import.py          # 新建 — 单元测试
frontend/src/api/datasource.ts              # 修改 — 新增导入 API
frontend/src/views/datasource/index.vue     # 修改 — 新增导入对话框
```

### 2. Excel 模板格式

| 列名 | 字段 | 必填 | 说明 |
|------|------|------|------|
| address | address | 是 | 协议地址（如 40001, 1.3.6.1.2.1.1.1.0） |
| data_type | data_type | 是 | 数据类型 |
| scale | scale | 否 | 缩放系数，默认 1.0 |
| offset | offset | 否 | 偏移量，默认 0.0 |
| enum_mapping | enum_mapping | 否 | 枚举映射 JSON 字符串 |
| is_dry_contact | is_dry_contact | 否 | 是否干接点，默认 false |

### 3. 点位导入服务

```python
# backend/app/services/point_import.py

import io
import json
import logging
from typing import Optional
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.gateway import DataSourcePoint

logger = logging.getLogger(__name__)

VALID_DATA_TYPES = {
    "int16", "uint16", "int32", "uint32",
    "float32", "float64", "bool", "string",
}

REQUIRED_COLUMNS = {"address", "data_type"}
OPTIONAL_COLUMNS = {"scale", "offset", "enum_mapping", "is_dry_contact"}
ALL_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS


def parse_excel(file_bytes: bytes) -> tuple[list[str], list[dict]]:
    """解析 Excel 文件，返回 (列名列表, 行数据列表)"""
    wb = load_workbook(filename=io.BytesIO(file_bytes), read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return [], []

    # 第一行为表头
    headers = [str(h).strip().lower() if h else "" for h in rows[0]]
    data = []
    for row_idx, row in enumerate(rows[1:], start=2):
        row_dict = {}
        for col_idx, header in enumerate(headers):
            if header in ALL_COLUMNS and col_idx < len(row):
                row_dict[header] = row[col_idx]
        if any(v is not None and v != "" for v in row_dict.values()):
            row_dict["_row"] = row_idx
            data.append(row_dict)

    return headers, data


async def validate_points(
    file_bytes: bytes,
    datasource_id: int,
    db: AsyncSession,
) -> dict:
    """校验 Excel 点位数据，返回校验报告"""
    headers, rows = parse_excel(file_bytes)

    if not rows:
        return {"total": 0, "passed": 0, "failed": 0, "errors": [{"row": 0, "field": "", "message": "Excel 文件无数据行"}]}

    # 检查必填列是否存在
    missing_cols = REQUIRED_COLUMNS - set(headers)
    if missing_cols:
        return {
            "total": 0, "passed": 0, "failed": 0,
            "errors": [{"row": 0, "field": "", "message": f"缺少必填列: {', '.join(missing_cols)}"}],
        }

    errors = []
    seen_addresses = set()

    # 查询数据库已有地址
    result = await db.execute(
        select(DataSourcePoint.address).where(DataSourcePoint.datasource_id == datasource_id)
    )
    existing_addresses = {r[0] for r in result.fetchall()}

    for row in rows:
        row_num = row.get("_row", 0)
        address = row.get("address")
        data_type = row.get("data_type")

        # 必填字段
        if not address or str(address).strip() == "":
            errors.append({"row": row_num, "field": "address", "message": "地址不能为空"})
            continue
        address = str(address).strip()

        if not data_type or str(data_type).strip() == "":
            errors.append({"row": row_num, "field": "data_type", "message": "数据类型不能为空"})
            continue
        data_type = str(data_type).strip().lower()

        # 数据类型校验
        if data_type not in VALID_DATA_TYPES:
            errors.append({
                "row": row_num, "field": "data_type",
                "message": f"无效数据类型: {data_type}，允许: {', '.join(sorted(VALID_DATA_TYPES))}",
            })

        # Excel 内部地址重复
        if address in seen_addresses:
            errors.append({"row": row_num, "field": "address", "message": f"地址重复: {address}"})
        seen_addresses.add(address)

        # 与数据库已有地址冲突
        if address in existing_addresses:
            errors.append({"row": row_num, "field": "address", "message": f"地址已存在: {address}"})

        # scale 数值校验
        scale = row.get("scale")
        if scale is not None and scale != "":
            try:
                float(scale)
            except (ValueError, TypeError):
                errors.append({"row": row_num, "field": "scale", "message": f"scale 必须为数值: {scale}"})

        # offset 数值校验
        offset_val = row.get("offset")
        if offset_val is not None and offset_val != "":
            try:
                float(offset_val)
            except (ValueError, TypeError):
                errors.append({"row": row_num, "field": "offset", "message": f"offset 必须为数值: {offset_val}"})

        # enum_mapping JSON 校验
        enum_mapping = row.get("enum_mapping")
        if enum_mapping is not None and enum_mapping != "":
            try:
                parsed = json.loads(str(enum_mapping))
                if not isinstance(parsed, dict):
                    errors.append({"row": row_num, "field": "enum_mapping", "message": "enum_mapping 必须为 JSON 对象"})
            except (json.JSONDecodeError, TypeError):
                errors.append({"row": row_num, "field": "enum_mapping", "message": f"enum_mapping JSON 格式无效"})

    total = len(rows)
    # 统计有错误的行数
    error_rows = set(e["row"] for e in errors)
    failed = len(error_rows)
    passed = total - failed

    return {"total": total, "passed": passed, "failed": failed, "errors": errors}


async def import_points(
    file_bytes: bytes,
    datasource_id: int,
    db: AsyncSession,
) -> dict:
    """校验并导入点位，返回导入结果"""
    # 先校验
    report = await validate_points(file_bytes, datasource_id, db)
    if report["failed"] > 0:
        return {"success": False, "report": report}

    # 解析并导入
    _, rows = parse_excel(file_bytes)
    imported = 0
    for row in rows:
        address = str(row["address"]).strip()
        data_type = str(row["data_type"]).strip().lower()
        scale = float(row.get("scale") or 1.0)
        offset_val = float(row.get("offset") or 0.0)

        enum_mapping = None
        raw_enum = row.get("enum_mapping")
        if raw_enum and str(raw_enum).strip():
            enum_mapping = json.loads(str(raw_enum))

        is_dry = row.get("is_dry_contact")
        is_dry_contact = str(is_dry).lower() in ("true", "1", "yes") if is_dry else False

        point = DataSourcePoint(
            datasource_id=datasource_id,
            address=address,
            data_type=data_type,
            scale=scale,
            offset=offset_val,
            enum_mapping=enum_mapping,
            is_dry_contact=is_dry_contact,
        )
        db.add(point)
        imported += 1

    await db.commit()
    return {"success": True, "imported": imported, "report": report}
```

### 4. 后端 API 端点

在 `backend/app/api/v1/datasources.py` 中新增两个端点（放在 `/{datasource_id}/test-connection` 之后，`DELETE` 之前）：

```python
from fastapi import UploadFile, File

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@router.post("/{datasource_id}/points/validate", summary="预校验点位 Excel")
async def validate_points_excel(
    datasource_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    # 文件格式校验
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 格式文件")

    # 文件大小校验
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 10MB，请分批导入")

    # 数据源存在性校验
    result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="数据源不存在")

    from ...services.point_import import validate_points
    report = await validate_points(content, datasource_id, db)
    return report


@router.post("/{datasource_id}/points/import", summary="批量导入点位")
async def import_points_excel(
    datasource_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 格式文件")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 10MB，请分批导入")

    result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="数据源不存在")

    from ...services.point_import import import_points
    result = await import_points(content, datasource_id, db)
    if not result["success"]:
        raise HTTPException(status_code=400, detail={"message": "校验失败", "report": result["report"]})
    return result
```

### 5. 前端 API 扩展

在 `frontend/src/api/datasource.ts` 新增：

```typescript
export function validatePoints(datasourceId: number, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post(`/v1/datasources/${datasourceId}/points/validate`, formData)
}

export function importPoints(datasourceId: number, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post(`/v1/datasources/${datasourceId}/points/import`, formData)
}
```

### 6. 前端导入对话框

在数据源管理页面的操作列中，新增"导入点位"按钮。点击后弹出导入对话框：

```vue
<!-- 导入点位对话框 -->
<el-dialog v-model="importDialogVisible" title="批量导入点位" width="650px">
  <div>
    <p style="margin-bottom: 12px; color: #909399; font-size: 13px;">
      上传 .xlsx 格式的点位配置文件，系统将自动校验数据有效性。
      必填列：address（地址）、data_type（数据类型）。
      可选列：scale、offset、enum_mapping、is_dry_contact。
    </p>
    <el-upload
      ref="uploadRef"
      :auto-upload="false"
      :limit="1"
      accept=".xlsx"
      :on-change="handleFileChange"
      :on-exceed="() => ElMessage.warning('只能上传一个文件')"
      drag
    >
      <el-icon style="font-size: 40px; color: #909399;"><Upload /></el-icon>
      <div>将文件拖到此处，或<em>点击上传</em></div>
    </el-upload>

    <!-- 校验报告 -->
    <div v-if="importReport" style="margin-top: 16px;">
      <el-alert
        :title="`校验完成：共 ${importReport.total} 条，通过 ${importReport.passed} 条，失败 ${importReport.failed} 条`"
        :type="importReport.failed === 0 ? 'success' : 'warning'"
        :closable="false"
        show-icon
      />
      <el-table v-if="importReport.errors.length > 0" :data="importReport.errors" size="small" max-height="200" style="margin-top: 8px;" border>
        <el-table-column prop="row" label="行号" width="70" />
        <el-table-column prop="field" label="字段" width="120" />
        <el-table-column prop="message" label="错误信息" />
      </el-table>
    </div>
  </div>
  <template #footer>
    <el-button @click="importDialogVisible = false">取消</el-button>
    <el-button :loading="validating" @click="handleValidate">校验</el-button>
    <el-button
      type="primary"
      :loading="importing"
      :disabled="!importReport || importReport.failed > 0"
      @click="handleImport"
    >
      确认导入
    </el-button>
  </template>
</el-dialog>
```

### 7. 关键约束

- **openpyxl 已安装**: 版本 3.1.2，无需额外安装
- **同步校验**: Excel 通常几百到几千行，直接在请求中同步处理
- **文件大小**: 前端 el-upload 的 before-upload 也做 10MB 限制
- **测试使用 mock**: 使用 openpyxl 创建内存中的 Excel 文件进行测试，不需要真实文件
- **不修改 DataSourcePoint 模型**: 模型已完整
- **API 路径**: `/api/v1/datasources/{id}/points/validate` 和 `/api/v1/datasources/{id}/points/import`
- **前端构建**: 完成后运行 `npm run build` 确保无编译错误

### Project Structure Notes

- `backend/app/services/point_import.py` — 新建
- `backend/app/api/v1/datasources.py` — 修改（新增 2 个端点）
- `backend/tests/test_point_import.py` — 新建
- `frontend/src/api/datasource.ts` — 修改（新增 2 个函数）
- `frontend/src/views/datasource/index.vue` — 修改（新增导入对话框）

### References

- [Source: models/gateway.py] DataSourcePoint 模型
- [Source: schemas/gateway.py] DataSourcePointCreate Schema
- [Source: api/v1/datasources.py] 现有数据源 API
- [Source: architecture.md#4.4] 点位批量导入预校验
- [Source: epics.md#Story 3.2] Acceptance Criteria

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

