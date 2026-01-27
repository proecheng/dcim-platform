from pypdf import PdfReader
import os

pdf_files = [
    ("虚拟电厂方案2.pdf", "虚拟电厂方案2_内容.txt"),
    ("虚拟电厂方案3.pdf", "虚拟电厂方案3_内容.txt"),
    ("虚拟电厂方案4-1.pdf", "虚拟电厂方案4-1_内容.txt"),
    ("虚拟电厂方案4-2.pdf", "虚拟电厂方案4-2_内容.txt"),
    ("虚拟电厂方案5.pdf", "虚拟电厂方案5_内容.txt"),
    ("虚拟电厂方案6.pdf", "虚拟电厂方案6_内容.txt"),
    ("虚拟电厂方案7.pdf", "虚拟电厂方案7_内容.txt"),
]

base_dir = r"D:\mytest1\factorysaving"
output_dir = r"D:\mytest1"

for pdf_name, txt_name in pdf_files:
    pdf_path = os.path.join(base_dir, pdf_name)
    txt_path = os.path.join(output_dir, txt_name)

    print(f"\n{'='*60}")
    print(f"处理: {pdf_name}")

    try:
        reader = PdfReader(pdf_path)
        print(f"页数: {len(reader.pages)}")

        full_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                full_text.append(f"--- 第 {i+1} 页 ---\n{text}")

        content = "\n\n".join(full_text)
        content = content.encode('utf-8', errors='replace').decode('utf-8')

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"已保存: {txt_name}")

    except Exception as e:
        print(f"错误: {e}")

print(f"\n{'='*60}")
print("全部完成!")
