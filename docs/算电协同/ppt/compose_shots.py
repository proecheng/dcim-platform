# -*- coding: utf-8 -*-
"""实景截图页真截图合成：真实截图作主图 + 叠加标题/数据大字/特性标注/底部要点/副图。
用法：python compose_shots.py 13   |  python compose_shots.py 14
界面文字100%真实(就是真截图像素)，叠加文字由本脚本可控渲染，零伪中文。"""
import sys, re
from PIL import Image, ImageDraw, ImageFont

W, H = 1536, 1024
PICS = r'D:\mytest1\docs\算电协同\pics'
OUT = r'D:\mytest1\docs\算电协同\ppt\page-%02d.png'

# 配色
BLUE = (31, 78, 121)      # 主色深蓝 #1F4E79
GREEN = (46, 139, 87)     # 翠绿 #2E8B57
ORANGE = (232, 131, 58)   # 强调橙 #E8833A
DGRAY = (51, 51, 51)      # 深灰
LGRAY = (242, 244, 247)   # 浅灰底 #F2F4F7
WHITE = (255, 255, 255)
MIDGRAY = (130, 138, 150)

FB = 'C:/Windows/Fonts/msyhbd.ttc'   # 雅黑粗
FR = 'C:/Windows/Fonts/msyh.ttc'     # 雅黑常规
FA = 'C:/Windows/Fonts/arialbd.ttf'  # Arial 粗(数字)

def F(path, size): return ImageFont.truetype(path, size)

TOK = re.compile(r'[A-Za-z0-9%×./+\-－·（）()\[\]、，:：]+|.')
def wrap(draw, text, font, max_w):
    lines, cur = [], ''
    for tok in TOK.findall(text):
        if tok == '\n':
            lines.append(cur); cur = ''; continue
        t = cur + tok
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur); cur = tok
    if cur: lines.append(cur)
    return lines

def fit(img, box_w, box_h):
    w, h = img.size
    s = min(box_w / w, box_h / h)
    return img.resize((int(w * s), int(h * s)), Image.LANCZOS)

def paste_shot(canvas, path, x, y, box_w, box_h, border):
    im = fit(Image.open(path).convert('RGB'), box_w, box_h)
    w, h = im.size
    # 阴影
    sh = Image.new('RGBA', (w + 16, h + 16), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([8, 8, w + 12, h + 12], 10, fill=(0, 0, 0, 40))
    canvas.paste(sh, (x - 4, y - 2), sh)
    canvas.paste(im, (x, y))
    ImageDraw.Draw(canvas).rounded_rectangle([x - 1, y - 1, x + w, y + h], 6, outline=border, width=2)
    return w, h

CFG = {
    13: dict(
        title='算侧底座已工程化落地（实景）', accent=GREEN, chip_orange_idx={4},
        hero='dcim-energy-pue.png', thumb='dcim-overview.png',
        callouts=[('当前 PUE', '1.34'), ('实时点位', '3412')],
        chips=['采集 5 秒级 · WebSocket 三通道', '概览接入 3412 实时点位',
               'PUE 实时拆分 IT/制冷/UPS', 'MILP+强化学习+启发式 · 96×15min',
               '6+ 类工业协议 · 30+ REST · 4 级告警'],
        points=[('实时监控', '采集 5 秒级、WebSocket 三通道推送；概览大屏接入 3412 个实时点位'),
                ('能　　效', 'PUE 实时计算（IT/制冷/UPS 拆分 + 数据质量校验 + 历史留存），演示环境 PUE 1.34（模拟数据）'),
                ('优化调度', 'MILP（96 时段/储能 SOC/需量约束）+ 强化学习 + 启发式；6 类可调度负荷、96×15min 调度计划'),
                ('协议接入', '6+ 类工业协议（Modbus/SNMP/MQTT/HTTP/BACnet 含 MS-TP/OPC-UA）；30+ 个 REST 模块、4 级告警')],
        footer='界面取自算力数据中心自有演示环境；PUE 1.34 为演示（模拟数据）口径，与电侧口径相互独立、不并列比较。'),
    14: dict(
        title='电侧底座首期验收全通过，可直接复用', accent=BLUE, chip_orange_idx={2},
        hero='energyhub-dc-ems.png', thumb='energyhub-vpp-dispatch.png',
        callouts=[('首期验收', '全通过'), ('VPP 可调', '4.01MW')],
        chips=['Docker+Dapr+MQTT 微服务', '首期验收全通过 · 可复用',
               'EMS 干跑 · 只生成意图不下发', '可审批/拒绝/过期/替代/审计',
               'EMS 工作台 IT 6MW+储能 10MWh', 'VPP 聚合可调容量 4.01MW'],
        points=[('架构状态', 'Docker+Dapr+MQTT+.NET/Python 微服务；首期已验收全通过、可复用'),
                ('可复用服务', '能源计量、电价、资源（源网荷储+VPP 校验）、优化调度、EMS、控制台/本地网关、配套 VPP（交易/结算）'),
                ('干跑安全模型', '仅生成可审批/拒绝/过期/替代/审计的意图指令，并标记未下发任何控制——即一期开环安全模型，无需重建'),
                ('界面佐证', 'EMS 工作台（IT 6MW+储能 10MWh、现货价驱动）、VPP 聚合可调容量 4.01MW')],
        footer='界面取自 EnergyHub/MicroGrid 自有演示环境（演示数据·非生产环境·不可作为合同验收依据），客户名称已脱敏；与算侧口径相互独立、不并列比较。'),
}

def render(page):
    c = CFG[page]
    acc = c['accent']
    cv = Image.new('RGB', (W, H), WHITE)
    d = ImageDraw.Draw(cv)
    # 顶部细色条
    d.rectangle([0, 0, W, 8], fill=acc)
    d.rectangle([0, 8, W, 11], fill=ORANGE)
    # 主标题
    ft = F(FB, 44)
    d.text((48, 34), c['title'], font=ft, fill=BLUE)
    d.rectangle([50, 96, 50 + 150, 102], fill=ORANGE)

    # 主截图（左）
    hx, hy = 40, 134
    hw, hh = paste_shot(cv, PICS + '\\' + c['hero'], hx, hy, 900, 540, acc)
    hero_bottom = hy + hh

    # 右列：数据大字 + 特性标注
    rx = hx + hw + 28
    rw = W - rx - 36
    cy = hy
    # 两个数据大字块（并排一行）
    fnum = F(FA, 58)
    fnum_cn = F(FB, 44)
    flbl = F(FR, 20)
    bh = 118
    bw = (rw - 16) // 2
    for i, (lbl, val) in enumerate(c['callouts']):
        bx = rx + i * (bw + 16)
        d.rounded_rectangle([bx, cy, bx + bw, cy + bh], 12, fill=LGRAY)
        d.rectangle([bx, cy + 16, bx + 5, cy + bh - 16], fill=ORANGE)
        d.text((bx + 20, cy + 18), lbl, font=flbl, fill=MIDGRAY)
        isnum = bool(re.match(r'^[\d.]+', val))
        fv = fnum if isnum else fnum_cn
        d.text((bx + 18, cy + 48), val, font=fv, fill=ORANGE)
    cy += bh + 18
    fch = F(FR, 21)
    for i, ch in enumerate(c['chips']):
        col = ORANGE if i in c.get('chip_orange_idx', set()) else acc
        lines = wrap(d, ch, fch, rw - 54)
        ch_h = 14 + len(lines) * 28 + 12
        d.rounded_rectangle([rx, cy, rx + rw, cy + ch_h], 10, outline=col, width=2, fill=WHITE)
        d.ellipse([rx + 16, cy + ch_h // 2 - 6, rx + 28, cy + ch_h // 2 + 6], fill=col)
        ty = cy + 13
        for ln in lines:
            d.text((rx + 40, ty), ln, font=fch, fill=DGRAY); ty += 28
        cy += ch_h + 12

    # 底部要点面板
    py0 = max(hero_bottom, cy) + 16
    if py0 > 700: py0 = 700
    d.rounded_rectangle([40, py0, W - 36, H - 16], 14, fill=LGRAY)
    # 副图缩略（右下）
    tw_box = 360
    tx = W - 36 - tw_box - 22
    tw, th = paste_shot(cv, PICS + '\\' + c['thumb'], tx, py0 + 22, tw_box, (H - 16) - (py0 + 22) - 46, acc)
    fcap = F(FR, 15)
    d.text((tx, py0 + 22 + th + 8), '副图：' + ('算侧概览大屏' if page == 13 else 'VPP 调度 · 可调 4.01MW'), font=fcap, fill=MIDGRAY)
    # 要点
    fh2 = F(FB, 23)
    fbody = F(FR, 21)
    px = 70
    pw = tx - px - 30
    yy = py0 + 24
    for k, v in c['points']:
        d.ellipse([px, yy + 8, px + 12, yy + 20], fill=acc)
        d.text((px + 24, yy + 2), k, font=fh2, fill=acc)
        kw = d.textlength(k, font=fh2)
        lines = wrap(d, v, fbody, pw - 24 - kw - 16)
        # 第一行接在标题后，其余换行对齐
        tx0 = px + 24 + kw + 14
        if lines:
            d.text((tx0, yy + 4), lines[0], font=fbody, fill=DGRAY)
            ny = yy + 32
            for ln in lines[1:]:
                d.text((px + 24, ny), ln, font=fbody, fill=DGRAY); ny += 28
            yy = ny + 8 if len(lines) > 1 else yy + 38
        else:
            yy += 38
    # 页脚口径说明
    ff = F(FR, 15)
    fl = wrap(d, c['footer'], ff, W - 90)
    fy = H - 12 - len(fl) * 20
    for ln in fl:
        d.text((48, fy), ln, font=ff, fill=MIDGRAY); fy += 20

    cv.save(OUT % page)
    print('saved', OUT % page, cv.size)

if __name__ == '__main__':
    render(int(sys.argv[1]))
