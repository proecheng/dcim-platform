const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType, PageNumber, PageBreak
} = require("docx");

// Colors
const C = {
  title: "1F3864",
  subtitle: "2E75B6",
  gray: "666666",
  text: "333333",
  white: "FFFFFF",
  headerBg: "4472C4",
  rowEven: "F2F7FB",
  greenBg: "E2EFDA",
  greenText: "548235",
  yellowBg: "FFF2CC",
  yellowText: "BF8F00",
  redBg: "FCE4EC",
  redText: "C62828",
  border: "B4C6E7",
};

const font = "Microsoft YaHei";
const bodySize = 21;
const headingColor = C.title;

function rp(opts = {}) {
  return {
    font, size: opts.size || bodySize,
    bold: opts.bold || false,
    color: opts.color || C.text,
    ...opts,
  };
}

function textRun(text, opts = {}) {
  return new TextRun({ text, ...rp(opts) });
}

function para(text, opts = {}) {
  return new Paragraph({
    spacing: { before: opts.before || 80, after: opts.after || 80 },
    alignment: opts.alignment,
    children: [textRun(text, opts)],
  });
}

const cellBorder = { style: BorderStyle.SINGLE, size: 1, color: C.border };
const borders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };

function headerCell(text, width) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders,
    shading: { fill: C.headerBg, type: ShadingType.CLEAR },
    margins: cellMargins,
    verticalAlign: "center",
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [textRun(text, { bold: true, color: C.white, size: 20 })] })],
  });
}

function dataCell(text, width, opts = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders,
    shading: opts.bg ? { fill: opts.bg, type: ShadingType.CLEAR } : undefined,
    margins: cellMargins,
    verticalAlign: "center",
    children: [new Paragraph({
      alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
      children: [textRun(text, { size: 20, color: opts.textColor || C.text, bold: opts.bold })],
    })],
  });
}

function statusCell(text, width) {
  const isComplete = text.includes("完成");
  const bg = isComplete ? C.greenBg : C.yellowBg;
  const tc = isComplete ? C.greenText : C.yellowText;
  return dataCell(text, width, { bg, textColor: tc, center: true, bold: true });
}

function makeTable(headers, rows, colWidths) {
  const totalW = colWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: totalW, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      new TableRow({ children: headers.map((h, i) => headerCell(h, colWidths[i])) }),
      ...rows.map((row, ri) =>
        new TableRow({
          children: row.map((cell, ci) => {
            if (typeof cell === "object" && cell._type === "status") {
              return statusCell(cell.text, colWidths[ci]);
            }
            return dataCell(typeof cell === "string" ? cell : cell.text, colWidths[ci], {
              bg: ri % 2 === 1 ? C.rowEven : undefined,
              center: cell.center,
              bold: cell.bold,
              textColor: cell.textColor,
            });
          }),
        })
      ),
    ],
  });
}

function heading1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 200 },
    children: [textRun(text, { bold: true, color: headingColor, size: 32 })],
  });
}

function heading2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 160 },
    children: [textRun(text, { bold: true, color: C.subtitle, size: 26 })],
  });
}

function st(text) { return { _type: "status", text }; }

// ============ BUILD DOCUMENT ============

const children = [];

// Title page
children.push(new Paragraph({ spacing: { before: 3000 } }));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 200 },
  children: [textRun("DCIM 算力中心智能监控系统", { bold: true, color: C.title, size: 44 })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 600 },
  children: [textRun("项目进展汇报", { bold: true, color: C.subtitle, size: 36 })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { after: 100 },
  children: [textRun("版本：V4.1.0", { color: C.gray, size: 24 })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { after: 100 },
  children: [textRun("日期：2026 年 3 月 15 日", { color: C.gray, size: 24 })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { after: 100 },
  children: [textRun("编制：proecheng", { color: C.gray, size: 24 })],
}));
children.push(new Paragraph({ children: [new PageBreak()] }));

// 一、整体进展
children.push(heading1("一、整体进展"));
children.push(para("项目已完成全部规划功能的开发与智能诊断系统扩展，当前版本 V4.1.0。本周重点完成了制冷功率转移（预冷 TCL 模型）五大 Epic 的全部实施、对抗性代码审查修复、以及 E2E API 测试补充。"));
children.push(para(""));

children.push(makeTable(
  ["指标", "数据"],
  [
    ["PRD 功能需求", "88 条（FR1-FR88）+ 非功能需求，全部覆盖"],
    ["Epic / Story", "33 个 Epic / 140+ 个 Story，全部完成"],
    ["开发阶段", "5 个阶段（MVP → Phase 1.5 → Phase 2 → 推广 → 智能诊断），全部交付"],
    ["技术栈", "Vue 3 + TypeScript + FastAPI + SQLAlchemy + WebSocket"],
    ["协议支持", "6 种工业协议（Modbus TCP/RTU、SNMP、MQTT、HTTP、BACnet、OPC-UA）"],
    ["本周提交", "117 次 Git Commit"],
  ],
  [3000, 6026]
));

// 二、本周重点工作
children.push(heading1("二、本周重点工作（2026-03-08 ~ 03-15）"));

children.push(heading2("2.1 制冷功率转移 - 预冷 TCL 模型（Epic 29-33）"));
children.push(para("基于《空调可转移功率算法调研与改进方案 V2.0》，完成了预冷 TCL 模型从数据建模到前端展示的全链路实施，共 5 个 Epic、17 个 Story："));

children.push(makeTable(
  ["Epic", "内容", "Story 数", "状态"],
  [
    ["Epic 29", "RC 热动力学核心模型", "7", st("✅ 完成")],
    ["Epic 30", "ASHRAE 安全约束与自动回退", "4", st("✅ 完成")],
    ["Epic 31", "谷时预冷计划引擎", "5", st("✅ 完成")],
    ["Epic 32", "RC 参数自动校准与分阶段部署", "4", st("✅ 完成")],
    ["Epic 33", "VPP 虚拟电厂接口", "3", st("✅ 完成")],
  ],
  [1200, 4326, 1200, 2300]
));

children.push(para(""));
children.push(para("核心技术亮点：", { bold: true }));
children.push(para("RC 热动力学模型：实现 C×dT/dt = Q_IT - Q_cool + (T_amb - T)/R 核心方程，支持温度预测与功率优化"));
children.push(para("温度裕度法安全兜底：ASHRAE 温度硬约束，裕度 < 2°C 时禁止转移制冷功率"));
children.push(para("7 项自动回退保护：温度超限/功率过载/传感器故障等场景自动恢复"));
children.push(para("贪心优化预冷调度：APScheduler 定时执行，谷时预冷/峰时释放"));
children.push(para("RC 参数最小二乘自动校准：3 阶段部署（验证→小范围→全量）"));
children.push(para("VPP 虚拟电厂接口：可调容量上报 + 调控指令接收 + 前端集成状态监控"));

children.push(heading2("2.2 智能诊断系统扩展（Epic 24-26 续）"));
children.push(para("完成 Epic 26 剩余 Story 和 Bug 修复："));

children.push(makeTable(
  ["Story", "内容", "状态"],
  [
    ["26.8", "边缘推理预留与 SBOM 管理", st("✅ 完成")],
    ["26.9", "训练数据异常检测（对抗样本防护）", st("✅ 完成")],
    ["26.10", "HMAC 密钥管理", st("✅ 完成")],
  ],
  [1500, 5226, 2300]
));

children.push(heading2("2.3 对抗性代码审查与 Bug 修复"));
children.push(para("执行全面对抗性代码审查，发现并修复多个问题："));

children.push(makeTable(
  ["序号", "修复内容", "优先级"],
  [
    ["1", "broadcast_to_role 方法不存在（4 处）→ 改用 broadcast_diagnosis", "HIGH"],
    ["2", "RejectRequest 被 FastAPI 误解为 query 参数 → 添加 Body(...) 注解", "HIGH"],
    ["3", "diagnosis.py 中 4 个重复路由覆盖 probability_tuning.py 新版实现 → 删除旧版", "HIGH"],
    ["4", "全系统 API 响应解析一致性修复（5 个文件 24 处）", "MEDIUM"],
    ["5", "巡检管理/工单管理枚举值修复（前端英文→后端中文枚举）", "MEDIUM"],
    ["6", "制冷监控 3 个页面详情弹窗数据解析错误", "MEDIUM"],
    ["7", "故障树编辑器浏览器验证修复（4 个问题）", "MEDIUM"],
    ["8", "转移配置抽屉修复 - 趋势数据+约束条件+负载率全链路修通", "MEDIUM"],
  ],
  [800, 6726, 1500]
));

children.push(heading2("2.4 测试与质量保障"));
children.push(para("新增 E2E API 测试覆盖 9 个未测试模块，大幅提升测试覆盖率："));

children.push(makeTable(
  ["测试类型", "规模", "结果"],
  [
    ["后端测试", "187 个文件，3474 个用例", st("✅ 全部通过")],
    ["前端单元测试（Vitest）", "161 个文件，1200+ 个用例", st("✅ 全部通过")],
    ["E2E Spec 文件", "12 个 spec 文件", st("✅ 全部通过")],
    ["本周新增 API 测试", "9 个模块，468 个用例", st("✅ 全部通过")],
  ],
  [3000, 3526, 2500]
));

children.push(heading2("2.5 前端数据链路统一（Epic 27）"));
children.push(para("完成前端数据链路审查和修复，共 10 个 Story："));
children.push(makeTable(
  ["Story", "内容", "状态"],
  [
    ["27.7", "数据链路 P0 问题修复 + P1 规划", st("✅ 完成")],
    ["27.8", "环境监控分组逻辑统一到 RealtimeStore", st("✅ 完成")],
    ["27.9", "Dashboard refreshData 并行调用优化", st("✅ 完成")],
    ["27.10", "BigscreenStore 性能优化 - 改为 setup API", st("✅ 完成")],
  ],
  [1500, 5226, 2300]
));

children.push(heading2("2.6 Demo 系统解耦（Epic 28）"));
children.push(para("完成 Demo 系统与生产数据隔离："));
children.push(makeTable(
  ["问题", "修复内容", "状态"],
  [
    ["P0-1", "_clear_demo_data_safe 方法缺失修复", st("✅ 完成")],
    ["P2-1", "Demo 数据隔离完善", st("✅ 完成")],
  ],
  [1500, 5226, 2300]
));

// 三、代码规模
children.push(heading1("三、代码规模"));

children.push(makeTable(
  ["维度", "数量"],
  [
    ["后端 API 模块", "63 个文件"],
    ["前端页面（Views）", "96 个"],
    ["前端组件（Components）", "90 个"],
    ["后端测试文件", "187 个"],
    ["前端单元测试文件", "161 个"],
    ["E2E Spec 文件", "12 个"],
  ],
  [3000, 6026]
));

// 四、核心功能模块
children.push(heading1("四、核心功能模块完成情况"));

children.push(makeTable(
  ["模块", "Epic", "状态"],
  [
    ["采集网关框架（6 种协议）", "1, 15", st("✅ 完成")],
    ["网关管理 + MQTT 通信", "2, 21", st("✅ 完成")],
    ["数据源管理 UI", "3", st("✅ 完成")],
    ["实时监控（六大子系统）", "4, 18", st("✅ 完成")],
    ["告警管理增强", "5, 20", st("✅ 完成")],
    ["能源管理 + 节能优化", "6", st("✅ 完成")],
    ["资产与容量管理", "7", st("✅ 完成")],
    ["物理拓扑 + 智能选址", "8", st("✅ 完成")],
    ["联动引擎 + 消防联动", "9, 19", st("✅ 完成")],
    ["视频监控集成", "10", st("✅ 完成")],
    ["运维管理（工单/巡检/知识库）", "11", st("✅ 完成")],
    ["报表与决策支持", "12", st("✅ 完成")],
    ["用户与系统管理", "13, 22", st("✅ 完成")],
    ["代码质量与测试", "14", st("✅ 完成")],
    ["多站点集中管理", "16", st("✅ 完成")],
    ["2.5D 视觉增强", "17", st("✅ 完成")],
    ["大屏增强 + OCR", "23", st("✅ 完成")],
    ["故障树诊断引擎", "24-25", st("✅ 完成")],
    ["诊断安全加固", "26", st("✅ 完成")],
    ["前端数据链路统一", "27", st("✅ 完成")],
    ["Demo 系统解耦", "28", st("✅ 完成")],
    ["RC 热动力学核心模型", "29", st("✅ 完成")],
    ["安全约束与自动回退", "30", st("✅ 完成")],
    ["谷时预冷计划引擎", "31", st("✅ 完成")],
    ["RC 参数自动校准", "32", st("✅ 完成")],
    ["VPP 虚拟电厂接口", "33", st("✅ 完成")],
  ],
  [4000, 2526, 2500]
));

// 五、版本演进
children.push(heading1("五、版本演进"));

children.push(makeTable(
  ["版本", "日期", "里程碑"],
  [
    ["V2.0.0", "2026-01-01", "架构重构（FastAPI + Vue 3 + TypeScript + WebSocket）"],
    ["V2.1.0", "2026-01-13", "Epic 1-8 完成，核心采集/监控/告警/能源/资产功能"],
    ["V3.0.0", "2026-02-20", "Epic 1-17 全部完成（86 Story），核心功能 100%"],
    ["V3.1.0", "2026-02-23", "Epic 1-23 全部完成（101 Story），全面质量保障"],
    [{ text: "V4.0.0", bold: true }, { text: "2026-03-08", bold: true }, { text: "Epic 24-28 完成，智能诊断 + 数据链路 + Demo 隔离", bold: true }],
    [{ text: "V4.1.0", bold: true, textColor: C.subtitle }, { text: "2026-03-15", bold: true, textColor: C.subtitle }, { text: "Epic 29-33 完成，制冷功率转移 TCL 模型全链路实施", bold: true, textColor: C.subtitle }],
  ],
  [1500, 1800, 5726]
));

// 六、下一步计划
children.push(heading1("六、下一步计划"));
children.push(para("功能开发已全部完成，建议后续重点工作："));

children.push(makeTable(
  ["优先级", "工作项", "说明"],
  [
    ["P0", "真实设备对接试点部署", "首批试点机房设备接入，验证 6 种协议适配器"],
    ["P0", "用户验收测试（UAT）", "组织运维团队进行功能验收"],
    ["P1", "RC 参数实测校准", "接入真实温度传感器数据，校准热动力学模型参数"],
    ["P1", "性能压测与安全审计", "模拟高并发场景，安全漏洞扫描"],
    ["P1", "用户培训与文档完善", "编制操作手册，组织培训"],
    ["P2", "多站点推广部署", "从试点机房扩展到多机房覆盖"],
    ["P2", "VPP 虚拟电厂对接", "与电网调度平台对接，实现需求响应"],
  ],
  [1200, 3200, 4626]
));

// Build document
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Microsoft YaHei", size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Microsoft YaHei" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Microsoft YaHei" },
        paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 1 } },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [textRun("DCIM 项目进展汇报 V4.1.0", { size: 16, color: C.gray })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            textRun("第 ", { size: 16, color: C.gray }),
            new TextRun({ children: [PageNumber.CURRENT], font, size: 16, color: C.gray }),
            textRun(" 页", { size: 16, color: C.gray }),
          ],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("docs/DCIM项目进展汇报_V4.1.0_20260315.docx", buffer);
  console.log("Report generated successfully!");
});
