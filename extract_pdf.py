from pypdf import PdfReader
import sys

pdf_path = r"D:\mytest1\factorysaving\虚拟电厂方案1.pdf"

try:
    reader = PdfReader(pdf_path)
    print(f"总页数: {len(reader.pages)}")
    print("=" * 50)

    # 提取所有页面的文本
    full_text = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            full_text.append(f"--- 第 {i+1} 页 ---\n{text}")

    # 输出到文件 (处理特殊字符)
    content = "\n\n".join(full_text)
    content = content.encode('utf-8', errors='replace').decode('utf-8')
    with open(r"D:\mytest1\虚拟电厂方案1_内容.txt", "w", encoding="utf-8") as f:
        f.write(content)

    print("文本已提取到: 虚拟电厂方案1_内容.txt")
    print("=" * 50)

    # 打印前几页预览
    for text in full_text[:5]:
        preview = text[:2000] if len(text) > 2000 else text
        preview = preview.encode('utf-8', errors='replace').decode('utf-8')
        print(preview)
        print()

except Exception as e:
    print(f"错误: {e}")
    sys.exit(1)
