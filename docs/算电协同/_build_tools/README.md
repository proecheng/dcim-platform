# 建设方案 Word 版 · 构建流水线说明

本目录归档把 `算电协同系统建设方案.md`（源）+ `pics/fig-*.png`（26 张配图）构建成 `算电协同系统建设方案.docx` 的脚本与图提示词，供后续会话重建。

## 一、源与产物
- 源 markdown：`../算电协同系统建设方案.md`，每图占位块为两行：
  `> **图 X-Y　图名**（…）` + `> **配图提示词**：…`
- 图片：`../pics/fig-X-Y.png`（26 张）。
- 产物：`../算电协同系统建设方案.docx`。

## 二、重建 docx（两步）
1. **预处理**：`python build_word.py`
   - 把每个图占位块替换为图片引用 `![图 X-Y　图名](pics/fig-X-Y.png){width=…}`（删除“配图提示词”行）；
   - 删除含制表符/方块字符的 ASCII 草图围栏块（**保留**公式块——公式块无此类字符）；
   - 改写“图目录”说明；输出 `../_build_建设方案.md`。
   - 图宽：竖图 fig-5-2 用 9cm，算法竖图 fig-6-13 用 12cm，方图 6-9/9-1 用 11cm，其余 15cm。
2. **转 docx**（`python build_word.py all` 一步到位；脚本已自动探测 pandoc：`shutil.which` + 固定路径兜底。Windows 下 pandoc 是 .cmd、subprocess 不解析 PATHEXT，故脚本内用绝对路径调用。手动等价命令）：
   ```
   pandoc _build_建设方案.md -o 算电协同系统建设方案.docx --toc --toc-depth=2 --metadata toc-title=目录 --resource-path=<docs/算电协同 绝对路径>
   ```
   - pandoc：`C:\Users\admin\.local\bin\pandoc.cmd`
   - LibreOffice（转 PDF 校验）：`C:\Users\admin\.local\libreoffice\program\soffice.exe --headless --convert-to pdf 文件.docx`

## 三、出图（micuapi gpt-image-2-pro）
- 端点 `https://www.micuapi.ai/v1/images/generations`，模型 `gpt-image-2-pro`，OpenAI 兼容，返回图片 URL。
- **必须用 curl**（urllib/python 默认 UA 被 Cloudflare 1010 拦；curl 可过）。见 `gen_image.py`（**API key 已抹除，需自行填入；key 由用户持有，勿提交进仓库**）。
- 用法：`python gen_image.py --batch figuresN.json`（顺序 1 张/次，满足“每次≤2张”防过载，含重试+间隔）。
- 各图提示词见 `figures*.json`。**提示词勿用 ∩ / ↑ / ↓ / ↔ / → 等符号**（会被模型当文字渲染进图），一律用规范中文与顿号。
- **每张图生成后必须 Read 检查“伪中文”（乱码/生造字），有则重画，不手工改图。**

## 四、符号复核与修复（2026-06-25 完成）

26 张图逐张目视复核（整图 + 关键区域放大像素级），6 张含违规符号，**已全部重画修复并重建 docx**（docx 内嵌图经字节比对确认为最新版、zip 完整性 OK）。修复链：`figures*.json` 提示词规范化（追加“禁箭头符号、方框连接用图形箭头”约束）→ `gen_image.py` 重画 7 张 → 逐张 Read 验证无伪中文/符号 → pandoc 重建。micuapi key 经环境变量 `MICUAPI_KEY` 传入（gen_image.py 已改为从 env 读取，仓库内仍为占位符）。

**已修复的 6 张（原违规 → 修复后）**：
- `fig-2-1`（figures7）：动作框“→ 排入” → “，排入”（∩ 此前已修为顿号）。
- `fig-2-2`（figures6）：上/下箭头文字各 1 处 `→` → 顿号/逗号。
- `fig-6-1`（figures.json）：文字标签 `24-7` → `24/7`；重画一度引入“绿电↔灰电”，经约束改为“绿电与灰电”。
- `fig-6-2`（figures.json）：“启停/限速 → 耗电…” → “启停或限速，耗电…”。
- `fig-6-9`（figures.json）：“算力→VPP置信容量” → “算力对VPP的置信容量”（右侧 ↔ 已是图形标尺）。
- `fig-6-10`（figures7）：中间框 2 处 `→` → 逗号（∩/↑ 此前已修）。

**附带内容修正**：`fig-10-3`（figures2）“编排器(operator)”与“人工操作员(operator)”重复标 operator → 已重画为“编排器(系统组件)”。

**正文 .md 的 ↔（7 处：图目录 / §2.5 题注 / §1.5.2 / 附录E / 修订说明等）**：已改为“与”或顿号。

**复核无符号问题的 20 张**：1-1 / 4-1 / 5-1 / 5-2 / 5-3 / 6-3 / 6-4 / 6-5 / 6-6 / 6-7 / 6-8 / 7-1 / 8-1 / 9-1 / 10-1 / 10-2 / 13-1 / 15-1 / 16-1。
- 订正：`fig-5-1` 无 24/7、CFE 字样（原“fig-5-1 含 24-7”系误记）。
- `fig-6-6` 公式 `S=√(P²+Q²)`、`≤`、`|P|` 渲染正确，属专业约束，保留。
- 流程图（5-3 / 6-3 / 6-4 / 16-1 等）框间箭头均为图形元素、非文字 `→`，规范。
- 概念式 `+`/`=`（如 1-1“电+算=算电协同”）、`×`（MEF×COP）、`≥80%`、范围连字符（30-50%、2.6-4年）、`24/7`（斜杠）属设计表达，保留。
- 未发现伪中文 / 乱码 / 生造字。
