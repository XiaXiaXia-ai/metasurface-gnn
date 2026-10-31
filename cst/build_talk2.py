# -*- coding: utf-8 -*-
"""Eight-slide talk: principle+features, pipeline, graph, network, models, results, plan, inspiration."""

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
TINT = RGBColor(0xE4, 0xF1, 0xF2)
PALE = RGBColor(0xC9, 0xD2, 0xDA)

FONT = "Microsoft YaHei"


def _set_font(run, size, color, bold=False, spacing=None):
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


def run(p, text, size, color, bold=False, spacing=None):
    r = p.add_run()
    r.text = text
    _set_font(r, size, color, bold=bold, spacing=spacing)
    return r


def rect(slide, x, y, w, h, fill, line_color=None, shape=MSO_SHAPE.RECTANGLE, line_w=1.25):
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


def arrow(slide, x1, y1, x2, y2, width=1.6):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = RGBColor(0x94, 0xA1, 0xAE)
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln.append(tail)
    return c


def badge(slide, x, y, d, num, color, size=12):
    s = rect(slide, x, y, d, d, None, color, MSO_SHAPE.OVAL, line_w=1.5)
    tf = s.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run(p, num, size, color, bold=True)


def header(slide, kicker, title, subtitle, title_size=31):
    tb = textbox(slide, 0.75, 0.42, 11.8, 0.30)
    p = para(tb.text_frame, first=True)
    run(p, "■ ", 9, TEAL)
    run(p, kicker, 12, TEAL, bold=True, spacing=120)

    tb = textbox(slide, 0.75, 0.74, 11.8, 0.66)
    p = para(tb.text_frame, first=True, line=1.0)
    run(p, title, title_size, NAVY, bold=True, spacing=-10)

    tb = textbox(slide, 0.75, 1.44, 11.8, 0.40)
    p = para(tb.text_frame, first=True, line=1.2)
    run(p, subtitle, 13.5, GRAY)

    rect(slide, 0.75, 1.92, 11.83, 0.014, LINE)


def pagenum(slide, idx, total=9):
    tb = textbox(slide, 11.60, 7.06, 1.00, 0.26)
    p = para(tb.text_frame, first=True, align=PP_ALIGN.RIGHT)
    run(p, f"{idx:02d}", 12, NAVY, bold=True)
    run(p, f" /{total:02d}", 10, MUTED)


def strip(slide, text, y=6.55):
    rect(slide, 0.75, y, 11.83, 0.50, NAVY)
    tb = textbox(slide, 0.98, y + 0.11, 11.4, 0.30)
    p = para(tb.text_frame, first=True)
    run(p, text, 12.5, WHITE)


# ----------------------------------------------------------------------------
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]

# ============================== 1 · 为什么是 GNN =============================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第一部分 · 为什么是 GNN", "三个特点，正好对上我们阵列的三个痛点",
       "400 个单元、只和邻居耦合、每个单元都带物理量——这三点决定了该用什么网络",
       title_size=29)

cards = [
    ("1", "只认邻居，不认网格",
     "400 个单元互相耦合。CNN 要整齐网格，缺单元、异形、曲面就失效。",
     "节点 = 单元，边 = 耦合；谁挨着谁就连边，布局变了只改图。"),
    ("2", "节点和边都是物理量",
     "码位、位置、Γ 都得进模型，不能只喂一张黑白比特图。",
     "节点 9 维（码位/位置/Γ/边界），边 5 维（位移/距离/方位）。"),
    ("3", "单元数变了，不用重训",
     "以后要做 40×40、缺口阵、曲面共形，每种都重训不现实。",
     "参数和阵列大小无关，换尺寸只换图，权重不动。"),
]
for i, (num, head, prob, sol) in enumerate(cards):
    x = 0.75 + i * 3.95
    rect(s, x, 2.14, 3.72, 3.66, LIGHT)
    rect(s, x, 2.14, 0.05, 3.66, TEAL)

    badge(s, x + 0.26, 2.34, 0.50, num, TEAL, size=13.5)

    tb = textbox(s, x + 0.26, 3.02, 3.18, 0.62)
    p = para(tb.text_frame, first=True, line=1.08)
    run(p, head, 17, NAVY, bold=True)

    tb = textbox(s, x + 0.26, 3.78, 3.18, 0.22)
    p = para(tb.text_frame, first=True)
    run(p, "我们的问题", 10, AMBER, bold=True, spacing=40)

    tb = textbox(s, x + 0.26, 4.04, 3.18, 0.78)
    p = para(tb.text_frame, first=True, line=1.28)
    run(p, prob, 11.5, GRAY)

    tb = textbox(s, x + 0.26, 4.90, 3.18, 0.22)
    p = para(tb.text_frame, first=True)
    run(p, "GNN 怎么接", 10, TEAL, bold=True, spacing=40)

    tb = textbox(s, x + 0.26, 5.14, 3.18, 0.56)
    p = para(tb.text_frame, first=True, line=1.28)
    run(p, sol, 11.5, INK)

# mechanism band
rect(s, 0.75, 5.98, 11.83, 0.68, TINT)
rect(s, 0.75, 5.98, 0.05, 0.68, TEAL)

for r in range(3):
    for c in range(3):
        is_c = (r == 1 and c == 1)
        rect(s, 0.95 + c * 0.20, 6.12 + r * 0.20, 0.18, 0.18,
             TEAL if is_c else TINT,
             TEAL if is_c else RGBColor(0x9C, 0xC7, 0xCB), MSO_SHAPE.OVAL, line_w=1.0)

tb = textbox(s, 1.90, 6.10, 10.4, 0.50)
p = para(tb.text_frame, first=True, line=1.25)
run(p, "一层 = 每个单元问一圈邻居；三层 = 看到三圈（≈ 1.4λ）。", 12, NAVY, bold=True)
run(p, "网络只管局部耦合，整孔径的干涉交给物理算子。", 12, GRAY)

s.notes_slide.notes_text_frame.text = (
    "GNN 三步：① 每个邻居 i 把自身状态和相对位置发给中心 j；"
    "② 中心把所有消息相加（与顺序无关）；③ 结合自身旧状态更新一次，这就是一层。"
    "堆三层，信息传三圈。")

pagenum(s, 1)

# ============================== 2 · 流程 ====================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第二部分 · 我们的流程", "从一串码，到一张方向图",
       "网络只算 400 个复数，8280 个方向由物理公式算出来")

rect(s, 0.75, 2.12, 5.60, 0.62, TINT)
tb = textbox(s, 0.98, 2.22, 5.2, 0.42)
p = para(tb.text_frame, first=True)
run(p, "数据：CST 全波仿真", 13, TEAL, bold=True)
run(p, "　2000 例 · 306 秒/例 · 单频单极化", 11.5, GRAY)

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
    rect(s, x, 3.10, BW, 2.30, WHITE, LINE, line_w=1.75)
    rect(s, x, 3.10, BW, 0.06, TEAL if i != 4 else AMBER)

    tb = textbox(s, x + 0.16, 3.26, 0.5, 0.30)
    p = para(tb.text_frame, first=True)
    run(p, num, 11, TEAL, bold=True)

    tb = textbox(s, x + 0.16, 3.58, BW - 0.28, 0.36)
    p = para(tb.text_frame, first=True)
    run(p, head, 16, NAVY, bold=True)

    tb = textbox(s, x + 0.16, 3.98, BW - 0.28, 0.95)
    p = para(tb.text_frame, first=True, line=1.30)
    run(p, body, 13, GRAY)

    if i < 4:
        rect(s, x + BW + 0.06, 4.05, 0.20, 0.20, RGBColor(0xC2, 0xCC, 0xD6), shape=MSO_SHAPE.RIGHT_ARROW)

tb = textbox(s, 0.75, 5.66, 8.0, 0.40)
p = para(tb.text_frame, first=True, line=1.25)
run(p, "训练时用 CST 的方向图当标签；推理时一次前向出整张图，不再跑仿真。", 12.5, GRAY)

rect(s, 8.95, 5.58, 3.62, 0.62, LIGHT, LINE)
tb = textbox(s, 9.15, 5.68, 3.3, 0.42)
p = para(tb.text_frame, first=True)
run(p, "损失：dB 域 asinh 压缩 MSE", 12, INK)

strip(s, "关键：网络不学“波怎么传播”，只学“每个单元的权重偏了多少”。")
pagenum(s, 2)

# ============================== 3 · 节点与边 ================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第三部分 · 节点与边", "节点和边，装的全是物理量",
       "400 个节点、2964 条边；每个数都有物理含义")

# nodes
rect(s, 0.75, 2.10, 5.72, 4.12, LIGHT)
rect(s, 0.75, 2.10, 0.05, 4.12, TEAL)
tb = textbox(s, 1.05, 2.24, 5.2, 0.40)
p = para(tb.text_frame, first=True)
run(p, "节点：400 个单元（9 个数）", 17, NAVY, bold=True)

node_rows = [
    ("身份", "码位 0/1、±1", "这一格是哪种相位"),
    ("位置", "x/λ、y/λ", "在阵列的哪个位置"),
    ("物理", "Γ 实部、虚部、|Γ|", "单元本身反多少、反多强"),
    ("边界", "是否边缘、法向", "邻居少不少、是不是平面"),
]
for i, (k, v, note) in enumerate(node_rows):
    y = 2.78 + i * 0.84
    tb = textbox(s, 1.05, y, 0.90, 0.30)
    p = para(tb.text_frame, first=True)
    run(p, k, 12.5, TEAL, bold=True)
    tb = textbox(s, 1.95, y, 4.3, 0.30)
    p = para(tb.text_frame, first=True)
    run(p, v, 13.5, INK)
    tb = textbox(s, 1.95, y + 0.32, 4.3, 0.30)
    p = para(tb.text_frame, first=True)
    run(p, note, 11.5, MUTED)

# edges
rect(s, 6.80, 2.10, 5.78, 4.12, LIGHT)
rect(s, 6.80, 2.10, 0.05, 4.12, AMBER)
tb = textbox(s, 7.10, 2.24, 5.2, 0.40)
p = para(tb.text_frame, first=True)
run(p, "边：2964 条（5 个数）", 17, NAVY, bold=True)

edge_rows = [
    ("位移", "Δx/λ、Δy/λ", "邻居在哪个方向"),
    ("距离", "r/λ", "隔了多远，耦合多强"),
    ("方位", "cos φ、sin φ", "正对还是斜着"),
]
for i, (k, v, note) in enumerate(edge_rows):
    y = 2.78 + i * 0.84
    tb = textbox(s, 7.10, y, 0.90, 0.30)
    p = para(tb.text_frame, first=True)
    run(p, k, 12.5, AMBER, bold=True)
    tb = textbox(s, 8.00, y, 4.3, 0.30)
    p = para(tb.text_frame, first=True)
    run(p, v, 13.5, INK)
    tb = textbox(s, 8.00, y + 0.32, 4.3, 0.30)
    p = para(tb.text_frame, first=True)
    run(p, note, 11.5, MUTED)

tb = textbox(s, 7.10, 5.42, 5.0, 0.60)
p = para(tb.text_frame, first=True, line=1.3)
run(p, "每格只连上下左右和四个对角，不做周期延拓。", 12, GRAY)

strip(s, "边缘单元只有 3–5 个邻居，靠“是否边缘”这一位告诉网络：别把它当内部单元。")
pagenum(s, 3)

# ============================== 4 · 网络 ====================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第四部分 · 网络", "输入 400 个单元，输出 400 个修正",
       "3 层消息传递；每单元出 2 个数，整张图再出 1 个复数")

flow = [("输入", "400 单元 × 9 维"), ("消息传递", "3 层，每层 64 维"), ("两个输出头", "每节点 2 个 ＋ 整图 1 个"), ("合成", "q = q0 + Δq + b")]
FW, FG = 2.62, 0.30
for i, (head, body) in enumerate(flow):
    x = 0.75 + i * (FW + FG)
    rect(s, x, 2.10, FW, 1.12, WHITE, LINE, line_w=1.75)
    rect(s, x, 2.10, FW, 0.05, TEAL)

    tb = textbox(s, x + 0.18, 2.26, FW - 0.3, 0.34)
    p = para(tb.text_frame, first=True)
    run(p, head, 16, NAVY, bold=True)

    tb = textbox(s, x + 0.18, 2.66, FW - 0.3, 0.40)
    p = para(tb.text_frame, first=True, line=1.15)
    run(p, body, 11.5, GRAY)

    if i < 3:
        rect(s, x + FW + 0.05, 2.56, 0.20, 0.20, RGBColor(0xC2, 0xCC, 0xD6), shape=MSO_SHAPE.RIGHT_ARROW)

ops = [
    ("1", "零初始化", "一开始 Δq = b = 0，输出正好等于 M0。之后涨的每一分，都是学出来的。",
     "→ 改进可归因；分布外还能退回 M0"),
    ("2", "去均值", "强制 Δq 的均值为 0，让 b 专门管“整块板一起偏”，两者不打架。",
     "→ |b| 才有物理意义（≈ 0.37）"),
    ("3", "物理读出", "不学 8280 个方向，用衍射公式算。可微，能直接做反设计。",
     "→ 反设计只需对 400 个 q 求梯度"),
    ("4", "复数拆两路", "实部、虚部分开算，避开复数求导的坑，行为完全可预期。",
     "→ 训练稳定，结果可复现"),
]
for i, (num, head, body, gain) in enumerate(ops):
    x = 0.72 + i * 3.02
    rect(s, x, 3.50, 2.88, 2.42, LIGHT)
    badge(s, x + 0.22, 3.66, 0.40, num, TEAL, size=11.5)

    tb = textbox(s, x + 0.72, 3.70, 2.05, 0.36)
    p = para(tb.text_frame, first=True)
    run(p, head, 15, NAVY, bold=True)

    tb = textbox(s, x + 0.22, 4.26, 2.50, 1.10)
    p = para(tb.text_frame, first=True, line=1.28)
    run(p, body, 12.5, INK)

    tb = textbox(s, x + 0.22, 5.40, 2.52, 0.42)
    p = para(tb.text_frame, first=True, line=1.15)
    run(p, gain, 10.5, MUTED)

strip(s, "四个设计都为同一件事：让网络只学“物理算不准的那一点”，其余交给物理。")
pagenum(s, 4)

# ============================== 5 · q 的四个符号 =============================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第四部分 · 补充", "q 是什么：四个符号，一次讲清",
       "q 是每个单元的复权重（幅度＋相位），它决定这一格怎么反波")

# equation panel
rect(s, 0.75, 2.10, 11.83, 0.78, LIGHT)
tb = textbox(s, 1.10, 2.24, 11.2, 0.50)
p = para(tb.text_frame, first=True)
run(p, "q", 26, NAVY, bold=True)
run(p, " = ", 24, GRAY)
run(p, "q0", 26, TEAL, bold=True)
run(p, "（标称）", 13, TEAL)
run(p, "  +  ", 20, GRAY)
run(p, "Δq", 26, AMBER, bold=True)
run(p, "（逐单元修正）", 13, AMBER)
run(p, "  +  ", 20, GRAY)
run(p, "b", 26, NAVY, bold=True)
run(p, "（共同偏移）", 13, NAVY)

rows = [
    ("q0", TEAL, "单元库里查出来的标称权重。这一格是 0 还是 1，就决定了它；0 参数。",
     "只有两个值：0.867∠−5.3° 和 0.852∠174.6°"),
    ("Δq", AMBER, "GNN 吐出来的逐单元修正，400 个复数。补的是邻居耦合、边缘效应带来的偏差。",
     "逐格不同，同一个宏比特里的 4 个单元也能不一样"),
    ("b", NAVY, "整张图平均出来的共同偏移，1 个复数。补的是整块板朝法向一起多反的那一点。",
     "所有单元共用同一个 b，网络自己学到 |b| ≈ 0.37"),
    ("q", NAVY, "三者相加，就是这一格最终的复权重；代进衍射公式，就得到 8280 个方向。",
     "它是网络真正交付的东西，也是反设计的抓手"),
]
for i, (sym, colr, what, note) in enumerate(rows):
    y = 3.06 + i * 0.76
    if i == 3:
        rect(s, 0.75, y - 0.06, 11.83, 0.76, TINT)

    tb = textbox(s, 0.80, y, 1.30, 0.34)
    p = para(tb.text_frame, first=True)
    run(p, sym, 19, colr, bold=True)

    tb = textbox(s, 2.05, y, 6.30, 0.62)
    p = para(tb.text_frame, first=True, line=1.2)
    run(p, what, 13, INK)

    tb = textbox(s, 8.55, y, 3.95, 0.62)
    p = para(tb.text_frame, first=True, line=1.2)
    run(p, note, 11.5, MUTED)

tb = textbox(s, 0.75, 6.14, 11.83, 0.30)
p = para(tb.text_frame, first=True)
run(p, "等价写法：论文里的 γ = Γ", 10.5, MUTED)
run(p, "bit", 8.5, MUTED)
run(p, "(1 + δ)，δ 就是这里 Δq/q0 那一类修正。", 10.5, MUTED)

strip(s, "一句话：q0 是“应该反多少”，Δq 是“实际偏了多少”，b 是“整块板一起偏了多少”。")
pagenum(s, 5)

# ============================== 6 · 四个模型 ================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第五部分 · 四个模型", "先分清 M0 / M1 / M2 / M3",
       "吃同一批数据、同一个划分，比出来的数才有意义")

heads = [("模型", 0.80, 2.0), ("是什么", 2.95, 5.3), ("干什么用", 8.55, 3.9)]
for txt, x, w in heads:
    tb = textbox(s, x, 2.10, w, 0.30)
    p = para(tb.text_frame, first=True)
    run(p, txt, 11.5, MUTED, bold=True, spacing=60)

rows = [
    ("M0", "纯物理：查单元库 + 衍射公式，0 参数", "物理下限，也是“完全不学习”的参照"),
    ("M1", "CNN（U-Net）：直接从码出方向图，21 万参数", "没有物理、没有图的对照"),
    ("M2", "GNN 直接出 q，不加 q0，9.7 万参数", "消融：残差到底值不值"),
    ("M3", "我们的：q = q0 + Δq + b，10 万参数", "主模型"),
]
for i, (name, what, use) in enumerate(rows):
    y = 2.50 + i * 0.88
    if name == "M3":
        rect(s, 0.75, y - 0.05, 11.83, 0.86, TINT)
    tb = textbox(s, 0.80, y + 0.14, 1.6, 0.46)
    p = para(tb.text_frame, first=True)
    run(p, name, 21, NAVY if name == "M3" else GRAY, bold=True)

    tb = textbox(s, 2.95, y + 0.16, 5.35, 0.46)
    p = para(tb.text_frame, first=True, line=1.2)
    run(p, what, 14, INK)

    tb = textbox(s, 8.55, y + 0.16, 3.95, 0.46)
    p = para(tb.text_frame, first=True, line=1.2)
    run(p, use, 13, GRAY)

tb = textbox(s, 0.75, 6.10, 11.83, 0.34)
p = para(tb.text_frame, first=True)
run(p, "另外还有 M0g：", 12, TEAL, bold=True)
run(p, "给 M0 每个样本单独拟合一个复数，只当“上界”参考，不是可用的模型。", 12, GRAY)

tb = textbox(s, 0.75, 6.52, 11.83, 0.34)
p = para(tb.text_frame, first=True)
run(p, "目前只跑了 M0 和 M3；M1、M2 还没训，是下一步要补的对照。", 12, AMBER, bold=True)

pagenum(s, 6)

# ============================== 6 · 结果 ====================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第六部分 · 结果", "291 个样本，法向的缺口补上了",
       "先跑 291 个样本（其中 44 例做测试），训练 5 个 epoch")

stats = [
    ("法向误差（θ=0°）", "−16.1 → +0.16", "dB"),
    ("RMSE", "4.65 → 2.64", "dB"),
    ("方向图相关", "0.87 → 0.96", "rho_db"),
]
for i, (lab, val, unit) in enumerate(stats):
    x = 0.75 + i * 4.05
    rect(s, x, 2.10, 3.72, 1.02, LIGHT)
    tb = textbox(s, x + 0.22, 2.22, 3.3, 0.28)
    p = para(tb.text_frame, first=True)
    run(p, lab, 11.5, GRAY)
    tb = textbox(s, x + 0.22, 2.52, 3.4, 0.46)
    p = para(tb.text_frame, first=True)
    run(p, val, 20, NAVY, bold=True)
    if unit:
        run(p, "  " + unit, 11, MUTED)

pic = s.shapes.add_picture(r"D:\DSHNESS\GNN\fig_talk\polar_compare.png",
                           Inches(0.75), Inches(3.26), width=Inches(7.95))
ph = 7.95 * pic.height / pic.width
rect(s, 0.75, 3.26, 7.95, ph, None, LINE, line_w=0.75)

tb = textbox(s, 0.75, 3.26 + ph + 0.08, 7.95, 0.46)
p = para(tb.text_frame, first=True, line=1.2)
run(p, "ρ 为单切面（φ=0°/180°）dB 域相关系数，样本取 test case 158；右上角 0.87 → 0.96 是全角域 rho_db。", 9.5, MUTED)

tb = textbox(s, 9.05, 3.16, 3.5, 0.28)
p = para(tb.text_frame, first=True)
run(p, "结论", 11, MUTED, bold=True, spacing=60)

concl = [
    ("|b| 自己学到 0.37", "和理论值一致——它自己找到了那个共同分量"),
    ("误差从法向迁到大角域", "法向 0.29 dB，掠射 4.1 dB 成了新短板"),
    ("291 例、5 个 epoch", "初步结果，全量 2000 例还没训"),
]
for i, (lead, tail) in enumerate(concl):
    y = 3.52 + i * 0.95
    tb = textbox(s, 9.05, y, 0.22, 0.30)
    p = para(tb.text_frame, first=True)
    run(p, "·", 18, TEAL, bold=True)

    tb = textbox(s, 9.30, y, 3.30, 0.75)
    p = para(tb.text_frame, first=True, line=1.2)
    run(p, lead, 12.5, NAVY, bold=True)
    p = para(tb.text_frame, line=1.2)
    run(p, tail, 11, GRAY)

pagenum(s, 7)

# ============================== 7 · 计划 ====================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第七部分 · 后续计划", "下一步：把四个维度打开",
       "模型骨架不用动，缺的是场景和数据")

plans = [
    ("尺寸外推", "20×20 → 更大口径", "滑窗、分块，块与块之间互相纠错"),
    ("异构单元", "不同相位单元混排", "需要异质图：节点和边都分类型"),
    ("曲面共形", "平面 → 曲面", "位置和法向已经进特征，改图结构即可"),
    ("多频宽带", "单频 → 多频", "色散进单元库；阵中 f0 已偏到 9.6 GHz"),
]
for i, (head, now, how) in enumerate(plans):
    col, row = i % 2, i // 2
    x = 0.75 + col * 6.05
    y = 2.12 + row * 1.90

    rect(s, x, y, 5.78, 1.70, LIGHT)
    rect(s, x, y, 0.05, 1.70, TEAL)

    tb = textbox(s, x + 0.28, y + 0.16, 5.2, 0.42)
    p = para(tb.text_frame, first=True)
    run(p, head, 18, NAVY, bold=True)

    tb = textbox(s, x + 0.28, y + 0.62, 5.25, 0.34)
    p = para(tb.text_frame, first=True)
    run(p, now, 13.5, AMBER, bold=True)

    tb = textbox(s, x + 0.28, y + 1.04, 5.25, 0.46)
    p = para(tb.text_frame, first=True, line=1.2)
    run(p, how, 12, GRAY)

rect(s, 0.75, 5.98, 11.83, 0.014, LINE)
tb = textbox(s, 0.75, 6.10, 11.8, 0.36)
p = para(tb.text_frame, first=True)
run(p, "近期：", 12.5, TEAL, bold=True)
run(p, "全量 2000 例训练", 12.5, INK)
run(p, "　→　中期：", 12.5, TEAL, bold=True)
run(p, "异质图 + 尺寸外推", 12.5, INK)
run(p, "　→　远期：", 12.5, TEAL, bold=True)
run(p, "曲面、多频、反设计闭环", 12.5, INK)

strip(s, "四个方向共用一个模型：换图、换单元库、换数据，不换网络。", y=6.55)
pagenum(s, 8)

# ============================== 8 · 启发 ====================================
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, WHITE)
header(s, "第八部分 · 会议启发", "两篇会议工作，两条能直接用的思路",
       "只借组织方式，不借网络结构")

cols = [
    ("异构 GCN", "节点是不同器件，边是物理连接",
     "→ 不同相位单元，就是多类型节点",
     r"D:\DSHNESS\GNN\fig_talk\conference_hetgcn.jpg",
     "Het-GCN：节点 = DR 单元与馈电探针（不同类型），边 = 相邻单元的物理连接；"
     "节点属性 = 尺寸 + 材料，边属性 = 相对位置；不同关系（DR-DR、DR-Probe）用不同权重。"
     "对应我们：不同相位单元就是不同节点类型。"),
    ("自回归外推", "一次只预测下一步，再喂回去",
     "→ 尺寸外推时，块与块可以这样接力",
     r"D:\DSHNESS\GNN\fig_talk\conference_ar.jpg",
     "网络只学“下一米”怎么变；把预测当输入，一步步推到 100 米；训练时故意喂错的预测，学会纠错"),
]
all_notes = []
for i, (head, sub_h, take, photo, notes) in enumerate(cols):
    x = 0.75 + i * 6.05
    rect(s, x, 2.12, 5.78, 4.10, LIGHT)
    rect(s, x, 2.12, 0.05, 4.10, TEAL if i == 0 else AMBER)

    tb = textbox(s, x + 0.30, 2.26, 5.1, 0.44)
    p = para(tb.text_frame, first=True)
    run(p, head, 19, NAVY, bold=True)

    tb = textbox(s, x + 0.30, 2.70, 5.1, 0.32)
    p = para(tb.text_frame, first=True)
    run(p, sub_h, 12, GRAY)

    pw = 4.78
    ph = pw * 9 / 16
    s.shapes.add_picture(photo, Inches(x + (5.78 - pw) / 2), Inches(3.02), width=Inches(pw))
    rect(s, x + (5.78 - pw) / 2, 3.02, pw, ph, None, LINE, line_w=0.75)

    tb = textbox(s, x + 0.30, 3.02 + ph + 0.12, 5.2, 0.34)
    p = para(tb.text_frame, first=True)
    run(p, take, 12.5, NAVY, bold=True)

    all_notes.append(head + "：" + notes)

s.notes_slide.notes_text_frame.text = "\n".join(all_notes)

strip(s, "借的是“异质图 + 逐步外推”的组织方式，不是他们的网络结构。")
pagenum(s, 9)

out = r"D:\DSHNESS\GNN\GNN_编码超表面_汇报_九页.pptx"
prs.save(out)
print("saved", out)










