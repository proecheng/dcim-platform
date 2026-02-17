# Story 6-5: 能效报告导出

## Story

As a 能源管理员,
I want 导出月度能效报告,
So that 我可以向管理层汇报能耗和节能成果。

## Status: Ready for Dev

## FR 追溯
- FR52: 能源管理员可以导出能效报告（含 PUE 趋势、电费对比、节能成果）

## Acceptance Criteria

1. Given 能源管理员在能效报告页面
   When 选择时间范围（月度）并点击"生成报告"
   Then 系统查询该时间段的 PUE 趋势、电费对比、节能成果数据并展示预览

2. Given 报告预览已生成
   When 点击"导出 Excel"
   Then 下载包含 PUE 趋势表、电费对比表、节能成果表的 .xlsx 文件

3. Given 报告预览已生成
   When 点击"导出 PDF"
   Then 下载包含标题、时间范围、PUE 趋势表格、电费对比表格、节能成果汇总的 PDF 文件

4. Given 导出完成
   Then 系统在 report_records 表中记录本次导出（report_type="energy_efficiency"）

5. Given 能源管理员选择不同月份
   When 生成报告
   Then 报告包含同比（去年同月）和环比（上月）对比数据

## 对抗性审查修复记录

### C1: ExecutionResult 无 cost_before/cost_after 字段
实际模型只有 energy_before(JSON)、energy_after(JSON)、actual_saving(Numeric)、achievement_rate(Numeric)。
修复：节能成果费用从 actual_saving 获取，节能电量从 energy_before/energy_after JSON 数组求和差值。

### C2: EnergyDaily 字段是 normal_energy 不是 flat_energy
修复：所有查询使用 EnergyDaily.normal_energy / EnergyMonthly.normal_energy / normal_cost。

### C3: PUEHistory 每15分钟记录，字段是 pue 不是 pue_value
修复：GROUP BY func.date(PUEHistory.record_time) 取日均值。

### C4: EnergyDaily 无分项电费字段，应优先用 EnergyMonthly
修复：电费对比优先查 EnergyMonthly（有 peak_cost/normal_cost/valley_cost），fallback 到 EnergyDaily × ElectricityPricing。

### H1: EnergyOpportunity.status 初始值是 "discovered" 不是 "pending"
修复：查询 status IN ('completed', 'executing')。

### H2: ExecutionResult.energy_before/energy_after 是 JSON 数组
格式 [{date, energy, cost}]。修复：解析 JSON 求和。

### H3: ReportRecord.template_id 可为 NULL
修复：显式设 template_id=None, file_path=None, file_size=None。

### H4: PDF 中文字体 Linux 不存在
修复：字体查找链 Windows → Ubuntu → CentOS → macOS → Helvetica fallback。

## 技术设计

### 后端实现

#### 1. 能效报告数据服务 `backend/app/services/energy_report_service.py`

```python
class EnergyReportService:
    @staticmethod
    async def generate_report_data(db: AsyncSession, year: int, month: int) -> dict:
        # 返回结构:
        {
            "report_info": { "year", "month", "generated_at", "period_start", "period_end" },
            "pue_trend": {
                "daily_values": [{"date", "avg_pue", "min_pue", "max_pue"}],
                "month_avg_pue", "month_min_pue", "month_max_pue",
                "yoy_change": float|None, "mom_change": float|None
            },
            "cost_comparison": {
                "current_month": { "total_energy", "total_cost", "peak_energy", "peak_cost",
                    "normal_energy", "normal_cost", "valley_energy", "valley_cost" },
                "last_month": {...}|None, "last_year_month": {...}|None,
                "yoy_change_rate": float|None, "mom_change_rate": float|None
            },
            "energy_saving": {
                "total_saving_cost", "total_saving_kwh",
                "opportunities_count", "executed_count", "avg_achievement_rate",
                "details": [{"title", "category", "saving_kwh", "saving_cost", "achievement_rate"}]
            },
            "energy_overview": {
                "total_energy", "daily_trend": [{"date", "total_energy", "pue"}]
            }
        }
```

数据来源与查询策略：

1. PUE 趋势 — PUEHistory（record_time=DateTime 每15分钟，字段=pue）
   GROUP BY func.date(record_time) → 日均/最小/最大
   同比环比：查去年同月和上月 AVG(pue)

2. 电费对比 — 优先 EnergyMonthly（有 peak_cost/normal_cost/valley_cost）
   Fallback：SUM(EnergyDaily.peak_energy) × peak_price 等
   period_type 映射：peak→peak_energy, flat→normal_energy, valley→valley_energy

3. 节能成果 — EnergyOpportunity(status IN completed/executing) → ExecutionPlan → ExecutionResult
   energy_before/energy_after 是 JSON [{date,energy,cost}]，解析求和
   saving_cost 用 actual_saving(Numeric 12,2)

4. 能耗概览 — EnergyDaily 按日聚合 SUM(total_energy)

#### 2. Excel 导出 `backend/app/services/energy_report_excel.py`

openpyxl 生成 5 Sheet：概览、PUE趋势、电费对比、节能成果、每日能耗
样式：表头加粗+背景色、冻结首行、列宽自适应、数字2位小数

#### 3. PDF 导出 `backend/app/services/energy_report_pdf.py`

reportlab 生成：封面、指标摘要、PUE表格、电费表格、节能表格
中文字体 fallback 链：SimHei(Win) → wqy-zenhei(Ubuntu/CentOS) → PingFang(macOS) → Helvetica

#### 4. API 端点 — energy.py 新增

- GET /energy/report/preview (require_viewer) → JSON 预览
- GET /energy/report/export (require_operator) → 文件流 format=excel|pdf
- 导出后写 ReportRecord(template_id=None, report_type="energy_efficiency")

### 前端实现

#### 5. 能效报告页面 `frontend/src/views/energy/report.vue`

月份选择器 + 生成按钮 → 4区块预览（指标卡片、PUE折线图、电费表、节能表）→ 导出按钮组
blob 下载模式复用 statistics.vue

#### 6. API 函数 energy.ts + 路由 router/index.ts

### 测试

#### 7. 后端测试 10 个用例

## Tasks

### Task 1: 能效报告数据服务 [后端]
- 创建 backend/app/services/energy_report_service.py
- EnergyReportService.generate_report_data(db, year, month)
- PUE: GROUP BY func.date(PUEHistory.record_time), 字段 pue
- 电费: 优先 EnergyMonthly, fallback EnergyDaily × ElectricityPricing
- 节能: status IN (completed,executing), 解析 JSON energy_before/energy_after
- 能耗: EnergyDaily 按日聚合
- 同比环比计算, 无数据返回零值
- 关键: normal_energy 不是 flat_energy, pue 不是 pue_value, discovered 不是 pending

### Task 2: Excel 导出服务 [后端]
- 创建 backend/app/services/energy_report_excel.py
- openpyxl 5 Sheet + 样式

### Task 3: PDF 导出服务 [后端]
- 创建 backend/app/services/energy_report_pdf.py
- reportlab + 中文字体 fallback 链

### Task 4: API 端点 [后端]
- energy.py 新增 preview + export 端点
- ReportRecord 记录(template_id=None)

### Task 5: 能效报告页面 [前端]
- frontend/src/views/energy/report.vue
- 月份选择、预览、ECharts、el-table、导出

### Task 6: API 函数与路由 [前端]
- energy.ts 新增 getEnergyReportPreview + exportEnergyReport
- router/index.ts energy-saving children 添加 report

### Task 7: 后端测试 [测试]
- backend/tests/test_energy_report.py 10 个用例

## Dev Notes

- normal_energy 不是 flat_energy, normal_cost 不是 flat_cost
- PUEHistory.pue 不是 pue_value, record_time 是 DateTime 每15分钟
- EnergyOpportunity 初始 status="discovered"
- ExecutionResult 无 cost_before/cost_after, 有 actual_saving(Numeric 12,2)
- ExecutionResult.energy_before/energy_after: JSON [{date,energy,cost}]
- ElectricityPricing period_type flat → EnergyDaily.normal_energy
- ReportRecord: template_id=None, file_path=None, file_size=None
- PDF 字体: Windows C:/Windows/Fonts/simhei.ttf, Linux 需 wqy-zenhei
- blob 下载参考 statistics.vue handleExport
