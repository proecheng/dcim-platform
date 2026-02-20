"""
PDF 报表生成服务
使用 reportlab 生成中文 PDF 报表
"""

import io
from datetime import datetime
from typing import Dict, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# 注册中文字体
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


def generate_report_pdf(report_data: Dict[str, Any], report_name: str) -> io.BytesIO:
    """
    生成报表 PDF

    Args:
        report_data: 报表数据，包含 title, period, summary, points, alarms 等
        report_name: 报表名称

    Returns:
        BytesIO: PDF 文件流
    """
    buffer = io.BytesIO()

    # 创建 PDF 文档
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm
    )

    # 样式定义
    styles = getSampleStyleSheet()

    # 中文样式
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontName="STSong-Light",
        fontSize=20,
        alignment=1,  # 居中
        spaceAfter=30,
    )

    heading2_style = ParagraphStyle(
        "CustomHeading2", parent=styles["Heading2"], fontName="STSong-Light", fontSize=14, spaceAfter=12, spaceBefore=12
    )

    normal_style = ParagraphStyle(
        "CustomNormal", parent=styles["Normal"], fontName="STSong-Light", fontSize=10, leading=14
    )

    # 构建 PDF 内容
    elements = []

    # 标题
    title = report_data.get("title", "数据报表")
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 0.5 * cm))

    # 报表信息
    period = report_data.get("period", "")
    if period:
        elements.append(Paragraph(f"统计周期：{period}", normal_style))

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elements.append(Paragraph(f"生成时间：{generated_at}", normal_style))
    elements.append(Spacer(1, 1 * cm))

    # 摘要统计
    summary = report_data.get("summary", {})
    if summary:
        elements.append(Paragraph("一、统计摘要", heading2_style))

        summary_data = []
        for key, value in summary.items():
            summary_data.append([key, str(value)])

        if summary_data:
            summary_table = Table(summary_data, colWidths=[6 * cm, 8 * cm])
            summary_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            elements.append(summary_table)
            elements.append(Spacer(1, 0.5 * cm))

    # 点位统计
    points = report_data.get("points", [])
    if points:
        elements.append(Paragraph("二、点位统计", heading2_style))

        # 表头
        point_headers = ["点位编码", "点位名称", "单位", "最小值", "最大值", "平均值", "数据条数"]
        point_data = [point_headers]

        # 数据行
        for point in points:
            point_data.append(
                [
                    point.get("code", ""),
                    point.get("name", ""),
                    point.get("unit", ""),
                    str(point.get("min", "-")),
                    str(point.get("max", "-")),
                    str(point.get("avg", "-")),
                    str(point.get("count", 0)),
                ]
            )

        point_table = Table(point_data, repeatRows=1)
        point_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
                ]
            )
        )
        elements.append(point_table)
        elements.append(Spacer(1, 0.5 * cm))

    # 告警统计
    alarms = report_data.get("alarms", {})
    if alarms:
        elements.append(Paragraph("三、告警统计", heading2_style))

        alarm_data = []
        for level, count in alarms.items():
            alarm_data.append([level, str(count)])

        if alarm_data:
            alarm_headers = ["告警级别", "数量"]
            alarm_data.insert(0, alarm_headers)

            alarm_table = Table(alarm_data, colWidths=[6 * cm, 8 * cm])
            alarm_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C5504B")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            elements.append(alarm_table)

    # 页脚
    elements.append(Spacer(1, 2 * cm))
    elements.append(
        Paragraph("— 报表结束 —", ParagraphStyle("Footer", parent=normal_style, alignment=1, textColor=colors.grey))
    )

    # 生成 PDF
    doc.build(elements)
    buffer.seek(0)

    return buffer


def generate_daily_report_pdf(report_data: Dict[str, Any]) -> io.BytesIO:
    """
    生成日报 PDF

    Args:
        report_data: 日报数据

    Returns:
        BytesIO: PDF 文件流
    """
    return generate_report_pdf(report_data, report_data.get("title", "日报"))


def generate_weekly_report_pdf(report_data: Dict[str, Any]) -> io.BytesIO:
    """
    生成周报 PDF

    Args:
        report_data: 周报数据

    Returns:
        BytesIO: PDF 文件流
    """
    return generate_report_pdf(report_data, report_data.get("title", "周报"))


def generate_monthly_report_pdf(report_data: Dict[str, Any]) -> io.BytesIO:
    """
    生成月报 PDF

    Args:
        report_data: 月报数据

    Returns:
        BytesIO: PDF 文件流
    """
    return generate_report_pdf(report_data, report_data.get("title", "月报"))
