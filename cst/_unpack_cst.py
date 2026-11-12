# -*- coding: utf-8 -*-
import struct, zipfile, io, os
src = r"D:\re_cst_code1110\code1110_on.cst"
dst = r"D:\DSHNESS\GNN\_code1110_on_patched.zip"
b = bytearray(open(src,"rb").read())
# patch local and central signatures DE->PK
for old,new in [(b"DE\x03\x04", b"PK\x03\x04"), (b"DE\x01\x02", b"PK\x01\x02")]:
    n=0; i=0
    while True:
        j=b.find(old,i)
        if j<0: break
        b[j:j+2]=new[:2]; n+=1; i=j+2
    print(old, n)
open(dst,"wb").write(b)
try:
    z=zipfile.ZipFile(dst)
    print("testzip:", z.testzip())
    for info in z.infolist():
        print("%10d %10d  %s" % (info.file_size, info.compress_size, info.filename))
    z.extractall(r"D:\DSHNESS\GNN\_cst_unpacked")
    print("extracted")
except Exception as e:
    print("ERR", type(e).__name__, e)
