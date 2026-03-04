const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, 
        Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType, 
        ShadingType, PageNumber, LevelFormat } = require('docx');

// 读取 Markdown 文件
const mdContent = fs.readFileSync('D:\\mytest1\\docs\\development-progress-report-2026-03.md', 'utf8');

// 解析 Markdown 内容
const lines = mdContent.split('\n');
const children = [];

// 配置列表编号
const numberingConfig = {
  config: [
    {
      reference: "bullets",
      levels: [
        { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 1440, hanging: 360 } } } }
      ]
    },
    {
      reference: "numbers",
      levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }
      ]
    }
  ]
};

let inTable = false;
let tableRows = [];
let currentListLevel = -1;

for (let i = 0; i < lines.length; i++) {
  const line = lines[i].trim();
  
  // 跳过空行
  if (!line) {
    if (!inTable) {
      children.push(new Paragraph({ text: "" }));
    }
    continue;
  }
  
  // 处理分隔线
  if (line === '---') {
    children.push(new Paragraph({ 
      text: "",
      border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "CCCCCC" } }
    }));
    continue;
  }
  
  // 处理标题
  if (line.startsWith('# ')) {
    children.push(new Paragraph({
      heading: HeadingLevel.HEADING_1,
      children: [new TextRun({ text: line.substring(2), bold: true, size: 32 })]
    }));
    currentListLevel = -1;
  } else if (line.startsWith('## ')) {
    children.push(new Paragraph({
      heading: HeadingLevel.HEADING_2,
      children: [new TextRun({ text: line.substring(3), bold: true, size: 28 })]
    }));
    currentListLevel = -1;
  } else if (line.startsWith('### ')) {
    children.push(new Paragraph({
      heading: HeadingLevel.HEADING_3,
      children: [new TextRun({ text: line.substring(4), bold: true, size: 26 })]
    }));
    currentListLevel = -1;
  } else if (line.startsWith('#### ')) {
    children.push(new Paragraph({
      heading: HeadingLevel.HEADING_4,
      children: [new TextRun({ text: line.substring(5), bold: true, size: 24 })]
    }));
    currentListLevel = -1;
  }
  // 处理列表
  else if (line.startsWith('- ') || line.startsWith('* ')) {
    const text = line.substring(2);
    const level = line.startsWith('  ') ? 1 : 0;
    children.push(new Paragraph({
      numbering: { reference: "bullets", level: level },
      children: [new TextRun(text)]
    }));
    currentListLevel = 0;
  } else if (/^\d+\.\s/.test(line)) {
    const text = line.replace(/^\d+\.\s/, '');
    children.push(new Paragraph({
      numbering: { reference: "numbers", level: 0 },
      children: [new TextRun(text)]
    }));
    currentListLevel = 0;
  }
  // 处理表格
  else if (line.startsWith('|')) {
    if (!inTable) {
      inTable = true;
      tableRows = [];
    }
    
    // 跳过分隔行
    if (line.includes('---')) {
      continue;
    }
    
    const cells = line.split('|').filter(c => c.trim()).map(c => c.trim());
    tableRows.push(cells);
    
    // 检查下一行是否还是表格
    if (i + 1 >= lines.length || !lines[i + 1].trim().startsWith('|')) {
      // 表格结束，创建表格
      const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
      const borders = { top: border, bottom: border, left: border, right: border };
      
      const colCount = tableRows[0].length;
      const colWidth = Math.floor(9360 / colCount);
      const columnWidths = Array(colCount).fill(colWidth);
      
      const rows = tableRows.map((rowCells, rowIndex) => {
        return new TableRow({
          children: rowCells.map(cellText => {
            return new TableCell({
              borders,
              width: { size: colWidth, type: WidthType.DXA },
              shading: { 
                fill: rowIndex === 0 ? "D5E8F0" : "FFFFFF", 
                type: ShadingType.CLEAR 
              },
              margins: { top: 80, bottom: 80, left: 120, right: 120 },
              children: [new Paragraph({ 
                children: [new TextRun({ 
                  text: cellText,
                  bold: rowIndex === 0
                })] 
              })]
            });
          })
        });
      });
      
      children.push(new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: columnWidths,
        rows: rows
      }));
      
      inTable = false;
      tableRows = [];
      currentListLevel = -1;
    }
  }
  // 处理普通段落
  else {
    // 解析粗体和代码
    const textRuns = [];
    let currentText = line;
    
    // 处理粗体 **text**
    const boldRegex = /\*\*([^*]+)\*\*/g;
    let lastIndex = 0;
    let match;
    
    while ((match = boldRegex.exec(currentText)) !== null) {
      if (match.index > lastIndex) {
        textRuns.push(new TextRun(currentText.substring(lastIndex, match.index)));
      }
      textRuns.push(new TextRun({ text: match[1], bold: true }));
      lastIndex = match.index + match[0].length;
    }
    
    if (lastIndex < currentText.length) {
      textRuns.push(new TextRun(currentText.substring(lastIndex)));
    }
    
    if (textRuns.length === 0) {
      textRuns.push(new TextRun(line));
    }
    
    children.push(new Paragraph({ children: textRuns }));
    currentListLevel = -1;
  }
}

// 创建文档
const doc = new Document({
  numbering: numberingConfig,
  styles: {
    default: {
      document: {
        run: { font: "Arial", size: 24 }
      }
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: "2E75B6" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 }
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: "2E75B6" },
        paragraph: { spacing: { before: 180, after: 100 }, outlineLevel: 1 }
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: "2E75B6" },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 }
      },
      {
        id: "Heading4",
        name: "Heading 4",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "2E75B6" },
        paragraph: { spacing: { before: 140, after: 70 }, outlineLevel: 3 }
      }
    ]
  },
  sections: [{
    properties: {
      page: {
        size: {
          width: 12240,
          height: 15840
        },
        margin: {
          top: 1440,
          right: 1440,
          bottom: 1440,
          left: 1440
        }
      }
    },
    headers: {
      default: new Header({
        children: [
          new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [
              new TextRun({
                text: "DCIM 系统开发进展报告",
                size: 20,
                color: "666666"
              })
            ]
          })
        ]
      })
    },
    footers: {
      default: new Footer({
        children: [
          new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [
              new TextRun({ text: "第 ", size: 20 }),
              new TextRun({ children: [PageNumber.CURRENT], size: 20 }),
              new TextRun({ text: " 页", size: 20 })
            ]
          })
        ]
      })
    },
    children: children
  }]
});

// 保存文档
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('D:\\mytest1\\docs\\development-progress-report-2026-03.docx', buffer);
  console.log('Word 文档已成功创建：D:\\mytest1\\docs\\development-progress-report-2026-03.docx');
}).catch(err => {
  console.error('创建文档失败：', err);
});
