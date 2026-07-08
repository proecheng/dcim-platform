# -*- coding: utf-8 -*-
"""Regenerate selected PPT page images with MICU, writing candidates first.

Usage:
    MICUAPI_KEY=... python redraw_micu_candidates.py --out-dir _redraw_x 3 6

The script intentionally does not store API keys. It reads MICUAPI_KEY from the
process environment and writes generated images to the selected candidate dir.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PICS = ROOT.parent / "pics"
PJSON = ROOT / "_prompts.json"
GEN = "https://www.micuapi.ai/v1/images/generations"
EDIT = "https://www.micuapi.ai/v1/images/edits"
MODEL = "gpt-image-2-pro"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


STYLE = """\
16:9 横版商务政务汇报幻灯片，扁平矢量信息图风格，专业严谨、科技感。
白色或极浅灰背景，顶部细深蓝色条，主标题左上对齐并有橙色短下划线。
配色：深蓝 #1F4E79、翠绿 #2E8B57、强调橙 #E8833A、深灰 #333333、浅灰 #F2F4F7。
中文用清晰无衬线黑体，英文数字用 Arial 风格。所有文字必须大字号、短标签、逐字正确。
严禁页码、页脚编号、乱码、伪中文、随机字母、水印、图标内文字、微小说明字。
"""


COMPACT_PAGE_SPECS: dict[int, str] = {
    3: """\
标题：执行摘要 · 价值总览
成因诊断：原页伪中文主要来自长段落、小号卡片正文和流程图内小字。请改为低文字密度价值总览页。
允许出现的文字只有以下清单，除清单外全图不要出现任何汉字、英文、数字或符号。
版式：上方只画三层概念图，三个大节点和一个公式：
电网
济南高新虚拟电厂
芯片园区智算中心
电 + 算 = 算电协同
中间四张大卡片，每张只写一行标题和一行数字：
合规达标｜绿电 ≥80%
降本增效｜净 40–175 万/年
绿色示范｜减碳 1.8–2.4 万吨
规模复制｜第 N 站 30–50%
底部深蓝数字带，只写六个大数字标签：
绿电≥80%
复用80%
建设510–1060万
净40–175万/年
回收2.6–4年
第N站30–50%
不要长段落，不要说明句，不要卡片正文，不要图标内文字。
""",
    6: """\
标题：建设必要性：合规·降本·示范·规模化
版式：左侧收益构成堆叠条，右侧四张纵向卡片。
右上角橙色大字：85–285 万元/年
四张卡片只写：合规刚需｜降本增效｜示范引领｜规模复制
左侧条形图标签只写：绿电绿证｜自然冷却｜需求响应｜峰谷套利｜需量节省
底部关键数字：适中档 85–285 万元/年｜第 N 站 30–50%
不要在图表内部写小字。
""",
    11: """\
标题：双向耦合：算随电调 + 电随算配
版式：左右双栏，中间圆形“协同编排器”。
左栏标题：算随电调。标签：绿电富余｜电价低谷｜不顶峰｜需求响应
右栏标题：电随算配。标签：储能补峰｜绿电搬运｜供电稳定｜ramp 管理
中心只写：双向耦合｜统一求解
底部短语：可延迟算力｜储能｜制冷｜短时功率
不要写长句，不要在箭头旁写小字。
""",
    13: """\
标题：算侧底座已工程化落地（实景）
成因诊断：原页伪中文来自复刻 DCIM 截图和仪表盘内部微小 UI 文字。请不要画真实截图，不要画带文字的界面；改成抽象无字仪表盘背景。
允许出现的文字只有以下清单，除清单外全图不要出现任何汉字、英文、数字或符号。
版式：左侧 60% 画深蓝抽象仪表盘背景，只能有无字折线、无字环形仪表、无字柱状图、无字色块；这些图形内部绝对不能有任何文字、数字、字母、刻度或设备编号。
右侧两张大数据卡：
当前 PUE
1.34
实时点位
3412
右侧六条大标签：
采集 5 秒级
WebSocket 三通道
PUE 拆分
96×15min
30+ REST
4 级告警
底部四个大标签：
实时监控
能效
优化调度
协议接入
禁止出现“DCIM”“kW”“UPS”“Modbus”“SNMP”“MQTT”“HTTP”“BACnet”等任何未列入清单的小字。
""",
    15: """\
标题：高复用 = 低风险 + 短周期
版式：三列卡片。
左列：既有复用｜DCIM｜EnergyHub｜MILP
中列：扩展接入｜数据治理｜接口复用｜审批留痕
右列：新增能力｜绿电碳语义｜算力柔性｜三流可视化
右上橙色大字：约 80% 复用
底部短语：Phase 1 约 4–6 周｜低风险｜短周期
不要画数据库小表格，不要写小字段。
""",
    16: """\
标题：建设内容总览：C1–C10，约半数为扩展复用
版式：四组分区网格。
新增：C1 绿电碳语义｜C2 算力作业｜C3 协同编排｜C5 三流可视化
重构：C4 目标函数
扩展：C6 AI 应用｜C7 市场交易｜C8 源网荷储｜C10 节能协同
硬件：C9 感知计量
关键数字：约 50% 复用｜10 项建设内容
每个格子只写一行短标签。
""",
    18: """\
标题：六大功能域（下）：变现 + 呈现（概览）
版式：三张大卡片横排。
卡片一：市场与 VPP 域｜三类柔性｜收益出口
卡片二：预冷与节能域｜谷段蓄冷｜峰段释放
卡片三：三流可视化与 AI 域｜冷·电·碳｜同源对齐
底部短语：一期建议态 · 不下控｜模型只翻译 · 不决策
不要画复杂流程小字。
""",
    20: """\
标题：六层分层架构
版式：六层横向堆叠架构图。
六层从上到下只写：展示交互层｜AI 协同决策层｜能力层｜执行控制层｜数据与计量层｜采集接入层
右侧三张卡：single-writer｜MILP + 规则｜安全优先
底部短语：DCIM 复用｜EnergyHub 复用｜外部数据接入
不要写公式长串，不要写层内小字。
""",
    22: """\
标题：数据架构与接口：6 新增 + 5 扩展 + 5 外部
版式：左侧六张新增表卡片，右侧接口与外部数据。
新增表：碳因子表｜绿证台账｜算力作业表｜调度计划｜光伏储能配置｜碳效率历史
右侧：5 扩展接口｜5 外部数据｜电价｜气象｜市场｜VPP｜绿证
底部治理标签：is_demo｜data_source｜site_id
不要画密集字段清单。
""",
    26: """\
标题：AI 应用矩阵：数值智能主导、语言智能辅助的闭环
版式：中心闭环圆环，四段只写：预测｜决策｜执行｜反馈学习
六张能力卡：多源预测｜强化学习｜图神经网络｜预测性维护｜异常漂移｜智能助手
关键数字：负荷 MAPE <5%｜光伏 <12%｜电价 <15%
底部边界：大模型不参与安全决策
不要写长解释。
""",
    27: """\
标题：三流合一数字孪生：冷·电·碳同坐标同时间轴
版式：三联视图。
左：冷流视图｜温度场｜COP
中：电流视图｜功率流｜储能
右：碳流视图｜CEF｜机柜级碳溯源
底部统一时间轴：15min 同步｜可回放｜可预演
所有流线和设备内部无文字。
""",
    30: """\
标题：节能技术协同：四项技术依赖调度协同
版式：左侧 PUE 曲线，右侧四张技术卡。
曲线标题：PUE 随自然冷却小时下降
四卡：自然冷却｜储能移峰｜RC 预冷｜余热回收
底部短语：一期试行｜一期不建设｜调度协同｜取舍共同物理成因
剖面图设备只画图标，不写小字。
""",
    31: """\
标题：创新点三层定位：方法·工程·研究
版式：三层金字塔。
底层：工程价值｜复用 DCIM｜单一写入｜可审计 MRV
中层：方法级创新｜三流耦合孪生｜算力时空可调｜MEF×COP 权衡｜置信容量｜暂态可行域
顶层：研究纵深｜一期可做｜二期深化
右侧大字：可立课题 · 发论文 · 申专利
不要写段落。
""",
    32: """\
标题：国内外差异化对标矩阵：一图看懂优势
版式：6 行 × 5 列矩阵，单元格只用 ✓、◐、—。
列标题：Google｜DeepMind｜Meta｜国内同类｜本方案
行标题：调度对象｜碳口径｜制冷耦合｜电气安全｜决策方法｜可审计性
图例：✓ 全覆盖｜◐ 部分覆盖｜— 未涉及
底部结论：冷·电·碳·算统一建模
不要在单元格内写句子。
""",
    33: """\
标题：MEF×COP 反直觉规律：正午追绿电不一定最优
成因诊断：上一版伪中文来自判定流程箭头、菱形框和连线旁的杂散笔迹，不是分辨率问题。请取消流程图，改为大卡片判定页。
允许出现的文字只有以下清单，除清单外全图不要出现任何汉字、英文、数字或符号。
版式：左侧 55% 画三曲线图，曲线仅保留四个大标签：
绿电
COP
MEF
时刻
右侧 2×2 四张大判定卡，每张只写一行：
正午绿电
COP下降
需量上升
夜谷转移
右上橙色结论卡只写：
不盲目追正午
底部三张数字卡：
COP 夏2.8 春秋3.5 冬4.0
MEF 减碳约5%
济南测算 3–5%
底部深蓝结论条：
多目标权衡优于单一追绿电
不要菱形判定框，不要流程箭头，不要手写笔触，不要箭头旁文字，不要表格小字。
""",
    34: """\
标题：七大核心算法总览：判定分支 + 安全回退
版式：左侧 MILP 链路，右侧 ramp 四步，底部七个算法芯片。
MILP 链路：目标构建 → 主求解 → 五级仲裁 → 写入计划
五级仲裁：安全｜在线 SLA｜电网 DR｜需量红线｜经济
ramp 四步：升降载速率｜稳态负载率｜热轨迹｜N+1 冗余
七芯片：CEF信号｜ramp四步｜MILP+仲裁｜MEF×COP｜预冷RC｜ELCC折算｜AI闭环
底部：一期建议态 · 不下发
不要在连线旁写字。
""",
    36: """\
标题：建设周期与实施计划
成因诊断：原页伪中文主要来自甘特图小字号、月度刻度和里程碑长句。请改为大阶段路线图，减少甘特小字。
允许出现的文字只有以下清单，除清单外全图不要出现任何汉字、英文、数字或符号。
版式：上方右侧橙色大数字：
6–8 个月
主体为四条横向大阶段带，从左到右排列：
Phase 1 合规可视
Phase 2 协同核心
Phase 3 交易增值
联调验收
阶段下方只放三个橙色里程碑：
绿电/CUE 可审计
建议态跑通
交易闭环
底部四个验收芯片：
计量100%
误触0次
净收益≥70%
30秒退回
不要 1–8 月密集刻度，不要小号甘特任务说明，不要里程碑长句。
""",
    38: """\
标题：直接经济效益与投资回收
版式：双数据卡 + 堆叠收益条 + 回收期对比。
数据卡：净 40–175 万/年｜回收 2.6–4 年
收益条标签：绿电绿证｜自然冷却+PUE｜需求响应｜峰谷套利｜需量节省
回收期卡：最优 2.6–4 年｜中性 5–7 年｜资产口径 4–8 年
底部：碳减排为影子价，不计入现金流
不要小字注释。
""",
    39: """\
标题：ROI 对标与 VPP 盈利资金流
成因诊断：原页伪中文来自资金流节点括号长句、箭头重复标签和底部副说明。请改为大节点资金流，节点内不写括号说明。
允许出现的文字只有以下清单，除清单外全图不要出现任何汉字、英文、数字或符号。
版式：上方三张口径卡：
资产口径 4–8年
软件口径 2.5–3年
资本金口径 3–4年
下方三方价值链，三个大节点只写：
数据中心
济南高新虚拟电厂
电网与电力市场
两条粗箭头标签只写：
资源上行
收益回流
右下两张分成卡：
数据中心 50–70%
聚合方 30–50%
底部两张收益卡：
自用降本
市场收益
不要节点括号长句，不要多层资金流小字，不要重复箭头文字，不要底部解释段落。
""",
    40: """\
标题：商业模式 · 出资结构 · 规模化经济
成因诊断：原页伪中文来自三档方案中的长说明和右侧路线图小字。请改为三阶段大卡 + 三个模式芯片。
允许出现的文字只有以下清单，除清单外全图不要出现任何汉字、英文、数字或符号。
版式：左侧三张递进大卡：
Phase 1 150–300万
Phase 2 450–750万
Phase 3 900–1300万
右侧三张说明卡只写标题：
出资结构
产品形态
规模化单位经济
产品形态芯片：
License
EMC
SaaS
底部橙色数字带：
第 N 站 30–50%
20–100 站规模化
不要资金流缩略图，不要小号路线图副标题，不要括号说明。
""",
    44: """\
标题：运行交付与安全：影子运行先行、30 秒一键退回手动
成因诊断：原页伪中文来自右侧长要点、安全卡片双行小字和告警小方框。请改为大时间轴和四张安全卡。
允许出现的文字只有以下清单，除清单外全图不要出现任何汉字、英文、数字或符号。
版式：右上橙色大数字：
30 秒接管回滚
主体上线时间轴四节点：
影子运行 ≥4–8周
人工接管
告警治理
SLA
中部四张安全卡，每张只写一行：
硬隔离白名单
决策可解释
保守降级
快速通道
底部三阶段：
Phase 1 纯只读
Phase 2 建议态
Phase 3 闭环
不要告警小方框，不要卡片副说明，不要右侧长段落，不要图标内文字。
""",
    45: """\
标题：分期建设 Gate 路线图与前期调研
成因诊断：原页伪中文来自 Gate 节点多行文本和底部调研带小标签。请改为大节点路线图，底部只保留短标签。
允许出现的文字只有以下清单，除清单外全图不要出现任何汉字、英文、数字或符号。
版式：横向 Gate 路线图，三阶段大节点：
Phase 1 保守档
150–300万
纯只读
Gate 1
计量100%
建议有效率≥80%
Phase 2 适中档
450–750万
建议态
Gate 2
净收益≥70%
回滚30秒
Phase 3 最佳档
900–1300万
闭环
Gate 3
DR资格
安全评审
底部调研带只写：
前期调研 2–4周
计量
源网荷储
算力作业
Token成本
标准接口
市场政策
商务组织
不要页号，不要底部小段落，不要节点内括号说明。
""",
    46: """\
标题：结论与行动建议：基础好 · 方向正 · 效益清 · 四方可签
成因诊断：原页伪中文来自四方图标内小字、CTA 长句和落地路径括号副说明。请改为结论卡 + 极简行动条。
允许出现的文字只有以下清单，除清单外全图不要出现任何汉字、英文、数字或符号。
版式：中部四张结论卡，每张只写标题和一行副标题：
基础好
复用率高周期短
方向正
多目标协同可审计
效益清
净收益40–175万/年
四方可签
政府投资技术运行
右侧橙色大数字：
40–175 万/年
底部行动条四步：
先做前期调研
启动 Phase 1
真实数据回填
按 Gate 升档
底部 CTA：
最小投入启动纯只读 Phase 1
不要在四方图标内写字，不要 CTA 长句，不要括号副说明，不要页号。
""",
}


TEXT_GUARD = """\
【最高优先级：本次重绘用于清除伪中文】
这是一张 16:9 中文商务汇报 PPT 整页图片，用于替换旧图中的伪中文/乱码。
以下规则优先级高于后文全部细节：
1. 只允许出现后文明确列出的标题、要点、关键数字、图例标签；可以把长句提炼为短标签，但绝对不要自创任何新文字。
2. 所有可见中文、英文、数字必须清晰可读、笔画正确、无错字、无生造字、无乱码、无随机字母、无水印、无页号。
3. 不要在图标、设备、截图框、仪表盘小格、连线、箭头、装饰纹理内部写微小文字；这些区域只能用纯图形、色块、线条或无字图标表达。
4. 每个文字块尽量短，优先使用 2-10 字大标签；如果长文本放不下，宁可删减解释性小字，也不能生成模糊小字。
5. 图表中的坐标、表头、卡片标题和关键数字必须大字号；底部不得出现页码、页脚编号、随机说明行。
6. 输出必须保持原有深蓝、翠绿、橙色、浅灰的政务科技信息图风格。
【必须避免】伪中文、形近错字、乱码、随机英文串、设备编号、水印、页码、重复小字、图标内文字。
"""


def run(cmd: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stdout


def download(url: str, out: Path) -> None:
    subprocess.run(
        ["curl", "-s", "--max-time", "300", "-A", UA, "-o", str(out), url],
        check=True,
    )


def build_prompt(item: dict, guard: str) -> str:
    page = int(item["page"])
    if guard == "compact" and page in COMPACT_PAGE_SPECS:
        return (
            STYLE
            + "\n【本页紧凑重绘内容】\n"
            + COMPACT_PAGE_SPECS[page]
            + "\n【文字铁律】只出现上述文字；所有汉字逐字正确；没有页码；没有任何其它小字。"
        )
    prompt = item["prompt"]
    page_specific = ""
    if page == 13:
        page_specific = """\
【本页特殊要求】
不要复刻原始截图里的密集 UI 小字。把截图区域重绘成干净的 DCIM 仪表盘示意：只保留大标签“当前 PUE 1.34”“实时点位 3412”“采集 5 秒级”“PUE 拆分”“96×15min”“30+ REST”“4 级告警”。界面内部其它位置一律无字，用图表线条和色块表示。
"""
    if page in {27, 30, 33, 34}:
        page_specific += """\
【复杂图页降密度要求】
流程图、桑基图、剖面图、算法链路只保留大标签，连线和箭头旁不要写字。小框内每框最多 6 个汉字或一个英文缩写；不允许出现第二行解释性小字。
"""
    if page in {32, 38, 39, 40, 45}:
        page_specific += """\
【表格/路线图要求】
表格单元格只写短词，严禁在单元格内加括号解释；路线图节点只写主标签和关键数字。
"""
    if guard == "none":
        return prompt
    if guard == "standard":
        return TEXT_GUARD + "\n" + page_specific + "\n" + prompt
    strict_extra = """\
【严格重绘附加约束】
请重新绘制整页，不要照抄旧图中的任何错误文字。所有文字必须用大字号、短标签。若某处文字无法保证正确，请删去该小字，只保留指定主标题、短标签和关键数字。
"""
    return TEXT_GUARD + "\n" + strict_extra + "\n" + page_specific + "\n" + prompt


def gen_one(
    item: dict,
    out_dir: Path,
    key: str,
    mode: str,
    guard: str,
    size_override: str | None,
    quality: str | None,
    resolution: str | None,
) -> str:
    page = int(item["page"])
    out = out_dir / f"page-{page:02d}.png"
    prompt = build_prompt(item, guard)
    size = size_override or item.get("size", "1536x1024")
    figs = item.get("ref_figs") or []

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as pf:
        pf.write(prompt)
        prompt_path = Path(pf.name)

    try:
        use_target_edit = mode == "target-edit"
        use_edit = use_target_edit or mode == "edit" or (mode == "auto" and figs)
        if use_target_edit:
            source = ROOT / f"page-{page:02d}.png"
            cmd = [
                "curl",
                "-s",
                "--max-time",
                "300",
                "-X",
                "POST",
                EDIT,
                "-H",
                "Authorization: Bearer " + key,
                "-A",
                UA,
                "-F",
                "model=" + MODEL,
                "-F",
                "size=" + size,
            ]
            if quality:
                cmd += ["-F", "quality=" + quality]
            if resolution:
                cmd += ["-F", "resolution=" + resolution]
            cmd += [
                "-F",
                "image=@" + source.name,
                "-F",
                "prompt=<" + str(prompt_path),
            ]
            raw = run(cmd, cwd=ROOT)
        elif use_edit and figs:
            cmd = [
                "curl",
                "-s",
                "--max-time",
                "300",
                "-X",
                "POST",
                EDIT,
                "-H",
                "Authorization: Bearer " + key,
                "-A",
                UA,
                "-F",
                "model=" + MODEL,
                "-F",
                "size=" + size,
            ]
            if quality:
                cmd += ["-F", "quality=" + quality]
            if resolution:
                cmd += ["-F", "resolution=" + resolution]
            cmd += ["-F", "prompt=<" + str(prompt_path)]
            for ref in figs[:2]:
                ref_path = PICS / Path(ref).name
                if ref_path.exists():
                    cmd += ["-F", "image=@" + ref_path.name]
            raw = run(cmd, cwd=PICS)
        else:
            body = {"model": MODEL, "prompt": prompt, "n": 1, "size": size}
            if quality:
                body["quality"] = quality
            if resolution:
                body["resolution"] = resolution
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as jf:
                json.dump(body, jf, ensure_ascii=False)
                json_path = Path(jf.name)
            try:
                cmd = [
                    "curl",
                    "-s",
                    "--max-time",
                    "300",
                    "-X",
                    "POST",
                    GEN,
                    "-H",
                    "Authorization: Bearer " + key,
                    "-H",
                    "Content-Type: application/json",
                    "-A",
                    UA,
                    "--data-binary",
                    "@" + str(json_path),
                ]
                raw = run(cmd)
            finally:
                json_path.unlink(missing_ok=True)

        try:
            data = json.loads(raw)["data"][0]
        except Exception:
            return "FAIL response=" + raw[:180].replace("\n", " ")

        if data.get("b64_json"):
            out.write_bytes(base64.b64decode(data["b64_json"]))
        elif data.get("url"):
            download(data["url"], out)
        else:
            return "FAIL no image field"

        size_bytes = out.stat().st_size
        return f"OK {size_bytes}"
    finally:
        prompt_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pages", nargs="+", type=int)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--mode",
        choices=["gen", "edit", "target-edit", "auto"],
        default="gen",
        help=(
            "gen: text-to-image; edit: reference figures from _prompts; "
            "target-edit: edit the existing page image itself"
        ),
    )
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument(
        "--guard",
        choices=["none", "standard", "strict", "compact"],
        default="standard",
        help="prompt guard injected before the page prompt",
    )
    parser.add_argument("--size-override", help="override image size, e.g. 3072x2048")
    parser.add_argument("--quality", default="high", help="MICU image quality parameter")
    parser.add_argument("--resolution", help="MICU resolution tier, e.g. 1k, 2k, 4k")
    args = parser.parse_args()

    key = os.environ.get("MICUAPI_KEY")
    if not key:
        raise SystemExit("MICUAPI_KEY is not set")

    items = {int(p["page"]): p for p in json.loads(PJSON.read_text(encoding="utf-8"))}
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    for page in args.pages:
        item = items[page]
        for attempt in range(1, args.attempts + 1):
            result = gen_one(
                item,
                out_dir,
                key,
                args.mode,
                args.guard,
                args.size_override,
                args.quality,
                args.resolution,
            )
            print(f"page-{page:02d} attempt {attempt}: {result}", flush=True)
            if result.startswith("OK"):
                break
            time.sleep(8)
        else:
            print(f"page-{page:02d} GAVEUP", flush=True)
    print("OUT_DIR=" + str(out_dir), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
