# -*- coding: utf-8 -*-
"""Dual-polarized ESS unit with a uniform n x n patch grid per quadrant
(no 4x4 coding pattern).  15 mm period, 3 mm vacuum, PEC ground z=-3.
Ring + cross + four PIN diodes ON + uniform patch texture.
"""
import sys, os, time, math, json
sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.interface, cst.results
PID = 38716
OUT = r"D:\DSHNESS\GNN\grid_out"
HALF = 7.5; H = 3.0; G = 1.0; RW = 3.0; LH = 0.45e-9

def brick(name, x0, x1, y0, y1, z0="0", z1="0", comp="unit", mat="PEC"):
    return ('With Brick\n .Reset\n .Name "%s"\n .Component "%s"\n .Material "%s"\n'
            ' .Xrange "%g","%g"\n .Yrange "%g","%g"\n .Zrange "%s","%s"\n .Create\nEnd With\n'
            % (name, comp, mat, x0, x1, y0, y1, z0, z1))

def build_vba(wr, wb, ps, gap, n):
    inner = HALF - wr
    arm = inner - G
    pitch = ps + gap
    v = []
    v.append('With Units\n .Geometry "mm"\n .Frequency "GHz"\n .Time "ns"\nEnd With')
    v.append('Solver.FrequencyRange "8","12"')
    v.append('With Background\n .ResetBackground\n .Type "Normal"\n .Epsilon "1.0"\n .Mu "1.0"\n'
             ' .XminSpace "0.0"\n .XmaxSpace "0.0"\n .YminSpace "0.0"\n .YmaxSpace "0.0"\n'
             ' .ZminSpace "0.0"\n .ZmaxSpace "7.5"\n .ApplyInAllDirections "False"\nEnd With')
    v.append('With Boundary\n .Xmin "unit cell"\n .Xmax "unit cell"\n .Ymin "unit cell"\n .Ymax "unit cell"\n'
             ' .Zmin "electric"\n .Zmax "open"\n .Xsymmetry "none"\n .Ysymmetry "none"\n .Zsymmetry "none"\n'
             ' .ApplyInAllDirections "True"\nEnd With')
    v.append('With FloquetPort\n .Reset\n .SetDialogTheta "0"\n .SetDialogPhi "0"\n .SetSortCode "+beta/pw"\n'
             ' .SetCustomizedListFlag "False"\n .Port "Zmax"\n .SetNumberOfModesConsidered "2"\n'
             ' .SetDistanceToReferencePlane "-7.5"\n .SetUseCircularPolarization "False"\nEnd With')
    v.append('With Mesh\n .MeshType "Tetrahedral"\nEnd With')
    v.append('With MeshSettings\n .SetMeshType "Tet"\n .Set "Version", 1\nEnd With')
    v.append(brick("sub", -HALF, HALF, -HALF, HALF, "-3", "0", "c1", "Vacuum"))
    v.append(brick("gnd", -HALF, HALF, -HALF, HALF, "-3", "-3", "c1", "PEC"))
    v.append(brick("ring_n", -HALF, HALF, inner, HALF, comp="c2"))
    v.append(brick("ring_s", -HALF, HALF, -HALF, -inner, comp="c2"))
    v.append(brick("ring_w", -HALF, -inner, -inner, inner, comp="c2"))
    v.append(brick("ring_e", inner, HALF, -inner, inner, comp="c2"))
    v.append(brick("bar_v", -wb/2, wb/2, -arm, arm, comp="c2"))
    v.append(brick("bar_h", -arm, arm, -wb/2, wb/2, comp="c2"))
    v.append('Solid.Add "c2:bar_v", "c2:bar_h"')
    # uniform n x n grid per quadrant, first cell touches the cross at +0.5
    start = wb/2.0
    for i in range(n):
        for j in range(n):
            x0 = start + i*pitch; x1 = x0 + ps
            y0 = start + j*pitch; y1 = y0 + ps
            for k,(sx,sy) in enumerate(((1,1),(1,-1),(-1,-1),(-1,1))):
                ax,bx = sorted((sx*x0, sx*x1))
                ay,by = sorted((sy*y0, sy*y1))
                v.append(brick("p_%d_%d_%d"%(i,j,k), ax,bx, ay,by, comp="c3"))
    for x1,y1,x2,y2,nm in [(0,arm,0,inner,"top"),(0,-arm,0,-inner,"bot"),
                            (arm,0,inner,0,"right"),(-arm,0,-inner,0,"left")]:
        v.append('With LumpedElement\n .Reset\n .SetName "d_%s"\n .Folder "Folder1"\n .SetType "RLCSerial"\n'
                 ' .SetR "3"\n .SetL "%g"\n .SetC "0"\n .SetGs "0"\n .SetI0 "1e-14"\n .SetT "300"\n'
                 ' .SetMonitor "True"\n .SetRadius "0.0"\n .CircuitFileName ""\n .CircuitId "1"\n'
                 ' .UseCopyOnly "True"\n .UseRelativePath "False"\n'
                 ' .SetP1 "False","%g","%g","0"\n .SetP2 "False","%g","%g","0"\n'
                 ' .SetInvert "False"\n .Wire ""\n .Position "end1"\n .Create\nEnd With\n'
                 % (nm, LH, x1, y1, x2, y2))
    v.append('With FDSolver\n .Reset\n .Stimulation "List","List"\n .ResetExcitationList\n'
             ' .AddToExcitationList "Zmax","TE(0,0);TM(0,0)"\n .LowFrequencyStabilization "False"\nEnd With')
    v.append('ChangeSolverType "HF Frequency Domain"')
    return "\n".join(v)

def read_s11(path, mode=1):
    res = cst.results.ProjectFile(path, allow_interactive=False)
    r3 = res.get_3d()
    item = r3.get_result_item(r"1D Results\S-Parameters\SZmax(%d),Zmax(%d)" % (mode, mode))
    rows = item.get_data(); best=None
    for row in rows:
        f=float(row[0])
        if best is None or abs(f-10.0)<abs(best[0]-10.0): best=(f,complex(row[1]))
    return best

def solve(tag, wr, wb, ps, gap, n):
    os.makedirs(OUT, exist_ok=True)
    de = cst.interface.DesignEnvironment(pid=PID); de.set_quiet_mode(True)
    for p in de.get_open_projects():
        try: p.close()
        except Exception: pass
    path=os.path.join(OUT,"grid_%s.cst"%tag); t0=time.time()
    prj=de.new_mws(); m=prj.model3d
    m.add_to_history("Build grid %s"%tag, build_vba(wr,wb,ps,gap,n))
    prj.save(path, include_results=False, allow_overwrite=True)
    m.run_solver()
    while True:
        try: running=m.is_solver_running()
        except Exception: running=False
        if not running: break
        if time.time()-t0>300: m.abort_solver(); raise RuntimeError("timeout")
        time.sleep(1)
    prj.save(path, include_results=True, allow_overwrite=True); prj.close()
    f1,s1=read_s11(path,1); f2,s2=read_s11(path,2)
    p1=math.degrees(math.atan2(s1.imag,s1.real)); p2=math.degrees(math.atan2(s2.imag,s2.real))
    print("%s wr=%.2f wb=%.2f ps=%.2f gap=%.2f n=%d | TE %.2f deg %.3f dB | TM %.2f deg %.3f dB | %.0f s"
          %(tag,wr,wb,ps,gap,n,p1,20*math.log10(max(abs(s1),1e-12)),p2,20*math.log10(max(abs(s2),1e-12)),time.time()-t0))

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--tag"); ap.add_argument("--wr",type=float,default=0.5)
    ap.add_argument("--wb",type=float,default=1.0); ap.add_argument("--ps",type=float,default=1.5)
    ap.add_argument("--gap",type=float,default=0.5); ap.add_argument("--n",type=int,default=3)
    a=ap.parse_args(); solve(a.tag,a.wr,a.wb,a.ps,a.gap,a.n)
