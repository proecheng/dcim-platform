const pptxgen = require('pptxgenjs');

async function createPresentation() {
    const pptx = new pptxgen();
    pptx.layout = 'LAYOUT_16x9';
    pptx.author = 'Claude';
    pptx.title = '算力中心智能监控系统';
    pptx.subject = 'V3.2 技术方案汇报';

    // 颜色定义 (不带#号，仅6位RGB)
    const colors = {
        bgPrimary: '0a1628',
        bgSecondary: '0d1b2a',
        bgTertiary: '112240',
        bgCard: '1a2a4a',
        bgCardLight: '243858',
        primary: '1890ff',
        primaryLight: '3da5ff',
        accent: '00d4ff',
        textPrimary: 'ffffff',
        textSecondary: 'e0e0e0',
        textMuted: 'a0a0a0',
        warning: 'faad14',
        success: '52c41a',
        successLight: '2d5a14'
    };

    // ========== Slide 1: 标题页 ==========
    let slide = pptx.addSlide();
    slide.background = { color: colors.bgPrimary };

    slide.addText('算力中心智能监控系统', {
        x: 0, y: 2.0, w: '100%', h: 1,
        fontSize: 44, bold: true, color: colors.accent,
        align: 'center', fontFace: 'Arial'
    });

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 3.8, y: 3.1, w: 2.4, h: 0.06,
        fill: { color: colors.primary }
    });

    slide.addText('Intelligent Computing Center Monitoring System', {
        x: 0, y: 3.3, w: '100%', h: 0.5,
        fontSize: 20, color: colors.textSecondary,
        align: 'center', fontFace: 'Arial'
    });

    slide.addText('V3.2 技术方案汇报', {
        x: 0, y: 4.0, w: '100%', h: 0.5,
        fontSize: 16, color: colors.textMuted,
        align: 'center', fontFace: 'Arial'
    });

    // ========== Slide 2: 系统核心功能模块 ==========
    slide = pptx.addSlide();
    slide.background = { color: colors.bgPrimary };

    // Header
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0, w: 10, h: 0.9,
        fill: { color: colors.bgTertiary }
    });
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0.88, w: 10, h: 0.04,
        fill: { color: colors.primary }
    });
    slide.addText('系统核心功能模块', {
        x: 0.5, y: 0.25, w: 9, h: 0.5,
        fontSize: 26, bold: true, color: colors.accent, fontFace: 'Arial'
    });

    // 左侧模块
    const leftModules = [
        { title: '动力监控', desc: 'UPS/配电/电池/发电机/ATS/列头柜' },
        { title: '环境监控', desc: '温湿度/空调/漏水/新风/消防' },
        { title: '安防监控', desc: '门禁/视频/消防/防盗' },
        { title: '资产管理', desc: '全生命周期管理/盘点/追溯' }
    ];

    leftModules.forEach((mod, i) => {
        const y = 1.2 + i * 1.1;
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: 0.5, y: y, w: 4.3, h: 0.95,
            fill: { color: colors.bgCard },
            line: { color: colors.primary, width: 0, dashType: 'solid' }
        });
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: 0.5, y: y, w: 0.08, h: 0.95,
            fill: { color: colors.primary }
        });
        slide.addText(mod.title, {
            x: 0.75, y: y + 0.15, w: 4, h: 0.35,
            fontSize: 16, bold: true, color: colors.accent, fontFace: 'Arial'
        });
        slide.addText(mod.desc, {
            x: 0.75, y: y + 0.5, w: 4, h: 0.35,
            fontSize: 12, color: colors.textSecondary, fontFace: 'Arial'
        });
    });

    // 右侧模块
    const rightModules = [
        { title: '容量管理', desc: '空间/电力/制冷/承重/网络' },
        { title: '能效管理', desc: 'PUE/能耗分项/碳排放/节能' },
        { title: '运维管理', desc: '工单/巡检/维保/变更/值班' },
        { title: '核心优势', desc: '用电管理 + 数字孪生3D可视化', highlight: true }
    ];

    rightModules.forEach((mod, i) => {
        const y = 1.2 + i * 1.1;
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: 5.2, y: y, w: 4.3, h: 0.95,
            fill: { color: colors.bgCard }
        });
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: 5.2, y: y, w: 0.08, h: 0.95,
            fill: { color: mod.highlight ? colors.warning : colors.primary }
        });
        slide.addText(mod.title, {
            x: 5.45, y: y + 0.15, w: 4, h: 0.35,
            fontSize: 16, bold: true, color: mod.highlight ? colors.warning : colors.accent, fontFace: 'Arial'
        });
        slide.addText(mod.desc, {
            x: 5.45, y: y + 0.5, w: 4, h: 0.35,
            fontSize: 12, color: colors.textSecondary, fontFace: 'Arial'
        });
    });

    // ========== Slide 3: 深色主题配色方案 ==========
    slide = pptx.addSlide();
    slide.background = { color: colors.bgPrimary };

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0, w: 10, h: 0.9,
        fill: { color: colors.bgTertiary }
    });
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0.88, w: 10, h: 0.04,
        fill: { color: colors.primary }
    });
    slide.addText('深色主题配色方案', {
        x: 0.5, y: 0.25, w: 9, h: 0.5,
        fontSize: 26, bold: true, color: colors.accent, fontFace: 'Arial'
    });

    // 左侧内容
    slide.addText('设计理念', {
        x: 0.5, y: 1.1, w: 4.5, h: 0.4,
        fontSize: 18, bold: true, color: colors.primary, fontFace: 'Arial'
    });
    slide.addText('采用深蓝科技风配色，营造专业监控中心氛围。强制覆盖Element Plus默认浅色变量，确保全局深色一致性。', {
        x: 0.5, y: 1.5, w: 4.5, h: 0.8,
        fontSize: 12, color: colors.textSecondary, fontFace: 'Arial'
    });

    slide.addText('核心改进', {
        x: 0.5, y: 2.4, w: 4.5, h: 0.4,
        fontSize: 18, bold: true, color: colors.primary, fontFace: 'Arial'
    });

    const improvements = [
        '1. 强制 color-scheme: dark 暗色模式',
        '2. 提高文字亮度确保可读性',
        '3. 组件级 !important 覆盖',
        '4. ECharts深色主题配置'
    ];
    improvements.forEach((item, i) => {
        slide.addText(item, {
            x: 0.5, y: 2.8 + i * 0.4, w: 4.5, h: 0.35,
            fontSize: 12, color: colors.textSecondary, fontFace: 'Arial'
        });
    });

    // 右侧颜色表
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 5.3, y: 1.1, w: 4.2, h: 3.8,
        fill: { color: colors.bgCardLight }
    });

    const colorList = [
        { name: '主背景', value: '#0a1628', color: '0a1628', border: true },
        { name: '三级背景', value: '#112240', color: '112240' },
        { name: '卡片背景', value: '#1a2a4a', color: '1a2a4a' },
        { name: '强调色', value: '#00d4ff', color: '00d4ff' },
        { name: '主要文字', value: '#ffffff', color: 'ffffff' }
    ];

    colorList.forEach((c, i) => {
        const y = 1.3 + i * 0.7;
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: 5.5, y: y, w: 0.8, h: 0.45,
            fill: { color: c.color },
            line: c.border ? { color: colors.primary, width: 1 } : undefined
        });
        slide.addText(c.name, {
            x: 6.45, y: y, w: 1.5, h: 0.45,
            fontSize: 12, color: colors.textMuted, fontFace: 'Arial', valign: 'middle'
        });
        slide.addText(c.value, {
            x: 8.0, y: y, w: 1.3, h: 0.45,
            fontSize: 12, color: colors.accent, fontFace: 'Arial', valign: 'middle'
        });
    });

    // ========== Slide 4: 数字孪生大屏系统 ==========
    slide = pptx.addSlide();
    slide.background = { color: colors.bgPrimary };

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0, w: 10, h: 0.9,
        fill: { color: colors.bgTertiary }
    });
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0.88, w: 10, h: 0.04,
        fill: { color: colors.primary }
    });
    slide.addText('数字孪生大屏系统', {
        x: 0.5, y: 0.25, w: 9, h: 0.5,
        fontSize: 26, bold: true, color: colors.accent, fontFace: 'Arial'
    });

    // 左侧功能特性
    slide.addText('功能特性', {
        x: 0.5, y: 1.1, w: 4.5, h: 0.35,
        fontSize: 16, bold: true, color: colors.primary, fontFace: 'Arial'
    });

    const features = [
        { title: '真实数据对接', desc: '对接实时数据API，环境/能源/告警/设备' },
        { title: '3D可视化', desc: 'Three.js实现，热力图/设备状态/告警气泡' },
        { title: '场景模式', desc: '支持自动巡航、手动导航、逐级下探' },
        { title: '便捷导航', desc: '侧边栏入口 + 仪表盘快捷操作' }
    ];

    features.forEach((f, i) => {
        const y = 1.5 + i * 0.9;
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: 0.5, y: y, w: 4.3, h: 0.75,
            fill: { color: colors.bgCard }
        });
        slide.addText(f.title, {
            x: 0.7, y: y + 0.1, w: 4, h: 0.3,
            fontSize: 13, bold: true, color: colors.accent, fontFace: 'Arial'
        });
        slide.addText(f.desc, {
            x: 0.7, y: y + 0.4, w: 4, h: 0.3,
            fontSize: 11, color: colors.textSecondary, fontFace: 'Arial'
        });
    });

    // 右侧数据流架构
    slide.addText('数据流架构', {
        x: 5.2, y: 1.1, w: 4.5, h: 0.35,
        fontSize: 16, bold: true, color: colors.primary, fontFace: 'Arial'
    });

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 5.2, y: 1.5, w: 4.3, h: 1.6,
        fill: { color: colors.primaryLight },
        line: { color: colors.primary, width: 1 }
    });
    slide.addText('API数据源', {
        x: 5.4, y: 1.6, w: 4, h: 0.3,
        fontSize: 12, bold: true, color: colors.accent, fontFace: 'Arial'
    });
    const apis = ['/api/v1/realtime/summary', '/api/v1/realtime', '/api/v1/alarms/active', '/api/v1/realtime/energy-dashboard'];
    apis.forEach((api, i) => {
        slide.addText(api, {
            x: 5.4, y: 1.95 + i * 0.28, w: 4, h: 0.25,
            fontSize: 10, color: colors.textMuted, fontFace: 'Arial'
        });
    });

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 5.2, y: 3.25, w: 4.3, h: 1.3,
        fill: { color: colors.primaryLight },
        line: { color: colors.primary, width: 1 }
    });
    slide.addText('场景层级导航', {
        x: 5.4, y: 3.35, w: 4, h: 0.3,
        fontSize: 12, bold: true, color: colors.accent, fontFace: 'Arial'
    });
    slide.addText('园区外观 → 建筑楼层', {
        x: 5.4, y: 3.7, w: 4, h: 0.25,
        fontSize: 10, color: colors.textMuted, fontFace: 'Arial'
    });
    slide.addText('机房内部 → 机柜U位', {
        x: 5.4, y: 3.95, w: 4, h: 0.25,
        fontSize: 10, color: colors.textMuted, fontFace: 'Arial'
    });
    slide.addText('设备详情 → 实时数据', {
        x: 5.4, y: 4.2, w: 4, h: 0.25,
        fontSize: 10, color: colors.textMuted, fontFace: 'Arial'
    });

    // ========== Slide 5: 模拟数据系统 ==========
    slide = pptx.addSlide();
    slide.background = { color: colors.bgPrimary };

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0, w: 10, h: 0.9,
        fill: { color: colors.bgTertiary }
    });
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0.88, w: 10, h: 0.04,
        fill: { color: colors.primary }
    });
    slide.addText('模拟数据系统 - 大楼布局', {
        x: 0.5, y: 0.25, w: 9, h: 0.5,
        fontSize: 26, bold: true, color: colors.accent, fontFace: 'Arial'
    });

    slide.addText('三层算力中心大楼结构', {
        x: 0.5, y: 1.05, w: 9, h: 0.35,
        fontSize: 16, bold: true, color: colors.primary, fontFace: 'Arial'
    });

    // 楼层卡片
    const floors = [
        { name: 'B1 地下制冷机房', items: ['冷水机组 x2', '冷却塔 x2', '水泵 x4'] },
        { name: 'F1 机房区A', items: ['机柜 20台', 'UPS x2 / 空调 x4', '配电柜 / PDU'] },
        { name: 'F2 机房区B', items: ['机柜 15台', 'UPS x2 / 空调 x4', '配电柜 / PDU'] },
        { name: 'F3 办公监控', items: ['机柜 8台', 'UPS x1 / 空调 x2', '监控中心 / 办公区'] }
    ];

    floors.forEach((floor, i) => {
        const x = 0.5 + i * 2.35;
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: x, y: 1.5, w: 2.2, h: 1.6,
            fill: { color: colors.bgCard }
        });
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: x, y: 1.5, w: 2.2, h: 0.06,
            fill: { color: colors.primary }
        });
        slide.addText(floor.name, {
            x: x + 0.1, y: 1.6, w: 2, h: 0.35,
            fontSize: 11, bold: true, color: colors.accent, fontFace: 'Arial'
        });
        floor.items.forEach((item, j) => {
            slide.addText(item, {
                x: x + 0.1, y: 2.0 + j * 0.32, w: 2, h: 0.3,
                fontSize: 10, color: colors.textSecondary, fontFace: 'Arial'
            });
        });
    });

    // 统计卡片
    const stats = [
        { value: '330', label: '总监控点位' },
        { value: '253', label: 'AI模拟量输入' },
        { value: '57', label: 'DI开关量输入' },
        { value: '20', label: 'AO/DO输出' }
    ];

    stats.forEach((stat, i) => {
        const x = 0.5 + i * 2.35;
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: x, y: 3.4, w: 2.2, h: 1.2,
            fill: { color: colors.bgCardLight },
            line: { color: colors.primary, width: 1 }
        });
        slide.addText(stat.value, {
            x: x, y: 3.55, w: 2.2, h: 0.6,
            fontSize: 32, bold: true, color: colors.accent, fontFace: 'Arial', align: 'center'
        });
        slide.addText(stat.label, {
            x: x, y: 4.15, w: 2.2, h: 0.35,
            fontSize: 11, color: colors.textMuted, fontFace: 'Arial', align: 'center'
        });
    });

    // ========== Slide 6: 容量管理与运维管理 ==========
    slide = pptx.addSlide();
    slide.background = { color: colors.bgPrimary };

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0, w: 10, h: 0.9,
        fill: { color: colors.bgTertiary }
    });
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0.88, w: 10, h: 0.04,
        fill: { color: colors.primary }
    });
    slide.addText('容量管理与运维管理模块', {
        x: 0.5, y: 0.25, w: 9, h: 0.5,
        fontSize: 26, bold: true, color: colors.accent, fontFace: 'Arial'
    });

    // 左侧 - 容量管理
    slide.addText('容量管理 (Phase 15)', {
        x: 0.5, y: 1.1, w: 4.5, h: 0.35,
        fontSize: 16, bold: true, color: colors.primary, fontFace: 'Arial'
    });

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0.5, y: 1.5, w: 4.3, h: 1.4,
        fill: { color: colors.bgCard }
    });
    slide.addText('四维容量监控', {
        x: 0.7, y: 1.6, w: 4, h: 0.3,
        fontSize: 13, bold: true, color: colors.accent, fontFace: 'Arial'
    });
    slide.addText('空间容量 | 电力容量 | 制冷容量 | 承重容量', {
        x: 0.7, y: 1.95, w: 4, h: 0.25,
        fontSize: 10, color: colors.accent, fontFace: 'Arial'
    });
    slide.addText('使用率 >80% 警告，>95% 严重', {
        x: 0.7, y: 2.5, w: 4, h: 0.25,
        fontSize: 11, color: colors.textSecondary, fontFace: 'Arial'
    });

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0.5, y: 3.0, w: 4.3, h: 1.4,
        fill: { color: colors.bgCard }
    });
    slide.addText('容量规划功能', {
        x: 0.7, y: 3.1, w: 4, h: 0.3,
        fontSize: 13, bold: true, color: colors.accent, fontFace: 'Arial'
    });
    slide.addText('新设备上架可行性评估\n自动检查资源可用性\n返回feasible状态和issues列表', {
        x: 0.7, y: 3.45, w: 4, h: 0.9,
        fontSize: 11, color: colors.textSecondary, fontFace: 'Arial'
    });

    // 右侧 - 运维管理
    slide.addText('运维管理 (Phase 16)', {
        x: 5.2, y: 1.1, w: 4.5, h: 0.35,
        fontSize: 16, bold: true, color: colors.primary, fontFace: 'Arial'
    });

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 5.2, y: 1.5, w: 4.3, h: 1.7,
        fill: { color: colors.bgCard }
    });
    slide.addText('工单管理', {
        x: 5.4, y: 1.6, w: 4, h: 0.3,
        fontSize: 13, bold: true, color: colors.accent, fontFace: 'Arial'
    });
    slide.addText('编号: WO-YYYYMMDD-XXX\n类型: 故障/维护/变更/其他', {
        x: 5.4, y: 1.95, w: 4, h: 0.5,
        fontSize: 11, color: colors.textSecondary, fontFace: 'Arial'
    });
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 5.4, y: 2.6, w: 3.9, h: 0.45,
        fill: { color: colors.successLight },
        line: { color: colors.success, width: 1 }
    });
    slide.addText('pending → assigned → processing → completed', {
        x: 5.5, y: 2.7, w: 3.8, h: 0.3,
        fontSize: 9, color: colors.textMuted, fontFace: 'Arial'
    });

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 5.2, y: 3.3, w: 4.3, h: 1.1,
        fill: { color: colors.bgCard }
    });
    slide.addText('巡检 + 知识库', {
        x: 5.4, y: 3.4, w: 4, h: 0.3,
        fontSize: 13, bold: true, color: colors.accent, fontFace: 'Arial'
    });
    slide.addText('巡检计划/任务自动生成\n知识库分类管理/全文搜索', {
        x: 5.4, y: 3.75, w: 4, h: 0.5,
        fontSize: 11, color: colors.textSecondary, fontFace: 'Arial'
    });

    // ========== Slide 7: 后端架构设计 ==========
    slide = pptx.addSlide();
    slide.background = { color: colors.bgPrimary };

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0, w: 10, h: 0.9,
        fill: { color: colors.bgTertiary }
    });
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0.88, w: 10, h: 0.04,
        fill: { color: colors.primary }
    });
    slide.addText('后端架构设计', {
        x: 0.5, y: 0.25, w: 9, h: 0.5,
        fontSize: 26, bold: true, color: colors.accent, fontFace: 'Arial'
    });

    slide.addText('分层架构', {
        x: 0.5, y: 1.05, w: 9, h: 0.35,
        fontSize: 16, bold: true, color: colors.primary, fontFace: 'Arial'
    });

    // 架构层
    const layers = [
        { name: 'API网关层', items: ['FastAPI框架', '认证中间件', '权限校验', '请求日志', '限流/异常/CORS'] },
        { name: '业务服务层', items: ['认证服务', '点位服务', '采集服务', '告警服务', 'WebSocket推送'] },
        { name: '数据访问层', items: ['UserRepo', 'PointRepo', 'AlarmRepo', 'HistoryRepo', 'ConfigRepo'] },
        { name: '数据存储层', items: ['SQLite/MySQL', '内存缓存', '文件存储', '报表/导出', ''] }
    ];

    layers.forEach((layer, i) => {
        const x = 0.5 + i * 2.35;
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: x, y: 1.45, w: 2.2, h: 2.0,
            fill: { color: colors.bgCard }
        });
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: x, y: 1.45, w: 0.06, h: 2.0,
            fill: { color: colors.primary }
        });
        slide.addText(layer.name, {
            x: x + 0.15, y: 1.55, w: 2, h: 0.3,
            fontSize: 12, bold: true, color: colors.accent, fontFace: 'Arial'
        });
        layer.items.forEach((item, j) => {
            if (item) {
                slide.addText(item, {
                    x: x + 0.15, y: 1.9 + j * 0.28, w: 2, h: 0.25,
                    fontSize: 10, color: colors.textSecondary, fontFace: 'Arial'
                });
            }
        });
    });

    // 技术栈
    const techStack = [
        { name: 'Vue 3', desc: 'TypeScript前端' },
        { name: 'FastAPI', desc: 'Python后端' },
        { name: 'Three.js', desc: '3D可视化' },
        { name: 'WebSocket', desc: '实时推送' },
        { name: 'ECharts', desc: '图表组件' }
    ];

    techStack.forEach((tech, i) => {
        const x = 0.5 + i * 1.9;
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: x, y: 3.7, w: 1.75, h: 0.9,
            fill: { color: colors.bgCardLight },
            line: { color: colors.primary, width: 1 }
        });
        slide.addText(tech.name, {
            x: x, y: 3.8, w: 1.75, h: 0.4,
            fontSize: 13, bold: true, color: colors.accent, fontFace: 'Arial', align: 'center'
        });
        slide.addText(tech.desc, {
            x: x, y: 4.2, w: 1.75, h: 0.3,
            fontSize: 9, color: colors.textMuted, fontFace: 'Arial', align: 'center'
        });
    });

    // ========== Slide 8: 监控点位设计 ==========
    slide = pptx.addSlide();
    slide.background = { color: colors.bgPrimary };

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0, w: 10, h: 0.9,
        fill: { color: colors.bgTertiary }
    });
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0, y: 0.88, w: 10, h: 0.04,
        fill: { color: colors.primary }
    });
    slide.addText('监控点位设计', {
        x: 0.5, y: 0.25, w: 9, h: 0.5,
        fontSize: 26, bold: true, color: colors.accent, fontFace: 'Arial'
    });

    slide.addText('点位类型定义', {
        x: 0.5, y: 1.05, w: 9, h: 0.35,
        fontSize: 16, bold: true, color: colors.primary, fontFace: 'Arial'
    });

    // 点位类型卡片
    const pointTypes = [
        { code: 'AI', name: 'Analog Input', desc: '模拟量输入\n温度/电压/功率' },
        { code: 'DI', name: 'Digital Input', desc: '开关量输入\n门禁/报警状态' },
        { code: 'AO', name: 'Analog Output', desc: '模拟量输出\n设定温度/风速' },
        { code: 'DO', name: 'Digital Output', desc: '开关量输出\n设备启停控制' }
    ];

    pointTypes.forEach((pt, i) => {
        const x = 0.5 + i * 2.35;
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: x, y: 1.45, w: 2.2, h: 1.5,
            fill: { color: colors.bgCard }
        });
        slide.addText(pt.code, {
            x: x, y: 1.55, w: 2.2, h: 0.45,
            fontSize: 18, bold: true, color: colors.accent, fontFace: 'Arial', align: 'center'
        });
        slide.addText(pt.name, {
            x: x, y: 2.0, w: 2.2, h: 0.3,
            fontSize: 10, color: colors.textMuted, fontFace: 'Arial', align: 'center'
        });
        slide.addText(pt.desc, {
            x: x, y: 2.35, w: 2.2, h: 0.55,
            fontSize: 10, color: colors.textSecondary, fontFace: 'Arial', align: 'center'
        });
    });

    // 编码规则
    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 0.5, y: 3.15, w: 9, h: 1.4,
        fill: { color: colors.bgCard },
        line: { color: colors.primary, width: 1 }
    });
    slide.addText('点位编码规则', {
        x: 0.7, y: 3.25, w: 8.5, h: 0.35,
        fontSize: 13, bold: true, color: colors.warning, fontFace: 'Arial'
    });
    slide.addText('{区域代码}_{设备类型}_{点位类型}_{序号}', {
        x: 0.7, y: 3.65, w: 8.5, h: 0.3,
        fontSize: 12, color: colors.textSecondary, fontFace: 'Courier New'
    });
    slide.addText('A1_TH_AI_001  → A1区-温湿度-模拟输入-001号', {
        x: 0.7, y: 4.0, w: 8.5, h: 0.25,
        fontSize: 11, color: colors.success, fontFace: 'Courier New'
    });
    slide.addText('A1_UPS_DI_001 → A1区-UPS-开关输入-001号', {
        x: 0.7, y: 4.3, w: 8.5, h: 0.25,
        fontSize: 11, color: colors.success, fontFace: 'Courier New'
    });

    // ========== Slide 9: Thank You ==========
    slide = pptx.addSlide();
    slide.background = { color: colors.bgPrimary };

    slide.addText('Thank You', {
        x: 0, y: 1.8, w: '100%', h: 0.8,
        fontSize: 40, bold: true, color: colors.accent,
        align: 'center', fontFace: 'Arial'
    });

    slide.addShape(pptx.shapes.RECTANGLE, {
        x: 4.0, y: 2.7, w: 2, h: 0.06,
        fill: { color: colors.primary }
    });

    slide.addText('算力中心智能监控系统 V3.2', {
        x: 0, y: 2.9, w: '100%', h: 0.5,
        fontSize: 18, color: colors.textSecondary,
        align: 'center', fontFace: 'Arial'
    });

    slide.addText('用电管理特色 + 数字孪生3D可视化', {
        x: 0, y: 3.4, w: '100%', h: 0.4,
        fontSize: 15, color: colors.warning,
        align: 'center', fontFace: 'Arial'
    });

    // 底部特性卡片
    const endFeatures = ['330个监控点位', '七大核心模块', '深色科技主题'];
    endFeatures.forEach((feat, i) => {
        const x = 2 + i * 2.2;
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: x, y: 4.0, w: 2, h: 0.7,
            fill: { color: colors.bgCard }
        });
        slide.addShape(pptx.shapes.RECTANGLE, {
            x: x, y: 4.0, w: 2, h: 0.05,
            fill: { color: colors.primary }
        });
        slide.addText(feat, {
            x: x, y: 4.2, w: 2, h: 0.4,
            fontSize: 12, color: colors.textSecondary,
            align: 'center', fontFace: 'Arial'
        });
    });

    // 保存文件
    const outputPath = 'D:/mytest1/workspace/算力中心智能监控系统-V3.2.pptx';
    await pptx.writeFile({ fileName: outputPath });
    console.log(`Presentation saved to: ${outputPath}`);
}

createPresentation().catch(err => {
    console.error('Failed to create presentation:', err);
    process.exit(1);
});
