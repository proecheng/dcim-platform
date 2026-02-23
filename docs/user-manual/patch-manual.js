// patch-manual.js - 将5个详细版页面内容合并到 generate-user-manual.js
// 用法: node docs/user-manual/patch-manual.js

const fs = require('fs');
const path = require('path');

const BASE = path.resolve(__dirname);
const MAIN_FILE = path.join(BASE, 'generate-user-manual.js');

// 读取原始文件
let content = fs.readFileSync(MAIN_FILE, 'utf-8');

// 读取各enriched文件的函数体
function readEnrichedFile(filename) {
  return fs.readFileSync(path.join(BASE, filename), 'utf-8');
}

const enriched_5_1_6 = readEnrichedFile('enriched-5-1-6.js');
const enriched_7_1_1 = readEnrichedFile('enriched-7-1-1.js');
const enriched_7_2_1 = readEnrichedFile('enriched-7-2-1.js');
const enriched_7_3_1 = readEnrichedFile('enriched-7-3-1.js');
const enriched_ch6 = readEnrichedFile('enriched-chapter6.js');

// ============================================================
// 1. 替换 chapter6() - 整个函数替换
// ============================================================
const ch6Start = content.indexOf("// ========== 第6章 告警中心 ==========");
const ch6End = content.indexOf("// ========== 第7章 管理域 ==========");
if (ch6Start === -1 || ch6End === -1) {
  console.error('找不到 chapter6 的边界标记');
  process.exit(1);
}
content = content.substring(0, ch6Start) + enriched_ch6 + '\n\n' + content.substring(ch6End);
console.log('✓ 替换 chapter6() 完成');

// ============================================================
// 2. 替换 5.1.6 配电拓扑 → 三相接线配置
//    策略: 从 powerPages 数组中移除最后一个元素(5.1.6)，
//    然后在 forEach 循环后插入 enriched_section_5_1_6() 调用
// ============================================================

// 移除 powerPages 中的 5.1.6 条目
const old516 = "    { h3: '5.1.6 配电拓扑'";
const idx516 = content.indexOf(old516);
if (idx516 === -1) {
  console.error('找不到 5.1.6 配电拓扑条目');
  process.exit(1);
}
// 找到这个条目的结尾 (下一个 },\n 或 },\n  ];)
const entry516End = content.indexOf(' },\n  ];\n', idx516);
if (entry516End === -1) {
  console.error('找不到 5.1.6 条目结尾');
  process.exit(1);
}
// 删除从 old516 开始到 },\n 的内容（包括前面的逗号和换行）
const beforeEntry = content.lastIndexOf('\n', idx516 - 1);
content = content.substring(0, beforeEntry) + '\n  ];\n' + content.substring(entry516End + ' },\n  ];\n'.length);
console.log('✓ 从 powerPages 移除 5.1.6 条目');

// 在 powerPages forEach 循环后、sections.push(BREAK()) 前插入 enriched 内容
// 找到 "  sections.push(BREAK());\n\n  // 5.2 制冷监控"
const breakBeforeCooling = '  sections.push(BREAK());\n\n  // 5.2 制冷监控';
const idxBreakCooling = content.indexOf(breakBeforeCooling);
if (idxBreakCooling === -1) {
  console.error('找不到 5.2 制冷监控前的 BREAK');
  process.exit(1);
}
// 在 BREAK() 前插入 enriched_section_5_1_6 函数定义和调用
const insert516 = `
  // === 5.1.6 三相接线配置（详细版）===
  sections.push(...enriched_section_5_1_6());

`;
content = content.substring(0, idxBreakCooling) + insert516 + content.substring(idxBreakCooling);
console.log('✓ 插入 enriched_section_5_1_6() 调用');

// ============================================================
// 3. 替换 7.1.1 能效监控
// ============================================================
const old711 = "    { h3: '7.1.1 能效监控'";
const idx711 = content.indexOf(old711);
if (idx711 === -1) {
  console.error('找不到 7.1.1 能效监控条目');
  process.exit(1);
}
// 找到条目结尾
const entry711End = content.indexOf(' },\n', idx711);
// 找到条目开始前的换行
const before711 = content.lastIndexOf('\n', idx711 - 1);
// 替换为空（从数组中移除）
content = content.substring(0, before711 + 1) + content.substring(entry711End + ' },\n'.length);
console.log('✓ 从 energyPages 移除 7.1.1 条目');

// 在 energyPages forEach 前插入 enriched 调用
const energyForEach = '  energyPages.forEach(page => {';
const idxEnergyForEach = content.indexOf(energyForEach);
if (idxEnergyForEach === -1) {
  console.error('找不到 energyPages.forEach');
  process.exit(1);
}
const insert711 = `  // === 7.1.1 能效监控（详细版）===
  sections.push(...enriched_section_7_1_1());

`;
content = content.substring(0, idxEnergyForEach) + insert711 + content.substring(idxEnergyForEach);
console.log('✓ 插入 enriched_section_7_1_1() 调用');

// ============================================================
// 4. 替换 7.2.1 资产台账
// ============================================================
const old721 = "    { h3: '7.2.1 资产台账'";
const idx721 = content.indexOf(old721);
if (idx721 === -1) {
  console.error('找不到 7.2.1 资产台账条目');
  process.exit(1);
}
const entry721End = content.indexOf(' },\n', idx721);
const before721 = content.lastIndexOf('\n', idx721 - 1);
content = content.substring(0, before721 + 1) + content.substring(entry721End + ' },\n'.length);
console.log('✓ 从 assetPages 移除 7.2.1 条目');

// 在 assetPages forEach 前插入
const assetForEach = '  assetPages.forEach(page => {';
const idxAssetForEach = content.indexOf(assetForEach);
if (idxAssetForEach === -1) {
  console.error('找不到 assetPages.forEach');
  process.exit(1);
}
const insert721 = `  // === 7.2.1 资产台账（详细版）===
  sections.push(...enriched_section_7_2_1());

`;
content = content.substring(0, idxAssetForEach) + insert721 + content.substring(idxAssetForEach);
console.log('✓ 插入 enriched_section_7_2_1() 调用');

// ============================================================
// 5. 替换 7.3.1 工单管理
// ============================================================
const old731 = "    { h3: '7.3.1 工单管理'";
const idx731 = content.indexOf(old731);
if (idx731 === -1) {
  console.error('找不到 7.3.1 工单管理条目');
  process.exit(1);
}
const entry731End = content.indexOf(' },\n', idx731);
const before731 = content.lastIndexOf('\n', idx731 - 1);
content = content.substring(0, before731 + 1) + content.substring(entry731End + ' },\n'.length);
console.log('✓ 从 opsPages 移除 7.3.1 条目');

// 在 opsPages forEach 前插入
const opsForEach = '  opsPages.forEach(page => {';
const idxOpsForEach = content.indexOf(opsForEach);
if (idxOpsForEach === -1) {
  console.error('找不到 opsPages.forEach');
  process.exit(1);
}
const insert731 = `  // === 7.3.1 工单管理（详细版）===
  sections.push(...enriched_section_7_3_1());

`;
content = content.substring(0, idxOpsForEach) + insert731 + content.substring(idxOpsForEach);
console.log('✓ 插入 enriched_section_7_3_1() 调用');

// ============================================================
// 6. 在文件顶部（工具函数之后）插入所有 enriched 函数定义
// ============================================================
const insertPoint = '// ========== 封面页 ==========';
const idxInsert = content.indexOf(insertPoint);
if (idxInsert === -1) {
  console.error('找不到封面页标记');
  process.exit(1);
}

const allEnrichedFunctions = `
// ========== 详细版页面函数（基于 Vue 源码分析）==========

${enriched_5_1_6}

${enriched_7_1_1}

${enriched_7_2_1}

${enriched_7_3_1}

`;

content = content.substring(0, idxInsert) + allEnrichedFunctions + content.substring(idxInsert);
console.log('✓ 插入所有 enriched 函数定义');

// ============================================================
// 写入结果
// ============================================================
fs.writeFileSync(MAIN_FILE, content, 'utf-8');
console.log('\n✅ 补丁完成！generate-user-manual.js 已更新。');
console.log('文件大小: ' + (Buffer.byteLength(content, 'utf-8') / 1024).toFixed(1) + ' KB');
console.log('\n下一步: node docs/user-manual/generate-user-manual.js');
