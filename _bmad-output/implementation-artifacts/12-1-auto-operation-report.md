# Story 12-1: 自动运行报表

## Story

As a 运维主管,
I want 系统自动生成运行报表,
So that 我可以定期了解机房运行状况。

## Status: Draft

## Brownfield Analysis

### Existing Code (MUST build upon)

**Models** (`backend/app/models/report.py`):
- `ReportTemplate` — template_name, template_type (daily/weekly/monthly/custom), template_config (JSON), point_ids (JSON), is_enabled, created_by
- `ReportRecord` — template_id, report_name, report_type, start_time, end_time, file_path, file_size, status (generating/completed/failed), error_message, generated_by

**Schemas** (`backend/app/schemas/report.py`):
- `ReportTemplateCreate/Update/Info`, `ReportRecordInfo`, `ReportGenerate`

**API** (`backend/app/api/v1/report.py`, prefix `/api/v1/reports`):
- Templates CRUD: GET/POST/PUT/DELETE `/templates`
- Generate: POST `/generate` — manual report generation with point stats + alarm counts
- Records: GET `/records` — paginated report records
- Download: GET `/download/{record_id}` — JSON/CSV/PDF export
- Daily/Weekly/Monthly: GET `/daily`, `/weekly`, `/monthly` — basic data endpoints

**Statistics API** (`backend/app/api/v1/statistics.py`, prefix `/api/v1/statistics`):
- GET `/alarms` — by_level, by_status, daily_trend, top_alarm_points, avg_resolve_duration
- GET `/energy` — power point daily averages
- GET `/availability` — overall + by device type availability %
- GET `/comparison` — week/month 同比环比

**Operation Statistics** (`backend/app/api/v1/operation.py`):
- GET `/operation/statistics` — total/pending/processing/completed orders, overdue inspections, knowledge count

**Frontend** (`frontend/src/api/modules/report.ts`):
- Full TypeScript types and API functions for templates, records, generate, download, daily/weekly/monthly
- Route at `/reports` pointing to `views/report/index.vue`

### What's Missing (Story 12-1 scope)

1. **ReportRecord needs `report_data` field** — to store the full JSON report content (alarm trends, energy comparison, work order stats, device availability) so it can be retrieved later
2. **Auto-generation scheduling config** — `ReportSchedule` model or fields on `ReportTemplate` to define auto-generation frequency and parameters
3. **Comprehensive report content** — current generate endpoint only collects point stats + alarm counts; needs alarm trends, energy comparison, work order stats, device availability
4. **同比/环比 analysis** — needs to be embedded in report data
5. **Auto-generate API endpoint** — trigger auto-generation for a given period type
6. **Schedule management endpoints** — CRUD for auto-report schedules

## Acceptance Criteria

1. Given 系统已积累运行数据, When 调用自动生成报表 API (日报/周报/月报), Then 系统生成包含告警趋势、能耗对比、工单统计、设备可用率的综合报表
2. And 报表支持同比/环比分析数据
3. And 报表记录保存到 ReportRecord 表，包含完整 report_data JSON
4. And 提供报表调度配置 CRUD（频率、启用/禁用）
5. And 提供手动触发自动报表生成的 API

## Technical Design

### 1. Model Changes

**Extend `ReportRecord`** — add `report_data` column (Text/JSON) to store full report content.

**New model: `ReportSchedule`** in `models/report.py`:
```python
class ReportSchedule(Base):
    __tablename__ = "report_schedules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="调度名称")
    report_type = Column(String(20), nullable=False, comment="报表类型: daily/weekly/monthly")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    cron_expression = Column(String(50), comment="Cron表达式")
    last_run_at = Column(DateTime, comment="上次运行时间")
    next_run_at = Column(DateTime, comment="下次运行时间")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

### 2. Schema Changes

**New schemas** in `schemas/report.py`:
- `ReportScheduleCreate` — name, report_type, is_enabled, cron_expression
- `ReportScheduleUpdate` — all optional
- `ReportScheduleResponse` — full model fields
- `AutoReportData` — structured response with alarm_trends, energy_comparison, workorder_stats, device_availability, comparison (同比环比)

### 3. API Changes

**New endpoints** in `api/v1/report.py`:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auto-generate` | 触发自动报表生成 (日报/周报/月报) |
| GET | `/schedules` | 获取报表调度列表 |
| POST | `/schedules` | 创建报表调度 |
| PUT | `/schedules/{id}` | 更新报表调度 |
| DELETE | `/schedules/{id}` | 删除报表调度 |

**POST `/auto-generate`** — accepts `report_type` (daily/weekly/monthly), generates comprehensive report:
- Alarm trends: by level, daily trend, top alarm points, avg resolve time
- Energy comparison: PUE, daily energy, 同比环比
- Work order stats: total/pending/processing/completed, by type
- Device availability: overall %, by device type
- Saves to ReportRecord with full report_data JSON

### 4. Frontend Changes

**New types** in `api/modules/report.ts`:
- `ReportSchedule` interface
- `AutoReportData` interface (alarm_trends, energy_comparison, workorder_stats, device_availability)
- API functions: `autoGenerateReport()`, `getReportSchedules()`, `createReportSchedule()`, `updateReportSchedule()`, `deleteReportSchedule()`

**No new Vue page needed** — existing `/reports` page will be enhanced in a later story or the existing page already covers report viewing.

### 5. Test Plan

Test file: `tests/test_report_auto.py`

| # | Test | Description |
|---|------|-------------|
| 1 | test_auto_generate_daily | 生成日报，验证返回包含 alarm_trends, energy_comparison, workorder_stats, device_availability |
| 2 | test_auto_generate_weekly | 生成周报 |
| 3 | test_auto_generate_monthly | 生成月报 |
| 4 | test_auto_generate_saves_record | 验证生成后 ReportRecord 有记录且 report_data 非空 |
| 5 | test_auto_generate_comparison | 验证同比环比数据存在 |
| 6 | test_schedule_crud_create | 创建调度 |
| 7 | test_schedule_crud_list | 列表查询 |
| 8 | test_schedule_crud_update | 更新调度 |
| 9 | test_schedule_crud_delete | 删除调度 |
| 10 | test_schedule_create_invalid_type | 无效 report_type 返回 422 |
| 11 | test_auto_generate_invalid_type | 无效 report_type 返回 422 |
| 12 | test_auto_generate_record_has_data | 通过 records API 获取记录，验证 report_data 字段 |

## Dev Tasks

1. [ ] Add `report_data` column to `ReportRecord` model
2. [ ] Add `ReportSchedule` model + register in `__init__.py`
3. [ ] Add new schemas: `ReportScheduleCreate/Update/Response`, `AutoReportData`
4. [ ] Implement `POST /auto-generate` endpoint with comprehensive data collection
5. [ ] Implement schedule CRUD endpoints
6. [ ] Add frontend TypeScript types and API functions
7. [ ] Write tests (12 tests)
