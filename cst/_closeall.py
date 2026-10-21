import sys, time
sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.interface
de = cst.interface.DesignEnvironment.connect_to_any()
de.set_quiet_mode(True)
for p in de.get_open_projects():
    print("closing", p.filename())
    try:
        p.close()
        print("  closed")
    except Exception as e:
        print("  close failed:", str(e)[:120])
time.sleep(2)
rest = [p.filename() for p in de.get_open_projects()]
print("still open:", rest)
if rest:
    print("closing the design environment ...")
    try:
        de.close()
        print("DE closed")
    except Exception as e:
        print("DE close failed:", str(e)[:120])
