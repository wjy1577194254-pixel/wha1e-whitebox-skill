#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_align.py —— 对位检查：把白模渲染半透明压在原片那一帧上，位移一眼就看出来

这是这活最核心的动作：不是"看着差不多"，是"叠上去对得上"。

用法：
  python3 tools/check_align.py 原片帧.png 渲染.png -o 对照.png
  python3 tools/check_align.py 原片帧.png 渲染.png -o 对照.png --opacity 0.45
  python3 tools/check_align.py 原片帧.png 渲染.png -o 对照.png --mode diff

输出三栏：原片 / 叠影（看对位）/ 白模渲染。--mode diff 时第三栏换成差值图，亮的地方就是没对上的地方。
"""
import argparse

import numpy as np
from PIL import Image, ImageDraw


def load(path, size=None):
    im = Image.open(path).convert('RGB')
    if size and im.size != size:
        im = im.resize(size, Image.LANCZOS)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('plate')
    ap.add_argument('render')
    ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--opacity', type=float, default=0.5)
    ap.add_argument('--mode', choices=['overlay', 'diff'], default='overlay')
    a = ap.parse_args()

    plate = load(a.plate)
    rnd = load(a.render, plate.size)
    W, H = plate.size

    if a.mode == 'diff':
        p = np.array(plate, dtype=np.float32)
        r = np.array(rnd, dtype=np.float32)
        d = np.clip(np.abs(p - r).mean(2) * 2.2, 0, 255).astype(np.uint8)
        diff = Image.fromarray(np.stack([d] * 3, axis=2))
        panels = [plate, diff, rnd]
        labels = ['PLATE (original)', 'DIFF (bright = misaligned)', 'WHITEBOX render']
    else:
        panels = [plate, Image.blend(plate, rnd, a.opacity), rnd]
        labels = ['PLATE (original)', 'OVERLAY (check alignment)', 'WHITEBOX render']

    pad = 8
    sheet = Image.new('RGB', (W * 3 + pad * 4, H + 34), (250, 250, 248))
    d = ImageDraw.Draw(sheet)
    for i, (im, lab) in enumerate(zip(panels, labels)):
        x = pad + i * (W + pad)
        sheet.paste(im, (x, 30))
        d.text((x, 8), lab, fill=(20, 20, 20))
    sheet.save(a.out, quality=94)
    print(f"写出 {a.out}  ({sheet.width}x{sheet.height})")


if __name__ == '__main__':
    main()
