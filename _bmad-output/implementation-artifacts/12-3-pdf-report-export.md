# Story 12-3: PDF报表导出

## Story

As a 运维主管,
I want 将报表导出为 PDF 格式,
So that 我可以打印或分享给不使用系统的人。

## Status: Draft

## Brownfield Analysis

- `services/pdf_generator.py` — existing reportlab PDF generator with Chinese font support
- `services/energy_report_pdf.py` — energy-specific PDF generator
- `GET /download/{record_id}?format=pdf` — existing download endpoint (uses mock data for PDF)
- `ReportRecord.report_data` — now stores full JSON from auto-generate (Story 12-1)

## What's Needed

A new endpoint `GET /auto-report-pdf/{record_id}` that reads the `report_data` JSON from a ReportRecord and generates a comprehensive PDF with all sections (alarm trends, energy comparison, work order stats, device availability, comparison).

## Technical Design

### New endpoint in `api/v1/report.py`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/auto-report-pdf/{record_id}` | 导出自动报表为 PDF |

### New service function in `services/pdf_generator.py`:

`generate_auto_report_pdf(report_data: dict) -> io.BytesIO` — generates PDF with sections for each data dimension.

### Frontend: add `exportAutoReportPdf()` function

### Tests: 3 tests
