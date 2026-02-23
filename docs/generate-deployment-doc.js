// docs/generate-deployment-doc.js
// 生成 DCIM 部署需求 Word 文档，输出路径: docs/DCIM部署需求文档_V3.1.0.docx
// 依赖: docx (npm install -g docx 或本地安装)
// 说明：遵循中文书写规范，包含页眉/页脚、A4 纸张、浅蓝色表头等格式要求。

const fs = require('fs');
const path = require('path');
const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  PageSize,
  AlignmentType,
  WidthType,
  Table,
  TableRow,
  TableCell,
  ShadingType,
  BorderStyle,
  Header,
  Footer,
  PageNumber,
} = require('docx');

async function generate() {
  const outputPath = path.resolve(__dirname, 'DCIM部署需求文档_V3.1.0.docx');

  // 页眉：居中显示文档标题
  const header = new Header({
    children: [
      new Paragraph({
        children: [new TextRun({ text: '算力中心智能监控系统 部署需求文档', bold: true })],
        alignment: AlignmentType.CENTER,
      }),
    ],
  });

  // 页脚：显示页码
  const footer = new Footer({
    children: [
      new Paragraph({
        children: [new TextRun('第 '), PageNumber.CURRENT, new TextRun(' 页')],
        alignment: AlignmentType.CENTER,
      }),
    ],
  });

  // 表头标题颜色
  const headerCellColor = 'D5E8F0';
  const makeBlockTable = (phaseTitle, items) => {
    const widths = [900, 1800, 2400, 1200, 900, 2160];
    const headerRow = new TableRow({
      children: ['序号','阶段/类别','设备/型号','数量','价格区间(人民币)','备注'].map((text, i) =>
        new TableCell({
          width: { size: widths[i], type: WidthType.DXA },
          shading: { fill: headerCellColor, type: ShadingType.CLEAR },
          children: [new Paragraph({ children: [new TextRun({ text, bold: true })] })],
        })
      ),
    });
    const rows = items.map((it, idx) => [
      String(idx + 1),
      phaseTitle,
      [it.label, it.model].filter(Boolean).join(' '),
      it.qty || '',
      it.price || '',
      it.note || '',
    ]);
    const dataRows = rows.map((cols) => new TableRow({
      children: cols.map((c, j) => new TableCell({
        width: { size: widths[j], type: WidthType.DXA },
        children: [new Paragraph({ children: [new TextRun(c)] })],
      }))
    }));
    const table = new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: widths,
      rows: [headerRow, ...dataRows],
      borders: {
        top: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' },
        bottom: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' },
        left: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' },
        right: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' },
      },
    });
    return [new Paragraph({ children: [] }), table];
  };

  // 硬件数据（分阶段，整理成若干块表格）
  const blocks = [];
  const phase1 = [
    { label: '应用服务器', model: '联想 SR250 V3', qty: '1 台', price: '2~3万', note: '' },
    { label: '采集网关', model: '研华 ARK-1220L', qty: '1 台', price: '0.5~0.8万', note: '' },
    { label: '交换机', model: 'H3C S5130 24口', qty: '1 台', price: '0.3~0.5万', note: '' },
    { label: 'UPS', model: 'APC BK650', qty: '1 台', price: '0.1万', note: '' },
  ];
  blocks.push(makeBlockTable('Phase 1 MVP', phase1));

  const phase1_5 = [
    { label: 'NVR', model: '海康 DS-7816N-R2 16路', qty: '1 台', price: '0.3~0.5万', note: '' },
    { label: '硬盘', model: '希捷 4TB', qty: '2 块', price: '0.12万', note: '' },
    { label: '摄像头', model: '海康 DS-2CD2T46', qty: '4~8 台', price: '0.2~0.4万', note: '' },
  ];
  blocks.push(makeBlockTable('Phase 1.5', phase1_5));

  const phase2 = [
    { label: '服务器升级', model: 'Dell R360, Xeon Silver 4410Y/64GB', qty: '1 台', price: '4~6万', note: '' },
    { label: '网关', model: '多台', qty: '2~3 台', price: '1~2.4万', note: '' },
    { label: '冷备件', model: '', qty: '1 台', price: '0.5~0.8万', note: '' },
    { label: 'NVR', model: '海康 DS-8832N 32路', qty: '1 台', price: '0.5~0.6万', note: '' },
    { label: '硬盘', model: '8TB×4', qty: '4 块', price: '0.4万', note: '' },
    { label: '摄像头', model: '8~16 台', qty: '8~16 台', price: '0.4~0.8万', note: '' },
    { label: '交换机', model: '1~2 台', qty: '1~2 台', price: '0.3~1 万', note: '' },
  ];
  blocks.push(makeBlockTable('Phase 2', phase2));

  const phase3 = [
    { label: 'DB服务器', model: 'Dell R660, Xeon Silver 4416+/64GB/4×4TB SSD RAID10', qty: '1 台', price: '6~9万', note: '' },
    { label: '网关', model: '多台', qty: '3~5 台', price: '1.5~4万', note: '' },
    { label: '冷备件', model: '', qty: '1 台', price: '0.5~0.8万', note: '' },
    { label: 'NVR', model: '海康 DS-8864N 64路', qty: '1 台', price: '0.5~0.6万', note: '' },
    { label: '摄像头', model: '16~32 台', qty: '16~32 台', price: '0.8~1.6万', note: '' },
    { label: '交换机', model: '2~4 台', qty: '2~4 台', price: '0.6~2万', note: '' },
    { label: '机柜', model: '42U', qty: '1 台', price: '0.3万', note: '' },
  ];
  blocks.push(makeBlockTable('推广', phase3));

  // 章节正文内容（硬件表块将在文档中按顺序展示）
  const sections = [];
  // 1. 文档信息等
  sections.push(new Paragraph({ children: [new TextRun({ text: '1. 文档信息', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun('标题: 算力中心智能监控系统 (DCIM) 部署需求文档')] }));
  sections.push(new Paragraph({ children: [new TextRun('版本: V3.1.0')] }));
  sections.push(new Paragraph({ children: [new TextRun('日期: 2026-02-23')] }));
  sections.push(new Paragraph({ children: [new TextRun('作者: proecheng')] }));
  // 2. 系统概述
  sections.push(new Paragraph({ children: [new TextRun({ text: '2. 系统概述', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun('功能: 实时监控、告警管理、能源管理、3D数字孪生、资产运维、联动引擎、视频监控、多站点管理')] }));
  sections.push(new Paragraph({ children: [new TextRun('架构: Vue 3 + FastAPI + PostgreSQL/TimescaleDB + Redis + EMQX')] }));
  // 3. 软件需求
  sections.push(new Paragraph({ children: [new TextRun({ text: '3. 软件需求', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun('3.1 操作系统 - 服务器：Ubuntu 22.04 LTS / CentOS 8+ / Rocky Linux 9，网关：Ubuntu 22.04 LTS')] }));
  sections.push(new Paragraph({ children: [new TextRun('3.2 运行时 - Docker 24.0+, Docker Compose 2.20+, Python 3.11+, Node.js 18+, npm 9+')] }));
  sections.push(new Paragraph({ children: [new TextRun('3.3 数据库中间件 - timescale/timescaledb:latest-pg16(5432)、redis:7-alpine(6379)、emqx/emqx:5(1883/8083/18083)、nginx:alpine(80)')] }));
  sections.push(new Paragraph({ children: [new TextRun('3.4 后端依赖 - FastAPI 0.109.0、SQLAlchemy 2.0.25、Pydantic 2.5.3、uvicorn 0.27.0、asyncpg 0.29.0、python-jose 3.3.0、bcrypt 4.0.1、websockets 12.0、APScheduler 3.10.4、reportlab 4.0+、numpy 1.24+、httpx 0.25+、openpyxl 3.1.2')] }));
  sections.push(new Paragraph({ children: [new TextRun('3.5 前端依赖 - Vue 3.4.15、TypeScript 5.9.3、Vite 5.0.11、Element Plus 2.5.3、ECharts 5.6.0、Three.js 0.182.0、Pinia 2.1.7')] }));
  sections.push(new Paragraph({ children: [new TextRun('3.6 可选 - PaddleOCR(电费单OCR,mock降级)、PyTorch 2.0+(ML,条件加载)、MediaMTX(RTSP转码兜底)')] }));
  // 4. 硬件需求（4阶段）- 将阶段表格块插入
  blocks.forEach((bl) => {
    sections.push(bl[0]);
    sections.push(bl[1]);
  });
  // 5. 预算汇总
  sections.push(new Paragraph({ children: [new TextRun({ text: '5. 预算汇总', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun('Phase1: 3.0~4.5万，累计3.0~4.5万')] }));
  sections.push(new Paragraph({ children: [new TextRun('Phase1.5: 0.6~1.0万，累计3.6~5.5万')] }));
  sections.push(new Paragraph({ children: [new TextRun('Phase2: 7.1~11.6万，累计10.7~17.1万')] }));
  sections.push(new Paragraph({ children: [new TextRun('推广: 10.2~18.0万，累计20.9~35.1万')] }));
  // 6 网络需求	
  sections.push(new Paragraph({ children: [new TextRun({ text: '6. 网络需求', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun('1) 千兆 VLAN 隔离，独立监控网段')] }));
  sections.push(new Paragraph({ children: [new TextRun('2) MQTT TCP 1883 服务端口需求')] }));
  sections.push(new Paragraph({ children: [new TextRun('3) 多站点 VPN/专线接入')] }));
  // 7 部署架构
  sections.push(new Paragraph({ children: [new TextRun({ text: '7. 部署架构', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun('单机（Docker Compose 5 服务）')] }));
  sections.push(new Paragraph({ children: [new TextRun('标准：应用 + DB 分离')] }));
  sections.push(new Paragraph({ children: [new TextRun('高可用：双机 + 主从 + Sentinel')] }));
  // 8 验收标准
  sections.push(new Paragraph({ children: [new TextRun({ text: '8. 验收标准', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun('服务器：内存测试（memtest）+ IO 测试（fio 72h）')] }));
  sections.push(new Paragraph({ children: [new TextRun('网关：Modbus 满负荷测试 48h')] }));
  sections.push(new Paragraph({ children: [new TextRun('NVR：满路录像 24h')] }));
  sections.push(new Paragraph({ children: [new TextRun('摄像头：画质、夜视、PoE 功能测试 24h')] }));


  // 9. 数字孪生系统部署需求
  sections.push(new Paragraph({ children: [new TextRun({ text: '9. 数字孪生系统部署需求', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun({ text: '', break: 1 })] }));
  // 9.1 系统概述
  sections.push(new Paragraph({ children: [new TextRun({ text: '9.1 系统概述', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun('数字孪生子系统基于 Three.js 构建数据中心3D可视化场景，实现机房楼层、机柜排列、冷热通道、设备状态的实时三维展示。采用客户端 WebGL 渲染架构，后端提供空间拓扑数据和实时设备状态推送。')] }));
  sections.push(new Paragraph({ children: [new TextRun('核心能力：3D机房场景漫游、机柜状态实时着色（正常/告警/离线）、告警脉冲动画、热力图/气流图/功率图多图层叠加、设备点击交互与历史数据弹窗、WebGL降级到2D平面图。')] }));
  // 9.2 软件需求
  sections.push(new Paragraph({ children: [new TextRun({ text: '9.2 软件需求', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun({ text: '9.2.1 前端3D渲染引擎', bold: true })] }));
  const dtSoftFrontendItems = [
    { label: 'Three.js', version: '0.182.0', note: '3D场景渲染核心引擎，WebGL封装' },
    { label: '@types/three', version: '0.182.0', note: 'TypeScript类型定义' },
    { label: 'OrbitControls', version: '内置', note: '相机轨道控制器（旋转/缩放/平移）' },
    { label: 'WebGLRenderer', version: 'WebGL 2.0', note: '硬件加速渲染，需浏览器支持WebGL' },
    { label: 'Raycaster', version: '内置', note: '鼠标射线拾取，实现机柜点击/悬浮交互' },
    { label: 'ECharts', version: '5.6.0', note: '设备历史数据弹窗图表（已在基础依赖中）' },
  ];
  const dtSoftFrontendWidths = [2400, 1200, 5760];
  const dtSoftFrontendHeaderRow = new TableRow({
    children: ['组件/库', '版本', '用途说明'].map((text, i) =>
      new TableCell({
        width: { size: dtSoftFrontendWidths[i], type: WidthType.DXA },
        shading: { fill: headerCellColor, type: ShadingType.CLEAR },
        children: [new Paragraph({ children: [new TextRun({ text, bold: true })] })],
      })
    ),
  });
  const dtSoftFrontendDataRows = dtSoftFrontendItems.map((it) => new TableRow({
    children: [it.label, it.version, it.note].map((c, j) => new TableCell({
      width: { size: dtSoftFrontendWidths[j], type: WidthType.DXA },
      children: [new Paragraph({ children: [new TextRun(c)] })],
    }))
  }));
  sections.push(new Paragraph({ children: [] }));
  sections.push(new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: dtSoftFrontendWidths,
    rows: [dtSoftFrontendHeaderRow, ...dtSoftFrontendDataRows],
    borders: { top: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' }, bottom: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' }, left: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' }, right: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' } },
  }));
  sections.push(new Paragraph({ children: [new TextRun({ text: '9.2.2 后端数字孪生服务', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun('• FloorMapGenerator — 楼层2D/3D布局数据生成服务，支持B1制冷机房、F1~F3机房区多楼层配置')] }));
  sections.push(new Paragraph({ children: [new TextRun('• Spatial API (/api/v1/spatial) — 空间拓扑树接口，提供站点→楼层→机房→行→机柜层级数据')] }));
  sections.push(new Paragraph({ children: [new TextRun('• Floor Map API (/api/v1/floor-map) — 楼层平面图/3D场景数据接口')] }));
  sections.push(new Paragraph({ children: [new TextRun('• Bigscreen API (/api/v1/bigscreen) — 大屏布局配置接口')] }));
  sections.push(new Paragraph({ children: [new TextRun('• WebSocket (/ws/realtime) — 实时设备状态推送，5秒刷新间隔，支持机柜状态实时着色更新')] }));
  sections.push(new Paragraph({ children: [new TextRun({ text: '9.2.3 客户端浏览器要求', bold: true })] }));
  const dtBrowserItems = [
    { browser: 'Chrome / Edge', version: '90+', note: '推荐，WebGL 2.0完整支持，性能最优' },
    { browser: 'Firefox', version: '90+', note: '支持，WebGL 2.0兼容' },
    { browser: 'Safari', version: '15+', note: '支持，需macOS 12+或iOS 15+' },
    { browser: 'IE / 旧版Edge', version: '不支持', note: '无WebGL 2.0支持，自动降级到2D平面图' },
  ];
  const dtBrowserWidths = [2400, 1800, 5160];
  const dtBrowserHeaderRow = new TableRow({
    children: ['浏览器', '最低版本', '说明'].map((text, i) =>
      new TableCell({
        width: { size: dtBrowserWidths[i], type: WidthType.DXA },
        shading: { fill: headerCellColor, type: ShadingType.CLEAR },
        children: [new Paragraph({ children: [new TextRun({ text, bold: true })] })],
      })
    ),
  });
  const dtBrowserDataRows = dtBrowserItems.map((it) => new TableRow({
    children: [it.browser, it.version, it.note].map((c, j) => new TableCell({
      width: { size: dtBrowserWidths[j], type: WidthType.DXA },
      children: [new Paragraph({ children: [new TextRun(c)] })],
    }))
  }));
  sections.push(new Paragraph({ children: [] }));
  sections.push(new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: dtBrowserWidths,
    rows: [dtBrowserHeaderRow, ...dtBrowserDataRows],
    borders: { top: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' }, bottom: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' }, left: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' }, right: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' } },
  }));
  // 9.3 硬件需求
  sections.push(new Paragraph({ children: [new TextRun({ text: '9.3 硬件需求', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun({ text: '9.3.1 客户端硬件要求（大屏展示终端）', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun('数字孪生3D场景在客户端浏览器中渲染，对展示终端的GPU性能有明确要求：')] }));
  const dtClientHwItems = [
    { item: '大屏展示主机', model: '联想 ThinkCentre M75q Gen 5 / Dell OptiPlex 7020 Micro', qty: '1~2台', price: '0.5~0.8万/台', note: '指挥中心/监控室大屏驱动' },
    { item: 'GPU（集成/独立）', model: 'AMD Radeon 680M (集成) 或 NVIDIA GTX 1650+ (独立)', qty: '随主机', price: '含在主机价格中', note: 'WebGL 2.0渲染，支持1080p@60fps' },
    { item: '内存', model: 'DDR5 16GB+', qty: '随主机', price: '含在主机价格中', note: 'Three.js场景+浏览器内存需求' },
    { item: '大屏显示器', model: '55寸/65寸 4K LED拼接屏 或 商用大屏', qty: '1~4块', price: '0.3~0.8万/块', note: '指挥中心展示墙' },
    { item: '大屏控制器', model: '多屏拼接控制器（如需拼接）', qty: '0~1台', price: '0.2~0.5万', note: '4屏以上拼接时需要' },
  ];
  const dtClientHwWidths = [1200, 2700, 900, 1500, 3060];
  const dtClientHwHeaderRow = new TableRow({
    children: ['设备', '推荐型号', '数量', '价格区间', '备注'].map((text, i) =>
      new TableCell({
        width: { size: dtClientHwWidths[i], type: WidthType.DXA },
        shading: { fill: headerCellColor, type: ShadingType.CLEAR },
        children: [new Paragraph({ children: [new TextRun({ text, bold: true })] })],
      })
    ),
  });
  const dtClientHwDataRows = dtClientHwItems.map((it) => new TableRow({
    children: [it.item, it.model, it.qty, it.price, it.note].map((c, j) => new TableCell({
      width: { size: dtClientHwWidths[j], type: WidthType.DXA },
      children: [new Paragraph({ children: [new TextRun(c)] })],
    }))
  }));
  sections.push(new Paragraph({ children: [] }));
  sections.push(new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: dtClientHwWidths,
    rows: [dtClientHwHeaderRow, ...dtClientHwDataRows],
    borders: { top: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' }, bottom: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' }, left: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' }, right: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' } },
  }));
  sections.push(new Paragraph({ children: [new TextRun({ text: '9.3.2 服务端增量需求', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun('数字孪生后端为纯数据服务（空间拓扑查询+WebSocket推送），无服务端3D渲染，不需要GPU服务器。服务端增量需求如下：')] }));
  sections.push(new Paragraph({ children: [new TextRun('• WebSocket并发连接：每个大屏/客户端占用1个WebSocket长连接，建议服务器支持50+并发WebSocket')] }));
  sections.push(new Paragraph({ children: [new TextRun('• 内存增量：空间拓扑缓存约50~200MB（取决于机柜数量），已包含在Phase1服务器16GB内存规划中')] }));
  sections.push(new Paragraph({ children: [new TextRun('• 带宽增量：每个WebSocket连接约2~5KB/s（5秒推送间隔），10个客户端约20~50KB/s，影响可忽略')] }));
  sections.push(new Paragraph({ children: [new TextRun('• 存储增量：3D布局配置数据约1~5MB/站点，无3D模型文件（程序化生成几何体）')] }));
  sections.push(new Paragraph({ children: [new TextRun({ text: '9.3.3 网络要求', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun('• 大屏终端到服务器：千兆以太网，延迟<10ms（同机房部署）')] }));
  sections.push(new Paragraph({ children: [new TextRun('• WebSocket端口：8080（与主API共用），需防火墙放行')] }));
  sections.push(new Paragraph({ children: [new TextRun('• 远程访问：如需远程查看3D大屏，建议VPN接入，带宽≥10Mbps')] }));
  // 9.4 数字孪生预算汇总
  sections.push(new Paragraph({ children: [new TextRun({ text: '9.4 数字孪生预算汇总', bold: true })] }));
  const dtBudgetItems = [
    { item: '大屏展示主机', qty: '1~2台', price: '0.5~1.6万', note: '含GPU、内存' },
    { item: '大屏显示器', qty: '1~4块', price: '0.3~3.2万', note: '55寸/65寸 4K' },
    { item: '大屏控制器', qty: '0~1台', price: '0~0.5万', note: '拼接屏时需要' },
    { item: '合计', qty: '', price: '0.8~5.3万', note: '根据大屏规模浮动' },
  ];
  const dtBudgetWidths = [2400, 1800, 2400, 2760];
  const dtBudgetHeaderRow = new TableRow({
    children: ['项目', '数量', '价格区间', '备注'].map((text, i) =>
      new TableCell({
        width: { size: dtBudgetWidths[i], type: WidthType.DXA },
        shading: { fill: headerCellColor, type: ShadingType.CLEAR },
        children: [new Paragraph({ children: [new TextRun({ text, bold: true })] })],
      })
    ),
  });
  const dtBudgetDataRows = dtBudgetItems.map((it) => new TableRow({
    children: [it.item, it.qty, it.price, it.note].map((c, j) => new TableCell({
      width: { size: dtBudgetWidths[j], type: WidthType.DXA },
      children: [new Paragraph({ children: [new TextRun(c)] })],
    }))
  }));
  sections.push(new Paragraph({ children: [] }));
  sections.push(new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: dtBudgetWidths,
    rows: [dtBudgetHeaderRow, ...dtBudgetDataRows],
    borders: { top: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' }, bottom: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' }, left: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' }, right: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' } },
  }));
  // 9.5 数字孪生验收标准
  sections.push(new Paragraph({ children: [new TextRun({ text: '9.5 数字孪生验收标准', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun('• 3D场景加载：首次加载≤3秒（千兆局域网），场景切换≤1秒')] }));
  sections.push(new Paragraph({ children: [new TextRun('• 渲染帧率：1080p分辨率下≥30fps，4K分辨率下≥20fps')] }));
  sections.push(new Paragraph({ children: [new TextRun('• 机柜数量支持：单楼层≥100个机柜流畅渲染')] }));
  sections.push(new Paragraph({ children: [new TextRun('• 实时数据延迟：设备状态变更到3D场景着色更新≤6秒（含5秒推送间隔）')] }));
  sections.push(new Paragraph({ children: [new TextRun('• 告警动画：告警机柜红色脉冲动画流畅，无卡顿')] }));
  sections.push(new Paragraph({ children: [new TextRun('• 交互响应：鼠标悬浮提示≤100ms，点击弹窗≤500ms')] }));
  sections.push(new Paragraph({ children: [new TextRun('• WebGL降级：不支持WebGL的浏览器自动切换到2D平面图，无白屏')] }));
  sections.push(new Paragraph({ children: [new TextRun('• 大屏连续运行：7×24小时无内存泄漏、无崩溃（72小时压力测试）')] }));
  // 9.6 未来扩展规划
  sections.push(new Paragraph({ children: [new TextRun({ text: '9.6 未来扩展规划', bold: true })] }));
  sections.push(new Paragraph({ children: [new TextRun('当前版本采用程序化几何体（BoxGeometry）生成机柜模型，未来可扩展：')] }));
  sections.push(new Paragraph({ children: [new TextRun('• 精细3D模型：引入GLTF/GLB格式精细机柜、空调、UPS模型（需GLTFLoader，增加50~200MB静态资源）')] }));
  sections.push(new Paragraph({ children: [new TextRun('• BIM集成：导入Revit/IFC建筑模型，实现建筑级数字孪生（需IFCLoader或服务端转换）')] }));
  sections.push(new Paragraph({ children: [new TextRun('• 物理仿真：CFD气流模拟可视化（需后端计算服务器，建议GPU服务器 NVIDIA T4/A10）')] }));
  sections.push(new Paragraph({ children: [new TextRun('• VR/AR支持：WebXR接入，需VR头显设备（Meta Quest 3等，约0.3~0.5万/台）')] }));
  sections.push(new Paragraph({ children: [new TextRun('• 多站点3D漫游：跨站点3D场景切换，需CDN加速3D资源分发')] }));

  // 构建文档
  const doc = new Document({ sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 720, bottom: 720, left: 720, right: 720 } } }, headers: { default: header }, footers: { default: footer }, children: sections }] });

  // 生成文档
  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(outputPath, buffer);
  console.log(`文档已生成: ${outputPath}`);
}

generate().catch((err) => {
  console.error('生成文档时出错：', err);
  process.exit(1);
});
