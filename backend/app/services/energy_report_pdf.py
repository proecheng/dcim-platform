"""
能效报告 PDF 导出 — Story 6-5
使用 reportlab CID 字体 (STSong-Light) 支持中文，与 pdf_generator.py 保持一致
"""
import io
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

# 注册中文字体 (CID 内置，无需外部文件)
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

_FONT = "STSong-Light"
_BLUE = colors.HexColor("#4472C4")


def _styles():
    base = getSampleStyleSheet()
    title = ParagraphStyle("RPTitle", parent=base["Heading1"], fontName=_FONT, fontSize=18, alignment=1, spaceAfter=20)
    h2 = ParagraphStyle("RPH2", parent=base["Heading2"], fontName=_FONT, fontSize=13, spaceBefore=14, spaceAfter=8)
    normal = ParagraphStyle("RPNormal", parent=base["Normal"], fontName=_FONT, fontSize=10, leading=14)
    return title, h2, normal


def _table(data: List[list], col_widths=None) -> Table:
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), _FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
    ]
    t.setStyle(TableStyle(style))
    return t


def _fmt(v, decimals=2) -> str:
    if v is None:
        return "-"
    try:
        return f"{float(v):.{decimals}f}"
    except (ValueError, TypeError):
        return str(v)


def generate_energy_report_pdf(report_data: dict) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    title_s, h2_s, normal_s = _styles()
    elements: list = []

    year = report_data.get("year", "")
    month = report_data.get("month", "")
    pue_trend = report_data.get("pue_trend", {})
    cost = report_data.get("cost_comparison", {})
    saving = report_data.get("energy_saving", {})
    overview = report_data.get("energy_overview", {})
    current_cost = cost.get("current_month", {})

    # ---- 封面 ----
    elements.append(Spacer(1, 4 * cm))
    elements.append(Paragraph(f"算力中心月度能效报告", title_s))
    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph(f"报告周期: {year}年{month}月", normal_s))
    elements.append(Paragraph(f"生成时间: {report_data.get('generated_at', '')}", normal_s))
    elements.append(Spacer(1, 1 * cm))

    # 关键指标
    elements.append(Paragraph("关键指标概览", h2_s))
    summary_data = [
        ["指标", "数值"],
        ["PUE均值", _fmt(pue_trend.get("month_avg_pue", 0), 4)],
        ["总能耗(kWh)", _fmt(overview.get("total_energy", 0))],
        ["总电费(元)", _fmt(current_cost.get("total_cost", 0))],
        ["节能金额(元)", _fmt(saving.get("total_saving_cost", 0))],
    ]
    elements.append(_table(summary_data, col_widths=[6 * cm, 6 * cm]))
    elements.append(PageBreak())

    # ---- PUE 趋势 ----
    elements.append(Paragraph("PUE 趋势", h2_s))
    pue_rows = [["日期", "平均PUE", "最小PUE", "最大PUE"]]
    for v in pue_trend.get("daily_values", []):
        pue_rows.append([
            str(v.get("date", "")),
            _fmt(v.get("avg_pue", 0), 4),
            _fmt(v.get("min_pue", 0), 4),
            _fmt(v.get("max_pue", 0), 4),
        ])
    if len(pue_rows) > 1:
        elements.append(_table(pue_rows))
    else:
        elements.append(Paragraph("暂无数据", normal_s))
    elements.append(Spacer(1, 0.5 * cm))

    # ---- 电费对比 ----
    elements.append(Paragraph("电费对比", h2_s))
    lm = cost.get("last_month", {})
    ly = cost.get("last_year_month", {})
    cost_rows = [["项目", "本月", "上月", "去年同月"]]
    for label, key in [("总电费", "total_cost"), ("峰时电费", "peak_cost"),
                       ("平时电费", "normal_cost"), ("谷时电费", "valley_cost"),
                       ("总电量", "total_energy"), ("峰时电量", "peak_energy"),
                       ("平时电量", "normal_energy"), ("谷时电量", "valley_energy")]:
        cost_rows.append([label, _fmt(current_cost.get(key, 0)),
                          _fmt(lm.get(key, 0)), _fmt(ly.get(key, 0))])
    elements.append(_table(cost_rows))
    elements.append(PageBreak())

    # ---- 节能成果 ----
    elements.append(Paragraph("节能成果", h2_s))
    cat_map = {1: "电费结构优化", 2: "设备运行优化", 3: "设备改造升级", 4: "综合能效提升"}
    saving_rows = [["方案名称", "类别", "节能(kWh)", "节省费用(元)", "达成率(%)"]]
    for item in saving.get("details", []):
        saving_rows.append([
            str(item.get("title", "")),
            cat_map.get(item.get("category"), ""),
            _fmt(item.get("saving_kwh", 0)),
            _fmt(item.get("saving_cost", 0)),
            _fmt(item.get("achievement_rate")),
        ])
    if len(saving_rows) > 1:
        elements.append(_table(saving_rows))
    else:
        elements.append(Paragraph("暂无数据", normal_s))
    elements.append(Spacer(1, 0.5 * cm))

    # ---- 每日能耗 ----
    elements.append(Paragraph("每日能耗", h2_s))
    daily_rows = [["日期", "总能耗(kWh)"]]
    for d in overview.get("daily_energy", []):
        daily_rows.append([str(d.get("date", "")), _fmt(d.get("total_energy", 0))])
    if len(daily_rows) > 1:
        elements.append(_table(daily_rows, col_widths=[6 * cm, 6 * cm]))
    else:
        elements.append(Paragraph("暂无数据", normal_s))

    # ---- 页脚 ----
    elements.append(Spacer(1, 2 * cm))
    elements.append(Paragraph("— 报告结束 —", ParagraphStyle(
        "Footer", parent=normal_s, alignment=1, textColor=colors.grey)))

    doc.build(elements)
    buffer.seek(0)
    return buffer
