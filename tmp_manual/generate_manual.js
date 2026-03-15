const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  Header, Footer, AlignmentType, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType, PageNumber, PageBreak
} = require("docx");

const font = "Microsoft YaHei";
const C = { title: "1F3864", subtitle: "2E75B6", gray: "666666", text: "333333", white: "FFFFFF", headerBg: "4472C4", rowEven: "F2F7FB", border: "B4C6E7" };

function tr(text, opts = {}) {
  return new TextRun({ text, font, size: opts.size || 21, bold: opts.bold, color: opts.color || C.text });
}

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 200 },
    children: [tr(text, { bold: true, color: C.title, size: 32 })] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 160 },
    children: [tr(text, { bold: true, color: C.subtitle, size: 26 })] });
}
function h3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 120 },
    children: [tr(text, { bold: true, color: C.text, size: 24 })] });
}
function p(text, opts = {}) {
  return new Paragraph({ spacing: { before: 60, after: 60 }, alignment: opts.align,
    children: [tr(text, opts)] });
}
function bold(text) { return p(text, { bold: true }); }

function img(filename, widthInch = 6.5) {
  const ssDir = path.join(__dirname, '..', 'docs', 'screenshots');
  const fp = path.join(ssDir, filename);
  if (!fs.existsSync(fp)) return p(`[截图缺失: ${filename}]`);
  const data = fs.readFileSync(fp);
  const ext = filename.endsWith('.png') ? 'png' : 'jpg';
  // Calculate height proportionally (assume 16:9 screenshots at 1920x1080)
  const w = Math.round(widthInch * 96);
  const h = Math.round(w * 1080 / 1920);
  return new Paragraph({
    spacing: { before: 120, after: 120 },
    alignment: AlignmentType.CENTER,
    children: [new ImageRun({
      type: ext === 'png' ? 'png' : 'jpg',
      data, transformation: { width: w, height: h },
      altText: { title: filename, description: filename, name: filename },
    })],
  });
}

function caption(text) {
  return new Paragraph({
    spacing: { before: 40, after: 120 },
    alignment: AlignmentType.CENTER,
    children: [tr(text, { size: 18, color: C.gray })],
  });
}

// Helper: screenshot + caption
function sc(filename, captionText, width) {
  return [img(filename, width), caption(captionText)];
}

const cellBorder = { style: BorderStyle.SINGLE, size: 1, color: C.border };
const borders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };

function hCell(text, w) {
  return new TableCell({ width: { size: w, type: WidthType.DXA }, borders,
    shading: { fill: C.headerBg, type: ShadingType.CLEAR }, margins: cellMargins,
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [tr(text, { bold: true, color: C.white, size: 20 })] })] });
}
function dCell(text, w, opts = {}) {
  return new TableCell({ width: { size: w, type: WidthType.DXA }, borders, margins: cellMargins,
    shading: opts.bg ? { fill: opts.bg, type: ShadingType.CLEAR } : undefined,
    children: [new Paragraph({ children: [tr(text, { size: 20 })] })] });
}
function tbl(headers, rows, widths) {
  const tw = widths.reduce((a,b) => a+b, 0);
  return new Table({ width: { size: tw, type: WidthType.DXA }, columnWidths: widths,
    rows: [
      new TableRow({ children: headers.map((h,i) => hCell(h, widths[i])) }),
      ...rows.map((r, ri) => new TableRow({ children: r.map((c,ci) => dCell(c, widths[ci], { bg: ri%2===1?C.rowEven:undefined })) })),
    ],
  });
}

// =============== BUILD DOCUMENT ===============
const children = [];

// Title page
children.push(new Paragraph({ spacing: { before: 2400 } }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
  children: [tr("算力中心智能监控系统", { bold: true, color: C.title, size: 44 })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
  children: [tr("DCIM - Data Center Infrastructure Management", { size: 22, color: C.gray })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 },
  children: [tr("用户使用说明书", { bold: true, color: C.subtitle, size: 36 })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
  children: [tr("版本：V4.1.0", { size: 22, color: C.gray })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
  children: [tr("日期：2026年3月15日", { size: 22, color: C.gray })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
  children: [tr("密级：内部文档", { size: 22, color: C.gray })] }));

children.push(new Paragraph({ children: [new PageBreak()] }));

// Revision history
children.push(h1("修订记录"));
children.push(tbl(
  ["版本", "日期", "说明"],
  [
    ["V3.1.0", "2026-02-23", "初始版本，覆盖全部 65 个系统界面"],
    ["V4.1.0", "2026-03-15", "更新至 V4.1.0，新增智能诊断/预冷模型/VPP 等模块，更新全部截图"],
  ],
  [1500, 1800, 5726]
));
children.push(new Paragraph({ children: [new PageBreak()] }));

// Chapter 1
children.push(h1("第1章 系统概述"));
children.push(h2("1.1 系统简介"));
children.push(p("算力中心智能监控系统（DCIM）是一套面向数据中心基础设施的综合管理平台，旨在为运维团队提供全方位的可观测性与控制能力。系统涵盖从设备数据采集、实时监控、智能告警、能源管理、资产运维到 3D 数字孪生的完整功能链路。"));
children.push(p(""));
children.push(bold("核心能力："));
children.push(p("多协议设备采集：支持 Modbus TCP/RTU、SNMP v2c/v3、MQTT、HTTP/REST、BACnet/IP、OPC-UA 等主流工业协议"));
children.push(p("实时监控：涵盖供配电、制冷、环境、安防消防四大子系统，数据刷新延迟小于 1 秒"));
children.push(p("智能告警：4 级告警体系（提示/次要/重要/紧急），支持告警升级、风暴抑制、自动派单"));
children.push(p("能源管理：PUE 实时监控、五时段电价管理、6 种节能分析插件"));
children.push(p("智能诊断：故障树诊断引擎、概率自适应调参、误判分析报告、A/B 测试"));
children.push(p("制冷优化：RC 热动力学模型、谷时预冷调度、ASHRAE 温度约束、自动回退保护"));
children.push(p("虚拟电厂：可调容量上报、调控指令执行、VPP 方案分析"));
children.push(p("3D 数字孪生：基于 Three.js 的机房三维模型、热力图、实时数据叠加"));

children.push(h2("1.2 技术架构"));
children.push(p("系统采用前后端分离的三层架构设计："));
children.push(p("前端层：Vue 3 + TypeScript + Element Plus + ECharts + Three.js"));
children.push(p("后端层：FastAPI + SQLAlchemy 2.0 (异步) + JWT 认证 + RBAC 权限 + WebSocket"));
children.push(p("数据层：SQLite (开发) / PostgreSQL + TimescaleDB (生产) + Redis + EMQX"));

children.push(h2("1.3 浏览器要求"));
children.push(p("Google Chrome 90+（推荐）、Microsoft Edge 90+、Mozilla Firefox 88+、Apple Safari 14+"));
children.push(p("建议屏幕分辨率 1920x1080 或更高。数字孪生大屏建议 4K 显示器。"));

children.push(h2("1.4 默认账户"));
children.push(p("用户名：admin，密码：admin123，角色：系统管理员（全部权限）"));
children.push(p("首次登录后请立即修改默认密码。"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// Chapter 2 - Installation (brief)
children.push(h1("第2章 安装与启动"));
children.push(h2("2.1 Windows 一键启动"));
children.push(p("双击项目根目录下的 start-smart.bat 即可自动启动后端和代理服务。"));
children.push(p("系统入口：http://localhost:3000"));
children.push(p("API 文档：http://localhost:8080/docs"));
children.push(h2("2.2 停止服务"));
children.push(p("双击 stop.bat 即可停止所有服务进程。"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// Chapter 3 - Login
children.push(h1("第3章 系统登录"));
children.push(p("访问系统地址后，显示登录页面。输入用户名和密码后点击「登录」按钮进入系统。"));
children.push(...sc("01-login.png", "图 3-1 系统登录页面"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// Chapter 4 - Dashboard
children.push(h1("第4章 综合概览"));
children.push(h2("4.1 仪表盘总览"));
children.push(p("登录后进入综合概览仪表盘，展示监控点位统计、实时功率、PUE 效率、需量状态、今日电费、节能建议等关键指标。"));
children.push(...sc("02-dashboard.png", "图 4-1 综合概览仪表盘（上半部分）"));
children.push(p("下方展示实时数据表格和最新告警列表："));
children.push(...sc("02-dashboard-bottom.png", "图 4-2 综合概览仪表盘（下半部分）"));
children.push(p("右上角可以展开用户菜单，进行个人设置或退出登录："));
children.push(...sc("56-user-dropdown.jpeg", "图 4-3 用户下拉菜单"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// Chapter 5 - Monitoring
children.push(h1("第5章 监控域"));

children.push(h2("5.1 供配电监控"));
children.push(h3("5.1.1 供配电总览"));
children.push(p("展示 UPS 数量、在线状态、告警数、电池组、配电柜、PDU 等关键统计，以及总负载和电池健康状况。"));
children.push(...sc("03-power-overview.png", "图 5-1 供配电总览"));

children.push(h3("5.1.2 UPS 监控"));
children.push(p("列出所有 UPS 设备的运行状态、输入/输出电压、负载率、电池状态等详细信息。"));
children.push(...sc("04-ups-monitor.png", "图 5-2 UPS 监控"));

children.push(h3("5.1.3 电池监控"));
children.push(p("展示电池组的 SOH（健康度）、SOC（充电状态）、温度等参数。"));
children.push(...sc("05-battery.png", "图 5-3 电池组监控"));

children.push(h3("5.1.4 机柜 PDU"));
children.push(p("机柜级配电单元监控，显示各机柜的功率、电流、负载率等。"));
children.push(...sc("06-pdu.png", "图 5-4 机柜 PDU 监控"));

children.push(h3("5.1.5 配电拓扑"));
children.push(p("可视化展示供配电系统的拓扑结构，从高压进线到末端机柜的完整配电路径。"));
children.push(...sc("07-power-topology.png", "图 5-5 配电拓扑"));

children.push(new Paragraph({ children: [new PageBreak()] }));

children.push(h2("5.2 制冷监控"));
children.push(h3("5.2.1 制冷总览"));
children.push(p("展示制冷设备总数、运行状态、送回风温度、群控状态等关键数据。"));
children.push(...sc("08-cooling-overview.jpeg", "图 5-6 制冷总览"));

children.push(h3("5.2.2 精密空调"));
children.push(p("列出所有精密空调设备的运行参数，包括设定温度、回风温度、送风温度、风速等。"));
children.push(...sc("09-cooling-indoor.jpeg", "图 5-7 精密空调监控"));

children.push(h3("5.2.3 冷通道"));
children.push(p("冷通道温湿度监控，确保 IT 设备进风温度在 ASHRAE 规范范围内。"));
children.push(...sc("10-cold-aisle.jpeg", "图 5-8 冷通道监控"));

children.push(h3("5.2.4 群控管理"));
children.push(p("制冷设备群控状态，支持联动群控和独立运行两种模式。"));
children.push(...sc("11-group-control.jpeg", "图 5-9 群控管理"));

children.push(new Paragraph({ children: [new PageBreak()] }));

children.push(h2("5.3 环境监控"));
children.push(h3("5.3.1 温湿度监控"));
children.push(p("实时展示各区域的温度和湿度数据，支持按区域/楼层筛选。"));
children.push(...sc("13-temp-humidity.jpeg", "图 5-10 温湿度监控"));

children.push(h3("5.3.2 漏水检测"));
children.push(p("漏水传感器状态监控，发现漏水时自动告警。"));
children.push(...sc("14-leak-detection.jpeg", "图 5-11 漏水检测"));

children.push(h2("5.4 安防消防"));
children.push(h3("5.4.1 安防总览"));
children.push(p("安防消防系统总览，展示门禁、视频监控、消防设备的运行状态。"));
children.push(...sc("15-security-overview.jpeg", "图 5-12 安防总览"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// Chapter 6 - Alarms
children.push(h1("第6章 告警中心"));
children.push(h2("6.1 告警记录"));
children.push(p("展示所有告警记录，支持按状态、级别、设备类型、数据来源筛选。可进行告警确认、批量处理等操作。"));
children.push(...sc("16-alarm-center.jpeg", "图 6-1 告警记录"));

children.push(h2("6.2 告警规则"));
children.push(p("管理告警触发规则，定义阈值条件和告警级别。"));
children.push(...sc("43-alarm-rules.jpeg", "图 6-2 告警规则"));

children.push(h2("6.3 告警屏蔽"));
children.push(p("配置告警屏蔽策略，在维护窗口期间临时屏蔽特定告警。"));
children.push(...sc("44-alarm-shield.jpeg", "图 6-3 告警屏蔽"));

children.push(h2("6.4 升级规则"));
children.push(p("配置告警升级链，超时未处理的告警自动升级通知更高级别负责人。"));
children.push(...sc("45-alarm-escalation.jpeg", "图 6-4 升级规则"));

children.push(h2("6.5 阈值规则"));
children.push(p("基于点位的阈值告警规则，支持多级阈值和持续时间条件。"));
children.push(...sc("46-alarm-threshold.jpeg", "图 6-5 阈值规则"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// Chapter 7 - Management
children.push(h1("第7章 管理域"));
children.push(h2("7.1 能效管理"));
children.push(h3("7.1.1 用电监控"));
children.push(p("实时展示总功率、IT 负载、制冷功率、PUE 值等能效指标。"));
children.push(...sc("17-energy-monitor.jpeg", "图 7-1 用电监控"));

children.push(h3("7.1.2 能耗统计"));
children.push(p("按日/周/月统计用电量和电费，支持分时段（峰/平/谷）分析。"));
children.push(...sc("18-energy-statistics.jpeg", "图 7-2 能耗统计"));

children.push(h3("7.1.3 节能分析"));
children.push(p("提供 6 种节能分析插件，识别节能机会和优化建议。"));
children.push(...sc("19-energy-analysis.jpeg", "图 7-3 节能分析"));

children.push(h3("7.1.4 负荷调节"));
children.push(p("负荷管理与需量控制，支持转移配置和削峰填谷策略。"));
children.push(...sc("20-load-regulation.jpeg", "图 7-4 负荷调节"));

children.push(h3("7.1.5 执行追踪"));
children.push(p("跟踪节能策略的执行状态和效果。"));
children.push(...sc("20b-execution.jpeg", "图 7-5 执行追踪"));

children.push(new Paragraph({ children: [new PageBreak()] }));

children.push(h2("7.2 资产与容量管理"));
children.push(h3("7.2.1 资产台账"));
children.push(p("设备资产的完整生命周期管理，包括基本信息、维保记录、变更历史。"));
children.push(...sc("21-assets-list.jpeg", "图 7-6 资产台账"));

children.push(h3("7.2.2 机柜管理"));
children.push(p("机柜 U 位可视化管理，直观展示设备安装位置和剩余空间。"));
children.push(...sc("22-cabinet-manage.jpeg", "图 7-7 机柜管理"));

children.push(h2("7.3 运维管理"));
children.push(h3("7.3.1 工单管理"));
children.push(p("工单的创建、分配、处理、关闭全流程管理。支持告警自动创建工单。"));
children.push(...sc("23-workorder.jpeg", "图 7-8 工单列表"));
children.push(p("点击「新建工单」打开工单创建对话框："));
children.push(...sc("42-workorder-create-dialog.jpeg", "图 7-9 新建工单对话框"));
children.push(p("告警工单规则标签页用于配置自动工单生成规则："));
children.push(...sc("54-workorder-auto-rules.jpeg", "图 7-10 告警工单规则"));
children.push(p("审批管理标签页展示工单审批流程："));
children.push(...sc("55-workorder-approval.jpeg", "图 7-11 工单审批管理"));

children.push(new Paragraph({ children: [new PageBreak()] }));

children.push(h3("7.3.2 巡检管理"));
children.push(p("巡检计划创建和巡检任务执行管理。"));
children.push(...sc("24-inspection.jpeg", "图 7-12 巡检管理"));
children.push(...sc("47-inspection-plans.jpeg", "图 7-13 巡检计划"));
children.push(...sc("48-inspection-tasks.jpeg", "图 7-14 巡检任务"));

children.push(h3("7.3.3 知识库"));
children.push(p("运维知识库，收集故障处理经验和操作指南。"));
children.push(...sc("25-knowledge.jpeg", "图 7-15 知识库"));
children.push(p("新建知识文章："));
children.push(...sc("53-knowledge-add.jpeg", "图 7-16 新建知识文章"));

children.push(h3("7.3.4 运维报表"));
children.push(p("运维数据分析报表，汇总工单、巡检、告警等统计数据。"));
children.push(...sc("25b-reports.jpeg", "图 7-17 运维报表"));

children.push(h2("7.4 虚拟电厂"));
children.push(h3("7.4.1 VPP 方案分析"));
children.push(p("虚拟电厂方案分析，评估数据中心参与电网需求响应的可行性和经济效益。"));
children.push(...sc("26-vpp-analysis.jpeg", "图 7-18 VPP 方案分析"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// Chapter 8 - Config
children.push(h1("第8章 配置域"));
children.push(h2("8.1 采集配置"));
children.push(h3("8.1.1 设备管理"));
children.push(p("管理所有被监控设备，支持添加、编辑、删除设备。"));
children.push(...sc("31-devices.jpeg", "图 8-1 设备管理"));
children.push(p("添加设备对话框："));
children.push(...sc("49-device-add-dialog.jpeg", "图 8-2 添加设备对话框"));

children.push(h3("8.1.2 点位管理"));
children.push(p("管理设备采集点位（AI/DI/AO/DO），配置量程、单位、采集频率等参数。"));
children.push(...sc("32-points.jpeg", "图 8-3 点位管理"));

children.push(h3("8.1.3 数据源管理"));
children.push(p("配置设备通信连接参数，支持 6 种工业协议。"));
children.push(...sc("33-datasources.jpeg", "图 8-4 数据源管理"));
children.push(p("添加数据源对话框："));
children.push(...sc("50-datasource-add-dialog.jpeg", "图 8-5 添加数据源对话框"));

children.push(h3("8.1.4 设备模板"));
children.push(p("预定义设备模板，快速批量创建同类设备和点位。"));
children.push(...sc("34-templates.jpeg", "图 8-6 设备模板管理"));

children.push(h3("8.1.5 网关管理"));
children.push(p("管理数据采集网关设备，监控网关在线状态和数据转发情况。"));
children.push(...sc("35-gateways.jpeg", "图 8-7 网关管理"));

children.push(h3("8.1.6 能源配置"));
children.push(p("配置电价策略、PUE 计算参数、需量管理等能源相关参数。"));
children.push(...sc("35b-energy-config.jpeg", "图 8-8 能源配置"));

children.push(new Paragraph({ children: [new PageBreak()] }));

children.push(h2("8.2 联动策略"));
children.push(p("配置事件驱动的自动化联动策略。"));
children.push(...sc("36-linkage.jpeg", "图 8-9 联动策略列表"));
children.push(p("创建联动策略："));
children.push(...sc("51-linkage-create-dialog.jpeg", "图 8-10 创建联动策略"));
children.push(p("联动执行记录："));
children.push(...sc("36b-execution-log.jpeg", "图 8-11 执行记录"));

children.push(h2("8.3 智能诊断"));
children.push(h3("8.3.1 诊断结果"));
children.push(p("展示故障树诊断引擎的分析结果，包括根因定位和置信度评分。"));
children.push(...sc("37-diagnosis-results.jpeg", "图 8-12 诊断结果"));

children.push(h3("8.3.2 诊断规则"));
children.push(p("管理诊断规则库，配置故障判定条件和推荐处置方案。"));
children.push(...sc("38-diagnosis-rules.jpeg", "图 8-13 诊断规则"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// Chapter 9 - System
children.push(h1("第9章 系统管理"));
children.push(h2("9.1 用户管理"));
children.push(p("管理系统用户账号，支持创建、编辑、禁用用户，分配角色（管理员/操作员/只读）。"));
children.push(...sc("27-user-manage.jpeg", "图 9-1 用户管理"));
children.push(p("新建用户对话框："));
children.push(...sc("40-user-create-dialog.jpeg", "图 9-2 新建用户对话框"));
children.push(p("编辑用户对话框："));
children.push(...sc("41-user-edit-dialog.jpeg", "图 9-3 编辑用户对话框"));

children.push(h2("9.2 站点管理"));
children.push(p("管理多个数据中心站点，配置站点基本信息和层级结构。"));
children.push(...sc("28-site-manage.jpeg", "图 9-4 站点管理"));
children.push(p("添加站点对话框："));
children.push(...sc("52-site-add-dialog.jpeg", "图 9-5 添加站点对话框"));

children.push(h2("9.3 审计日志"));
children.push(p("记录所有用户操作的审计日志，支持按时间、操作类型、用户筛选。"));
children.push(...sc("29-audit-log.jpeg", "图 9-6 审计日志"));

children.push(h2("9.4 系统设置"));
children.push(p("系统全局参数配置，包括模拟器开关、告警通知设置、数据保留策略等。"));
children.push(...sc("30-system-settings.jpeg", "图 9-7 系统设置"));

children.push(h2("9.5 智能选址"));
children.push(p("基于多维度评估模型的数据中心选址决策支持。"));
children.push(...sc("30b-site-selection.jpeg", "图 9-8 智能选址"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// Appendix
children.push(h1("附录A 常见问题解答"));
children.push(h2("A.1 登录失败"));
children.push(p("症状：登录时返回 500 Internal Server Error"));
children.push(p("原因：bcrypt 库版本 5.0+ 与 passlib 1.7.4 不兼容"));
children.push(p("解决：cd backend && .venv\\Scripts\\python.exe -m pip install \"bcrypt==4.0.1\""));

children.push(h2("A.2 端口被占用"));
children.push(p("运行 stop.bat 清理占用进程，或手动执行 taskkill /F /PID <PID>"));

children.push(h2("A.3 前端修改不生效"));
children.push(p("start-smart.bat 使用静态文件模式，修改前端后需要重新构建：cd frontend && npm run build"));
children.push(p("开发模式推荐使用 npm run dev（自动热更新）。"));

// Build
const doc = new Document({
  styles: {
    default: { document: { run: { font, size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font }, paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font }, paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font }, paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } },
    ],
  },
  sections: [{
    properties: {
      page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, right: 1200, bottom: 1440, left: 1200 } },
    },
    headers: {
      default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
        children: [tr("DCIM 用户使用说明书 V4.1.0", { size: 16, color: C.gray })] })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
        children: [tr("第 ", { size: 16, color: C.gray }), new TextRun({ children: [PageNumber.CURRENT], font, size: 16, color: C.gray }), tr(" 页", { size: 16, color: C.gray })] })] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("docs/DCIM系统用户使用说明书_V4.1.0.docx", buffer);
  console.log("Manual generated with " + children.length + " elements!");
});
