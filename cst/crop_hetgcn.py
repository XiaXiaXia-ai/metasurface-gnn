# -*- coding: utf-8 -*-
"""Crop the Het-GCN slide photo into a clean screenshot."""

import os

from PIL import Image

SRC = r"C:\Users\Xia\.dsh\attachments\v1\objects\24\24eec31f4a5e941b99277a72c51169fbf763b157c07de98a25726287f1786bab"
OUT = r"D:\DSHNESS\GNN\fig_talk"
os.makedirs(OUT, exist_ok=True)

# box in source pixels (left, top, right, bottom); tuned to sit inside the screen
BOX = (250, 385, 2155, 1420)

im = Image.open(SRC).convert("RGB")
out = im.crop(BOX).resize((1600, 900), Image.LANCZOS)
p = os.path.join(OUT, "conference_hetgcn.jpg")
out.save(p, quality=92)
print("saved", p, out.size)

