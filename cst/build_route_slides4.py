# -*- coding: utf-8 -*-
"""Four-slide deck: route, GNN architecture, status & directions, conference borrowables."""

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
CREAM = RGBColor(0xFD, 0xF4, 0xE8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
PALE = RGBColor(0xC9, 0xD2, 0xDA)
ARROW = RGBColor(0xAF, 0xBA, 0xC5)
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


def sub(p, text, size, color, bold=False):
    return run(p, text, size, color, bold=bold, baseline=-25000)


def rect(slide, x, y, w, h, fill, line_color=None, shape=MSO_SHAPE.RECTANGLE, line_w=0.75):
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


def arrow(slide, x1, y1, x2, y2, color=RGBColor(0x94, 0xA1, 0xAE), width=1.2):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln.append(tail)
    return c


def badge(slide, x, y, d, num, color, size=8.5):
    s = rect(slide, x, y, d, d, None, color, MSO_SHAPE.OVAL, line_w=1.0)
    tf = s.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run(p, num, size, color, bold=True)


def header(slide, kicker, title, subtitle, title_size=27, sub_size=10.8):
    tb = textbox(slide, 0.7, 0.38, 11.9, 0.24)
    p = para(tb.text_frame, first=True)
    run(p, "■ ", 7, TEAL)
    run(p, kicker, 9.5, TEAL, bold=True, spacing=140)

    tb = textbox(slide, 0.7, 0.64, 11.9, 0.60)
    p = para(tb.text_frame, first=True, line=1.0)
    run(p, title, title_size, NAVY, bold=True, spacing=-10)

    tb = textbox(slide, 0.7, 1.28, 11.9, 0.38)
    p = para(tb.text_frame, first=True, line=1.2)
    run(p, subtitle, sub_size, GRAY)

    rect(slide, 0.7, 1.74, 11.93, 0.012, LINE)


def pagenum(slide, idx, total=5):
    tb = textbox(slide, 11.55, 7.02, 1.08, 0.24)
    p = para(tb.text_frame, first=True, align=PP_ALIGN.RIGHT)
    run(p, f"{idx:02d}", 10, NAVY, bold=True)
    run(p, f" /{total:02d}", 8.5, MUTED)


def footnote(slide, text):
    tb = textbox(slide, 0.70, 6.96, 10.6, 0.22)
    p = para(tb.text_frame, first=True)
    run(p, text, 7.5, MUTED)


# ----------------------------------------------------------------------------
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]

# ============================== SLIDE 1 (GNN 机理) ==========================
w1 = prs.slides.add_slide(blank)
rect(w1, 0, 0, 13.333, 7.5, WHITE)

header(
    w1,
    "GNN 机理",
    "一次消息传递，就是一次邻居之间的耦合",
    "节点是单元、边是耦合：一层 = 邻居影响一次；堆三层 = 影响传到三个单元之外",
    title_size=26,
)

# ---- message-passing diagram ----
cx, cy, R, SP = 2.50, 2.95, 0.24, 0.72
for r in range(3):
    for c in range(3):
        nx, ny = cx + (c - 1) * SP, cy + (r - 1) * SP
        is_c = (r == 1 and c == 1)
        node = rect(w1, nx - R, ny - R, 2 * R, 2 * R,
                    TEAL if is_c else TINT,
                    TEAL if is_c else RGBColor(0x9C, 0xC7, 0xCB),
                    MSO_SHAPE.OVAL)
        tf = node.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run(p, "j" if is_c else "i", 8.5, WHITE if is_c else TEAL, bold=True)

for r in range(3):
    for c in range(3):
        if r == 1 and c == 1:
            continue
        nx, ny = cx + (c - 1) * SP, cy + (r - 1) * SP
        dx, dy = cx - nx, cy - ny
        L = (dx * dx + dy * dy) ** 0.5
        arrow(w1, nx + dx / L * R, ny + dy / L * R, cx - dx / L * R, cy - dy / L * R)

tb = textbox(w1, 0.82, 3.96, 3.40, 0.40)
p = para(tb.text_frame, first=True, line=1.2)
run(p, "一层：8 个邻居各发一条消息；三层：信息走 3 格 ≈ 1.4λ", 7.6, MUTED)

# ---- three steps ----
def formula(p, parts, size=9.2, color=TEAL):
    for txt, is_sub in parts:
        if is_sub:
            sub(p, txt, size * 0.72, color)
        else:
            run(p, txt, size, color)

steps = [
    ("01", "消息", [("m", 0), ("ij", 1), (" = φ( h", 0), ("i", 1), (", h", 0), ("j", 1), (", e", 0), ("ij", 1), (" )", 0)],
     "邻居 i 对 j 说什么；e_ij 携带相对位置，权重随几何变"),
    ("02", "聚合", [("a", 0), ("j", 1), (" = Σ", 0), ("i", 1), (" m", 0), ("ij", 1)],
     "把邻居的话加起来；求和与顺序无关，节点重排结果不变"),
    ("03", "更新", [("h", 0), ("j", 1), (" ← ψ( h", 0), ("j", 1), (", a", 0), ("j", 1), (" )", 0)],
     "结合自身旧状态；残差 + LayerNorm，堆几层都不塌"),
]
for i, (num, name, parts, desc) in enumerate(steps):
    y = 1.98 + i * 0.74
    badge(w1, 4.55, y + 0.04, 0.26, num, TEAL, size=7.6)

    tb = textbox(w1, 4.92, y, 7.7, 0.26)
    p = para(tb.text_frame, first=True)
    run(p, name + "　", 10.5, NAVY, bold=True)
    formula(p, parts)

    tb = textbox(w1, 4.92, y + 0.28, 7.7, 0.30)
    p = para(tb.text_frame, first=True, line=1.15)
    run(p, desc, 8.3, GRAY)

# ---- comparison table ----
tb = textbox(w1, 0.72, 4.28, 0.9, 0.22)
p = para(tb.text_frame, first=True)
run(p, "网络", 7.6, MUTED, bold=True, spacing=50)
tb = textbox(w1, 1.86, 4.28, 1.2, 0.22)
p = para(tb.text_frame, first=True)
run(p, "局部性", 7.6, MUTED, bold=True, spacing=50)
tb = textbox(w1, 3.16, 4.28, 2.8, 0.22)
p = para(tb.text_frame, first=True)
run(p, "权重怎么来", 7.6, MUTED, bold=True, spacing=50)

tbl = [
    ("MLP", "无", "全连接，每个输入一根权重"),
    ("CNN", "规则网格", "每种偏移一个固定卷积核"),
    ("GNN", "任意图", "由边特征 e_ij 生成"),
]
for i, (name, loc, wsrc) in enumerate(tbl):
    y = 4.52 + i * 0.42
    if name == "GNN":
        rect(w1, 0.70, y - 0.04, 5.55, 0.40, TINT)

    tb = textbox(w1, 0.72, y, 1.0, 0.24)
    p = para(tb.text_frame, first=True)
    run(p, name, 9.6, NAVY if name == "GNN" else INK, bold=True)

    tb = textbox(w1, 1.86, y + 0.01, 1.25, 0.24)
    p = para(tb.text_frame, first=True)
    run(p, loc, 8.6, GRAY)

    tb = textbox(w1, 3.16, y + 0.01, 3.0, 0.24)
    p = para(tb.text_frame, first=True)
    run(p, wsrc, 8.6, GRAY)

# ---- why it fits ----
whys = [
    ("节点 = 单元", "：几何、码位、Γ 都是现成特征"),
    ("边 = 耦合", "：近场 / 表面波 / 衍射可分类、可截断"),
    ("层数 = 耦合半径", "：3 层 ≈ 3 个单元（1.4λ）"),
    ("增删单元不改代码", "：异形混排、曲面共形都能直接上"),
]
for i, (lead, tail) in enumerate(whys):
    y = 4.32 + i * 0.44
    tb = textbox(w1, 6.55, y, 0.12, 0.24)
    p = para(tb.text_frame, first=True)
    run(p, "·", 12, TEAL, bold=True)

    tb = textbox(w1, 6.78, y, 5.90, 0.26)
    p = para(tb.text_frame, first=True)
    run(p, lead, 9.0, NAVY, bold=True)
    run(p, tail, 8.6, GRAY)

rect(w1, 6.55, 4.24, 0.030, 1.78, TEAL)

rect(w1, 0.70, 6.12, 11.93, 0.46, NAVY)
tb = textbox(w1, 0.92, 6.21, 11.5, 0.30)
p = para(tb.text_frame, first=True)
run(p, "一句话：", 9.2, RGBColor(0x7F, 0xC4, 0xC9), bold=True)
run(p, "GNN 不是「更深的 CNN」，而是把「谁影响谁」显式写进模型——这正是超表面阵列最需要的那件事。", 9.2, WHITE)

footnote(w1, "参考：文献总结_架构与代码分析.md §2；Khoram 2023 的图卷积即此类消息传递的一个特例")
pagenum(w1, 1)

# ============================== SLIDE 2 (技术路线) ==========================
s1 = prs.slides.add_slide(blank)
rect(s1, 0, 0, 13.333, 7.5, WHITE)

header(
    s1,
    "技术路线",
    "物理主干 + 学习修正 + 物理读出",
    "20×20 1-bit 编码超表面 → 8280 个方向：网络只学 400 个复权重，传播交给写死的可微算子",
    title_size=27,
)

rect(s1, 0.85, 1.88, 11.64, 0.48, LIGHT)
rect(s1, 0.85, 1.88, 0.040, 0.48, TEAL)
tb = textbox(s1, 1.02, 1.95, 11.3, 0.34)
p = para(tb.text_frame, first=True)
run(p, "数据　", 8.6, TEAL, bold=True)
run(p, "CST 全波：20×20 · 10 GHz · 2° 网格 8280 点 · 306 s/例 · 已生成 2000 例（单频、单入射、单极化）", 8.6, INK)

cards = [
    ("01", "编码 → 阵列", ["10×10 宏比特", "block=2 → 400 单元", "每单元 1-bit 相位"]),
    ("02", "建图", ["400 节点 × 9 特征", "8 邻域 → 2964 条边", "边特征 Δx, Δy, r（÷λ）"]),
    ("03", "GNN 修正", ["3 层边条件消息传递", "Δq：400 个复数", "整图池化 → b：1 个复数"]),
    ("04", "权重合成", ["q = q0 + Δq + b", "q0 查单元库（0 参数）", "零初始化 → 起点 = M0"]),
    ("05", "物理读出", ["S = Σ qₙ·exp(jk·rₙ)", "σ = |Eθ|² + |Eφ|²", "8280 个方向 → dBsm"]),
]
CW, CG, CY, CH2 = 2.12, 0.26, 2.56, 1.56
for i, (num, name, lines) in enumerate(cards):
    x = 0.85 + i * (CW + CG)
    rect(s1, x, CY, CW, CH2, WHITE, LINE)
    rect(s1, x, CY, CW, 0.030, NAVY if i < 4 else TEAL)

    tb = textbox(s1, x + 0.13, CY + 0.12, 0.4, 0.22)
    p = para(tb.text_frame, first=True)
    run(p, num, 8, TEAL, bold=True)

    tb = textbox(s1, x + 0.13, CY + 0.33, CW - 0.22, 0.26)
    p = para(tb.text_frame, first=True)
    run(p, name, 11.5, NAVY, bold=True)

    tb = textbox(s1, x + 0.13, CY + 0.64, CW - 0.22, CH2 - 0.70)
    tf = tb.text_frame
    for j, ln in enumerate(lines):
        p = para(tf, first=(j == 0), line=1.34, space_after=3)
        run(p, ln, 8.8, GRAY)

    if i < 4:
        rect(s1, x + CW + 0.045, CY + 0.72, 0.17, 0.15, ARROW, shape=MSO_SHAPE.RIGHT_ARROW)

rect(s1, 1.82, 2.40, 0.15, 0.13, ARROW, shape=MSO_SHAPE.DOWN_ARROW)

rect(s1, 0.85, 4.28, 11.64, 0.010, LINE)
tb = textbox(s1, 0.85, 4.34, 5.0, 0.20)
p = para(tb.text_frame, first=True)
run(p, "同一套前向，三种用法", 7.8, MUTED, bold=True)

blocks = [
    ("训练", TEAL, ["损失：dB 域 asinh 压缩 MSE", "sinθ 立体角权重 + 主瓣 ×3", "AdamW，早停只看 val"]),
    ("评估", TEAL, ["rho_lin / rho_db / bias / rmse", "分带误差 0–5° … 60–90°", "对照 M0 / M0g / M1 / M2 / M3"]),
    ("反设计（下一步）", AMBER, ["对 q 求梯度 → 松弛 + 二值化", "CST 复核 Top-K", "回写码本，形成闭环"]),
]
bw = [3.72, 3.72, 3.60]
bx = [0.85, 4.77, 8.69]
for i, (name, colr, lines) in enumerate(blocks):
    rect(s1, bx[i], 4.58, bw[i], 1.28, WHITE, LINE if colr == TEAL else AMBER)
    rect(s1, bx[i], 4.58, 0.034, 1.28, colr)

    tb = textbox(s1, bx[i] + 0.18, 4.66, bw[i] - 0.3, 0.24)
    p = para(tb.text_frame, first=True)
    run(p, name, 10, colr, bold=True)

    tb = textbox(s1, bx[i] + 0.18, 4.94, bw[i] - 0.32, 0.84)
    tf = tb.text_frame
    for j, ln in enumerate(lines):
        p = para(tf, first=(j == 0), line=1.36, space_after=2)
        run(p, ln, 8.6, INK)

rect(s1, 0.85, 6.16, 11.64, 0.46, NAVY)
tb = textbox(s1, 1.05, 6.25, 11.3, 0.30)
p = para(tb.text_frame, first=True)
run(p, "三条不变量：", 9.2, RGBColor(0x7F, 0xC4, 0xC9), bold=True)
run(p, "物理主干 0 参数　·　只学 400 个复权重　·　零初始化使 M3 起点恰为 M0", 9.2, WHITE)

footnote(s1, "依据：后续工作计划.md · GNN代码解读.md · 一份真实数据的全流程演示.md")
pagenum(s1, 2)

# ============================== SLIDE 2 =====================================
s2 = prs.slides.add_slide(blank)
rect(s2, 0, 0, 13.333, 7.5, WHITE)

header(
    s2,
    "我们的实现",
    "GNN 只学一件事：每个单元的复权重修正",
    "400 节点 · 2964 条边 · 3 层边条件消息传递；每节点只出 2 个数（Δq 的实部 / 虚部）",
    title_size=27,
)

# column heads
heads = [("1", 0.72, "图怎么建"), ("2", 4.90, "一层怎么算"), ("3", 8.85, "怎么变成 q")]
for num, x, txt in heads:
    badge(s2, x, 1.88, 0.26, num, TEAL, size=8)
    tb = textbox(s2, x + 0.34, 1.87, 3.0, 0.26)
    p = para(tb.text_frame, first=True)
    run(p, txt, 11.2, NAVY, bold=True)

# ---- column 1: graph ----
GX, GY_, CELL = 0.82, 2.30, 0.335
for r in range(5):
    for c in range(5):
        x = GX + c * CELL
        y = GY_ + r * CELL
        center = (r == 2 and c == 2)
        ring = abs(r - 2) <= 1 and abs(c - 2) <= 1 and not center
        fill = TEAL if center else (TINT if ring else WHITE)
        border = TEAL if (center or ring) else LINE
        rect(s2, x, y, CELL, CELL, fill, border)

tb = textbox(s2, GX, GY_ + 5 * CELL + 0.08, 1.9, 0.20)
p = para(tb.text_frame, first=True)
run(p, "■ 中心 j　　■ 8 邻域 i　　□ 其余", 7.2, MUTED)

tb = textbox(s2, 0.72, 4.28, 3.90, 0.24)
p = para(tb.text_frame, first=True)
run(p, "节点 9 维", 8.6, TEAL, bold=True)
tb = textbox(s2, 0.72, 4.52, 3.90, 0.46)
p = para(tb.text_frame, first=True, line=1.25)
run(p, "bit · bit±1 · x/λ · y/λ · Γ 实部 · Γ 虚部 · |Γ| · 边界 · n̂·ẑ", 8.0, INK)

tb = textbox(s2, 0.72, 5.05, 3.90, 0.24)
p = para(tb.text_frame, first=True)
run(p, "边 5 维", 8.6, TEAL, bold=True)
tb = textbox(s2, 0.72, 5.29, 3.90, 0.46)
p = para(tb.text_frame, first=True, line=1.25)
run(p, "Δx/λ · Δy/λ · r/λ · cos φ · sin φ（相对方位）", 8.0, INK)

tb = textbox(s2, 0.72, 5.78, 3.90, 0.40)
p = para(tb.text_frame, first=True, line=1.2)
run(p, "2964 = 760 + 760 + 1444，无周期延拓；边缘单元邻居少，靠边界位标记。", 7.6, MUTED)

# ---- column 2: message passing ----
rect(s2, 4.90, 2.28, 3.55, 0.96, LIGHT)
rect(s2, 4.90, 2.28, 0.034, 0.96, TEAL)
tb = textbox(s2, 5.06, 2.36, 3.30, 0.80)
tf = tb.text_frame
p = para(tf, first=True, line=1.30)
run(p, "m", 9.2, INK)
sub(p, "ij", 9.2, INK)
run(p, " = MLP", 9.2, INK)
sub(p, "msg", 7.0, INK)
run(p, "( [ h", 9.2, INK)
sub(p, "i", 9.2, INK)
run(p, ", h", 9.2, INK)
sub(p, "j", 9.2, INK)
run(p, ", e", 9.2, INK)
sub(p, "ij", 9.2, INK)
run(p, " ] )", 9.2, INK)

p = para(tf, line=1.30, space_before=4)
run(p, "h", 9.2, INK)
sub(p, "j", 9.2, INK)
run(p, " ← LN( h", 9.2, INK)
sub(p, "j", 9.2, INK)
run(p, " + MLP", 9.2, INK)
sub(p, "upd", 7.0, INK)
run(p, "( [ h", 9.2, INK)
sub(p, "j", 9.2, INK)
run(p, ", Σ", 9.2, INK)
sub(p, "i", 9.2, INK)
run(p, " m", 9.2, INK)
sub(p, "ij", 9.2, INK)
run(p, " ] ) )", 9.2, INK)

notes2 = [
    ("边条件卷积", "权重由 e_ij 生成，不是 GCN 那种固定邻接加权"),
    ("sum 聚合", "节点重排不改变结果（置换等变）"),
    ("3 层 → 半径 3 格 ≈ 1.4λ", "感受野 7×7，覆盖 1–2 个单元的耦合尺度"),
    ("残差 + LayerNorm", "3 层不塌，也不需要更深"),
]
for i, (h, d) in enumerate(notes2):
    y = 3.42 + i * 0.62
    tb = textbox(s2, 4.90, y, 3.55, 0.22)
    p = para(tb.text_frame, first=True)
    run(p, h, 8.8, NAVY, bold=True)
    tb = textbox(s2, 4.90, y + 0.22, 3.55, 0.32)
    p = para(tb.text_frame, first=True, line=1.15)
    run(p, d, 7.8, GRAY)

# ---- column 3: heads ----
rect(s2, 8.85, 2.28, 3.60, 0.62, LIGHT)
tb = textbox(s2, 9.00, 2.34, 3.35, 0.50)
p = para(tb.text_frame, first=True, line=1.2)
run(p, "head：Linear(64 → 2)", 8.8, NAVY, bold=True)
p = para(tb.text_frame, line=1.2)
run(p, "每节点出 (Re Δq, Im Δq)", 8.0, GRAY)

rect(s2, 8.85, 3.02, 3.60, 0.62, LIGHT)
tb = textbox(s2, 9.00, 3.08, 3.35, 0.50)
p = para(tb.text_frame, first=True, line=1.2)
run(p, "全局支路：mean-pool → MLP", 8.8, NAVY, bold=True)
p = para(tb.text_frame, line=1.2)
run(p, "整图出 1 个复数 b", 8.0, GRAY)

rect(s2, 8.85, 3.76, 3.60, 0.50, NAVY)
tb = textbox(s2, 9.00, 3.88, 3.35, 0.30)
p = para(tb.text_frame, first=True)
run(p, "q = q0 + Δq + b", 10.2, WHITE, bold=True)

notes3 = [
    ("101k 参数", "M1 U-Net 是 212k；M0 是 0"),
    ("零初始化", "Δq = b = 0 → 初始输出恰为 M0"),
    ("不加注意力", "规则栅格 + 小样本，GAT 先过拟合"),
]
for i, (h, d) in enumerate(notes3):
    y = 4.48 + i * 0.58
    tb = textbox(s2, 8.85, y, 3.60, 0.22)
    p = para(tb.text_frame, first=True)
    run(p, h, 8.8, NAVY, bold=True)
    tb = textbox(s2, 8.85, y + 0.21, 3.60, 0.30)
    p = para(tb.text_frame, first=True, line=1.15)
    run(p, d, 7.8, GRAY)

# bottom strip
rect(s2, 0.72, 6.14, 11.73, 0.46, NAVY)
tb = textbox(s2, 0.92, 6.23, 11.4, 0.30)
p = para(tb.text_frame, first=True)
run(p, "边界：", 9.0, RGBColor(0x7F, 0xC4, 0xC9), bold=True)
run(p, "长程干涉不归 GNN 管——整孔径相干叠加由 8280×400 算子精确给出；要更长程就加边类型（M4），而不是加深网络。", 9.0, WHITE)

footnote(s2, "依据：GNN代码解读.md §2、§6.2–6.4；参数量与图规模由 tests/test_graph.py 钉住")
pagenum(s2, 3)

# ============================== SLIDE 3 =====================================
s3 = prs.slides.add_slide(blank)
rect(s3, 0, 0, 13.333, 7.5, WHITE)

header(
    s3,
    "现状与方向",
    "镜面已补上，误差迁移到大角域",
    "先跑 291 个样本（其中 44 例 test），训练 5 epoch：骨架已经闭合，剩下的是四个维度的泛化",
    title_size=27,
)

stats = [
    ("镜面误差  θ = 0", "−16.1 dB  →  +0.16 dB", "M0  →  M3"),
    ("RMSE", "4.65 dB  →  2.64 dB", "全角域"),
    ("rho_db", "0.865  →  0.958", "弥散结构"),
]
for i, (lab, val, sub_t) in enumerate(stats):
    x = 0.70 + i * 2.03
    rect(s3, x, 1.92, 1.88, 0.94, LIGHT)
    tb = textbox(s3, x + 0.14, 1.99, 1.62, 0.22)
    p = para(tb.text_frame, first=True)
    run(p, lab, 8.2, GRAY)
    tb = textbox(s3, x + 0.14, 2.22, 1.66, 0.26)
    p = para(tb.text_frame, first=True)
    run(p, val, 10.2, NAVY, bold=True)
    tb = textbox(s3, x + 0.14, 2.52, 1.62, 0.22)
    p = para(tb.text_frame, first=True)
    run(p, sub_t, 7.6, MUTED)

tb = textbox(s3, 0.70, 3.10, 5.9, 0.24)
p = para(tb.text_frame, first=True)
run(p, "M3 分带 RMSE（test）", 9, NAVY, bold=True)
run(p, "　　误差已从镜面锥迁到 60–90° 掠射区", 8, MUTED)

bands = [("0–5°", 0.29), ("5–15°", 0.98), ("15–30°", 0.99), ("30–60°", 1.50), ("60–90°", 4.10)]
maxv, maxw = 4.10, 3.05
for i, (lab, v) in enumerate(bands):
    y = 3.42 + i * 0.38
    tb = textbox(s3, 0.70, y - 0.02, 0.75, 0.22)
    p = para(tb.text_frame, first=True)
    run(p, lab, 8.2, GRAY)
    w = max(0.06, v / maxv * maxw)
    rect(s3, 1.50, y + 0.02, w, 0.15, AMBER if v > 2 else TEAL)
    tb = textbox(s3, 1.50 + w + 0.08, y - 0.02, 0.7, 0.22)
    p = para(tb.text_frame, first=True)
    run(p, f"{v:.2f} dB", 8.2, INK)

tb = textbox(s3, 0.70, 5.42, 6.0, 0.45)
p = para(tb.text_frame, first=True, line=1.25)
run(p, "M0 的 0–5° 误差是 14.0 dB，M3 压到 0.29 dB；", 8.2, INK)
run(p, "新的短板是大角域（4.10 dB）——倾斜因子与边缘效应。", 8.2, INK)

tb = textbox(s3, 6.95, 1.92, 5.7, 0.24)
p = para(tb.text_frame, first=True)
run(p, "往哪走：四个维度", 9, NAVY, bold=True)

dirs = [
    ("01", "目标 · 换挡", "随机码 → 结构化码本（斜坡 / 多波束 / 零陷）", "预测 RCS → 匹配目标方向图"),
    ("02", "规模 · 外推", "固定 20×20 → 可变口径（滑窗 / 分块）", "GNN 与尺寸无关，算子按尺寸预计算"),
    ("03", "频率 · 宽带", "单频 10 GHz → 多频", "阵中 f0 = 9.6 GHz、Q = 4.86，色散进单元库"),
    ("04", "单元 · 异构", "双半径贴片 → 异形 / 异相单元混排", "异质图（多类型节点 / 边）才有用武之地"),
]
for i, (num, head, now, nxt) in enumerate(dirs):
    y = 2.20 + i * 0.98
    rect(s3, 6.95, y, 5.68, 0.90, WHITE, LINE)
    rect(s3, 6.95, y, 0.034, 0.90, TEAL if i != 0 else AMBER)

    badge(s3, 7.10, y + 0.10, 0.28, num, TEAL, size=7.6)

    tb = textbox(s3, 7.48, y + 0.09, 2.0, 0.24)
    p = para(tb.text_frame, first=True)
    run(p, head, 10.5, NAVY, bold=True)

    tb = textbox(s3, 7.48, y + 0.37, 5.0, 0.22)
    p = para(tb.text_frame, first=True)
    run(p, now, 7.9, GRAY)

    tb = textbox(s3, 7.48, y + 0.61, 5.0, 0.22)
    p = para(tb.text_frame, first=True)
    run(p, nxt, 7.9, INK)

rect(s3, 0.70, 6.14, 11.93, 0.44, NAVY)
tb = textbox(s3, 0.92, 6.22, 11.5, 0.28)
p = para(tb.text_frame, first=True)
run(p, "判断：", 9.2, RGBColor(0x7F, 0xC4, 0xC9), bold=True)
run(p, "方法骨架已经闭合，接下来不是换网络，而是把「目标 × 规模 × 频率 × 单元」四个维度逐个打开。", 9.2, WHITE)

footnote(s3, "数字来源：demo_out/eval/metrics_summary.csv（M3 与 M0，test，44 例）")
pagenum(s3, 4)

# ============================== SLIDE 4 =====================================
s4 = prs.slides.add_slide(blank)
rect(s4, 0, 0, 13.333, 7.5, WHITE)

header(
    s4,
    "会议借鉴",
    "两篇会议工作，四件可以借的事",
    "只取组织方式——异质图、残差、读出、闭环；网络结构不必照搬",
    title_size=27,
)

for (x, w, txt) in [(1.32, 2.50, "借鉴点"), (4.02, 3.40, "他们怎么做的"), (7.72, 4.80, "我们怎么用")]:
    tb = textbox(s4, x, 1.86, w, 0.22)
    p = para(tb.text_frame, first=True)
    run(p, txt, 8.2, MUTED, bold=True, spacing=60)

rows = [
    ("01", "异质图：节点与边都分类型",
     "节点 = 面 / 楔 / 收发点，边 = LoS / 反射 / 绕射；每类边一套消息函数",
     "不同相位单元 = 多类型节点（各带 Γ 与几何）；耦合机制 = 多类型边 → 异相混排的骨架"),
    ("02", "主干 × 可退化残差",
     "m = A·fθ(h)，令 fθ ≡ 1 即退回解析解，用作消融基线",
     "我们已是 q0 + Δq + b：δ ≡ 0 就是 M0。写进方法论，并当作消融与 OOD 兜底"),
    ("03", "物理读出，不学 decoder",
     "按物理路径池化复数消息，再取 dB；不是全图平均",
     "8280×400 传播算子直接读出；消息聚合用 sum，而不是定长邻居拼接"),
    ("04", "闭环 rollout",
     "0 → 100 m 逐面推进，训练时喂自己的预测压住漂移",
     "尺寸 / 频率外推时用 scheduled sampling 抑制误差累积（提议，尚未实现）"),
]
ROW_H, STEP, Y0 = 0.90, 0.98, 2.16
for i, (num, head, theirs, ours) in enumerate(rows):
    y = Y0 + i * STEP
    if i % 2 == 0:
        rect(s4, 0.70, y, 11.93, ROW_H, LIGHT)

    tb = textbox(s4, 0.84, y, 0.45, ROW_H, anchor=MSO_ANCHOR.MIDDLE)
    p = para(tb.text_frame, first=True)
    run(p, num, 11.5, PALE, bold=True)

    tb = textbox(s4, 1.32, y, 2.50, ROW_H, anchor=MSO_ANCHOR.MIDDLE)
    p = para(tb.text_frame, first=True, line=1.12)
    run(p, head, 11.2, NAVY, bold=True)

    tb = textbox(s4, 4.02, y, 3.40, ROW_H, anchor=MSO_ANCHOR.MIDDLE)
    p = para(tb.text_frame, first=True, line=1.28)
    run(p, theirs, 8.8, GRAY)

    tb = textbox(s4, 7.72, y, 4.80, ROW_H, anchor=MSO_ANCHOR.MIDDLE)
    p = para(tb.text_frame, first=True, line=1.28)
    run(p, ours, 8.8, INK)

rect(s4, 0.70, 6.30, 11.93, 0.012, LINE)
tb = textbox(s4, 0.70, 6.42, 11.9, 0.28)
p = para(tb.text_frame, first=True)
run(p, "一句话：", 8.8, AMBER, bold=True)
run(p, "借的是「异质图 + 物理残差」的组织方式，不是他们的网络结构。", 8.8, INK)

pagenum(s4, 5)

out = r"D:\DSHNESS\GNN\GNN_编码超表面_技术路线_五页.pptx"
prs.save(out)
print("saved", out)



