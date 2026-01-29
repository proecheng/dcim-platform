const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, TableOfContents, HeadingLevel,
  BorderStyle, WidthType, ShadingType, VerticalAlign, PageNumber, PageBreak, ImageRun } = require("docx");

const COLOR = { primary: "1A5276", accent: "2980B9", dark: "2C3E50", text: "333333", light: "F2F7FB", headerBg: "D5E8F0", white: "FFFFFF", border: "BBBBBB" };
const tableBorder = { style: BorderStyle.SINGLE, size: 1, color: COLOR.border };
const cellBorders = { top: tableBorder, bottom: tableBorder, left: tableBorder, right: tableBorder };

function hCell(text, width) {
  return new TableCell({
    borders: cellBorders, width: { size: width, type: WidthType.DXA },
    shading: { fill: COLOR.headerBg, type: ShadingType.CLEAR }, verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text, bold: true, size: 21, font: "Microsoft YaHei" })] })]
  });
}
function dCell(text, width, opts = {}) {
  return new TableCell({
    borders: cellBorders, width: { size: width, type: WidthType.DXA },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({ alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT, spacing: { before: 40, after: 40 },
      children: [new TextRun({ text, size: 20, font: "Microsoft YaHei", ...opts })] })]
  });
}

function makeTable(headers, rows, widths) {
  const cw = widths || headers.map(() => Math.floor(9360 / headers.length));
  return new Table({
    columnWidths: cw,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, i) => hCell(h, cw[i])) }),
      ...rows.map(row => new TableRow({ children: row.map((c, i) => dCell(c, cw[i])) }))
    ]
  });
}

function h1(text) { return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 200 }, children: [new TextRun({ text })] }); }
function h2(text) { return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 160 }, children: [new TextRun({ text })] }); }
function h3(text) { return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 120 }, children: [new TextRun({ text })] }); }
function p(text, opts = {}) { return new Paragraph({ spacing: { before: 60, after: 60 }, indent: opts.indent ? { left: 360 } : undefined, children: [new TextRun({ text, size: 21, font: "Microsoft YaHei", ...opts })] }); }
function bp(text) { return new Paragraph({ numbering: { reference: "bullet-list", level: 0 }, spacing: { before: 40, after: 40 }, children: [new TextRun({ text, size: 21, font: "Microsoft YaHei" })] }); }
function boldP(label, value) { return new Paragraph({ spacing: { before: 60, after: 60 }, children: [new TextRun({ text: label, bold: true, size: 21, font: "Microsoft YaHei" }), new TextRun({ text: value, size: 21, font: "Microsoft YaHei" })] }); }
function emptyLine() { return new Paragraph({ spacing: { before: 80, after: 80 }, children: [] }); }
function pb() { return new Paragraph({ children: [new PageBreak()] }); }

// Image helper function
function img(filename, caption) {
  const imgPath = `D:/mytest1/screenshots/${filename}`;
  const imgData = fs.readFileSync(imgPath);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 200, after: 100 },
      children: [
        new ImageRun({
          type: "png",
          data: imgData,
          transformation: { width: 550, height: 310 },
          altText: { title: caption, description: caption, name: filename }
        })
      ]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 60, after: 200 },
      children: [new TextRun({ text: caption, size: 18, italics: true, color: "666666", font: "Microsoft YaHei" })]
    })
  ];
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Microsoft YaHei", size: 21, color: COLOR.text } } },
    paragraphStyles: [
      { id: "Title", name: "Title", basedOn: "Normal", run: { size: 52, bold: true, color: COLOR.primary, font: "Microsoft YaHei" }, paragraph: { spacing: { before: 240, after: 120 }, alignment: AlignmentType.CENTER } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 32, bold: true, color: COLOR.primary, font: "Microsoft YaHei" }, paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 26, bold: true, color: COLOR.dark, font: "Microsoft YaHei" }, paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 23, bold: true, color: COLOR.accent, font: "Microsoft YaHei" }, paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullet-list", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [
    // ========== 封面 ==========
    {
      properties: {
        page: { margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } }
      },
      children: [
        emptyLine(), emptyLine(), emptyLine(), emptyLine(), emptyLine(), emptyLine(), emptyLine(),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", size: 24, color: COLOR.accent, font: "Microsoft YaHei" })] }),
        emptyLine(),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 }, children: [new TextRun({ text: "算力中心智能监控系统", size: 56, bold: true, color: COLOR.primary, font: "Microsoft YaHei" })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 }, children: [new TextRun({ text: "（DCIM）", size: 40, bold: true, color: COLOR.accent, font: "Microsoft YaHei" })] }),
        emptyLine(),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: "用 户 使 用 手 册", size: 44, bold: true, color: COLOR.dark, font: "Microsoft YaHei" })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", size: 24, color: COLOR.accent, font: "Microsoft YaHei" })] }),
        emptyLine(), emptyLine(), emptyLine(),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: "版本：V2.1.0", size: 24, color: COLOR.text, font: "Microsoft YaHei" })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: "发布日期：2026年1月13日", size: 24, color: COLOR.text, font: "Microsoft YaHei" })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: "文档密级：内部公开", size: 24, color: COLOR.text, font: "Microsoft YaHei" })] }),
      ]
    },
    // ========== 目录和正文 ==========
    {
      properties: { page: { margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
      headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "算力中心智能监控系统 - 用户手册 V2.1", size: 16, color: "999999", font: "Microsoft YaHei", italics: true })] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "第 ", size: 18, font: "Microsoft YaHei" }), new TextRun({ children: [PageNumber.CURRENT], size: 18, font: "Microsoft YaHei" }), new TextRun({ text: " 页 / 共 ", size: 18, font: "Microsoft YaHei" }), new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, font: "Microsoft YaHei" }), new TextRun({ text: " 页", size: 18, font: "Microsoft YaHei" })] })] }) },
      children: [
        h1("目录"),
        new TableOfContents("目录", { hyperlink: true, headingStyleRange: "1-3" }),
        pb(),

        // ========== 第一章 系统概述 ==========
        h1("第一章  系统概述"),
        h2("1.1 系统简介"),
        p("算力中心智能监控系统（DCIM，Data Center Infrastructure Management）是一套专业的数据中心基础设施管理平台，为数据中心运维团队提供全方位的机房动力环境监控、设备管理、告警管理、历史数据分析和用电管理等功能。"),
        p("系统采用 B/S 架构，用户通过浏览器即可访问所有功能，无需安装客户端软件。系统支持实时监控、多级告警、数据分析、节能优化等核心能力，帮助运维人员高效管理数据中心基础设施。"),

        h2("1.2 系统架构"),
        p("系统采用前后端分离的现代 Web 架构，由以下三层组成："),
        makeTable(["层级", "技术栈", "说明"], [
          ["前端展示层", "Vue 3 + TypeScript + Element Plus", "提供用户交互界面，支持 ECharts 图表和 Three.js 3D 大屏"],
          ["后端服务层", "FastAPI + SQLAlchemy + Pydantic", "提供 RESTful API 和 WebSocket 实时推送服务"],
          ["数据存储层", "SQLite（支持升级到 PostgreSQL）", "存储设备数据、监控点位、告警记录、历史数据等"],
        ], [2200, 3800, 3360]),

        h2("1.3 主要功能"),
        makeTable(["功能模块", "说明"], [
          ["监控仪表盘", "实时展示机房环境状态、设备运行情况、告警统计概览"],
          ["点位管理", "支持 AI/DI/AO/DO 四种点位类型，最多 100 个监控点位"],
          ["告警管理", "多级告警（紧急/重要/次要/提示）、声音提醒、实时推送"],
          ["历史数据", "多维度数据查询、趋势分析、数据导出"],
          ["用电管理（V2.1）", "PUE 实时监测、能耗统计、节能建议、配电拓扑"],
          ["系统设置", "阈值配置、用户管理、系统日志、授权信息"],
        ], [2800, 6560]),
        pb(),

        // ========== 第二章 系统安装与启动 ==========
        h1("第二章  系统安装与启动"),
        h2("2.1 环境要求"),
        makeTable(["环境", "版本要求", "说明"], [
          ["Python", "3.9 或更高", "后端运行环境"],
          ["Node.js", "18 或更高", "前端构建工具"],
          ["npm 或 yarn", "最新稳定版", "前端包管理器"],
          ["浏览器", "Chrome 90+ / Firefox 88+ / Edge 90+", "客户端访问"],
        ], [2000, 3360, 4000]),

        h2("2.2 启动方式"),
        h3("方式一：一键启动（推荐）"),
        boldP("Windows 系统：", "双击 start.bat 文件"),
        bp("系统自动检查 Python 和 Node.js 环境"),
        bp("自动清理占用的端口（8080、3000）"),
        bp("检查并安装后端依赖"),
        bp("首次启动自动初始化数据库"),
        bp("依次启动后端和前端服务"),
        bp("自动打开浏览器访问系统"),

        h3("方式二：手动启动"),
        p("启动后端服务："),
        bp("进入 backend 目录"),
        bp("创建并激活 Python 虚拟环境：python -m venv .venv"),
        bp("安装依赖：pip install -r requirements.txt"),
        bp("启动服务：uvicorn app.main:app --reload --host 0.0.0.0 --port 8080"),
        emptyLine(),
        p("启动前端服务："),
        bp("进入 frontend 目录"),
        bp("安装依赖：npm install"),
        bp("启动服务：npm run dev"),

        h2("2.3 访问地址"),
        makeTable(["服务", "访问地址", "说明"], [
          ["前端界面", "http://localhost:3000", "用户操作界面"],
          ["后端 API", "http://localhost:8080", "API 服务端口"],
          ["API 文档", "http://localhost:8080/docs", "Swagger 交互式接口文档"],
        ], [2000, 3800, 3560]),
        pb(),

        // ========== 第三章 登录与账户管理 ==========
        h1("第三章  登录与账户管理"),
        h2("3.1 默认账户"),
        makeTable(["用户名", "密码", "角色", "权限范围"], [
          ["admin", "admin123", "管理员", "所有功能，包括用户管理和系统配置"],
        ], [1800, 2000, 1800, 3760]),
        p("注意：首次登录后建议立即修改默认密码，确保系统安全。", { bold: true, color: "CC0000" }),

        h2("3.2 登录步骤"),
        bp("打开浏览器，在地址栏输入系统访问地址"),
        bp("在登录页面输入用户名和密码"),
        bp('点击【登录】按钮进入系统'),
        bp("系统将自动跳转到监控仪表盘首页"),

        h2("3.3 修改密码"),
        bp("点击页面右上角的用户头像"),
        bp('在下拉菜单中选择【修改密码】'),
        bp("输入当前密码和新密码（至少 8 位字符）"),
        bp('确认新密码后点击【保存】'),
        pb(),

        // ========== 第四章 监控仪表盘 ==========
        h1("第四章  监控仪表盘"),
        p("监控仪表盘是系统首页，提供机房整体运行状态的实时概览，便于运维人员快速掌握全局信息。"),
        ...img("01_dashboard.png", "图 4-1 监控仪表盘界面"),

        h2("4.1 统计卡片"),
        p("页面顶部展示四个统计卡片，显示关键运行指标："),
        makeTable(["卡片名称", "说明", "正常状态"], [
          ["监控点位", "系统中已配置的总点位数量", "显示总数"],
          ["正常点位", "当前运行正常的点位数量", "数量越多越好"],
          ["告警点位", "当前处于告警状态的点位数量", "为 0 表示无异常"],
          ["离线点位", "失去通讯的点位数量", "为 0 表示全部在线"],
        ], [2200, 4360, 2800]),

        h2("4.2 实时数据表格"),
        p("显示所有监控点位的实时数据，包含以下字段："),
        bp("点位编码：唯一标识符（如 A1_TH_AI_001）"),
        bp("点位名称：易读名称（如 A1区温度）"),
        bp("类型：AI / DI / AO / DO"),
        bp("当前值：实时数据及单位"),
        bp("状态：正常（绿色）/ 告警（红色）/ 离线（灰色）"),
        bp("更新时间：数据最后更新时间"),

        h2("4.3 最新告警"),
        p("显示最近的活动告警列表，包括告警级别、告警点位、告警信息和告警时间。点击告警条目可跳转至告警详情页面。"),

        h2("4.4 数据刷新"),
        bp("系统每 10 秒自动刷新实时数据"),
        bp("WebSocket 实时推送告警信息"),
        bp('可点击页面【刷新】按钮手动刷新数据'),
        pb(),

        // ========== 第五章 点位管理 ==========
        h1("第五章  点位管理"),
        p("点位是监控系统的基本单元，代表一个传感器或控制对象。系统最多支持 100 个监控点位。"),
        ...img("02_devices.png", "图 5-1 点位管理界面"),

        h2("5.1 点位类型"),
        makeTable(["类型", "全称", "说明", "应用示例"], [
          ["AI", "模拟量输入", "采集连续变化的模拟信号", "温度、湿度、电压、电流"],
          ["DI", "开关量输入", "采集开/关两种状态信号", "门禁状态、设备运行状态"],
          ["AO", "模拟量输出", "输出连续变化的控制信号", "温度设定值、风速调节"],
          ["DO", "开关量输出", "输出开/关控制指令", "设备启停控制"],
        ], [1200, 1800, 3160, 3200]),

        h2("5.2 查看点位列表"),
        bp('点击左侧导航菜单【点位管理】进入页面'),
        bp("使用顶部筛选栏按类型（AI/DI/AO/DO）筛选"),
        bp("使用搜索框搜索点位名称或编码"),
        bp("点击列表中的点位可查看详细信息"),

        h2("5.3 点位编码规则"),
        p("编码格式：{区域}_{设备类型}_{点位类型}_{序号}"),
        makeTable(["编码示例", "区域", "设备类型", "点位类型", "序号"], [
          ["A1_TH_AI_001", "A1区", "温湿度传感器(TH)", "AI(模拟量输入)", "001"],
          ["A1_UPS_DI_001", "A1区", "UPS", "DI(开关量输入)", "001"],
          ["B2_AC_AO_002", "B2区", "精密空调(AC)", "AO(模拟量输出)", "002"],
        ], [2200, 1200, 2360, 2200, 1400]),
        pb(),

        // ========== 第六章 告警管理 ==========
        h1("第六章  告警管理"),
        p("告警管理帮助运维人员及时发现和处理机房异常情况，支持多级告警和声音提醒。"),
        ...img("03_alarms.png", "图 6-1 告警管理界面"),

        h2("6.1 告警级别"),
        makeTable(["级别", "标识颜色", "说明", "建议响应时间"], [
          ["紧急 (Critical)", "红色", "严重影响系统运行的异常", "立即处理"],
          ["重要 (Major)", "橙色", "影响部分功能的异常", "30 分钟内"],
          ["次要 (Minor)", "蓝色", "潜在问题或轻微异常", "2 小时内"],
          ["提示 (Info)", "灰色", "信息通知，无需紧急处理", "可延后处理"],
        ], [2200, 1600, 3160, 2400]),

        h2("6.2 查看告警"),
        bp('点击左侧导航菜单【告警管理】进入页面'),
        bp("默认显示当前活动告警列表"),
        bp('通过顶部标签切换查看【已确认】和【已解决】告警'),
        bp("支持按告警级别、时间范围、点位名称筛选"),

        h2("6.3 处理告警"),
        h3("确认告警"),
        bp("选择需要处理的告警记录"),
        bp('点击【确认】按钮'),
        bp("输入确认备注（如：已查看现场，正在排查）"),
        bp('确认后告警状态变为【已确认】'),
        h3("解决告警"),
        bp("选择已确认的告警记录"),
        bp('点击【解决】按钮'),
        bp("输入处理结果（如：已更换传感器，恢复正常）"),
        bp('解决后告警状态变为【已解决】'),
        pb(),

        // ========== 第七章 历史数据查询 ==========
        h1("第七章  历史数据查询"),
        p("历史数据查询用于对监控数据进行回溯分析和趋势研判，支持多维度查询和数据导出。"),
        ...img("04_history.png", "图 7-1 历史数据查询界面"),

        h2("7.1 查询条件"),
        bp("选择查询点位：从点位列表中选择一个或多个点位"),
        bp("设置时间范围：选择查询的开始时间和结束时间"),
        bp("选择数据粒度：原始数据 / 分钟汇总 / 小时汇总 / 日汇总"),

        h2("7.2 查看结果"),
        bp("趋势图表：折线图或柱状图展示数据变化趋势"),
        bp("统计信息：最大值、最小值、平均值、标准差、变化率"),
        bp("数据表格：按时间序列展示详细数据记录"),

        h2("7.3 导出数据"),
        p("支持将查询结果导出为以下格式："),
        makeTable(["格式", "扩展名", "适用场景"], [
          ["Excel", ".xlsx", "数据分析、报表制作"],
          ["CSV", ".csv", "通用数据交换、批量导入"],
          ["PDF", ".pdf", "打印、归档"],
          ["JSON", ".json", "程序接口、数据对接"],
        ], [2000, 2000, 5360]),
        pb(),

        // ========== 第八章 用电管理 ==========
        h1("第八章  用电管理（V2.1 新功能）"),
        p("用电管理模块是 V2.1 版本新增的核心功能，帮助管理者全面掌握数据中心能耗状况，实现精细化用电管理和节能优化。"),
        ...img("05_energy_monitor.png", "图 8-1 用电监控界面"),

        h2("8.1 用电监控"),
        h3("PUE 监控"),
        p("PUE（Power Usage Effectiveness，电源使用效率）是衡量数据中心能效的关键指标。"),
        boldP("计算公式：", "PUE = 总功率 / IT 负载功率"),
        makeTable(["PUE 范围", "等级", "说明"], [
          ["1.0", "理想值", "不可能达到，所有电力全部用于 IT 设备"],
          ["1.2 ~ 1.5", "优秀", "数据中心能效表现优异"],
          ["1.5 ~ 2.0", "一般", "存在一定优化空间"],
          ["> 2.0", "需改进", "能效较低，应重点关注优化"],
        ], [2000, 1600, 5760]),

        h3("功能特性"),
        bp("实时 PUE 仪表盘：大号仪表盘实时显示当前 PUE 值"),
        bp("PUE 趋势图：支持 24 小时、30 天、12 周、12 个月多维度趋势分析"),
        bp("功率分布：查看 IT 负载、制冷系统、UPS 损耗、照明及其他功率占比"),

        h2("8.2 能耗统计"),
        bp("日能耗统计：总电量、总电费、平均功率、平均 PUE"),
        bp("月能耗统计：本月总电量、总电费、每日趋势"),
        bp("同环比分析：与昨天、上周、上月数据对比"),

        h3("电价配置"),
        p("系统支持五档分时电价配置："),
        makeTable(["电价类型", "默认价格（元/kWh）", "默认时段", "说明"], [
          ["尖峰", "1.5", "根据地区政策配置", "用电最高峰时段"],
          ["峰时", "1.2", "8:00 ~ 22:00", "日间高峰时段"],
          ["平时", "0.8", "其他时段", "正常用电时段"],
          ["谷时", "0.4", "23:00 ~ 7:00", "夜间低谷时段"],
          ["深谷", "0.2", "根据地区政策配置", "用电最低谷时段"],
        ], [1600, 2400, 2760, 2600]),

        h2("8.3 节能建议"),
        bp("系统自动分析用电数据，生成节能建议"),
        bp("建议类型：温度优化、负载均衡、时段调整、设备更换、能效提升"),
        bp("建议优先级：高（红色）、中（橙色）、低（蓝色）"),
        bp("节能效果跟踪：对比预期节能与实际节能数据"),
        pb(),

        // ========== 第九章 系统设置 ==========
        h1("第九章  系统设置"),
        ...img("06_settings.png", "图 9-1 系统设置界面"),

        h2("9.1 阈值配置"),
        p("阈值用于定义告警触发条件，当监控数据超出设定范围时自动产生告警。"),
        bp('进入【系统设置】→【阈值配置】'),
        bp('点击【新增阈值】'),
        bp("选择关联点位，设置上限值、下限值、告警级别、延迟时间"),
        bp("保存配置后立即生效"),

        h2("9.2 用户管理"),
        makeTable(["角色", "权限范围"], [
          ["管理员 (Admin)", "所有功能，包括用户管理和系统配置"],
          ["操作员 (Operator)", "查看数据、操作设备、确认和处理告警"],
          ["观察员 (Viewer)", "仅可查看数据和报表，无操作权限"],
        ], [3000, 6360]),

        h2("9.3 系统日志"),
        makeTable(["日志类型", "说明"], [
          ["操作日志", "记录用户操作行为（登录、修改、删除等）"],
          ["系统日志", "记录系统事件（启动、错误、警告等）"],
          ["通讯日志", "记录 API 调用和通讯记录"],
        ], [2800, 6560]),

        h2("9.4 授权信息"),
        bp("许可证类型：基础版 / 标准版 / 企业版"),
        bp("点位限制：当前许可最多可监控的点位数"),
        bp("已用点位：当前已使用的点位数量"),
        bp("到期时间：许可证有效期"),
        pb(),

        // ========== 第十章 常见问题 ==========
        h1("第十章  常见问题（FAQ）"),
        h2("Q1：无法登录系统"),
        bp("确认用户名和密码正确（区分大小写）"),
        bp("检查用户账户是否被禁用（联系管理员）"),
        bp("尝试重置密码"),
        bp("清除浏览器缓存后重试"),

        h2("Q2：实时数据不更新"),
        bp("检查网络连接是否正常"),
        bp("刷新浏览器页面（F5 或 Ctrl+R）"),
        bp("检查后端服务是否正常运行"),

        h2("Q3：告警没有声音提醒"),
        bp("检查浏览器是否允许页面播放声音"),
        bp("检查系统音量设置"),
        bp("首次访问页面时需要点击页面任意位置激活音频权限"),

        h2("Q4：PUE 显示异常值"),
        bp("当 IT 负载功率为 0 时 PUE 无法正确计算"),
        bp("检查功率传感器是否正常工作"),
        bp("查看实时功率数据是否在合理范围内"),

        h2("Q5：忘记管理员密码"),
        bp('联系其他管理员在【用户管理】中重置密码'),
        bp("如果是唯一管理员，需要通过数据库直接修改密码"),
        pb(),

        // ========== 附录 ==========
        h1("附录"),
        h2("附录 A：快捷键"),
        makeTable(["快捷键", "功能说明"], [
          ["Ctrl + R / F5", "刷新当前页面"],
          ["Ctrl + S", "保存表单数据（编辑状态下）"],
          ["Esc", "关闭弹出对话框"],
          ["F12", "打开浏览器开发者工具（调试用）"],
        ], [3000, 6360]),

        h2("附录 B：浏览器兼容性"),
        makeTable(["浏览器", "最低版本", "推荐版本"], [
          ["Google Chrome", "90+", "最新版（推荐）"],
          ["Mozilla Firefox", "88+", "最新版"],
          ["Microsoft Edge", "90+", "最新版"],
          ["Apple Safari", "14+", "最新版"],
        ], [3120, 3120, 3120]),
        p("注意：系统不支持 Internet Explorer 浏览器。", { bold: true, color: "CC0000" }),

        h2("附录 C：技术支持"),
        bp("系统文档：查阅项目 README.md 文件"),
        bp("API 文档：访问 http://localhost:8080/docs 查看接口说明"),
        bp("如遇技术问题，请联系系统管理员或技术支持团队"),
        emptyLine(), emptyLine(),
        new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "━━━━━━━━━━━  文档结束  ━━━━━━━━━━━", size: 22, color: COLOR.accent, font: "Microsoft YaHei" })] }),
        emptyLine(),
        new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "文档版本：V2.1.0  |  最后更新：2026-01-29  |  算力中心智能监控系统", size: 18, color: "999999", font: "Microsoft YaHei" })] }),
      ]
    }
  ]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("算力中心智能监控系统_用户手册_V2.1.docx", buffer);
  console.log("文档已生成: 算力中心智能监控系统_用户手册_V2.1.docx（含截图）");
});
