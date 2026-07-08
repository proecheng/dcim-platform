#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预处理建设方案 md：图占位块→图片引用(删提示词)、移除ASCII草图(保留公式)、转docx。"""
import re, sys, subprocess, os, shutil

BASE = "D:/mytest1/docs/算电协同"
SRC = BASE + "/算电协同系统建设方案.md"
TMP = BASE + "/_build_建设方案.md"
OUT = BASE + "/算电协同系统建设方案.docx"
FW = "　"  # 全角空格

def preprocess():
    src = open(SRC, encoding="utf-8").read()

    # 1) 图占位块（题注行 + 配图提示词行）→ 图片引用（pandoc 隐式图=带题注）
    cnt = [0]
    def repl_fig(m):
        num, name = m.group(1), m.group(2).strip()
        cnt[0] += 1
        w = "9cm" if num == "5-2" else ("12cm" if num == "6-13" else ("11cm" if num in ("6-9", "9-1") else "15cm"))
        return "![图 %s%s%s](pics/fig-%s.png){width=%s}\n" % (num, FW, name, num, w)
    pat = re.compile(r"> \*\*图 (\d+-\d+)" + FW + r"([^*\n]+?)\*\*[^\n]*\n> \*\*配图提示词\*\*：[^\n]*\n")
    src = pat.sub(repl_fig, src)

    # 2) 移除含制表符/方块字符的 ASCII 草图围栏块（保留公式块——公式块无此类字符）
    rm = [0]
    def repl_code(m):
        if re.search(r"[─-▟■-◿]", m.group(0)):
            rm[0] += 1
            return ""
        return m.group(0)
    src = re.sub(r"```[^\n]*\n.*?\n```\n?", repl_code, src, flags=re.S)

    # 3) 小修：5-3 注的"上图为"→"下图为"（图已移到注下方）；图目录占位约定→已生成
    src = src.replace("上图为", "下图为")
    src = re.sub(r"> \*\*配图占位约定\*\*：[^\n]*\n",
                 "> 本方案各图已由 AI 生成并插入正文对应位置（图号采用“图 章号-序号”）。\n", src)

    # Word reference style may render Markdown horizontal rules as stray dots.
    src = re.sub(r"(?m)^---\s*\n?", "", src)

    open(TMP, "w", encoding="utf-8").write(src)
    print("figures->img:", cnt[0], "| ascii removed:", rm[0])
    return cnt[0], rm[0]

def _find_pandoc():
    # Windows 下 pandoc 常是 .cmd，subprocess 不解析 PATHEXT，须用绝对路径
    for name in ("pandoc", "pandoc.cmd", "pandoc.exe"):
        p = shutil.which(name)
        if p:
            return p
    fallback = r"C:\Users\admin\.local\bin\pandoc.cmd"
    if os.path.exists(fallback):
        return fallback
    raise FileNotFoundError("未找到 pandoc，请安装或加入 PATH（见 README 二）")

def to_docx():
    pandoc = _find_pandoc()
    ref = BASE + "/_build_tools/reference.docx"
    cmd = [pandoc, TMP, "-o", OUT, "--toc", "--toc-depth=2",
           "--metadata", "toc-title=目录", "--resource-path", BASE]
    if os.path.exists(ref):
        cmd += ["--reference-doc", ref]  # 学位论文版式：宋体小四/首行缩进2字/1.5倍行距/标题黑体
    subprocess.run(cmd, check=True, cwd=BASE)
    print("DOCX", OUT, os.path.getsize(OUT))

if __name__ == "__main__":
    preprocess()
    if len(sys.argv) > 1 and sys.argv[1] == "all":
        to_docx()
