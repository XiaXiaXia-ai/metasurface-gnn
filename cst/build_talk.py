# -*- coding: utf-8 -*-
"""Nine-slide talk deck: GNN principle, features, pipeline, graph, network, models, results, plan, inspiration."""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.ns import qn

NAVY = RGBColor(0x12, 0x26, 0x3A)
INK = RGBColor(0x2B, 0x38, 0x45)
GRAY = RGBColor(0x5E, 0x6B, 0x78)
MUTED = RGBColor(0x8A, 0x96, 0xA2)
TEAL = RGBColor(0x0E, 0x7C, 0x86)
AMBER = RGBColor(0xC9, 0x7A, 0x24)
LIGHT = RGBColor(0xF4, 0xF6, 0xF8)
LINE = RGBColor(0xDD, 0xE3, 0xE9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
PALE = RGBColor(0xC9, 0xD2, 0xDA)
TINT = RGBColor(0xE4, 0xF1, 0xF2)

FONT = "Microsoft YaHei"


def _set_font(run, size, color, bold=False, spacing=None, baseline=None):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = color
    f.name = FONT
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = rPr.makeelement(qn("a:ea"), {})
        rPr.append(ea)
    ea.set("typeface", FONT)
    if spacing is not None:
        rPr.set("spc", str(spacing))
    if baseline is not None:
        rPr.set("baseline", str(baseline))


def _strip_style(shape):
    sp = shape._element
    style = sp.find(qn("p:style"))
    if style is not None:
        sp.remove(style)


def textbox(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tb


def para(tf, first=False, space_before=0, space_after=0, line=1.1, align=PP_ALIGN.LEFT):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.line_spacing = line
    p.space_before = Pt(space_before)
    p.space_after = Pt(space_after)
    return p


def run(p, text, size, color, bold=False, spacing=None, baseline=None):
    r = p.add_run()
    r.text = text
    _set_font(r, size, color, bold=bold, spacing=spacing, baseline=baseline)
    return r


def rect(slide, x, y, w, h, fill, line_color=None, shape=MSO_SHAPE.RECTANGLE, line_w=1.0):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    _strip_style(s)
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line_color is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line_color
        s.line.width = Pt(line_w)
    s.shadow.inherit = False
    if s.has_text_frame:
        s.text_frame.text = ""
    return s


def arrow(slide, x1, y1, x2, y2, color=RGBColor(0x94, 0xA1, 0xAE), width=1.6):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln.append(tail)
    return c


def badge(slide, x, y, d, num, color, size=11):
    s = rect(slide, x, y, d, d, None, color, MSO_SHAPE.OVAL, line_w=1.25)
    tf = s.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run(p, num, size, color, bold=True)


def header(slide, kicker, title, subtitle, title_size=30):
    tb = textbox(slide, 0.75, 0.42, 11.8, 0.28)
    p = para(tb.text_frame, first=True)
    run(p, "■ ", 9, TEAL)
    run(p, kicker, 12, TEAL, bold=True, spacing=120)

    tb = textbox(slide, 0.75, 0.72, 11.8, 0.66)
    p = para(tb.text_frame, first=True, line=1.0)
    run(p, title, title_size, NAVY, bold=True, spacing=-10)

    tb = textbox(slide, 0.75, 1.42, 11.8, 0.40)
    p = para(tb.text_frame, first=True, line=1.2)
    run(p, subtitle, 13.5, GRAY)

    rect(slide, 0.75, 1.90, 11.83, 0.014, LINE)


def pagenum(slide, idx, total=9):
    tb = textbox(slide, 11.55, 7.04, 1.05, 0.26)
    p = para(tb.text_frame, first=True, align=PP_ALIGN.RIGHT)
    run(p, f"{idx:02d}", 12, NAVY, bold=True)
    run(p, f" /{total:02d}", 10, MUTED)


def strip(slide, text, y=6.55):
    rect(slide, 0.75, y, 11.83, 0.52, NAVY)
    tb = textbox(slide, 0.98, y + 0.11, 11.4, 0.32)
    p = para(tb.text_frame, first=True)
    run(p, text, 12.5, WHITE)


# ----------------------------------------------------------------------------
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]

# ============================== 1 · 原理 ====================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第一部分 · GNN 原理", "每个单元，问一圈邻居",
       "一层 = 看一圈邻居；堆三层 = 看到三圈", title_size=31)

cx, cy, R, SP = 2.75, 3.95, 0.42, 1.12
for r in range(3):
    for c in range(3):
        nx, ny = cx + (c - 1) * SP, cy + (r - 1) * SP
        is_c = (r == 1 and c == 1)
        node = rect(s, nx - R, ny - R, 2 * R, 2 * R,
                    TEAL if is_c else TINT, TEAL if is_c else RGBColor(0x9C, 0xC7, 0xCB),
                    MSO_SHAPE.OVAL, line_w=1.5)
        tf = node.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run(p, "j" if is_c else "i", 13, WHITE if is_c else TEAL, bold=True)

for r in range(3):
    for c in range(3):
        if r == 1 and c == 1:
            continue
        nx, ny = cx + (c - 1) * SP, cy + (r - 1) * SP
        dx, dy = cx - nx, cy - ny
        L = (dx * dx + dy * dy) ** 0.5
        arrow(s, nx + dx / L * R, ny + dy / L * R, cx - dx / L * R, cy - dy / L * R)

tb = textbox(s, 0.95, 5.45, 3.9, 0.6)
p = para(tb.text_frame, first=True, line=1.25)
run(p, "每个单元有 8 个邻居（这里是示意）", 11.5, MUTED)

steps = [
    ("1", "发消息", "邻居 i 把自己的状态、还有“我离你多远、在哪个方向”，发给中心 j。"),
    ("2", "汇总", "中心把所有邻居的消息加起来。谁先谁后无所谓，加起来就行。"),
    ("3", "更新", "中心结合自己原来的状态，更新一次——这就是“一层”。"),
]
for i, (num, head, body) in enumerate(steps):
    y = 2.25 + i * 1.28
    badge(s, 5.25, y + 0.02, 0.46, num, TEAL, size=13)
    tb = textbox(s, 5.90, y, 6.5, 0.40)
    p = para(tb.text_frame, first=True)
    run(p, head, 20, NAVY, bold=True)
    tb = textbox(s, 5.90, y + 0.46, 6.4, 0.60)
    p = para(tb.text_frame, first=True, line=1.25)
    run(p, body, 13.5, INK)

strip(s, "GNN 的全部就是这三步：没有卷积核，只有“谁给谁发消息”。堆三层，信息就传到三圈之外。")
pagenum(s, 1)

# ============================== 2 · 特点 ====================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第一部分 · GNN 特点", "三个别的网络做不到的事",
       "这也是为什么它适合“单元阵列”这种对象", title_size=31)

cards = [
    ("1", "不怕不规则", "CNN 要求整齐网格；GNN 只问“谁挨着谁”。缺单元、异形混排、曲面，都能直接算。"),
    ("2", "结构和物理对得上", "节点就是单元，边就是耦合。模型在算什么，一眼能看懂，不是黑箱。"),
    ("3", "单元数变了不改网络", "参数和阵列大小无关。20×20 和 40×40 用的是同一套权重。"),
]
for i, (num, head, body) in enumerate(cards):
    x = 0.75 + i * 3.98
    rect(s, x, 2.35, 3.72, 3.55, LIGHT)
    rect(s, x, 2.35, 0.05, 3.55, TEAL)

    badge(s, x + 0.28, 2.62, 0.50, num, TEAL, size=14)

    tb = textbox(s, x + 0.28, 3.30, 3.20, 0.80)
    p = para(tb.text_frame, first=True, line=1.1)
    run(p, head, 19, NAVY, bold=True)

    tb = textbox(s, x + 0.28, 4.20, 3.20, 1.55)
    p = para(tb.text_frame, first=True, line=1.35)
    run(p, body, 13.5, INK)

tb = textbox(s, 0.75, 6.05, 11.8, 0.40)
p = para(tb.text_frame, first=True)
run(p, "MLP：没有局部性", 13, GRAY)
run(p, "　　·　　", 13, MUTED)
run(p, "CNN：绑死网格", 13, GRAY)
run(p, "　　·　　", 13, MUTED)
run(p, "GNN：只认邻居", 13, TEAL, bold=True)

strip(s, "一句话：GNN 把“谁影响谁”写进了模型结构，而不是让网络自己猜。")
pagenum(s, 2)

# ============================== 3 · 流程 ====================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第二部分 · 我们的流程", "从一串码，到一张方向图",
       "网络只算 400 个复数，8280 个方向由物理公式算出来")

# CST chip
rect(s, 0.75, 2.20, 4.10, 0.62, TINT)
tb = textbox(s, 0.95, 2.30, 3.80, 0.42)
p = para(tb.text_frame, first=True, line=1.15)
run(p, "数据：CST 全波仿真", 12.5, TEAL, bold=True)
run(p, "　2000 例，306 秒/例", 12, GRAY)

steps = [
    ("1", "码 → 阵列", "100 bit\n→ 400 单元"),
    ("2", "查单元库", "每个单元\n一个 Γ → q0"),
    ("3", "GNN", "每单元 Δq\n＋ 全局 b"),
    ("4", "合成", "q = q0\n+ Δq + b"),
    ("5", "物理算子", "→ 8280 个\n方向的 σ"),
]
BW, BG = 2.12, 0.32
for i, (num, head, body) in enumerate(steps):
    x = 0.75 + i * (BW + BG)
    rect(s, x, 3.25, BW, 1.75, WHITE, LINE, line_w=1.5)
    rect(s, x, 3.25, BW, 0.06, TEAL if i != 4 else AMBER)

    tb = textbox(s, x + 0.16, 3.38, 0.5, 0.28)
    p = para(tb.text_frame, first=True)
    run(p, num, 11, TEAL, bold=True)

    tb = textbox(s, x + 0.16, 3.66, BW - 0.28, 0.34)
    p = para(tb.text_frame, first=True)
    run(p, head, 15, NAVY, bold=True)

    tb = textbox(s, x + 0.16, 4.08, BW - 0.28, 0.80)
    p = para(tb.text_frame, first=True, line=1.25)
    run(p, body, 12, GRAY)

    if i < 4:
        rect(s, x + BW + 0.06, 3.95, 0.20, 0.20, RGBColor(0xC2, 0xCC, 0xD6), shape=MSO_SHAPE.RIGHT_ARROW)

# loss chip
rect(s, 8.95, 5.25, 3.62, 0.62, LIGHT, LINE)
tb = textbox(s, 9.12, 5.35, 3.35, 0.42)
p = para(tb.text_frame, first=True, line=1.15)
run(p, "损失：dB 域 asinh 压缩 MSE", 12, INK)

tb = textbox(s, 0.75, 5.30, 7.9, 0.55)
p = para(tb.text_frame, first=True, line=1.3)
run(p, "训练时用 CST 的方向图当标签；推理时一次前向就出整张图，不再跑仿真。", 12.5, GRAY)

strip(s, "关键：网络不学“波怎么传播”，只学“每个单元的权重偏了多少”。传播交给写死的衍射公式。")
pagenum(s, 3)

# ============================== 4 · 节点与边 ================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第三部分 · 节点与边", "节点和边，装的全是物理量",
       "400 个节点、2964 条边；每个数都有物理含义，不是随便凑的特征")

# nodes
rect(s, 0.75, 2.20, 5.75, 3.95, LIGHT)
rect(s, 0.75, 2.20, 0.05, 3.95, TEAL)
tb = textbox(s, 1.05, 2.38, 5.2, 0.40)
p = para(tb.text_frame, first=True)
run(p, "节点：400 个单元", 18, NAVY, bold=True)

node_groups = [
    ("身份", "码位 0/1、±1"),
    ("位置", "x/λ、y/λ"),
    ("物理", "Γ 实部、Γ 虚部、|Γ|"),
    ("边界", "是否边缘、法向"),
]
for i, (k, v) in enumerate(node_groups):
    y = 2.95 + i * 0.72
    tb = textbox(s, 1.05, y, 1.05, 0.34)
    p = para(tb.text_frame, first=True)
    run(p, k, 13, TEAL, bold=True)
    tb = textbox(s, 2.10, y, 4.2, 0.34)
    p = para(tb.text_frame, first=True)
    run(p, v, 13.5, INK)

tb = textbox(s, 1.05, 5.85, 5.2, 0.30)
p = para(tb.text_frame, first=True)
run(p, "告诉网络：这个单元在哪、什么状态、反了多少", 11, MUTED)

# edges
rect(s, 6.80, 2.20, 5.78, 3.95, LIGHT)
rect(s, 6.80, 2.20, 0.05, 3.95, AMBER)
tb = textbox(s, 7.10, 2.38, 5.2, 0.40)
p = para(tb.text_frame, first=True)
run(p, "边：2964 条", 18, NAVY, bold=True)

edge_groups = [
    ("位移", "Δx/λ、Δy/λ"),
    ("距离", "r/λ"),
    ("方位", "cos φ、sin φ"),
]
for i, (k, v) in enumerate(edge_groups):
    y = 2.95 + i * 0.72
    tb = textbox(s, 7.10, y, 1.05, 0.34)
    p = para(tb.text_frame, first=True)
    run(p, k, 13, AMBER, bold=True)
    tb = textbox(s, 8.15, y, 4.2, 0.34)
    p = para(tb.text_frame, first=True)
    run(p, v, 13.5, INK)

tb = textbox(s, 7.10, 5.30, 5.2, 0.65)
p = para(tb.text_frame, first=True, line=1.3)
run(p, "告诉网络：往哪个方向、隔多远，耦合该有多强", 11, MUTED)

strip(s, "8 邻域、不做周期延拓：边缘单元只有 3–5 个邻居，靠“边缘标记”告诉网络别当成内部单元。")
pagenum(s, 4)

# ============================== 5 · 网络 ====================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第四部分 · 网络", "输入 400 个单元，输出 400 个修正",
       "3 层消息传递，每单元出 2 个数；整张图再出 1 个复数")

flow = [("输入", "400 单元 × 9 维"), ("消息传递", "3 层，每层 64 维"), ("两个输出头", "每节点 2 个 ＋ 整图 1 个"), ("合成", "q = q0 + Δq + b")]
FW, FG = 2.62, 0.30
for i, (head, body) in enumerate(flow):
    x = 0.75 + i * (FW + FG)
    rect(s, x, 2.22, FW, 1.05, WHITE, LINE, line_w=1.5)
    rect(s, x, 2.22, FW, 0.05, TEAL)

    tb = textbox(s, x + 0.18, 2.38, FW - 0.3, 0.32)
    p = para(tb.text_frame, first=True)
    run(p, head, 15, NAVY, bold=True)

    tb = textbox(s, x + 0.18, 2.74, FW - 0.3, 0.34)
    p = para(tb.text_frame, first=True)
    run(p, body, 11.5, GRAY)

    if i < 3:
        rect(s, x + FW + 0.05, 2.60, 0.20, 0.20, RGBColor(0xC2, 0xCC, 0xD6), shape=MSO_SHAPE.RIGHT_ARROW)

ops = [
    ("1", "零初始化", "一开始 Δq = b = 0，输出正好等于 M0。之后涨的每一分，都是学出来的。"),
    ("2", "去均值", "强制 Δq 的均值为 0，让 b 专门管“整块板一起偏”，两者不打架。"),
    ("3", "物理读出", "不学 8280 个方向，用衍射公式算。可微，能直接做反设计。"),
]
for i, (num, head, body) in enumerate(ops):
    x = 0.75 + i * 3.98
    rect(s, x, 3.75, 3.72, 2.30, LIGHT)
    badge(s, x + 0.26, 3.95, 0.44, num, TEAL, size=12)

    tb = textbox(s, x + 0.84, 4.00, 2.70, 0.38)
    p = para(tb.text_frame, first=True)
    run(p, head, 16, NAVY, bold=True)

    tb = textbox(s, x + 0.26, 4.62, 3.20, 1.25)
    p = para(tb.text_frame, first=True, line=1.35)
    run(p, body, 12.5, INK)

strip(s, "三个设计都是为了同一件事：让网络只学“物理算不准的那一点”，其余交给物理。")
pagenum(s, 5)

# ============================== 6 · 四个模型 ================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第五部分 · 四个模型", "先分清 M0 / M1 / M2 / M3",
       "四个模型吃同一批数据、同一个划分，比出来的数才有意义")

heads = [("模型", 0.80, 2.0), ("是什么", 2.95, 5.3), ("干什么用", 8.55, 3.9)]
for txt, x, w in heads:
    tb = textbox(s, x, 2.12, w, 0.30)
    p = para(tb.text_frame, first=True)
    run(p, txt, 11.5, MUTED, bold=True, spacing=60)

rows = [
    ("M0", "纯物理：查单元库 + 衍射公式，0 参数", "物理下限，也是“完全不学习”的参照"),
    ("M1", "CNN（U-Net）：直接从码出方向图，21 万参数", "没有物理、没有图的对照"),
    ("M2", "GNN 直接出 q，不加 q0，9.7 万参数", "消融：残差到底值不值"),
    ("M3", "我们的：q = q0 + Δq + b，10 万参数", "主模型"),
]
for i, (name, what, use) in enumerate(rows):
    y = 2.52 + i * 0.86
    if name == "M3":
        rect(s, 0.75, y - 0.06, 11.83, 0.80, TINT)
    tb = textbox(s, 0.80, y + 0.10, 1.6, 0.44)
    p = para(tb.text_frame, first=True)
    run(p, name, 20, NAVY if name == "M3" else GRAY, bold=True)

    tb = textbox(s, 2.95, y + 0.12, 5.35, 0.44)
    p = para(tb.text_frame, first=True, line=1.2)
    run(p, what, 13.5, INK)

    tb = textbox(s, 8.55, y + 0.12, 3.95, 0.44)
    p = para(tb.text_frame, first=True, line=1.2)
    run(p, use, 13, GRAY)

tb = textbox(s, 0.75, 6.02, 11.83, 0.45)
p = para(tb.text_frame, first=True, line=1.25)
run(p, "另外还有 M0g：", 12, TEAL, bold=True)
run(p, "给 M0 每个样本单独拟合一个复数，只当“上界”参考，不是可用的模型。", 12, GRAY)

pagenum(s, 6)

# ============================== 7 · 结果 ====================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第六部分 · 结果", "291 个样本，镜面补上了",
       "先跑 291 个样本（其中 44 例做测试），训练 5 个 epoch 的初步结果")

stats = [
    ("镜面误差", "−16.1 → +0.16", "dB"),
    ("RMSE", "4.65 → 2.64", "dB"),
    ("方向图相关", "0.87 → 0.96", "rho_db"),
]
for i, (lab, val, unit) in enumerate(stats):
    x = 0.75 + i * 4.05
    rect(s, x, 2.18, 3.72, 1.05, LIGHT)
    tb = textbox(s, x + 0.22, 2.30, 3.3, 0.28)
    p = para(tb.text_frame, first=True)
    run(p, lab, 11.5, GRAY)
    tb = textbox(s, x + 0.22, 2.60, 3.4, 0.44)
    p = para(tb.text_frame, first=True)
    run(p, val, 20, NAVY, bold=True)
    run(p, "  " + unit, 11, MUTED)

tb = textbox(s, 0.75, 3.55, 5.6, 0.34)
p = para(tb.text_frame, first=True)
run(p, "M3 分角度误差（dB）", 13, NAVY, bold=True)

bands = [("0–5°", 0.29), ("5–15°", 0.98), ("15–30°", 0.99), ("30–60°", 1.50), ("60–90°", 4.10)]
for i, (lab, v) in enumerate(bands):
    y = 3.98 + i * 0.46
    tb = textbox(s, 0.75, y, 0.95, 0.30)
    p = para(tb.text_frame, first=True)
    run(p, lab, 12, GRAY)

    w = max(0.08, v / 4.10 * 3.10)
    rect(s, 1.75, y + 0.04, w, 0.22, AMBER if v > 2 else TEAL)

    tb = textbox(s, 1.75 + w + 0.10, y, 1.0, 0.30)
    p = para(tb.text_frame, first=True)
    run(p, f"{v:.2f}", 12, INK)

concl = [
    ("网络自己学到 |b| = 0.37，和理论值一致", "它自己找到了那个“共同模”"),
    ("误差从镜面转移到了大角域", "镜面 14 dB → 0.29；掠射 4.1 dB 成了新短板"),
    ("这只是初步结果", "291 例、5 个 epoch；全量 2000 例还没训"),
]
for i, (lead, tail) in enumerate(concl):
    y = 2.18 + i * 1.10
    tb = textbox(s, 6.85, y, 0.3, 0.34)
    p = para(tb.text_frame, first=True)
    run(p, "·", 18, TEAL, bold=True)

    tb = textbox(s, 7.12, y, 5.45, 0.90)
    p = para(tb.text_frame, first=True, line=1.25)
    run(p, lead, 13.5, NAVY, bold=True)
    p = para(tb.text_frame, line=1.25)
    run(p, tail, 12, GRAY)

strip(s, "结论：物理主干是对的，网络只补了它算不准的那部分；这一步已经能跑通，剩下的是把数据量和场景补上。")
pagenum(s, 7)

# ============================== 8 · 计划 ====================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第七部分 · 后续计划", "下一步：把四个维度打开",
       "模型骨架已经不用动，缺的是场景和数据")

plans = [
    ("尺寸外推", "20×20 → 更大口径", "滑窗、分块，块与块之间互相纠错"),
    ("异构单元", "不同相位单元混排", "需要异质图：节点和边都分类型"),
    ("曲面共形", "平面 → 曲面", "位置和法向已经进特征，改图结构即可"),
    ("多频宽带", "单频 → 多频", "色散进单元库；阵中 f0 已经偏到 9.6 GHz"),
]
for i, (head, now, how) in enumerate(plans):
    col, row = i % 2, i // 2
    x = 0.75 + col * 6.05
    y = 2.20 + row * 1.78

    rect(s, x, y, 5.80, 1.58, LIGHT)
    rect(s, x, y, 0.05, 1.58, TEAL)

    tb = textbox(s, x + 0.26, y + 0.16, 5.2, 0.40)
    p = para(tb.text_frame, first=True)
    run(p, head, 18, NAVY, bold=True)

    tb = textbox(s, x + 0.26, y + 0.60, 5.25, 0.34)
    p = para(tb.text_frame, first=True)
    run(p, now, 13, AMBER, bold=True)

    tb = textbox(s, x + 0.26, y + 0.98, 5.25, 0.50)
    p = para(tb.text_frame, first=True, line=1.2)
    run(p, how, 12, GRAY)

# roadmap
rect(s, 0.75, 5.95, 11.83, 0.022, LINE)
tb = textbox(s, 0.75, 6.05, 11.8, 0.40)
p = para(tb.text_frame, first=True)
run(p, "近期：", 12, TEAL, bold=True)
run(p, "全量 2000 例训练", 12, INK)
run(p, "　→　中期：", 12, TEAL, bold=True)
run(p, "异质图 + 尺寸外推", 12, INK)
run(p, "　→　远期：", 12, TEAL, bold=True)
run(p, "曲面、多频、反设计闭环", 12, INK)

pagenum(s, 8)

# ============================== 9 · 启发 ====================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第八部分 · 会议启发", "两篇会议工作，两条能直接用的思路",
       "只借组织方式，不借网络结构")

cols = [
    ("异构 GCN", "节点分类型，边也分类型",
     ["面、楔、收发点 = 不同节点", "直射、反射、绕射 = 不同边",
      "每种边有自己的消息函数", "→ 我们的不同相位单元，就是多类型节点"]),
    ("自回归外推", "一次只预测下一步，再喂回去",
     ["网络只学“下一米”怎么变", "把预测当输入，一步步推到 100 米",
      "训练时故意喂错的预测，学会纠错", "→ 尺寸外推时，块与块之间可以这样接力"]),
]
for i, (head, sub_h, items) in enumerate(cols):
    x = 0.75 + i * 6.05
    rect(s, x, 2.20, 5.80, 3.95, LIGHT)
    rect(s, x, 2.20, 0.05, 3.95, TEAL if i == 0 else AMBER)

    tb = textbox(s, x + 0.28, 2.38, 5.2, 0.40)
    p = para(tb.text_frame, first=True)
    run(p, head, 19, NAVY, bold=True)

    tb = textbox(s, x + 0.28, 2.82, 5.2, 0.34)
    p = para(tb.text_frame, first=True)
    run(p, sub_h, 12.5, GRAY)

    for j, it in enumerate(items):
        y = 3.35 + j * 0.62
        tb = textbox(s, x + 0.28, y, 0.2, 0.34)
        p = para(tb.text_frame, first=True)
        run(p, "·", 14, TEAL if i == 0 else AMBER, bold=True)

        tb = textbox(s, x + 0.52, y, 5.0, 0.40)
        p = para(tb.text_frame, first=True, line=1.15)
        run(p, it, 13, INK if not it.startswith("→") else NAVY,
            bold=it.startswith("→"))

strip(s, "借的是“异质图 + 逐步外推”的组织方式，不是他们的网络结构。")
pagenum(s, 9)

out = r"D:\DSHNESS\GNN\GNN_编码超表面_汇报_九页.pptx"
prs.save(out)
print("saved", out)
