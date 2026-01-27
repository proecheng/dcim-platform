const pptxgen = require('pptxgenjs');
const html2pptx = require('C:/Users/admin/.claude/plugins/cache/anthropic-agent-skills/document-skills/69c0b1a06741/skills/pptx/scripts/html2pptx.js');
const path = require('path');

async function createPresentation() {
    const pptx = new pptxgen();
    pptx.layout = 'LAYOUT_16x9';
    pptx.author = 'Claude';
    pptx.title = '算力中心智能监控系统';
    pptx.subject = 'V3.2 技术方案汇报';

    const slides = [
        'slide1.html',
        'slide2.html',
        'slide3.html',
        'slide4.html',
        'slide5.html',
        'slide6.html',
        'slide7.html',
        'slide8.html',
        'slide9.html'
    ];

    const workDir = 'D:/mytest1/workspace';

    for (let i = 0; i < slides.length; i++) {
        const slidePath = path.join(workDir, slides[i]);
        console.log(`Processing slide ${i + 1}: ${slides[i]}`);
        try {
            await html2pptx(slidePath, pptx);
            console.log(`  Slide ${i + 1} completed`);
        } catch (err) {
            console.error(`  Error on slide ${i + 1}:`, err.message);
        }
    }

    const outputPath = path.join(workDir, '算力中心智能监控系统-V3.2.pptx');
    await pptx.writeFile({ fileName: outputPath });
    console.log(`\nPresentation saved to: ${outputPath}`);
}

createPresentation().catch(err => {
    console.error('Failed to create presentation:', err);
    process.exit(1);
});
