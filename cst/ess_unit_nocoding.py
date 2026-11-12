# -*- coding: utf-8 -*-
"""ESS on 态单元胞（去掉 4x4 编码贴片）的参数化仿真脚本。

结构（15 mm 周期，3 mm 真空基板，PEC 地板 z=-3 mm，顶层 z=0）：
  * PEC 方环：外半宽 7.5 mm，环宽 wr，由 4 个 brick 拼成；
  * 中间竖条：宽 wb，从 y=-(7.5-wr-g) 到 +(7.5-wr-g)，g=1.0 mm；
  * 竖条两端各通过一个 RLCSerial 集总元件（R=3 Ohm，L=0.45 nH）
    接到方环内边，元件长度恰为 g；
  * 可选中心垫片：宽 wp、高 hp，与竖条同 component，用 Solid.Add 合并；
  * Floquet 端口在 Zmax，参考面 -7.5 mm（即 z=0 结构面），
    Zmin 为 electric，x/y 为 unit cell；8-12 GHz，10 GHz 取 S11。

用法：
  python ess_unit_nocoding.py --wr 0.8 --wb 1.0 --wp 0 --hp 0 --tag demo --outdir out
  python ess_unit_nocoding.py --sweep cases.csv --outdir out
  python ess_unit_nocoding.py --wr 0.8 --wb 1.0 --dry-run --outdir out

注意：--dry-run 不会 import cst；正常模式才连接 CST。
SetL 的单位是 H（CST 文档中 L[H]），所以 0.45 nH 写成 4.5e-10。
"""

import argparse
import csv
import json
import math
import os
import re
import sys
import time
from datetime import datetime

# 让 Windows 管道/控制台按 UTF-8 输出中文日志（Python 3.7+）。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ===================== 固定几何 / 求解设置 =====================
PERIOD = 15.0                 # mm
HALF = PERIOD / 2.0           # 7.5 mm
SUBSTRATE_H = 3.0             # mm
G = 1.0                       # 竖条端部到方环内边的固定间隙 mm
R_OHM = 3.0                   # 导通态等效电阻 Ohm
L_H = 0.45e-9                 # 导通态等效电感 H（0.45 nH）
FMIN_GHZ = 8.0
FMAX_GHZ = 12.0
F0_GHZ = 10.0
Z_BACK = 7.5                  # Zmax 背景空间 / 端口到参考面距离 mm
REF_PLANE = -7.5              # SetDistanceToReferencePlane
FREQ_TOL_GHZ = 0.5            # 最近频点允许偏离 10 GHz 的范围

CST_LIB_DEFAULT = r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries"

# CST 可能给 S11 结果起不同的树路径，按优先级尝试，最后再扫描。
S11_CANDIDATES = [
    r"1D Results\S-Parameters\SZmax(1),Zmax(1)",
    r"1D Results\S-Parameters\SZmax(1),Zmax(1) [1]",
    r"1D Results\S-Parameters\SZmax(1),Zmax(1) [TE(0,0)]",
]

CSV_FIELDS = [
    "tag", "wr_mm", "wb_mm", "wp_mm", "hp_mm", "g_mm",
    "frequency_ghz", "s11_db", "phase_port_deg", "phase_physical_deg",
    "s11_real", "s11_imag", "project",
]


class CaseError(Exception):
    """可预期的单点/批量错误。"""


class CstConnectionError(CaseError):
    """CST 连接或启动失败。"""


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def fmt_num(x):
    """稳定、紧凑的数字文本，避免 -0。"""
    x = float(x)
    if abs(x) < 1e-12:
        return "0"
    return "%.12g" % x


def wrap180(deg):
    """把角度折到 (-180, 180]，仅用于附加显示字段。"""
    d = (float(deg) + 180.0) % 360.0 - 180.0
    if abs(d + 180.0) < 1e-12:
        d = 180.0
    return d


def auto_tag(wr, wb, wp, hp):
    return "wr%.2f_wb%.2f_wp%.2f_hp%.2f" % (wr, wb, wp, hp)


def sanitize_tag(tag, wr, wb, wp, hp):
    """只保留文件名安全字符；空 tag 自动生成。"""
    if tag is None or not str(tag).strip():
        return auto_tag(wr, wb, wp, hp)
    raw = str(tag).strip()
    safe = re.sub(r"[^0-9A-Za-z_.-]+", "_", raw).strip("._-")
    if not safe:
        safe = auto_tag(wr, wb, wp, hp)
    if safe != raw:
        log("[warn] tag %r 含文件名不安全字符，改用 %r" % (raw, safe))
    return safe


def validate_params(wr, wb, wp, hp):
    """检查几何自洽性，返回 (wr, wb, wp, hp)。"""
    try:
        wr, wb, wp, hp = float(wr), float(wb), float(wp), float(hp)
    except (TypeError, ValueError):
        raise CaseError("几何参数必须是数字：wr=%r wb=%r wp=%r hp=%r" % (wr, wb, wp, hp))

    for name, val in (("wr", wr), ("wb", wb), ("wp", wp), ("hp", hp)):
        if not math.isfinite(val):
            raise CaseError("%s 必须是有限数值" % name)
        if val < 0:
            raise CaseError("%s 不能为负：%g" % (name, val))

    if wr <= 0:
        raise CaseError("wr 必须大于 0")
    if wr >= HALF - 0.5:
        raise CaseError("wr 过大，方环内边只剩 %.3f mm" % (HALF - wr))
    if wb <= 0:
        raise CaseError("wb 必须大于 0")

    inner = HALF - wr
    bar_half = HALF - wr - G
    if bar_half <= 0.1:
        raise CaseError("wr=%g 时竖条长度 %.3f mm 过短（需 7.5-wr-g>0）" % (wr, 2.0 * bar_half))
    if inner - wb / 2.0 < 0.2:
        raise CaseError("wb=%g 太宽，竖条会碰到方环左右边（间隙 %.3f mm）"
                        % (wb, inner - wb / 2.0))

    has_pad_w = wp > 0
    has_pad_h = hp > 0
    if has_pad_w != has_pad_h:
        raise CaseError("wp 和 hp 必须同时为 0（不加垫片）或同时大于 0")

    if has_pad_w:
        clear_x = inner - wp / 2.0
        clear_y = inner - hp / 2.0
        if clear_x < 0.5 - 1e-9:
            raise CaseError("垫片到方环左右内边只有 %.3f mm，要求 >= 0.5 mm" % clear_x)
        if clear_y < 0.5 - 1e-9:
            raise CaseError("垫片到方环上下内边只有 %.3f mm，要求 >= 0.5 mm" % clear_y)
        # 垫片不能伸进竖条端部与方环之间的集总元件间隙
        if hp / 2.0 > bar_half + 1e-9:
            raise CaseError("hp=%g 过大，垫片会伸进集总元件间隙（竖条半长 %.3f mm）"
                            % (hp, bar_half))

    if not (0.5 <= wr <= 1.2):
        log("[warn] wr=%g 超出推荐范围 0.5-1.2 mm" % wr)
    if not (0.6 <= wb <= 3.0):
        log("[warn] wb=%g 超出推荐范围 0.6-3.0 mm" % wb)

    return wr, wb, wp, hp


def _brick(name, comp, material, x0, x1, y0, y1, z0, z1):
    return """With Brick
    .Reset
    .Name "%s"
    .Component "%s"
    .Material "%s"
    .Xrange "%s", "%s"
    .Yrange "%s", "%s"
    .Zrange "%s", "%s"
    .Create
End With""" % (name, comp, material, fmt_num(x0), fmt_num(x1),
               fmt_num(y0), fmt_num(y1), fmt_num(z0), fmt_num(z1))


def build_vba_body(wr, wb, wp, hp):
    """返回可交给 Model3D.add_to_history 的 VBA 主体（不含 Sub Main）。"""
    inner = HALF - wr
    bar_half = HALF - wr - G
    has_pad = wp > 0 and hp > 0
    lines = []

    lines.append("""With Units
    .Geometry "mm"
    .Frequency "GHz"
    .Time "ns"
    .TemperatureUnit "Kelvin"
    .Voltage "V"
    .Current "A"
    .Resistance "Ohm"
    .Conductance "Siemens"
    .Capacitance "PikoF"
    .Inductance "NanoH"
    .SetResultUnit "frequency", "frequency", ""
End With""")
    lines.append('Solver.FrequencyRange "%s", "%s"' % (fmt_num(FMIN_GHZ), fmt_num(FMAX_GHZ)))

    # 真空基板 + PEC 地板（z=-3 mm，零厚度 PEC 片）
    lines.append(_brick("Substrate", "component1", "Vacuum",
                        -HALF, HALF, -HALF, HALF, -SUBSTRATE_H, 0.0))
    lines.append(_brick("Ground", "component1", "PEC",
                        -HALF, HALF, -HALF, HALF, -SUBSTRATE_H, -SUBSTRATE_H))

    # 方环：4 个不重叠 brick（上下通长，左右夹在中间）
    lines.append(_brick("Ring_N", "component2", "PEC",
                        -HALF, HALF, inner, HALF, 0.0, 0.0))
    lines.append(_brick("Ring_S", "component2", "PEC",
                        -HALF, HALF, -HALF, -inner, 0.0, 0.0))
    lines.append(_brick("Ring_W", "component2", "PEC",
                        -HALF, -inner, -inner, inner, 0.0, 0.0))
    lines.append(_brick("Ring_E", "component2", "PEC",
                        inner, HALF, -inner, inner, 0.0, 0.0))

    # 中间竖条
    lines.append(_brick("Bar", "component2", "PEC",
                        -wb / 2.0, wb / 2.0, -bar_half, bar_half, 0.0, 0.0))

    # 可选中心垫片：同一 component、z=0，并与竖条合并
    if has_pad:
        lines.append(_brick("Pad", "component2", "PEC",
                            -wp / 2.0, wp / 2.0, -hp / 2.0, hp / 2.0, 0.0, 0.0))
        lines.append('Solid.Add "component2:Bar", "component2:Pad"')

    # 两个 RLCSerial 集总元件：从竖条端部到方环内边，长度 g=1 mm
    for name, y1, y2 in (("Lump_top", bar_half, inner),
                         ("Lump_bottom", -bar_half, -inner)):
        lines.append("""With LumpedElement
    .Reset
    .SetName "%s"
    .Folder "Folder1"
    .SetType "RLCSerial"
    .SetR "%s"
    .SetL "%s"
    .SetC "0"
    .SetGs "0"
    .SetI0 "1e-14"
    .SetT "300"
    .SetMonitor "True"
    .SetRadius "0.0"
    .CircuitFileName ""
    .CircuitId "1"
    .UseCopyOnly "True"
    .UseRelativePath "False"
    .SetP1 "False", "0", "%s", "0"
    .SetP2 "False", "0", "%s", "0"
    .SetInvert "False"
    .Wire ""
    .Position "end1"
    .Create
End With""" % (name, fmt_num(R_OHM), fmt_num(L_H), fmt_num(y1), fmt_num(y2)))

    # 背景：仅 Zmax 方向留 7.5 mm 给端口
    lines.append("""With Background
    .ResetBackground
    .Type "Normal"
    .Epsilon "1.0"
    .Mu "1.0"
    .XminSpace "0.0"
    .XmaxSpace "0.0"
    .YminSpace "0.0"
    .YmaxSpace "0.0"
    .ZminSpace "0.0"
    .ZmaxSpace "%s"
    .ApplyInAllDirections "False"
End With""" % fmt_num(Z_BACK))

    # Floquet 端口：Zmax，参考面移到 z=0
    lines.append("""With FloquetPort
    .Reset
    .SetDialogTheta "0"
    .SetDialogPhi "0"
    .SetSortCode "+beta/pw"
    .SetCustomizedListFlag "False"
    .Port "Zmax"
    .SetNumberOfModesConsidered "2"
    .SetDistanceToReferencePlane "%s"
    .SetUseCircularPolarization "False"
End With""" % fmt_num(REF_PLANE))

    # 边界：x/y 周期，Zmin 电壁，Zmax 开放（Floquet 端口所在面）
    lines.append("""With Boundary
    .Xmin "unit cell"
    .Xmax "unit cell"
    .Ymin "unit cell"
    .Ymax "unit cell"
    .Zmin "electric"
    .Zmax "open"
    .Xsymmetry "none"
    .Ysymmetry "none"
    .Zsymmetry "none"
    .ApplyInAllDirections "True"
End With""")

    # 四面体网格 + 频域求解器，TE(0,0)/TM(0,0) 正入射
    lines.append("""With Mesh
    .MeshType "Tetrahedral"
End With
With MeshSettings
    .SetMeshType "Tet"
    .Set "Version", 1
End With
With FDSolver
    .Reset
    .Stimulation "List", "List"
    .ResetExcitationList
    .AddToExcitationList "Zmax", "TE(0,0);TM(0,0)"
    .LowFrequencyStabilization "False"
End With""")
    lines.append('ChangeSolverType "HF Frequency Domain"')
    return "\n".join(lines)


def build_vba_macro(wr, wb, wp, hp, tag):
    """生成完整可读的 VBA 宏文本（用于 dry-run 人工检查）。"""
    body = build_vba_body(wr, wb, wp, hp)
    body_indented = "\n".join(("    " + ln) if ln.strip() else ln for ln in body.splitlines())
    header = """' ESS on-state unit cell (no 4x4 coding patches)
' tag: %s
' wr=%s mm, wb=%s mm, wp=%s mm, hp=%s mm, g=%s mm
' period=15 mm, substrate=3 mm vacuum, PEC ground at z=-3 mm
' Floquet port Zmax, reference plane -7.5 mm, 8-12 GHz, TE(0,0)/TM(0,0)
' Generated by ess_unit_nocoding.py at %s
""" % (tag, fmt_num(wr), fmt_num(wb), fmt_num(wp), fmt_num(hp), fmt_num(G),
       datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return header + "Sub Main()\n" + body_indented + "\nEnd Sub\n"


def ensure_dir(path):
    if path:
        os.makedirs(path, exist_ok=True)


def write_text_atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def save_json(path, obj):
    write_text_atomic(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _csv_value(v):
    if isinstance(v, float):
        return "%.10g" % v
    return str(v)


def upsert_csv_row(path, rec):
    """按 tag 更新一行；文件不存在则写表头。"""
    rows = []
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    if row.get("tag"):
                        rows.append(row)
        except Exception as exc:
            log("[warn] 读取 %s 失败，将重建：%s" % (path, exc))
            rows = []

    new_row = dict((k, _csv_value(rec.get(k, ""))) for k in CSV_FIELDS)
    replaced = False
    for i, row in enumerate(rows):
        if row.get("tag") == new_row["tag"]:
            rows[i] = new_row
            replaced = True
            break
    if not replaced:
        rows.append(new_row)

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict((k, row.get(k, "")) for k in CSV_FIELDS))
    os.replace(tmp, path)


def _add_cst_path():
    path = os.environ.get("CST_PYTHON_LIB", CST_LIB_DEFAULT)
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)
    return path


def load_results_module():
    _add_cst_path()
    try:
        import cst.results
        return cst.results
    except Exception as exc:
        raise CaseError(
            "无法导入 cst.results（请检查 CST 安装/ PYTHONPATH）。\n"
            "  CST 库路径: %s\n"
            "  原始错误: %s" % (_add_cst_path(), exc))


def _is_s11_path(path):
    p = path.replace(" ", "").lower()
    return ("s-parameters" in p and "zmax(1)" in p and "zmax(1),zmax(1)" in p)


def pick_s11_item(result3d):
    """优先用标准路径，否则扫描结果树，兼容不同 CST 版本/模式名。"""
    items = []
    try:
        items = list(result3d.get_tree_items())
    except Exception:
        items = []
    for candidate in S11_CANDIDATES:
        if candidate in items:
            return candidate
    for item in items:
        if _is_s11_path(item):
            return item
    for item in items:
        low = item.replace(" ", "").lower()
        if "s-parameters" in low and "zmax" in low:
            return item
    detail = "\n  ".join(items[:20]) if items else "(结果树为空)"
    raise CaseError("工程中找不到 Zmax 端口的 S11 结果。\n"
                    "  可用结果（前 20 条）:\n  " + detail)


def read_s11(project_path):
    """读取工程中 Zmax 端口 S11，返回 (freq_ghz, complex_s11, treepath)。"""
    if not os.path.isfile(project_path):
        raise CaseError("工程文件不存在：%s" % project_path)
    results = load_results_module()
    try:
        project = results.ProjectFile(project_path, allow_interactive=False)
        result3d = project.get_3d()
    except Exception as exc:
        raise CaseError(
            "无法打开工程结果：%s\n"
            "  cst.results.ProjectFile 读取失败：%s\n"
            "  工程需已保存且包含结果（include_results=True），且不能是打包/加密工程。" %
            (project_path, exc))

    try:
        treepath = pick_s11_item(result3d)
        item = result3d.get_result_item(treepath)
        data = item.get_data()
        xlabel = ""
        try:
            xlabel = item.xlabel
        except Exception:
            pass
        if xlabel and "GHz" not in str(xlabel):
            raise CaseError("S11 频率轴单位不是 GHz：%r" % (xlabel,))
        if isinstance(data, tuple) and len(data) >= 2 and not isinstance(data[0], (list, tuple)):
            rows = [data]          # 极少数版本返回单个 (freq, value) 元组
        elif isinstance(data, (list, tuple)):
            rows = list(data)
        else:
            rows = [data]
        if not rows:
            raise CaseError("S11 结果为空：%s" % treepath)
    except CaseError:
        raise
    except Exception as exc:
        raise CaseError("读取 S11 结果失败（%s）：%s" % (treepath, exc))

    best = None
    for row in rows:
        try:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                freq = float(row[0])
                val = row[1]
                if isinstance(val, complex):
                    s = val
                elif isinstance(val, (list, tuple)) and len(val) == 2:
                    s = complex(float(val[0]), float(val[1]))
                else:
                    s = complex(val)
            else:
                continue
        except Exception:
            continue
        if not math.isfinite(freq):
            continue
        dist = abs(freq - F0_GHZ)
        if best is None or dist < best[0]:
            best = (dist, freq, s)

    if best is None:
        raise CaseError("S11 结果中没有可解析的 (freq, value) 数据：%s" % treepath)
    if best[0] > FREQ_TOL_GHZ:
        raise CaseError("最近频点 %.4f GHz 偏离 10 GHz 超过 %.2f GHz"
                        % (best[1], FREQ_TOL_GHZ))
    return best[1], best[2], treepath


def read_s11_retry(project_path, attempts=3, delay=1.0):
    last = None
    for i in range(attempts):
        try:
            return read_s11(project_path)
        except Exception as exc:
            last = exc
            if i + 1 < attempts:
                time.sleep(delay)
    raise last


def make_record(tag, wr, wb, wp, hp, freq, s, project_path, vba_path,
                treepath, reused=False, elapsed_s=None):
    mag = abs(s)
    s11_db = 20.0 * math.log10(max(mag, 1e-300))
    phase_port = math.degrees(math.atan2(s.imag, s.real))
    phase_physical = phase_port + 180.0
    rec = {
        "tag": tag,
        "wr_mm": round(wr, 6),
        "wb_mm": round(wb, 6),
        "wp_mm": round(wp, 6),
        "hp_mm": round(hp, 6),
        "g_mm": G,
        "period_mm": PERIOD,
        "substrate_h_mm": SUBSTRATE_H,
        "frequency_ghz": round(freq, 8),
        "s11_db": round(s11_db, 8),
        "phase_port_deg": round(phase_port, 8),
        "phase_physical_deg": round(phase_physical, 8),
        "phase_physical_wrapped_deg": round(wrap180(phase_physical), 8),
        "s11_real": round(s.real, 12),
        "s11_imag": round(s.imag, 12),
        "result_treepath": treepath,
        "project": project_path,
        "vba": vba_path,
        "reused_project": bool(reused),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if elapsed_s is not None:
        rec["solve_elapsed_s"] = round(elapsed_s, 1)
    return rec


def project_paths(outdir, tag):
    return (os.path.join(outdir, "project_%s.cst" % tag),
            os.path.join(outdir, "result_%s.json" % tag),
            os.path.join(outdir, "vba_%s.txt" % tag))


def valid_record(rec, tag, wr, wb, wp, hp):
    if not isinstance(rec, dict) or rec.get("tag") != tag:
        return False
    for key, val in (("wr_mm", wr), ("wb_mm", wb), ("wp_mm", wp), ("hp_mm", hp)):
        try:
            if abs(float(rec.get(key)) - float(val)) > 1e-6:
                return False
        except (TypeError, ValueError):
            return False
    for key in ("s11_db", "phase_port_deg", "phase_physical_deg"):
        try:
            if not math.isfinite(float(rec.get(key))):
                return False
        except (TypeError, ValueError):
            return False
    return True


def load_existing(outdir, tag, wr, wb, wp, hp):
    """已有 JSON 直接复用；只有工程时尝试从工程读结果并补写 JSON。"""
    project_path, json_path, vba_path = project_paths(outdir, tag)
    if os.path.isfile(json_path):
        try:
            rec = load_json(json_path)
            if valid_record(rec, tag, wr, wb, wp, hp):
                return rec
            log("[warn] %s 参数与本次不一致或字段缺失，将重算" % json_path)
        except Exception as exc:
            log("[warn] %s 不是有效 JSON（%s），将重算" % (json_path, exc))
    if os.path.isfile(project_path):
        try:
            freq, s, treepath = read_s11_retry(project_path)
            rec = make_record(tag, wr, wb, wp, hp, freq, s, project_path,
                              vba_path, treepath, reused=True)
            save_json(json_path, rec)
            upsert_csv_row(os.path.join(outdir, "results.csv"), rec)
            log("[reuse] 从已有工程读取 %s：|S11|=%.3f dB, port=%.3f deg"
                % (tag, rec["s11_db"], rec["phase_port_deg"]))
            return rec
        except Exception as exc:
            log("[warn] 工程 %s 存在但读取结果失败：%s" %
                (project_path, str(exc).replace("\n", " ")[:300]))
    return None


class CstSession(object):
    """延迟连接，失败时可重置后重连。"""

    def __init__(self):
        self.de = None

    def connect(self):
        if self.de is not None:
            return
        _add_cst_path()
        try:
            import cst.interface
        except Exception as exc:
            raise CstConnectionError(
                "CST 连接失败：无法导入 cst.interface。\n"
                "  CST 库路径: %s\n"
                "  原始错误: %s\n"
                "  若本机 CST 2026 启动即崩溃（NETAPI32 0xc0000005），"
                "需先修复/重装 CST 或改用可正常启动的版本。" % (_add_cst_path(), exc))
        try:
            self.de = cst.interface.DesignEnvironment.connect_to_any_or_new()
            try:
                self.de.set_quiet_mode(True)
            except Exception:
                pass
            log("已连接 CST Design Environment")
        except Exception as exc:
            self.de = None
            raise CstConnectionError(
                "CST 连接/启动失败：%s\n"
                "  请确认 CST 2026 可手动正常启动；本机已知启动崩溃"
                "（NETAPI32 0xc0000005）时无法自动仿真。\n"
                "  可用环境变量 CST_PYTHON_LIB 指定 python_cst_libraries 路径。"
                % (str(exc).replace("\n", " ")[:500]))

    def reset(self):
        de, self.de = self.de, None
        if de is not None:
            try:
                de.close()
            except Exception:
                pass

    def close(self):
        self.reset()


def simulate_case(session, tag, wr, wb, wp, hp, outdir, timeout_s=3600.0):
    """建模 -> 保存 -> 求解 -> 保存结果 -> 读 S11；失败抛异常且不写结果 JSON。"""
    project_path, json_path, vba_path = project_paths(outdir, tag)
    write_text_atomic(vba_path, build_vba_macro(wr, wb, wp, hp, tag))

    prj = None
    t0 = time.time()
    session.connect()
    try:
        prj = session.de.new_mws()
        model = prj.model3d
        time.sleep(0.3)
        model.add_to_history("Build ESS unit cell (no coding)",
                             build_vba_body(wr, wb, wp, hp))
        # 先保存无结果工程，便于求解中断后检查模型
        prj.save(project_path, include_results=False, allow_overwrite=True)
        log("[solve] %s 建模完成，开始求解（%g-%g GHz）" % (tag, FMIN_GHZ, FMAX_GHZ))

        model.run_solver()
        deadline = time.time() + float(timeout_s)
        while True:
            try:
                running = bool(model.is_solver_running())
            except Exception:
                running = False
            if not running:
                break
            if time.time() > deadline:
                try:
                    model.abort_solver()
                except Exception:
                    pass
                raise CaseError("求解超时（> %.0f s）" % timeout_s)
            time.sleep(1.0)

        prj.save(project_path, include_results=True, allow_overwrite=True)
        prj.close()
        prj = None
        time.sleep(0.5)

        freq, s, treepath = read_s11_retry(project_path)
        rec = make_record(tag, wr, wb, wp, hp, freq, s, project_path,
                          vba_path, treepath, elapsed_s=time.time() - t0)
        # 只有成功读到 S11 才写 JSON/CSV
        save_json(json_path, rec)
        upsert_csv_row(os.path.join(outdir, "results.csv"), rec)
        log("[done] %s  %.3f GHz  |S11|=%.3f dB  port=%.3f deg  physical=%.3f deg  (%.0f s)"
            % (tag, freq, rec["s11_db"], rec["phase_port_deg"],
               rec["phase_physical_deg"], time.time() - t0))
        return rec
    finally:
        if prj is not None:
            try:
                prj.close()
            except Exception:
                pass


def solve_with_retries(session, tag, wr, wb, wp, hp, outdir, retries, timeout_s):
    last = None
    attempts = max(0, int(retries)) + 1
    for i in range(attempts):
        try:
            return simulate_case(session, tag, wr, wb, wp, hp, outdir, timeout_s)
        except Exception as exc:
            last = exc
            log("[error] %s 第 %d/%d 次失败：%s"
                % (tag, i + 1, attempts, str(exc).replace("\n", " ")[:400]))
            session.reset()
            if i + 1 < attempts:
                time.sleep(2.0)
    if isinstance(last, CaseError):
        raise last
    raise CaseError("求解失败：%s" % (str(last).replace("\n", " ")[:500]))


def read_cases_csv(path):
    """读取 cases.csv；返回 (cases, errors)。支持 BOM、空行和 # 注释。"""
    if not os.path.isfile(path):
        raise CaseError("cases.csv 不存在：%s" % path)
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        lines = [ln for ln in fh if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        raise CaseError("cases.csv 为空：%s" % path)

    cases = []
    errors = []
    reader = csv.DictReader(lines)
    if reader.fieldnames is None:
        raise CaseError("cases.csv 缺少表头（需要 wr,wb,wp,hp,tag）")
    field_map = dict((str(name).strip().lower(), name) for name in reader.fieldnames)
    if "wr" not in field_map or "wb" not in field_map:
        raise CaseError("cases.csv 表头必须至少包含 wr,wb（wp,hp,tag 可选）")

    for lineno, row in enumerate(reader, start=2):
        try:
            def getv(key, default="0"):
                real = field_map.get(key)
                if real is None:
                    return default
                val = row.get(real)
                return default if val is None or str(val).strip() == "" else str(val).strip()
            wr = float(getv("wr"))
            wb = float(getv("wb"))
            wp = float(getv("wp", "0"))
            hp = float(getv("hp", "0"))
            tag = getv("tag", "")
            cases.append({"wr": wr, "wb": wb, "wp": wp, "hp": hp, "tag": tag})
        except Exception as exc:
            errors.append("第 %d 行解析失败：%s" % (lineno, exc))
    return cases, errors


def run_dry(args, cases):
    ensure_dir(args.outdir)
    written = []
    failures = []
    for case in cases:
        try:
            wr, wb, wp, hp = validate_params(case["wr"], case["wb"], case["wp"], case["hp"])
            tag = sanitize_tag(case.get("tag"), wr, wb, wp, hp)
            path = os.path.join(args.outdir, "vba_%s.txt" % tag)
            write_text_atomic(path, build_vba_macro(wr, wb, wp, hp, tag))
            written.append(path)
            log("[dry-run] %s" % path)
        except Exception as exc:
            failures.append(str(exc))
            log("[error] dry-run 失败：%s" % exc)
    log("dry-run 完成：%d 个 VBA 文件，%d 个失败；未连接 CST" % (len(written), len(failures)))
    return 0 if not failures else 1


def run_single(args):
    wr, wb, wp, hp = validate_params(args.wr, args.wb, args.wp, args.hp)
    tag = sanitize_tag(args.tag, wr, wb, wp, hp)
    ensure_dir(args.outdir)
    if args.dry_run:
        return run_dry(args, [{"wr": wr, "wb": wb, "wp": wp, "hp": hp, "tag": tag}])

    session = CstSession()
    try:
        rec = solve_with_retries(session, tag, wr, wb, wp, hp, args.outdir,
                                 args.retries, args.timeout)
    finally:
        session.close()
    print(json.dumps(rec, ensure_ascii=False, indent=2), flush=True)
    return 0


def run_sweep(args):
    ensure_dir(args.outdir)
    cases, errors = read_cases_csv(args.sweep)
    if errors:
        for msg in errors:
            log("[error] cases.csv %s" % msg)
    if not cases:
        log("cases.csv 没有可用数据点")
        return 1

    # 先做参数检查，避免跑到一半才发现坏行
    good = []
    used_tags = {}
    for idx, case in enumerate(cases, start=1):
        try:
            wr, wb, wp, hp = validate_params(case["wr"], case["wb"], case["wp"], case["hp"])
            tag = sanitize_tag(case.get("tag"), wr, wb, wp, hp)
            if tag in used_tags and used_tags[tag] != (wr, wb, wp, hp):
                raise CaseError("tag %r 重复且参数不同（第 %d 行）" % (tag, idx + 1))
            used_tags[tag] = (wr, wb, wp, hp)
            good.append({"wr": wr, "wb": wb, "wp": wp, "hp": hp, "tag": tag})
        except Exception as exc:
            errors.append("第 %d 个数据点：%s" % (idx, exc))
            log("[error] 跳过坏数据点 %d：%s" % (idx, exc))

    if args.dry_run:
        return run_dry(args, good)

    session = CstSession()
    ok = 0
    skipped = 0
    try:
        for idx, case in enumerate(good, start=1):
            tag = case["tag"]
            if not args.force:
                existing = load_existing(args.outdir, tag, case["wr"], case["wb"],
                                         case["wp"], case["hp"])
                if existing is not None:
                    skipped += 1
                    try:
                        upsert_csv_row(os.path.join(args.outdir, "results.csv"), existing)
                    except Exception as exc:
                        log("[warn] 补写 results.csv 失败：%s" % exc)
                    log("[skip] %s 已有结果（%d/%d）" % (tag, idx, len(good)))
                    continue
            try:
                session.connect()
                solve_with_retries(session, tag, case["wr"], case["wb"], case["wp"],
                                    case["hp"], args.outdir, args.retries, args.timeout)
                ok += 1
            except Exception as exc:
                errors.append("%s: %s" % (tag, exc))
                log("[fail] %s：%s" % (tag, str(exc).replace("\n", " ")[:400]))
                session.reset()
    finally:
        session.close()

    log("批量结束：成功 %d，跳过 %d，失败 %d；results.csv = %s"
        % (ok, skipped, len(errors), os.path.join(args.outdir, "results.csv")))
    return 0 if not errors else 1


def build_arg_parser():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="ESS on 态单元胞（无 4x4 编码贴片）参数化仿真 / 批量扫描")
    ap.add_argument("--wr", type=float, default=0.8,
                    help="方环宽度 mm（推荐 0.5-1.2，默认 0.8）")
    ap.add_argument("--wb", type=float, default=1.0,
                    help="竖条宽度 mm（推荐 0.6-3.0，默认 1.0）")
    ap.add_argument("--wp", type=float, default=0.0,
                    help="中心垫片宽度 mm（0 表示不加，默认 0）")
    ap.add_argument("--hp", type=float, default=0.0,
                    help="中心垫片高度 mm（0 表示不加，默认 0）")
    ap.add_argument("--tag", default="", help="结果文件名标签，默认由几何参数生成")
    ap.add_argument("--outdir", default=os.path.join(here, "ess_unit_nocoding_out"),
                    help="输出目录（默认脚本旁 ess_unit_nocoding_out）")
    ap.add_argument("--sweep", default="", help="批量模式：cases.csv 路径")
    ap.add_argument("--dry-run", action="store_true",
                    help="只写 outdir/vba_<tag>.txt，不连接 CST")
    ap.add_argument("--force", action="store_true", help="批量模式忽略已有结果，强制重算")
    ap.add_argument("--retries", type=int, default=1, help="单点求解失败后的重试次数（默认 1）")
    ap.add_argument("--timeout", type=float, default=3600.0, help="单点求解超时秒数（默认 3600）")
    ap.add_argument("--debug", action="store_true", help="异常时打印完整 traceback")
    return ap


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    try:
        if args.sweep:
            return run_sweep(args)
        return run_single(args)
    except KeyboardInterrupt:
        log("用户中断")
        return 130
    except Exception as exc:
        if args.debug:
            import traceback
            traceback.print_exc()
        log("[error] %s" % str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
