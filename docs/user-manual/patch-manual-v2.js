// patch-manual-v2.js — Comprehensive patcher to integrate ALL enriched batch files
// Usage: node D:/mytest1/docs/user-manual/patch-manual-v2.js
const fs = require('fs');
const path = require('path');

const DIR = path.resolve(__dirname);
const MAIN = path.join(DIR, 'generate-user-manual.js');
const BAK = MAIN + '.bak';

// Backup
fs.copyFileSync(MAIN, BAK);
console.log('Backup created:', BAK);

let src = fs.readFileSync(MAIN, 'utf-8');

// === Step 1: Read all batch files, strip module.exports ===
const batchFiles = [
  'enriched-batch1-power.js',
  'enriched-batch2-cooling.js',
  'enriched-batch3-env-security.js',
  'enriched-batch5-energy-ops.js',
  'enriched-batch7-config.js',
  'enriched-batch8-system-bigscreen.js',
];

let allFunctions = '\n// ========== Enriched batch functions (auto-injected by patch-manual-v2.js) ==========\n\n';
for (const f of batchFiles) {
  let content = fs.readFileSync(path.join(DIR, f), 'utf-8');
  // Strip module.exports block
  content = content.replace(/module\.exports\s*=\s*\{[^}]*\};?/gs, '');
  // Strip leading comments (first 3 lines typically)
  const lines = content.split('\n');
  const firstFuncIdx = lines.findIndex(l => l.startsWith('function '));
  if (firstFuncIdx > 0) {
    content = lines.slice(firstFuncIdx).join('\n');
  }
  allFunctions += `// --- from ${f} ---\n` + content.trim() + '\n\n';
}

// === Step 2: Inject function definitions before coverPage ===
const coverMarker = '// ========== \u5c01\u9762\u9875 ==========';
if (!src.includes(coverMarker)) { console.error('Cannot find cover page marker'); process.exit(1); }
src = src.replace(coverMarker, allFunctions + '\n' + coverMarker);
console.log('Injected all enriched function definitions');

// === Step 3: Helper to replace array+forEach blocks ===
function replaceArrayAndForEach(source, arrayName, replacementLines) {
  // Match: const arrayName = [...]; (multiline)
  const arrRegex = new RegExp(`  const ${arrayName} = \\[[\\s\\S]*?\\];`, 'g');
  source = source.replace(arrRegex, '  // [patched] ' + arrayName + ' replaced by enriched functions');
  // Match: arrayName.forEach(page => { ... });
  const forEachRegex = new RegExp(`  ${arrayName}\.forEach\\(page => \\{[\\s\\S]*?\\}\\);`, 'g');
  source = source.replace(forEachRegex, replacementLines.map(l => '  ' + l).join('\n'));
  return source;
}

// === Step 4: Patch chapter5 ===
src = replaceArrayAndForEach(src, 'powerPages', [
  'sections.push(...enriched_section_5_1_1());',
  'sections.push(...enriched_section_5_1_2());',
  'sections.push(...enriched_section_5_1_3());',
  'sections.push(...enriched_section_5_1_4());',
  'sections.push(...enriched_section_5_1_5());',
]);
console.log('Patched chapter5: powerPages');

src = replaceArrayAndForEach(src, 'coolingPages', [
  'sections.push(...enriched_section_5_2_1());',
  'sections.push(...enriched_section_5_2_2());',
  'sections.push(...enriched_section_5_2_3());',
  'sections.push(...enriched_section_5_2_4());',
  'sections.push(...enriched_section_5_2_5());',
]);
console.log('Patched chapter5: coolingPages');

src = replaceArrayAndForEach(src, 'envPages', [
  'sections.push(...enriched_section_5_3_1());',
  'sections.push(...enriched_section_5_3_2());',
  'sections.push(...enriched_section_5_3_3());',
  'sections.push(...enriched_section_5_3_4());',
]);
console.log('Patched chapter5: envPages');

src = replaceArrayAndForEach(src, 'securityPages', [
  'sections.push(...enriched_section_5_4_1());',
  'sections.push(...enriched_section_5_4_2());',
  'sections.push(...enriched_section_5_4_3());',
  'sections.push(...enriched_section_5_4_4());',
  'sections.push(...enriched_section_5_4_5());',
  'sections.push(...enriched_section_5_4_6());',
]);
console.log('Patched chapter5: securityPages');

// === Step 5: Patch chapter7 ===
src = replaceArrayAndForEach(src, 'energyPages', [
  'sections.push(...enriched_section_7_1_2());',
  'sections.push(...enriched_section_7_1_3());',
  'sections.push(...enriched_section_7_1_4());',
  'sections.push(...enriched_section_7_1_5());',
  'sections.push(...enriched_section_7_1_6());',
]);
console.log('Patched chapter7: energyPages');

src = replaceArrayAndForEach(src, 'assetPages', [
  'sections.push(...enriched_section_7_2_2());',
  'sections.push(...enriched_section_7_2_3());',
  'sections.push(...enriched_section_7_2_4());',
]);
console.log('Patched chapter7: assetPages');

src = replaceArrayAndForEach(src, 'opsPages', [
  'sections.push(...enriched_section_7_3_2());',
  'sections.push(...enriched_section_7_3_3());',
  'sections.push(...enriched_section_7_3_4());',
  'sections.push(...enriched_section_7_3_5());',
]);
console.log('Patched chapter7: opsPages');

// Replace VPP inline section
const vppStart = "  // 7.4 \u865a\u62df\u7535\u5382";
const vppEnd = "  sections.push(BREAK());\n\n  return sections;\n}";
const vppStartIdx = src.indexOf(vppStart);
const vppEndIdx = src.indexOf(vppEnd, vppStartIdx);
if (vppStartIdx > 0 && vppEndIdx > vppStartIdx) {
  const before = src.substring(0, vppStartIdx);
  const after = src.substring(vppEndIdx);
  src = before + '  // 7.4 \u865a\u62df\u7535\u5382\n  sections.push(H2(\'7.4 \u865a\u62df\u7535\u5382\'));\n  sections.push(P(\'\u865a\u62df\u7535\u5382\uff08VPP\uff09\u6a21\u5757\u5c06\u6570\u636e\u4e2d\u5fc3\u7684\u67d4\u6027\u8d1f\u8377\u8d44\u6e90\u865a\u62df\u5316\uff0c\u53c2\u4e0e\u7535\u7f51\u9700\u6c42\u54cd\u5e94\u548c\u8f85\u52a9\u670d\u52a1\u5e02\u573a\u3002\'));\n  sections.push(...enriched_section_7_4_1());\n  sections.push(BREAK());\n\n' + after;
  console.log('Patched chapter7: VPP section');
}

// === Step 6: Patch chapter8 ===
src = replaceArrayAndForEach(src, 'collectPages', [
  'enriched_section_8_1_1(sections);',
  'enriched_section_8_1_2(sections);',
  'enriched_section_8_1_3(sections);',
  'enriched_section_8_1_4(sections);',
  'enriched_section_8_1_5(sections);',
  'enriched_section_8_1_6(sections);',
  'enriched_section_8_1_7(sections);',
  'enriched_section_8_1_8(sections);',
]);
console.log('Patched chapter8: collectPages');

src = replaceArrayAndForEach(src, 'alarmRulePages', [
  'enriched_section_8_2_1(sections);',
  'enriched_section_8_2_2(sections);',
  'enriched_section_8_2_3(sections);',
  'enriched_section_8_2_4(sections);',
]);
console.log('Patched chapter8: alarmRulePages');

src = replaceArrayAndForEach(src, 'linkagePages', [
  'enriched_section_8_3_1(sections);',
  'enriched_section_8_3_2(sections);',
  'enriched_section_8_3_3(sections);',
  'enriched_section_8_3_4(sections);',
  'enriched_section_8_3_5(sections);',
  'enriched_section_8_3_5b(sections);',
]);
console.log('Patched chapter8: linkagePages');

src = replaceArrayAndForEach(src, 'diagPages', [
  'enriched_section_8_4_1(sections);',
  'enriched_section_8_4_2(sections);',
]);
console.log('Patched chapter8: diagPages');

// === Step 7: Patch chapter9 ===
src = replaceArrayAndForEach(src, 'sysPages', [
  'sections.push(...enriched_section_9_1());',
  'sections.push(...enriched_section_9_2());',
  'sections.push(...enriched_section_9_3());',
  'sections.push(...enriched_section_9_4());',
  'sections.push(...enriched_section_9_5());',
]);
console.log('Patched chapter9: sysPages');

// === Step 8: Patch chapter10 ===
const ch10Old = `function chapter10() {
  return [
    H1('\u7b2c10\u7ae0 \u6570\u5b57\u5b6a\u751f\u5927\u5c4f'),
    P(''),
    H2('10.1 \u5927\u5c4f\u6982\u8ff0'),`;
const ch10New = `function chapter10() {
  return [
    H1('\u7b2c10\u7ae0 \u6570\u5b57\u5b6a\u751f\u5927\u5c4f'),
    P(''),
    ...enriched_section_10_1(),`;
if (src.includes(ch10Old)) {
  // Find the rest of the old chapter10 content to remove
  const ch10Start = src.indexOf(ch10Old);
  const ch10BreakIdx = src.indexOf('    BREAK(),\n  ];\n}', ch10Start);
  if (ch10BreakIdx > ch10Start) {
    const before = src.substring(0, ch10Start);
    const after = src.substring(ch10BreakIdx);
    src = before + `function chapter10() {\n  return [\n    H1('\u7b2c10\u7ae0 \u6570\u5b57\u5b6a\u751f\u5927\u5c4f'),\n    P(''),\n    ...enriched_section_10_1(),\n    ` + after;
    console.log('Patched chapter10');
  }
}

// === Step 9: Write result ===
fs.writeFileSync(MAIN, src, 'utf-8');
console.log('\nPatch complete! File written:', MAIN);
console.log('Backup at:', BAK);
console.log('\nRun: node ' + MAIN);