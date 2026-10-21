# -*- coding: utf-8 -*-
"""Build the delivery document for the 2x2 macro-cell baseline."""
import os
import shutil

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

WS = r"D:\DSHNESS\GNN"
FIG = os.path.join(WS, "fig")
os.makedirs(FIG, exist_ok=True)
for name in ("ff_10.png", "ff_9.8.png"):
    src = os.path.join(r"D:\ff_er265_r2_b2\post", name)
    dst = os.path.join(FIG, "b2_" + name)
    if os.path.isfile(src) and not os.path.isfile(dst):
        shutil.copyfile(src, dst)

OUT = os.path.join(WS, "编码超表面_2x2基线_总结.docx")

doc = Document()
for sec in doc.sections:
    sec.left_margin = Cm(2.2)
    sec.right_margin = Cm(2.2)
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.2)

TEXT_W = 16.0  # cm, fits the 16.6 cm text column
IMG_W = 14.6   # cm, slightly narrower so two figures can share a page

st = doc.styles["Normal"]
st.font.name = "Times New Roman"
st.font.size = Pt(10.5)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
st.paragraph_format.space_after = Pt(4)
st.paragraph_format.line_spacing = 1.15

for lvl in (1, 2):
    hs = doc.styles["Heading %d" % lvl]
    hs.font.name = "Times New Roman"
    hs.element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
    hs.font.color.rgb = RGBColor(0, 0, 0)
    hs.font.size = Pt(14 if lvl == 1 else 12)


def para(text, bold=False, size=None, align=None, space_after=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    if size:
        r.font.size = Pt(size)
    if align:
        p.alignment = align
    if space_after is not None:
        p.paragraph_format.space_after = Pt(space_after)
    return p


def caption(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(8)
    return p


def _no_split(row, header=False):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit")
    trPr.append(el)
    if header:
        trPr.append(OxmlElement("w:tblHeader"))


def table(header, rows, widths=None, font=9):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        cell = t.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(font)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(v))
            run.font.size = Pt(font)
    if widths:
        total = sum(widths)
        widths = [w * TEXT_W / total for w in widths]
        for i, w in enumerate(widths):
            t.columns[i].width = Cm(w)
            for row in t.rows:
                row.cells[i].width = Cm(w)
    t.autofit = False
    _no_split(t.rows[0], header=True)
    for row in t.rows[1:]:
        _no_split(row)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


# ============================ title ============================
title = doc.add_paragraph()
tr = title.add_run("1-bit 编码超表面 20×20 阵列仿真总结")
tr.bold = True
tr.font.size = Pt(20)
tr.font.name = "Times New Roman"
tr.element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

sub = doc.add_paragraph()
sr = sub.add_run("基线配置：2×2 宏单元编码  |  εr = 2.65 低损耗基板  |  10 GHz")
sr.font.size = Pt(11)
sr.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

meta = doc.add_paragraph()
mr = meta.add_run("CST Studio Suite 2026 (HF Time Domain)    文档生成日期：2026-10-21\n"
                  "工程文件：D:\\META_coding_array_er265_r2_b2.cst")
mr.font.size = Pt(9)
mr.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER

# ============================ 1 ============================
doc.add_heading("1  结论摘要", level=1)
para("本工作建立了 20×20（400 单元）1-bit 反射式编码超表面的全波模型，并完成了 "
     "9.8–10.2 GHz 五个频点的远场求解与后处理。以 2×2 宏单元为编码基元"
     "（总单元数不变，独立比特数 100）的版本作为交付基线。")
para("主要结果：")
para("• 10 GHz 镜面 RCS 由同尺寸 PEC 板的 19.34 dBsm 降至 10.80 dBsm，镜面缩减 8.54 dB；")
para("• 9.8 GHz 达到全带最好值：5.22 dBsm，缩减 13.95 dB；")
para("• 相对逐比特随机编码（10 GHz 缩减 5.53 dB），2×2 宏单元带来约 3.0 dB 的额外抑制；")
para("• 方向图已呈典型弥散形态，镜面残留仅比弥散瓣底高约 1 dB，说明编码真正压制了镜面分量。")
para("同时需要指出两项尚未闭合的问题：单元胞的 |S11| 仅约 −1.3 dB（无损基板理论上应接近 0 dB），"
     "以及实测缩减量仍比理想 1-bit 模型低约 20 dB，主因是混合编码阵列中单元相位偏离周期单元胞。")

# ============================ 2 ============================
doc.add_heading("2  结构参数", level=1)
table(
    ["项目", "取值", "说明"],
    [
        ["单元周期 P", "14.0 mm", "0.467λ @ 10 GHz"],
        ["阵列规模", "20 × 20 = 400", "总尺寸 280 × 280 mm（9.34λ）"],
        ["基板", "material1", "εr = 2.65，tanδ = 0.0013，h = 1.5 mm"],
        ["地板", "PEC", "z = 0，零厚度，覆盖整个阵列"],
        ["贴片", "圆形 PEC", "z = 1.5 mm，两种半径"],
        ["编码基元", "2 × 2 宏单元", "10 × 10 = 100 独立比特"],
        ["宏单元尺寸", "28 mm", "0.93λ < λ，无栅瓣"],
    ],
    widths=[4.0, 4.6, 8.4],
)
para("宏单元尺寸受栅瓣条件约束：BLOCK × P 必须小于一个波长。10 GHz 时 λ = 30 mm，"
     "2×2 的 28 mm 已接近上限；若用 3×3（42 mm = 1.4λ）将出现栅瓣，"
     "因此 2×2 是本周期下可用的最大分块。", size=9.5)

# ============================ 3 ============================
doc.add_heading("3  单元胞设计", level=1)
para("单元胞采用周期边界 + 双侧 Floquet 口、法向入射 TE(0,0)/TM(0,0) 激励，"
     "四面体网格 + 频域求解，取 10 GHz 处 SZmax(1),Zmax(1) 的幅度与相位：")
table(
    ["状态", "贴片半径", "相位 @10 GHz", "|S11|", "相位差", "幅度差"],
    [
        ["bit 0", "r = 4.7 mm", "−5.3°", "−1.24 dB", "179.95°", "0.15 dB"],
        ["bit 1", "r = 2.0 mm", "174.6°", "−1.39 dB", "—", "—"],
    ],
    widths=[2.4, 3.4, 3.4, 2.8, 3.0, 3.0],
)
para("两个状态的相位差为 179.95°，幅度几乎相等，满足 1-bit 编码对等幅反相的要求。"
     "相比之下，早期 FR-4（εr 4.3 / tanδ 0.025）方案的两个状态幅度相差 3.5 dB，"
     "这是其镜面抑制只有 2.85 dB 的直接原因。", size=9.5)

# ============================ 4 ============================
doc.add_heading("4  编码矩阵", level=1)
para("随机种子 SEED = 20261020，在 10 × 10 宏单元上生成，46 个 1 / 54 个 0，"
     "每个比特覆盖 2 × 2 个物理单元（共 400 单元，单元数不变）：")
mono = doc.add_paragraph()
mono.alignment = WD_ALIGN_PARAGRAPH.CENTER
mr = mono.add_run("1101010001\n0001000000\n0011110101\n0000101101\n0001000100\n"
                  "1100110011\n1111100000\n0010000110\n1011111011\n1010111001")
mr.font.name = "Consolas"
mr.font.size = Pt(9)
mono.paragraph_format.space_after = Pt(8)

# ============================ 5 ============================
doc.add_heading("5  仿真设置", level=1)
table(
    ["类别", "设置"],
    [
        ["求解器", "HF Time Domain，六面体网格（PBA）"],
        ["激励", "平面波，法向入射 −z，E // x，参考频率 10 GHz"],
        ["边界", "六面 expanded open"],
        ["计算域", "背景空间 15 mm（六面），盒尺寸 310 × 310 × 31.5 mm"],
        ["最小距离", "λ/4 @ 10 GHz = 7.49 mm"],
        ["频率范围", "9.0 – 11.0 GHz"],
        ["远场监视器", "9.8 / 9.9 / 10.0 / 10.1 / 10.2 GHz（5 个）"],
        ["稳态判据", "−40 dB"],
        ["网格", "LinesPerWavelength = 20；约 2.8×10⁶ 六面体单元"],
        ["求解时间", "279.7 s（GPU 加速）"],
    ],
    widths=[3.6, 13.4],
)
para("说明：远场监视器必须在求解前定义——本工程关闭了 TD 结果缓存，求解结束后无法追加频点。"
     "由于 CST 自带的 ASCII / .ffs 导出只会输出求解时存储的 5° 网格，后处理改用 "
     "AddListEvaluationPoint + CalculateList + GetList 接口，按 1° 重新求值"
     "（181 × 360 = 65,160 点/频点），该接口与存储表的逐点偏差小于 0.01 dB。", size=9.5)
para("背景空间 15 mm 已由三组对比实验确认（7.5 / 15 / 30 mm）：7.5 mm 与 15 mm 的镜面仅差 0.19 dB，"
     "但深零点未收敛（逐点散布可达 9 dB）；15 mm 与 30 mm 的镜面与平均散射电平完全一致"
     "（差 0.01 dB），而 30 mm 多耗 32% 时间和 83% 网格量。故 15 mm 取为默认计算域。", size=9.5)

# ============================ 6 ============================
doc.add_heading("6  仿真结果", level=1)
para("镜面 RCS 与同尺寸 PEC 板（σ = 4πA²/λ²，10 GHz 时 19.34 dBsm）对比：", space_after=6)
table(
    ["频率 (GHz)", "镜面 RCS (dBsm)", "PEC 板 (dBsm)", "缩减 (dB)", "HPBW (°)", "第一副瓣 (dB)"],
    [
        ["9.8", "5.22", "19.16", "−13.95", "9.9", "−7.3"],
        ["9.9", "8.38", "19.25", "−10.87", "9.4", "−9.1"],
        ["10.0", "10.80", "19.34", "−8.54", "11.3", "−11.0"],
        ["10.1", "12.54", "19.43", "−6.88", "11.1", "−11.8"],
        ["10.2", "13.82", "19.51", "−5.69", "11.0", "−12.2"],
    ],
    widths=[2.6, 3.4, 3.2, 2.8, 2.4, 3.2],
)

doc.add_picture(os.path.join(FIG, "b2_ff_10.png"), width=Cm(IMG_W))
caption("图 1  10 GHz 远场：左为上半球 uv 面分布（归一化至峰值），右为 φ = 0°/45°/90° 三条切线")

doc.add_picture(os.path.join(FIG, "b2_ff_9.8.png"), width=Cm(IMG_W))
caption("图 2  9.8 GHz 远场（全带最好，镜面缩减 13.95 dB）")

doc.add_picture(os.path.join(FIG, "comparison.png"), width=Cm(IMG_W))
caption("图 3  四种配置的镜面缩减与绝对镜面电平随频率的变化")

doc.add_heading("6.1  与早期配置的对比", level=2)
table(
    ["频率", "FR-4 (3.65/5.6)", "εr2.65 (4.7/1.0)", "εr2.65 (4.7/2.0)", "2×2 基线"],
    [
        ["9.8 GHz", "−5.13 dB", "−8.09 dB", "−8.31 dB", "−13.95 dB"],
        ["9.9", "−3.77", "−6.61", "−6.80", "−10.87"],
        ["10.0", "−2.85", "−5.36", "−5.53", "−8.54"],
        ["10.1", "−2.21", "−4.42", "−4.57", "−6.88"],
        ["10.2", "−1.76", "−3.72", "−3.85", "−5.69"],
    ],
    widths=[2.6, 4.2, 3.8, 3.8, 3.4],
)

# ============================ 7 ============================
doc.add_heading("7  讨论", level=1)
doc.add_heading("7.1  2×2 宏单元为何更有效", level=2)
para("独立比特从 400 降到 100，但每个宏单元成为 28 mm 的相干散射体，散射方向图更“碎”；"
     "同时相邻同相位单元增多，显著削弱了混合编码引入的互耦失谐。这与“阵中单元相位偏离周期单元胞”"
     "的判断一致：逐比特编码时，每个单元都被不同相位的邻居包围，实际相位被拉偏，编码效率下降。")
doc.add_heading("7.2  频点趋势", level=2)
para("五个频点的缩减量随频率单调变化（9.8 GHz 最好，10.2 GHz 最差），且尚未出现拐点，"
     "说明最优工作点在 9.8 GHz 以下。而单元胞在 9.8 GHz 的相位差（约 166°）反而比 10 GHz 更差，"
     "两者矛盾恰好指向同一结论：阵中互耦使单元有效电长度变大，工作点整体向低频偏移。")
doc.add_heading("7.3  尚未闭合的问题", level=2)
para("(1) 单元胞 |S11| 仅约 −1.3 dB。tanδ = 0.0013 近似无损，PEC 地板 + 无耗基板在正入射下"
     "应接近全反射。约 27% 的功率未回到基模，最可能是单元胞边界设置中表面波/高阶模被吸收。"
     "该项不影响缩减量的相对比较，但会使绝对 RCS 与效率口径系统性偏低约 1.3 dB。"
     "建议用“无贴片纯基板”单元胞做一次核对。")
para("(2) 实测缩减（−8.5 dB @10 GHz）仍明显低于理想 1-bit 模型（按单元胞 Γ 推算约 −30 dB）。"
     "差距主要来自阵列环境下的单元相位偏离，而非数值误差；2×2 宏单元已回收其中约 3 dB。")
para("(3) 未做网格与边界距离的收敛性对照。当前网格 20 线/波长、边界 λ/4，"
     "建议至少用一倍网格或 λ/2 边界复核一次主瓣与镜面电平。")

# ============================ 8 ============================
doc.add_heading("8  复现步骤", level=1)
para("工作区 D:\\DSHNESS\\GNN 下的脚本按以下顺序执行：", space_after=4)
table(
    ["步骤", "脚本", "作用"],
    [
        ["1", "build_coding_array.py", "建模脚本（参数、几何、边界、监视器）"],
        ["2", "run_new_array.py", "调用建模脚本并求解、保存结果"],
        ["3", "export_farfield.py", "按 1° 导出 5 个频点的 3D 远场"],
        ["4", "postprocess_farfield.py", "生成 1D 切线、2D uv 图与 summary.csv"],
    ],
    widths=[1.6, 5.4, 10.0],
)
para("关键参数集中在 build_coding_array.py 顶部：R0 / R1（两个贴片半径）、BLOCK（宏单元边长）、"
     "FARFIELD_FREQS（监视器频点）、BG_SPACE（背景空间）、MESH_STEPS（网格密度）。"
     "修改 BLOCK 时需保证 BLOCK × P < λ。", size=9.5)

doc.add_heading("9  数据文件", level=1)
table(
    ["内容", "路径"],
    [
        ["CST 工程（基线）", "D:\\META_coding_array_er265_r2_b2.cst"],
        ["3D 远场原始数据", "D:\\ff_er265_r2_b2\\ff_9.8.txt … ff_10.2.txt（各 65,160 点）"],
        ["后处理结果", "D:\\ff_er265_r2_b2\\post\\（5 张图 + summary.csv）"],
        ["对比图与报告插图", "D:\\DSHNESS\\GNN\\fig\\"],
    ],
    widths=[4.6, 12.4],
)

para("")
para("注：本文所有 RCS 均为平面波激励下的散射场结果（CST 中监视器名带 [pw] 后缀），"
     "已扣除入射波；缩减量定义为“阵列镜面 RCS − 同尺寸 PEC 板 RCS”。", size=9)

doc.save(OUT)
print("saved:", OUT, os.path.getsize(OUT), "bytes")
