const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
  BorderStyle, WidthType, ShadingType, PageNumber, PageBreak
} = require("docx");

// ========== 配置 ==========
const FONT = "Microsoft YaHei";
const PAGE_WIDTH = 11906; // A4
const PAGE_HEIGHT = 16838;
const MARGIN = 1440;
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2; // 9026

// ========== 工具函数 ==========
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const headerBorder = { style: BorderStyle.SINGLE, size: 1, color: "4472C4" };
const headerBorders = { top: headerBorder, bottom: headerBorder, left: headerBorder, right: headerBorder };

function headerCell(text, width) {
  return new TableCell({
    borders: headerBorders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: "4472C4", type: ShadingType.CLEAR },
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text, bold: true, font: FONT, size: 20, color: "FFFFFF" })] })]
  });
}

function cell(text, width, opts = {}) {
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: opts.shading ? { fill: opts.shading, type: ShadingType.CLEAR } : undefined,
    margins: { top: 50, bottom: 50, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
      children: [new TextRun({ text, font: FONT, size: 20, bold: !!opts.bold, color: opts.color || "333333" })]
    })]
  });
}

function makeTable(headers, rows, colWidths) {
  const tableWidth = colWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: tableWidth, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      new TableRow({ children: headers.map((h, i) => headerCell(h, colWidths[i])) }),
      ...rows.map((row, ri) => new TableRow({
        children: row.map((c, ci) => cell(c, colWidths[ci], { shading: ri % 2 === 1 ? "F2F7FB" : undefined, center: ci > 0 && headers.length <= 4 }))
      }))
    ]
  });
}

function heading1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 200 },
    children: [new TextRun({ text, font: FONT, size: 32, bold: true, color: "1F3864" })]
  });
}

function heading2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 160 },
    children: [new TextRun({ text, font: FONT, size: 26, bold: true, color: "2E75B6" })]
  });
}

function bodyText(text, opts = {}) {
  return new Paragraph({
    spacing: { before: 80, after: 80 },
    children: [new TextRun({ text, font: FONT, size: 21, color: opts.color || "333333", bold: !!opts.bold })]
  });
}

// ========== 文档内容 ==========
const children = [];

// 封面标题
children.push(new Paragraph({ spacing: { before: 3000 } }));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 200 },
  children: [new TextRun({ text: "DCIM 算力中心智能监控系统", font: FONT, size: 44, bold: true, color: "1F3864" })]
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 600 },
  children: [new TextRun({ text: "项目进展汇报", font: FONT, size: 36, bold: true, color: "2E75B6" })]
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 100 },
  children: [new TextRun({ text: "版本：V3.1.0", font: FONT, size: 24, color: "666666" })]
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 100 },
  children: [new TextRun({ text: "日期：2026 年 2 月 23 日", font: FONT, size: 24, color: "666666" })]
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 100 },
  children: [new TextRun({ text: "编制：proecheng", font: FONT, size: 24, color: "666666" })]
}));

// 分页
children.push(new Paragraph({ children: [new PageBreak()] }));

// 一、整体进展
children.push(heading1("一、整体进展"));
children.push(bodyText("项目已完成全部规划功能的开发，当前版本 V3.1.0。"));
children.push(bodyText(""));
children.push(makeTable(
  ["指标", "数据"],
  [
    ["PRD 功能需求", "88 条（FR1-FR88）+ 非功能需求，全部覆盖"],
    ["Epic / Story", "23 个 Epic / 101 个 Story，全部完成"],
    ["开发阶段", "4 个阶段（MVP → Phase 1.5 → Phase 2 → 推广），全部交付"],
    ["技术栈", "Vue 3 + TypeScript + FastAPI + SQLAlchemy + WebSocket"],
    ["协议支持", "6 种工业协议（Modbus TCP/RTU、SNMP、MQTT、HTTP、BACnet、OPC-UA）"],
  ],
  [3000, 6026]
));

// 二、BMAD 方法论执行情况
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading1("二、BMAD 方法论执行情况"));
children.push(bodyText("项目按照 BMAD 方法论完整走完了从分析到实现的全流程："));
children.push(bodyText(""));
children.push(makeTable(
  ["阶段", "产出物", "状态"],
  [
    ["1-分析", "产品简报（Product Brief）", "✅ 完成"],
    ["2-规划", "PRD（88 条需求）+ PRD 验证报告", "✅ 完成"],
    ["3-方案设计", "系统架构文档 + Epics & Stories + 实施就绪检查", "✅ 完成"],
    ["4-实施", "Sprint 规划 → Story 创建 → 开发 → 代码审查 → 回顾", "✅ 23 个 Epic 全部完成"],
  ],
  [2000, 5026, 2000]
));

// 三、代码规模
children.push(bodyText(""));
children.push(heading1("三、代码规模"));
children.push(makeTable(
  ["维度", "数量"],
  [
    ["后端 API 模块", "56 个文件"],
    ["前端页面（Views）", "73 个"],
    ["前端组件（Components）", "77 个"],
    ["后端测试文件", "109 个"],
    ["前端单元测试文件", "155 个"],
    ["E2E 测试文件", "13 个"],
  ],
  [4500, 4526]
));

// 四、测试与质量保障
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading1("四、测试与质量保障"));

children.push(heading2("4.1 测试覆盖"));
children.push(makeTable(
  ["测试类型", "规模", "结果"],
  [
    ["后端测试", "109 个文件，1350+ 用例", "全部通过"],
    ["前端单元测试（Vitest）", "155 个文件，1182 个用例", "全部通过"],
    ["E2E 集成测试（Playwright）", "13 个 spec 文件，144 个用例", "全部通过"],
  ],
  [3000, 3500, 2526]
));

children.push(heading2("4.2 代码审查"));
children.push(bodyText("完成 CR-01 ~ CR-12 共 12 项代码审查修复："));
children.push(bodyText(""));
children.push(makeTable(
  ["编号", "优先级", "修复内容"],
  [
    ["CR-01", "HIGH", "升级链 JSON 从 description 迁移到专用 escalation_chain 字段"],
    ["CR-02", "HIGH", "condition_expr 后端 JSON schema 校验 + 前端反序列化错误提示"],
    ["CR-03", "HIGH", "OCR 文件魔数校验 + API 层 10MB 前置大小检查"],
    ["CR-04", "HIGH", "WebSocket 单例 onUnmounted 安全清理"],
    ["CR-05", "MEDIUM", "Three.js GridHelper/Fog 资源清理完善"],
    ["CR-06", "MEDIUM", "屏蔽策略编辑改为先创建后删除，防止数据丢失"],
    ["CR-07", "MEDIUM", "批量配置下发改为 3 并发控制"],
    ["CR-08", "MEDIUM", "24h 告警数按 device_type 过滤"],
    ["CR-09", "MEDIUM", "阈值全量加载标记技术债务"],
    ["CR-10", "LOW", "BigscreenHistoryDialog 非数字 deviceId 显示明确提示"],
    ["CR-11", "LOW", "网关页面标签修正"],
    ["CR-12", "LOW", "条件组深度限制改为 prop + 禁用按钮带 tooltip"],
  ],
  [1200, 1400, 6426]
));

children.push(heading2("4.3 代码质量"));
children.push(bodyText("全量 ruff format + lint 自动修复：270 lint fixes，144 files reformatted"));
children.push(bodyText("TypeScript 类型检查：零错误"));
children.push(bodyText("前端生产构建：验证通过"));

// 五、核心功能模块完成情况
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading1("五、核心功能模块完成情况"));
children.push(makeTable(
  ["模块", "Epic", "状态"],
  [
    ["采集网关框架（6 种协议）", "1, 15", "✅ 完成"],
    ["网关管理 + MQTT 通信", "2, 21", "✅ 完成"],
    ["数据源管理 UI", "3", "✅ 完成"],
    ["实时监控（六大子系统）", "4, 18", "✅ 完成"],
    ["告警管理增强", "5, 20", "✅ 完成"],
    ["能源管理 + 节能优化", "6", "✅ 完成"],
    ["资产与容量管理", "7", "✅ 完成"],
    ["物理拓扑 + 智能选址", "8", "✅ 完成"],
    ["联动引擎 + 消防联动", "9, 19", "✅ 完成"],
    ["视频监控集成", "10", "✅ 完成"],
    ["运维管理（工单/巡检/知识库）", "11", "✅ 完成"],
    ["报表与决策支持", "12", "✅ 完成"],
    ["用户与系统管理", "13, 22", "✅ 完成"],
    ["代码质量与测试", "14", "✅ 完成"],
    ["多站点集中管理", "16", "✅ 完成"],
    ["2.5D 视觉增强", "17", "✅ 完成"],
    ["大屏增强 + OCR", "23", "✅ 完成"],
  ],
  [4000, 1500, 3526]
));

// 六、近期重点工作
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(heading1("六、近期重点工作（2026-02-21 ~ 02-23）"));

children.push(makeTable(
  ["序号", "工作内容", "说明"],
  [
    ["1", "Epic 18-23 开发完成", "Phase 2 补充，替换全部占位页面为完整业务页面"],
    ["2", "对抗性代码审查", "CR-01 ~ CR-12 共 12 项技术债务修复"],
    ["3", "QA 自动化测试补充", "两轮测试，新增 24 个测试文件 / 385 用例"],
    ["4", "监控运维基础设施", "健康检查端点、结构化日志、错误追踪、性能指标"],
    ["5", "全面性能优化", "前后端响应速度提升"],
    ["6", "菜单三区重构", "监控域/管理域/配置域分区，RBAC 角色过滤"],
    ["7", "配电拓扑增强", "关联已有设备功能 + DeviceSyncService 双向同步"],
  ],
  [800, 3000, 5226]
));

// 七、版本演进
children.push(bodyText(""));
children.push(heading1("七、版本演进"));
children.push(makeTable(
  ["版本", "日期", "里程碑"],
  [
    ["V2.0.0", "2026-01-01", "架构重构（FastAPI + Vue 3 + TypeScript + WebSocket）"],
    ["V2.1.0", "2026-01-13", "Epic 1-8 完成，核心采集/监控/告警/能源/资产功能"],
    ["V3.0.0", "2026-02-20", "Epic 1-17 全部完成（86 Story），核心功能 100%"],
    ["V3.1.0", "2026-02-23", "Epic 1-23 全部完成（101 Story），全面质量保障"],
  ],
  [1500, 2000, 5526]
));

// 八、下一步计划
children.push(bodyText(""));
children.push(heading1("八、下一步计划"));
children.push(bodyText("功能开发已全部完成，建议后续重点工作："));
children.push(bodyText(""));
children.push(makeTable(
  ["优先级", "工作项", "说明"],
  [
    ["P0", "真实设备对接试点部署", "首批试点机房设备接入，验证 6 种协议适配器"],
    ["P0", "用户验收测试（UAT）", "组织运维团队进行功能验收"],
    ["P1", "性能压测与安全审计", "模拟高并发场景，安全漏洞扫描"],
    ["P1", "用户培训与文档完善", "编制操作手册，组织培训"],
    ["P2", "多站点推广部署", "从试点机房扩展到多机房覆盖"],
  ],
  [1200, 3000, 4826]
));

// ========== 构建文档 ==========
const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: FONT, color: "1F3864" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: FONT, color: "2E75B6" },
        paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 1 } },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_WIDTH, height: PAGE_HEIGHT },
        margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN }
      }
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: "DCIM \u7B97\u529B\u4E2D\u5FC3\u667A\u80FD\u76D1\u63A7\u7CFB\u7EDF - \u9879\u76EE\u8FDB\u5C55\u6C47\u62A5", font: FONT, size: 16, color: "999999" })]
        })]
      })
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "\u7B2C ", font: FONT, size: 16, color: "999999" }),
            new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "999999" }),
            new TextRun({ text: " \u9875", font: FONT, size: 16, color: "999999" }),
          ]
        })]
      })
    },
    children
  }]
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = "docs/DCIM项目进展汇报_V3.1.0_20260223.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("Generated: " + outPath);
});
