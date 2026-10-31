# -*- coding: utf-8 -*-
"""Crop / rectify the two conference photos into slide-ready screenshots."""

import os

import numpy as np
from PIL import Image

OUT = r"D:\DSHNESS\GNN\fig_talk"
os.makedirs(OUT, exist_ok=True)

JOBS = [
    # name, source, quad (TL, TR, BR, BL) in source pixels, post-crop (l, t, r, b)
    ("conference_graph", r"C:\Users\Xia\.dsh\attachments\v1\objects\f0\f0cc8cf19d830602be9f57508e4fe78ed55f8d69a50310248e0a21e94163cb2f",
     [(478, 316), (2200, 289), (2189, 1310), (488, 1341)], (18, 18, 1586, 833)),
    ("conference_ar", r"C:\Users\Xia\.dsh\attachments\v1\objects\26\2645b8da190a79febdcd9a2048c5e979d814a59ec0a9bb5f1e26674856898bd6",
     [(188, 263), (2103, 297), (2108, 1313), (197, 1329)], (80, 64, 1588, 822)),
]

W, H = 1600, 900


def coeffs(dst, src):
    A, B = [], []
    for (u, v), (x, y) in zip(dst, src):
        A.append([u, v, 1, 0, 0, 0, -u * x, -v * x])
        B.append(x)
        A.append([0, 0, 0, u, v, 1, -u * y, -v * y])
        B.append(y)
    res = np.linalg.solve(np.array(A, float), np.array(B, float))
    return res.tolist()


for name, path, quad, box in JOBS:
    img = Image.open(path).convert("RGB")
    dst = [(0, 0), (W, 0), (W, H), (0, H)]
    c = coeffs(dst, quad)
    out = img.transform((W, H), Image.PERSPECTIVE, c, resample=Image.BICUBIC)
    out = out.crop(box).resize((W, H), Image.LANCZOS)
    p = os.path.join(OUT, name + ".jpg")
    out.save(p, quality=92)
    print("saved", p, out.size)





