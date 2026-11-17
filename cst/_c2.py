import sys
sys.path.insert(0, r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries")
import cst.interface
de = cst.interface.DesignEnvironment.connect_to_any_or_new()
de.set_quiet_mode(True)
opened = de.get_open_projects()
print("open projects:", len(opened))
for p in opened:
    try:
        fn = p.filename()
        p.close()
        print("closed:", fn)
    except Exception as e:
        print("close err:", str(e)[:60])
print("remaining:", [p.filename() for p in de.get_open_projects()])
