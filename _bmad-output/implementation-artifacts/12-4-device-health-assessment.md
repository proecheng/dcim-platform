# Story 12-4: 设备健康度评估

## Story

As a 运维主管,
I want 查看设备健康度评估,
So that 我可以提前规划维保和更换。

## Status: Draft

## Technical Design

### New model: `DeviceHealthScore` in `models/report.py`
- device_id (FK to devices), score (0-100), health_level (健康/关注/预警/危险)
- alarm_count, maintenance_count, last_maintenance_at, calculated_at

### New API endpoints in `api/v1/report.py`:
- POST `/device-health/calculate` — 计算所有设备健康度
- GET `/device-health` — 获取设备健康度列表（支持排序、筛选）
- GET `/device-health/{device_id}` — 获取单个设备健康度

### Health score algorithm:
- Base score: 100
- Deductions: critical alarms (-15 each), major alarms (-8), minor (-3)
- Deductions: overdue maintenance (-20)
- Bonus: recent maintenance (+5)
- Clamp to 0-100

### Health levels:
- 80-100: 健康
- 60-79: 关注
- 40-59: 预警
- 0-39: 危险

### Tests: 6 tests
