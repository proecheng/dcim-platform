const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const html2pptx = require("C:/Users/admin/.claude/plugins/cache/anthropic-agent-skills/document-skills/69c0b1a06741/skills/pptx/scripts/html2pptx.js");

const WS = __dirname;
const SLIDES = path.join(WS, "slides");
const IMG = path.resolve(WS, "../newpic");
const OUT = path.resolve(WS, "../路演PPT-数据中心数字孪生大屏系统.pptx");

// ── Colors ──
const C = {
  bg: "#0B1929", bgLight: "#0F2238", bgCard: "#132D4A",
  accent: "#00B4D8", accentDark: "#0077B6", accentLight: "#48CAE4",
  teal: "#00E5A0", orange: "#FF8C42", red: "#FF4757",
  white: "#FFFFFF", gray: "#8FA3B0", grayLight: "#B8C9D4", grayDark: "#4A6375",
};

// ── Gradient backgrounds ──
async function makeGradient(name, c1, c2, angle = "y1='0%' y2='100%'") {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720">
    <defs><linearGradient id="g" x1="0%" ${angle} x2="0%">
      <stop offset="0%" stop-color="${c1}"/>
      <stop offset="100%" stop-color="${c2}"/>
    </linearGradient></defs>
    <rect width="100%" height="100%" fill="url(#g)"/>
  </svg>`;
  const out = path.join(SLIDES, name);
  await sharp(Buffer.from(svg)).png().toFile(out);
  return out;
}

async function makeGradientDiag(name, c1, c2) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720">
    <defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="${c1}"/>
      <stop offset="50%" stop-color="${c2}"/>
      <stop offset="100%" stop-color="${c1}"/>
    </linearGradient></defs>
    <rect width="100%" height="100%" fill="url(#g)"/>
  </svg>`;
  const out = path.join(SLIDES, name);
  await sharp(Buffer.from(svg)).png().toFile(out);
  return out;
}

// ── Accent bar SVG ──
async function makeAccentBar(name, color, w, h) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}">
    <rect width="100%" height="100%" fill="${color}" rx="3"/>
  </svg>`;
  const out = path.join(SLIDES, name);
  await sharp(Buffer.from(svg)).png().toFile(out);
  return out;
}

// ── HTML slide template ──
function slideHTML(bgColor, content) {
  return `<!DOCTYPE html><html><head><style>
html{background:${bgColor}}
body{width:720pt;height:405pt;margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;
  background:${bgColor};display:flex;flex-direction:column}
.pad{margin:36pt 44pt}
h1{color:#FFFFFF;font-size:28pt;margin:0 0 8pt 0;letter-spacing:1pt}
h2{color:#00B4D8;font-size:20pt;margin:0 0 12pt 0}
h3{color:#FFFFFF;font-size:16pt;margin:0 0 6pt 0}
p{color:#B8C9D4;font-size:11pt;line-height:1.6;margin:4pt 0}
.accent{color:#00B4D8}
.teal{color:#00E5A0}
.orange{color:#FF8C42}
.white{color:#FFFFFF}
.small{font-size:9pt;color:#8FA3B0}
</style></head><body>${content}</body></html>`;
}

// ── Write slide HTML ──
function writeSlide(name, html) {
  const p = path.join(SLIDES, name);
  fs.writeFileSync(p, html);
  return p;
}

// ── Main ──
async function main() {
  console.log("Preparing assets...");

  // Generate background gradients
  const bgDark = await makeGradient("bg_dark.png", "#060E1A", "#0F2238");
  const bgCover = await makeGradientDiag("bg_cover.png", "#060E1A", "#0D2847");
  const bgCards = await makeGradient("bg_cards.png", "#08131F", "#0F2238");
  const bgEnd = await makeGradientDiag("bg_end.png", "#0D2847", "#060E1A");
  const accentBarFile = await makeAccentBar("accent_bar.png", "#00B4D8", 4, 60);

  console.log("Building slides...");
  const pptx = new pptxgen();
  pptx.layout = "LAYOUT_16x9";
  pptx.author = "Digital Twin Team";
  pptx.title = "数据中心数字孪生大屏系统 - 路演 PPT";

  // =====================================================
  // SLIDE 1: COVER
  // =====================================================
  writeSlide("s01.html", slideHTML("#080F1E", `
    <div style="margin:80pt 50pt 0 50pt">
      <p style="color:#00B4D8;font-size:12pt;letter-spacing:3pt">DIGITAL TWIN VISUALIZATION PLATFORM</p>
      <h1 style="font-size:34pt;margin-top:12pt;line-height:1.3">数据中心数字孪生大屏系统</h1>
      <div style="width:60pt;height:3pt;background:#00B4D8;margin:16pt 0"></div>
      <p style="font-size:14pt;color:#B8C9D4;margin-top:12pt">上传 CAD 图纸，5 分钟生成数据中心 3D 模型</p>
      <p style="font-size:14pt;color:#B8C9D4">走进虚拟机房，直观感知每台设备的运行状态</p>
      <p style="font-size:9pt;color:#4A6375;margin-top:40pt">产品路演  |  2026</p>
    </div>
  `));
  await html2pptx(path.join(SLIDES, "s01.html"), pptx, { tmpDir: SLIDES });

  // =====================================================
  // SLIDE 2: PAIN POINTS
  // =====================================================
  writeSlide("s02.html", slideHTML("#0A1525", `
    <div class="pad">
      <p style="color:#00B4D8;font-size:10pt;letter-spacing:2pt">THE PROBLEM</p>
      <h1>数据中心运维的四大痛点</h1>
      <div style="display:flex;gap:14pt;margin-top:20pt">
        <div style="flex:1;background:rgba(19,45,74,0.8);border-radius:6pt;padding:18pt;border-left:3pt solid #FF4757">
          <h3 style="color:#FF4757;font-size:13pt">看不清</h3>
          <p style="font-size:10pt">数千设备分布多个机房，无法直观掌握全局状态，值班人员依赖经验判断</p>
        </div>
        <div style="flex:1;background:rgba(19,45,74,0.8);border-radius:6pt;padding:18pt;border-left:3pt solid #FF8C42">
          <h3 style="color:#FF8C42;font-size:13pt">排不快</h3>
          <p style="font-size:10pt">告警只有数字和文字，无法定位故障设备，排查靠人工翻阅手册，平均处理时间长</p>
        </div>
        <div style="flex:1;background:rgba(19,45,74,0.8);border-radius:6pt;padding:18pt;border-left:3pt solid #00B4D8">
          <h3 style="color:#00B4D8;font-size:13pt">算不准</h3>
          <p style="font-size:10pt">能源数据散落各系统，PUE 计算滞后，电费归因困难，节能方案无法量化验证</p>
        </div>
        <div style="flex:1;background:rgba(19,45,74,0.8);border-radius:6pt;padding:18pt;border-left:3pt solid #00E5A0">
          <h3 style="color:#00E5A0;font-size:13pt">卖不动</h3>
          <p style="font-size:10pt">客户参观看不到科技感，演示依赖 PPT，无法建立信任，转化率低</p>
        </div>
      </div>
    </div>
  `));
  await html2pptx(path.join(SLIDES, "s02.html"), pptx, { tmpDir: SLIDES });

  // =====================================================
  // SLIDE 3: OUR SOLUTION - PRODUCT OVERVIEW
  // =====================================================
  writeSlide("s03.html", slideHTML("#0A1525", `
    <div class="pad">
      <p style="color:#00B4D8;font-size:10pt;letter-spacing:2pt">OUR SOLUTION</p>
      <h1>新一代数字孪生大屏产品</h1>
      <p style="font-size:12pt;color:#B8C9D4;margin-bottom:16pt">以 <b style="color:#00E5A0">易用性</b> 和 <b style="color:#00E5A0">智能诊断</b> 为核心卖点，通过沉浸式 3D 体验打动客户</p>
      <div style="display:flex;gap:16pt;margin-top:8pt">
        <div style="flex:1;background:#132D4A;border-radius:6pt;padding:14pt;text-align:center">
          <h3 style="color:#00B4D8;font-size:32pt;margin-bottom:4pt">5 min</h3>
          <p style="font-size:10pt;color:#FFFFFF">CAD 图纸生成 3D 模型</p>
        </div>
        <div style="flex:1;background:#132D4A;border-radius:6pt;padding:14pt;text-align:center">
          <h3 style="color:#00E5A0;font-size:32pt;margin-bottom:4pt">60 fps</h3>
          <p style="font-size:10pt;color:#FFFFFF">100机柜流畅渲染</p>
        </div>
        <div style="flex:1;background:#132D4A;border-radius:6pt;padding:14pt;text-align:center">
          <h3 style="color:#FF8C42;font-size:32pt;margin-bottom:4pt">1 小时</h3>
          <p style="font-size:10pt;color:#FFFFFF">零基础上手操作</p>
        </div>
        <div style="flex:1;background:#132D4A;border-radius:6pt;padding:14pt;text-align:center">
          <h3 style="color:#48CAE4;font-size:32pt;margin-bottom:4pt">5 min</h3>
          <p style="font-size:10pt;color:#FFFFFF">Docker 一键部署</p>
        </div>
      </div>
      <div id="img_placeholder" class="placeholder" style="width:632pt;height:1pt;margin-top:8pt"></div>
    </div>
  `));
  const { slide: s03 } = await html2pptx(path.join(SLIDES, "s03.html"), pptx, { tmpDir: SLIDES });
  // Add product login page image
  s03.addImage({ path: path.join(IMG, "19c32812c9e25.png"), x: 0.6, y: 4.2, w: 8.8, h: 0.9, sizing: { type: "cover", w: 8.8, h: 0.9 } });

  // =====================================================
  // SLIDE 4: PRODUCT DEMO - 3D DASHBOARD
  // =====================================================
  writeSlide("s04.html", slideHTML("#0A1525", `
    <div style="margin:24pt 44pt 0 44pt">
      <p style="color:#00B4D8;font-size:10pt;letter-spacing:2pt">PRODUCT DEMO</p>
      <h1 style="font-size:22pt">沉浸式 3D 数字孪生主控大屏</h1>
      <p style="font-size:10pt;color:#8FA3B0">多层级穿越 · 告警导航飞行 · 实时数据叠加 · 3D+2D 分屏</p>
    </div>
  `));
  const { slide: s04 } = await html2pptx(path.join(SLIDES, "s04.html"), pptx, { tmpDir: SLIDES });
  s04.addImage({ path: path.join(IMG, "19c3282d7a703.png"), x: 0.4, y: 1.55, w: 9.2, h: 3.75, sizing: { type: "contain", w: 9.2, h: 3.75 } });

  // =====================================================
  // SLIDE 5: SMART ALARM DIAGNOSTICS
  // =====================================================
  writeSlide("s05.html", slideHTML("#0A1525", `
    <div style="margin:24pt 44pt 0 44pt">
      <p style="color:#00B4D8;font-size:10pt;letter-spacing:2pt">SMART DIAGNOSTICS</p>
      <h1 style="font-size:22pt">智能诊断：分步排查引导</h1>
      <p style="font-size:10pt;color:#8FA3B0">告警直达 · 故障决策树 · 诊断+工单+视频+历史 四合一面板</p>
    </div>
  `));
  const { slide: s05 } = await html2pptx(path.join(SLIDES, "s05.html"), pptx, { tmpDir: SLIDES });
  s05.addImage({ path: path.join(IMG, "19c3285568610.png"), x: 0.4, y: 1.55, w: 9.2, h: 3.75, sizing: { type: "contain", w: 9.2, h: 3.75 } });

  // =====================================================
  // SLIDE 6: ENERGY VISUALIZATION
  // =====================================================
  writeSlide("s06.html", slideHTML("#0A1525", `
    <div style="margin:24pt 44pt 0 44pt">
      <p style="color:#00B4D8;font-size:10pt;letter-spacing:2pt">ENERGY VISUALIZATION</p>
      <h1 style="font-size:22pt">能源可视化：电力 + 气流粒子动画</h1>
      <p style="font-size:10pt;color:#8FA3B0">GPU 粒子系统 · 电价联动特效 · PUE 实时监控 · 成本视角模式</p>
    </div>
  `));
  const { slide: s06 } = await html2pptx(path.join(SLIDES, "s06.html"), pptx, { tmpDir: SLIDES });
  s06.addImage({ path: path.join(IMG, "19c32912522d9.png"), x: 0.4, y: 1.55, w: 9.2, h: 3.75, sizing: { type: "contain", w: 9.2, h: 3.75 } });

  // =====================================================
  // SLIDE 7: MORE FEATURES (3 images)
  // =====================================================
  writeSlide("s07.html", slideHTML("#0A1525", `
    <div style="margin:24pt 44pt 0 44pt">
      <p style="color:#00B4D8;font-size:10pt;letter-spacing:2pt">MORE FEATURES</p>
      <h1 style="font-size:20pt;margin-bottom:4pt">全链路功能覆盖</h1>
      <div style="display:flex;gap:10pt;margin-top:6pt">
        <div style="flex:1;text-align:center">
          <div style="background:#132D4A;border-radius:4pt;height:180pt;width:210pt;overflow:hidden"></div>
          <p style="font-size:10pt;color:#FFFFFF;margin-top:6pt"><b>CAD 导入建模</b></p>
          <p style="font-size:8pt">DXF/DWG 自动转 3D</p>
        </div>
        <div style="flex:1;text-align:center">
          <div style="background:#132D4A;border-radius:4pt;height:180pt;width:210pt;overflow:hidden"></div>
          <p style="font-size:10pt;color:#FFFFFF;margin-top:6pt"><b>巡检报告生成</b></p>
          <p style="font-size:8pt">PDF/Word 一键导出</p>
        </div>
        <div style="flex:1;text-align:center">
          <div style="background:#132D4A;border-radius:4pt;height:180pt;width:210pt;overflow:hidden"></div>
          <p style="font-size:10pt;color:#FFFFFF;margin-top:6pt"><b>数据源管理</b></p>
          <p style="font-size:8pt">多协议采集配置</p>
        </div>
      </div>
    </div>
  `));
  const { slide: s07 } = await html2pptx(path.join(SLIDES, "s07.html"), pptx, { tmpDir: SLIDES });
  s07.addImage({ path: path.join(IMG, "19c32958d294a.png"), x: 0.42, y: 1.42, w: 2.92, h: 2.1, sizing: { type: "cover", w: 2.92, h: 2.1 } });
  s07.addImage({ path: path.join(IMG, "19c329e44abac.png"), x: 3.54, y: 1.42, w: 2.92, h: 2.1, sizing: { type: "cover", w: 2.92, h: 2.1 } });
  s07.addImage({ path: path.join(IMG, "19c329b7f3e5a.png"), x: 6.66, y: 1.42, w: 2.92, h: 2.1, sizing: { type: "cover", w: 2.92, h: 2.1 } });

  // =====================================================
  // SLIDE 8: DEVICE DETAIL + EXHIBITION MODE
  // =====================================================
  writeSlide("s08.html", slideHTML("#0A1525", `
    <div style="margin:24pt 44pt 0 44pt">
      <p style="color:#00B4D8;font-size:10pt;letter-spacing:2pt">IMMERSIVE EXPERIENCE</p>
      <h1 style="font-size:20pt;margin-bottom:4pt">设备级细节 + 展示模式</h1>
      <div style="display:flex;gap:12pt;margin-top:6pt">
        <div style="flex:1">
          <div style="background:#132D4A;border-radius:4pt;height:210pt;width:315pt;overflow:hidden"></div>
          <p style="font-size:10pt;color:#FFFFFF;margin-top:6pt"><b>设备详情面板</b> — 实时数据、历史曲线、告警记录、资产信息</p>
        </div>
        <div style="flex:1">
          <div style="background:#132D4A;border-radius:4pt;height:210pt;width:315pt;overflow:hidden"></div>
          <p style="font-size:10pt;color:#FFFFFF;margin-top:6pt"><b>展示模式</b> — 自动参观路线、语音讲解、一键演示</p>
        </div>
      </div>
    </div>
  `));
  const { slide: s08 } = await html2pptx(path.join(SLIDES, "s08.html"), pptx, { tmpDir: SLIDES });
  s08.addImage({ path: path.join(IMG, "19c3293562da6.png"), x: 0.42, y: 1.38, w: 4.38, h: 2.84, sizing: { type: "cover", w: 4.38, h: 2.84 } });
  s08.addImage({ path: path.join(IMG, "19c32a3249490.png"), x: 5.2, y: 1.38, w: 4.38, h: 2.84, sizing: { type: "cover", w: 4.38, h: 2.84 } });

  // =====================================================
  // SLIDE 9: USER MANAGEMENT
  // =====================================================
  writeSlide("s09.html", slideHTML("#0A1525", `
    <div style="margin:24pt 44pt 0 44pt">
      <p style="color:#00B4D8;font-size:10pt;letter-spacing:2pt">MULTI-TENANT</p>
      <h1 style="font-size:20pt;margin-bottom:4pt">多租户架构 + 精细权限</h1>
      <div style="display:flex;gap:14pt;margin-top:2pt">
        <div style="flex:5">
          <div style="background:#132D4A;border-radius:4pt;height:220pt;overflow:hidden"></div>
        </div>
        <div style="flex:3;padding-top:10pt">
          <div style="background:#132D4A;border-radius:6pt;padding:14pt;margin-bottom:8pt">
            <h3 style="color:#00B4D8;font-size:11pt">三级权限体系</h3>
            <p style="font-size:9pt">Admin / Operator / Viewer 精细化管控</p>
          </div>
          <div style="background:#132D4A;border-radius:6pt;padding:14pt;margin-bottom:8pt">
            <h3 style="color:#00E5A0;font-size:11pt">租户数据隔离</h3>
            <p style="font-size:9pt">tenant_id 强制过滤，数据绝对安全</p>
          </div>
          <div style="background:#132D4A;border-radius:6pt;padding:14pt;margin-bottom:8pt">
            <h3 style="color:#FF8C42;font-size:11pt">白标定制</h3>
            <p style="font-size:9pt">Logo、主题色、欢迎语可自定义</p>
          </div>
          <div style="background:#132D4A;border-radius:6pt;padding:14pt">
            <h3 style="color:#48CAE4;font-size:11pt">审计日志</h3>
            <p style="font-size:9pt">所有操作记录，保留 90 天</p>
          </div>
        </div>
      </div>
    </div>
  `));
  const { slide: s09 } = await html2pptx(path.join(SLIDES, "s09.html"), pptx, { tmpDir: SLIDES });
  s09.addImage({ path: path.join(IMG, "19c329fc6e921.png"), x: 0.42, y: 1.38, w: 5.5, h: 3.3, sizing: { type: "cover", w: 5.5, h: 3.3 } });

  // =====================================================
  // SLIDE 10: CORE DIFFERENTIATORS
  // =====================================================
  writeSlide("s10.html", slideHTML("#0C1828", `
    <div class="pad">
      <p style="color:#00B4D8;font-size:10pt;letter-spacing:2pt">WHY US</p>
      <h1 style="font-size:24pt">五大核心竞争优势</h1>
      <div style="display:flex;gap:10pt;margin-top:16pt">
        <div style="flex:1;background:#132D4A;border-radius:6pt;padding:16pt;border-top:3pt solid #00B4D8">
          <h3 style="color:#00B4D8;font-size:12pt;text-align:center">极致易用</h3>
          <p style="font-size:9pt;text-align:center;margin-top:8pt">1 小时上手<br/>拖拽式建模<br/>游戏化交互</p>
        </div>
        <div style="flex:1;background:#132D4A;border-radius:6pt;padding:16pt;border-top:3pt solid #00E5A0">
          <h3 style="color:#00E5A0;font-size:12pt;text-align:center">智能诊断</h3>
          <p style="font-size:9pt;text-align:center;margin-top:8pt">分步排查引导<br/>语音播报<br/>四合一面板</p>
        </div>
        <div style="flex:1;background:#132D4A;border-radius:6pt;padding:16pt;border-top:3pt solid #FF8C42">
          <h3 style="color:#FF8C42;font-size:12pt;text-align:center">能源可视化</h3>
          <p style="font-size:9pt;text-align:center;margin-top:8pt">双流粒子动画<br/>电价联动特效<br/>PUE 实时追踪</p>
        </div>
        <div style="flex:1;background:#132D4A;border-radius:6pt;padding:16pt;border-top:3pt solid #48CAE4">
          <h3 style="color:#48CAE4;font-size:12pt;text-align:center">产品化交付</h3>
          <p style="font-size:9pt;text-align:center;margin-top:8pt">Docker 部署<br/>多租户架构<br/>天级交付周期</p>
        </div>
        <div style="flex:1;background:#132D4A;border-radius:6pt;padding:16pt;border-top:3pt solid #B8C9D4">
          <h3 style="color:#B8C9D4;font-size:12pt;text-align:center">开放集成</h3>
          <p style="font-size:9pt;text-align:center;margin-top:8pt">标准 API<br/>6 种采集协议<br/>无缝对接</p>
        </div>
      </div>
      <p style="font-size:10pt;color:#8FA3B0;margin-top:16pt;text-align:center">竞品 = 项目制定制，学习曲线陡，只报警不指导，静态热力图 → 我们 = 产品化，开箱即用，智能引导，沉浸体验</p>
    </div>
  `));
  await html2pptx(path.join(SLIDES, "s10.html"), pptx, { tmpDir: SLIDES });

  // =====================================================
  // SLIDE 11: MARKET & COMPETITION
  // =====================================================
  writeSlide("s11.html", slideHTML("#0A1525", `
    <div class="pad">
      <p style="color:#00B4D8;font-size:10pt;letter-spacing:2pt">MARKET</p>
      <h1 style="font-size:22pt">目标市场与竞争格局</h1>
      <div style="display:flex;gap:16pt;margin-top:14pt">
        <div style="flex:2">
          <div style="background:#132D4A;border-radius:6pt;padding:14pt;margin-bottom:10pt">
            <h3 style="color:#00B4D8;font-size:11pt">目标客户</h3>
            <p style="font-size:9pt;margin-top:6pt">中型数据中心运营商 · 企业自建数据中心 · IDC 服务商</p>
            <p style="font-size:9pt">首期聚焦 <b style="color:#00E5A0">100 机柜</b> 级别，国内市场优先</p>
          </div>
          <div id="chart_area" class="placeholder" style="width:280pt;height:165pt"></div>
        </div>
        <div style="flex:3">
          <div id="comp_table" class="placeholder" style="width:360pt;height:240pt"></div>
        </div>
      </div>
    </div>
  `));
  const { slide: s11, placeholders: p11 } = await html2pptx(path.join(SLIDES, "s11.html"), pptx, { tmpDir: SLIDES });
  // Competition table
  const compArea = p11.find(p => p.id === "comp_table") || p11[1];
  if (compArea) {
    s11.addTable([
      [
        { text: "竞品", options: { fill: { color: "0077B6" }, color: "FFFFFF", bold: true, fontSize: 9 } },
        { text: "3D能力", options: { fill: { color: "0077B6" }, color: "FFFFFF", bold: true, fontSize: 9 } },
        { text: "易用性", options: { fill: { color: "0077B6" }, color: "FFFFFF", bold: true, fontSize: 9 } },
        { text: "价格", options: { fill: { color: "0077B6" }, color: "FFFFFF", bold: true, fontSize: 9 } },
      ],
      [{ text: "优锘 ThingJS", options: { fontSize: 8 } }, { text: "自研引擎", options: { fontSize: 8 } }, { text: "中", options: { fontSize: 8 } }, { text: "10-50万/年", options: { fontSize: 8 } }],
      [{ text: "蓝图 BlueMap", options: { fontSize: 8, fill: { color: "0D2847" } } }, { text: "BIM集成", options: { fontSize: 8, fill: { color: "0D2847" } } }, { text: "低", options: { fontSize: 8, fill: { color: "0D2847" } } }, { text: "50-200万", options: { fontSize: 8, fill: { color: "0D2847" } } }],
      [{ text: "DataV 阿里云", options: { fontSize: 8 } }, { text: "有限3D", options: { fontSize: 8 } }, { text: "高", options: { fontSize: 8 } }, { text: "5-15万/年", options: { fontSize: 8 } }],
      [{ text: "51World", options: { fontSize: 8, fill: { color: "0D2847" } } }, { text: "高精度", options: { fontSize: 8, fill: { color: "0D2847" } } }, { text: "低", options: { fontSize: 8, fill: { color: "0D2847" } } }, { text: "100-500万", options: { fontSize: 8, fill: { color: "0D2847" } } }],
      [
        { text: "我们", options: { fontSize: 8, bold: true, color: "00E5A0" } },
        { text: "Babylon.js GPU粒子", options: { fontSize: 8, bold: true, color: "00E5A0" } },
        { text: "极高", options: { fontSize: 8, bold: true, color: "00E5A0" } },
        { text: "15-150万", options: { fontSize: 8, bold: true, color: "00E5A0" } },
      ],
    ], {
      ...compArea, border: { pt: 0.5, color: "1A3A5C" },
      color: "B8C9D4", rowH: [0.4, 0.38, 0.38, 0.38, 0.38, 0.42],
      colW: [1.2, 1.4, 0.8, 1.1], valign: "middle", align: "center"
    });
  }
  // Pie chart for market positioning
  const chartArea = p11.find(p => p.id === "chart_area") || p11[0];
  if (chartArea) {
    s11.addChart(pptx.charts.PIE, [{
      name: "市场定位",
      labels: ["新客户(无DCIM)", "已有DCIM升级", "IDC服务商"],
      values: [40, 35, 25]
    }], {
      ...chartArea, showPercent: true, showLegend: true, legendPos: "b",
      legendFontSize: 8, legendColor: "B8C9D4",
      chartColors: ["00B4D8", "0077B6", "48CAE4"],
      dataLabelColor: "FFFFFF", dataLabelFontSize: 9
    });
  }

  // =====================================================
  // SLIDE 12: BUSINESS MODEL
  // =====================================================
  writeSlide("s12.html", slideHTML("#0C1828", `
    <div class="pad">
      <p style="color:#00B4D8;font-size:10pt;letter-spacing:2pt">BUSINESS MODEL</p>
      <h1 style="font-size:22pt">商业模式：三级版本 + 年度维保</h1>
      <div style="display:flex;gap:14pt;margin-top:14pt;align-items:flex-start">
        <div style="flex:1;background:#132D4A;border-radius:8pt;padding:18pt;border-top:3pt solid #48CAE4">
          <h3 style="color:#48CAE4;font-size:14pt;text-align:center">基础版</h3>
          <p style="font-size:9pt;text-align:center;color:#8FA3B0;margin-top:4pt">小型机房 ≤50 机柜</p>
          <h3 style="color:#FFFFFF;font-size:22pt;text-align:center;margin-top:10pt">15 - 25 万</h3>
          <p style="font-size:8pt;text-align:center;color:#8FA3B0">永久授权</p>
          <p style="font-size:8pt;margin-top:10pt;color:#B8C9D4">3D 漫游<br/>基础告警<br/>热力图<br/>Modbus/SNMP</p>
        </div>
        <div style="flex:1;background:#132D4A;border-radius:8pt;padding:18pt;border-top:3pt solid #00B4D8;transform:scale(1.03)">
          <p style="color:#00B4D8;font-size:7pt;text-align:center;letter-spacing:2pt;margin-bottom:4pt">RECOMMENDED</p>
          <h3 style="color:#00B4D8;font-size:14pt;text-align:center">专业版</h3>
          <p style="font-size:9pt;text-align:center;color:#8FA3B0;margin-top:4pt">中型 50-200 机柜</p>
          <h3 style="color:#FFFFFF;font-size:22pt;text-align:center;margin-top:10pt">40 - 60 万</h3>
          <p style="font-size:8pt;text-align:center;color:#8FA3B0">永久授权</p>
          <p style="font-size:8pt;margin-top:10pt;color:#B8C9D4">基础版全部功能 +<br/>能源可视化<br/>CAD 导入<br/>诊断引导<br/>PDF 报告</p>
        </div>
        <div style="flex:1;background:#132D4A;border-radius:8pt;padding:18pt;border-top:3pt solid #00E5A0">
          <h3 style="color:#00E5A0;font-size:14pt;text-align:center">企业版</h3>
          <p style="font-size:9pt;text-align:center;color:#8FA3B0;margin-top:4pt">大型 200+ 机柜</p>
          <h3 style="color:#FFFFFF;font-size:22pt;text-align:center;margin-top:10pt">80 - 150 万</h3>
          <p style="font-size:8pt;text-align:center;color:#8FA3B0">永久授权</p>
          <p style="font-size:8pt;margin-top:10pt;color:#B8C9D4">专业版全部功能 +<br/>多租户<br/>AI 预测<br/>全协议支持<br/>自定义开发</p>
        </div>
      </div>
      <p style="font-size:9pt;color:#8FA3B0;text-align:center;margin-top:14pt">附加收入: 年度维保 (授权费 15-20%) + 实施服务 (5-20万/次) + 模型定制 (0.5-2万/款) + SaaS 订阅 (可选)</p>
    </div>
  `));
  await html2pptx(path.join(SLIDES, "s12.html"), pptx, { tmpDir: SLIDES });

  // =====================================================
  // SLIDE 13: TECH ARCHITECTURE
  // =====================================================
  writeSlide("s13.html", slideHTML("#0A1525", `
    <div class="pad">
      <p style="color:#00B4D8;font-size:10pt;letter-spacing:2pt">TECHNOLOGY</p>
      <h1 style="font-size:22pt">技术架构：模块化单体 → 微服务演进</h1>
      <div style="display:flex;gap:14pt;margin-top:10pt">
        <div style="flex:3">
          <div style="background:#132D4A;border-radius:6pt;padding:14pt">
            <h3 style="color:#00B4D8;font-size:11pt;margin-bottom:8pt">MVP 架构 (6 容器)</h3>
            <div style="display:flex;gap:6pt;flex-wrap:wrap">
              <div style="background:#0B1929;border:1pt solid #0077B6;border-radius:4pt;padding:6pt 10pt;flex:1;min-width:80pt">
                <p style="font-size:8pt;color:#00B4D8"><b>Nginx</b></p>
                <p style="font-size:7pt">反向代理 + SSL</p>
              </div>
              <div style="background:#0B1929;border:1pt solid #00E5A0;border-radius:4pt;padding:6pt 10pt;flex:2;min-width:160pt">
                <p style="font-size:8pt;color:#00E5A0"><b>FastAPI 单体应用</b></p>
                <p style="font-size:7pt">3D场景 | 数据 | 告警 | 用户 | 能源 | 报告 | 集成</p>
              </div>
              <div style="background:#0B1929;border:1pt solid #48CAE4;border-radius:4pt;padding:6pt 10pt;flex:1;min-width:80pt">
                <p style="font-size:8pt;color:#48CAE4"><b>Vue3 前端</b></p>
                <p style="font-size:7pt">Babylon.js 3D</p>
              </div>
            </div>
            <div style="display:flex;gap:6pt;margin-top:6pt">
              <div style="background:#0B1929;border:1pt solid #FF8C42;border-radius:4pt;padding:6pt 10pt;flex:1">
                <p style="font-size:8pt;color:#FF8C42"><b>TimescaleDB</b></p>
                <p style="font-size:7pt">时序 + 关系</p>
              </div>
              <div style="background:#0B1929;border:1pt solid #FF8C42;border-radius:4pt;padding:6pt 10pt;flex:1">
                <p style="font-size:8pt;color:#FF8C42"><b>Redis</b></p>
                <p style="font-size:7pt">缓存</p>
              </div>
              <div style="background:#0B1929;border:1pt solid #FF8C42;border-radius:4pt;padding:6pt 10pt;flex:1">
                <p style="font-size:8pt;color:#FF8C42"><b>EMQX</b></p>
                <p style="font-size:7pt">MQTT Broker</p>
              </div>
            </div>
          </div>
        </div>
        <div style="flex:2">
          <div style="background:#132D4A;border-radius:6pt;padding:14pt;margin-bottom:8pt">
            <h3 style="color:#00E5A0;font-size:11pt">技术栈</h3>
            <p style="font-size:8pt;margin-top:6pt"><b style="color:#FFFFFF">3D 引擎:</b> Babylon.js (GPU 粒子)</p>
            <p style="font-size:8pt"><b style="color:#FFFFFF">前端:</b> Vue 3 + TypeScript</p>
            <p style="font-size:8pt"><b style="color:#FFFFFF">后端:</b> FastAPI (Python)</p>
            <p style="font-size:8pt"><b style="color:#FFFFFF">数据库:</b> TimescaleDB</p>
            <p style="font-size:8pt"><b style="color:#FFFFFF">协议:</b> Modbus/SNMP/BACnet/OPC-UA/MQTT</p>
          </div>
          <div style="background:#132D4A;border-radius:6pt;padding:14pt">
            <h3 style="color:#FF8C42;font-size:11pt">演进路线</h3>
            <p style="font-size:8pt;margin-top:6pt"><b style="color:#00B4D8">Phase 1:</b> 模块化单体 (6容器)</p>
            <p style="font-size:8pt"><b style="color:#00B4D8">Phase 2:</b> 部分拆分 (采集+AI)</p>
            <p style="font-size:8pt"><b style="color:#00B4D8">Phase 3:</b> 完整微服务</p>
          </div>
        </div>
      </div>
    </div>
  `));
  await html2pptx(path.join(SLIDES, "s13.html"), pptx, { tmpDir: SLIDES });

  // =====================================================
  // SLIDE 14: ROADMAP
  // =====================================================
  writeSlide("s14.html", slideHTML("#0C1828", `
    <div class="pad">
      <p style="color:#00B4D8;font-size:10pt;letter-spacing:2pt">ROADMAP</p>
      <h1 style="font-size:22pt;margin-bottom:12pt">产品路线图 — 25~34 周交付 MVP</h1>
      <div style="display:flex;gap:4pt;margin-top:12pt">
        <div style="flex:1;text-align:center">
          <div style="background:#00B4D8;border-radius:50%;width:28pt;height:28pt;margin:0 auto;display:flex;align-items:center;justify-content:center">
            <p style="color:#FFFFFF;font-size:10pt;font-weight:bold;margin:0">M1</p>
          </div>
          <p style="font-size:8pt;color:#FFFFFF;margin-top:6pt"><b>技术验证</b></p>
          <p style="font-size:7pt">4-6 周</p>
          <p style="font-size:7pt">Babylon.js Demo<br/>Modbus 采集</p>
        </div>
        <div style="flex:0.3;display:flex;align-items:center;padding-top:0"><div style="width:100%;height:2pt;background:#0077B6;margin-top:-40pt"></div></div>
        <div style="flex:1;text-align:center">
          <div style="background:#0077B6;border-radius:50%;width:28pt;height:28pt;margin:0 auto;display:flex;align-items:center;justify-content:center">
            <p style="color:#FFFFFF;font-size:10pt;font-weight:bold;margin:0">M2</p>
          </div>
          <p style="font-size:8pt;color:#FFFFFF;margin-top:6pt"><b>MVP-alpha</b></p>
          <p style="font-size:7pt">8-10 周</p>
          <p style="font-size:7pt">3D漫游+数据<br/>+告警+Docker</p>
        </div>
        <div style="flex:0.3;display:flex;align-items:center;padding-top:0"><div style="width:100%;height:2pt;background:#0077B6;margin-top:-40pt"></div></div>
        <div style="flex:1;text-align:center">
          <div style="background:#0077B6;border-radius:50%;width:28pt;height:28pt;margin:0 auto;display:flex;align-items:center;justify-content:center">
            <p style="color:#FFFFFF;font-size:10pt;font-weight:bold;margin:0">M4</p>
          </div>
          <p style="font-size:8pt;color:#FFFFFF;margin-top:6pt"><b>MVP-beta</b></p>
          <p style="font-size:7pt">6-8 周</p>
          <p style="font-size:7pt">能源可视化<br/>+CAD+报告</p>
        </div>
        <div style="flex:0.3;display:flex;align-items:center;padding-top:0"><div style="width:100%;height:2pt;background:#0077B6;margin-top:-40pt"></div></div>
        <div style="flex:1;text-align:center">
          <div style="background:#00E5A0;border-radius:50%;width:28pt;height:28pt;margin:0 auto;display:flex;align-items:center;justify-content:center">
            <p style="color:#0B1929;font-size:10pt;font-weight:bold;margin:0">M6</p>
          </div>
          <p style="font-size:8pt;color:#FFFFFF;margin-top:6pt"><b>正式发布</b></p>
          <p style="font-size:7pt">2-3 周</p>
          <p style="font-size:7pt">产品上线<br/>开始销售</p>
        </div>
        <div style="flex:0.3;display:flex;align-items:center;padding-top:0"><div style="width:100%;height:2pt;background:#0077B6;margin-top:-40pt"></div></div>
        <div style="flex:1;text-align:center">
          <div style="background:#FF8C42;border-radius:50%;width:28pt;height:28pt;margin:0 auto;display:flex;align-items:center;justify-content:center">
            <p style="color:#FFFFFF;font-size:10pt;font-weight:bold;margin:0">M7</p>
          </div>
          <p style="font-size:8pt;color:#FFFFFF;margin-top:6pt"><b>Phase 2</b></p>
          <p style="font-size:7pt">12-16 周</p>
          <p style="font-size:7pt">AI诊断+预测<br/>+协议扩展</p>
        </div>
      </div>
      <div style="display:flex;gap:10pt;margin-top:24pt">
        <div style="flex:1;background:#132D4A;border-radius:4pt;padding:10pt;text-align:center;border-left:3pt solid #00B4D8">
          <p style="font-size:9pt;color:#FFFFFF"><b>MVP-alpha 目标</b></p>
          <p style="font-size:8pt">可演示产品原型</p>
        </div>
        <div style="flex:1;background:#132D4A;border-radius:4pt;padding:10pt;text-align:center;border-left:3pt solid #00E5A0">
          <p style="font-size:9pt;color:#FFFFFF"><b>MVP-beta 目标</b></p>
          <p style="font-size:8pt">最小可销售产品</p>
        </div>
        <div style="flex:1;background:#132D4A;border-radius:4pt;padding:10pt;text-align:center;border-left:3pt solid #FF8C42">
          <p style="font-size:9pt;color:#FFFFFF"><b>Phase 2 目标</b></p>
          <p style="font-size:8pt">智能增强、客户粘性</p>
        </div>
      </div>
    </div>
  `));
  await html2pptx(path.join(SLIDES, "s14.html"), pptx, { tmpDir: SLIDES });

  // =====================================================
  // SLIDE 15: BUSINESS GOALS & KPI
  // =====================================================
  writeSlide("s15.html", slideHTML("#0A1525", `
    <div style="margin:28pt 44pt 0 44pt">
      <p style="color:#00B4D8;font-size:10pt;letter-spacing:2pt">BUSINESS GOALS</p>
      <h1 style="font-size:20pt">商业目标与关键指标</h1>
      <div style="display:flex;gap:14pt;margin-top:10pt">
        <div style="flex:1">
          <div style="background:#132D4A;border-radius:6pt;padding:12pt;margin-bottom:8pt">
            <h3 style="color:#00B4D8;font-size:11pt;margin-bottom:6pt">首年目标</h3>
            <div style="display:flex;gap:8pt">
              <div style="flex:1;text-align:center;background:#0B1929;border-radius:4pt;padding:8pt">
                <h3 style="color:#00E5A0;font-size:22pt">3-5</h3>
                <p style="font-size:8pt;color:#FFFFFF">签约客户</p>
              </div>
              <div style="flex:1;text-align:center;background:#0B1929;border-radius:4pt;padding:8pt">
                <h3 style="color:#00E5A0;font-size:22pt">300万</h3>
                <p style="font-size:8pt;color:#FFFFFF">合同额</p>
              </div>
            </div>
          </div>
          <div style="background:#132D4A;border-radius:6pt;padding:12pt">
            <h3 style="color:#FF8C42;font-size:11pt;margin-bottom:6pt">第二年目标</h3>
            <div style="display:flex;gap:8pt">
              <div style="flex:1;text-align:center;background:#0B1929;border-radius:4pt;padding:8pt">
                <h3 style="color:#FF8C42;font-size:22pt">10-15</h3>
                <p style="font-size:8pt;color:#FFFFFF">签约客户</p>
              </div>
              <div style="flex:1;text-align:center;background:#0B1929;border-radius:4pt;padding:8pt">
                <h3 style="color:#FF8C42;font-size:22pt">1000万</h3>
                <p style="font-size:8pt;color:#FFFFFF">合同额</p>
              </div>
              <div style="flex:1;text-align:center;background:#0B1929;border-radius:4pt;padding:8pt">
                <h3 style="color:#FF8C42;font-size:22pt">80%+</h3>
                <p style="font-size:8pt;color:#FFFFFF">续费率</p>
              </div>
            </div>
          </div>
        </div>
        <div style="flex:1">
          <div style="background:#132D4A;border-radius:6pt;padding:14pt">
            <h3 style="color:#48CAE4;font-size:11pt;margin-bottom:8pt">核心 KPI</h3>
            <div style="margin-bottom:6pt;border-bottom:1pt solid #1A3A5C;padding-bottom:6pt">
              <p style="font-size:9pt"><b style="color:#FFFFFF">客户演示通过率</b></p>
              <p style="font-size:18pt;color:#00E5A0;margin:0"><b>≥ 80%</b></p>
            </div>
            <div style="margin-bottom:6pt;border-bottom:1pt solid #1A3A5C;padding-bottom:6pt">
              <p style="font-size:9pt"><b style="color:#FFFFFF">系统可用性</b></p>
              <p style="font-size:18pt;color:#00B4D8;margin:0"><b>99.9%</b></p>
            </div>
            <div style="margin-bottom:6pt;border-bottom:1pt solid #1A3A5C;padding-bottom:6pt">
              <p style="font-size:9pt"><b style="color:#FFFFFF">3D 渲染帧率</b></p>
              <p style="font-size:18pt;color:#48CAE4;margin:0"><b>≥ 60 fps</b></p>
            </div>
            <div>
              <p style="font-size:9pt"><b style="color:#FFFFFF">NPS 推荐度</b></p>
              <p style="font-size:18pt;color:#FF8C42;margin:0"><b>≥ 30</b></p>
            </div>
          </div>
        </div>
      </div>
    </div>
  `));
  await html2pptx(path.join(SLIDES, "s15.html"), pptx, { tmpDir: SLIDES });

  // =====================================================
  // SLIDE 16: THANK YOU / CLOSING
  // =====================================================
  writeSlide("s16.html", slideHTML("#080F1E", `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%">
      <p style="color:#00B4D8;font-size:11pt;letter-spacing:4pt;margin-bottom:12pt">DIGITAL TWIN VISUALIZATION PLATFORM</p>
      <h1 style="font-size:38pt;text-align:center;margin:0">感谢聆听</h1>
      <div style="width:80pt;height:3pt;background:#00B4D8;margin:20pt 0"></div>
      <h2 style="font-size:16pt;color:#FFFFFF;text-align:center;margin-top:8pt">数据中心数字孪生大屏系统</h2>
      <p style="font-size:11pt;color:#8FA3B0;text-align:center;margin-top:16pt">让数据中心运维从"盲人摸象"变为"一目了然"</p>
      <p style="font-size:9pt;color:#4A6375;text-align:center;margin-top:30pt">联系我们  |  产品演示  |  商务合作</p>
    </div>
  `));
  await html2pptx(path.join(SLIDES, "s16.html"), pptx, { tmpDir: SLIDES });

  // ── Save ──
  console.log("Saving presentation...");
  await pptx.writeFile({ fileName: OUT });
  console.log(`Done! Saved to: ${OUT}`);
}

main().catch(e => { console.error(e); process.exit(1); });
