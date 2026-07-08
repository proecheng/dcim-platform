# -*- coding: utf-8 -*-
"""从建设方案 .md 抽取指定新增图的题注+配图提示词，生成 figures-biz.json（出图批处理输入）。
单一真相源=正文 .md 的 配图提示词 行；避免提示词与正文不一致。"""
import re, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")

BASE = "D:/mytest1/docs/算电协同"
SRC = BASE + "/算电协同系统建设方案.md"
OUT_JSON = BASE + "/_build_tools/figures-biz.json"
FW = "　"

# 本次新增的 13 张图（业务流程图 + 算法流程图）
WANT = ["4-2", "4-3", "4-4", "4-5", "4-6", "4-7",
        "6-11", "6-12", "6-13", "6-14", "6-15", "6-16", "6-17"]
FORBIDDEN = "→↔∩↑↓"

src = open(SRC, encoding="utf-8").read()
pat = re.compile(r"> \*\*图 (\d+-\d+)" + FW + r"([^*\n]+?)\*\*[^\n]*\n> \*\*配图提示词\*\*：([^\n]*)\n")
found = {m.group(1): (m.group(2).strip(), m.group(3).strip()) for m in pat.finditer(src)}

figs, problems = [], []
for num in WANT:
    if num not in found:
        problems.append("缺图占位: 图 " + num)
        continue
    title, prompt = found[num]
    bad = [c for c in FORBIDDEN if c in prompt]
    if bad:
        problems.append("图 %s 提示词含违规符号 %s" % (num, "".join(bad)))
    if "24-7" in prompt:
        problems.append("图 %s 提示词含 24-7（应为 24/7）" % num)
    figs.append({"out": "%s/pics/fig-%s.png" % (BASE, num),
                 "prompt": prompt, "size": "1536x1024", "_title": title})

json.dump(figs, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("写出 %d 张到 %s" % (len(figs), OUT_JSON))
for p in problems:
    print("  [WARN]", p)
if not problems:
    print("  提示词符号合规检查通过（无 箭头/交集符号 / 无 24-7）")
sys.exit(1 if problems else 0)
