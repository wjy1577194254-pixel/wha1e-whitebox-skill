# -*- coding: utf-8 -*-
"""camera grid: 一次渲一堆候选机位，拼成对照图，用人眼挑。"""
import os, subprocess, sys, itertools, shutil
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BL = "/Applications/Blender.app/Contents/MacOS/Blender"
SCENE = os.path.join(ROOT, 'scenes', 'panda_scene.py')
OUT = os.path.join(ROOT, 'out', 'camgrid')

CANDIDATES = [
    ("A", (0.0, -11.0, 2.60), (0, 6, 1.20), 24),
    ("B", (0.0, -12.5, 3.00), (0, 6, 1.10), 26),
    ("C", (0.0, -10.0, 2.30), (0, 6, 1.30), 22),
    ("D", (0.0, -13.5, 3.40), (0, 6, 1.00), 28),
    ("E", (0.0, -11.5, 2.90), (0, 6, 1.60), 24),
    ("F", (0.0, -9.5, 2.10), (0, 6, 1.40), 20),
]


def run(shot, frame, res):
    os.makedirs(OUT, exist_ok=True)
    paths = []
    for name, loc, tgt, lens in CANDIDATES:
        cam = f"{loc[0]},{loc[1]},{loc[2]};{tgt[0]},{tgt[1]},{tgt[2]};{lens}"
        tag = f"{name}"
        subprocess.run([BL, '-b', '--factory-startup', '-P', SCENE, '--',
                        f'--shot={shot}', f'--frames={frame}',
                        f'--res={res}', f'--cam={cam}', f'--tag={tag}'],
                       capture_output=True)
        paths.append((name, os.path.join(ROOT, 'out', f'shot{shot}_{tag}',
                                         f'shot{shot}_{tag}_f{frame:04d}.png')))
    return paths


def sheet(paths, ref, out_path, frame):
    plate = Image.open(ref).convert('RGB')
    tw = 640
    th = int(tw * plate.height / plate.width)
    plate = plate.resize((tw, th), Image.LANCZOS)
    cols = 2
    rows = (len(paths) + 1 + cols - 1) // cols
    S = Image.new('RGB', (tw * cols, th * rows), (18, 18, 18))
    d = ImageDraw.Draw(S)
    S.paste(plate, (0, 0))
    d.text((8, 8), f"PLATE f{frame}", fill=(255, 255, 0))
    for k, (name, p) in enumerate(paths):
        i = k + 1
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert('RGB').resize((tw, th), Image.LANCZOS)
        x, y = (i % cols) * tw, (i // cols) * th
        S.paste(im, (x, y))
        d.text((x + 8, y + 8), name, fill=(255, 255, 0))
    S.save(out_path, quality=88)
    print("WROTE", out_path, S.size)


if __name__ == '__main__':
    shot = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    frame = int(sys.argv[2]) if len(sys.argv) > 2 else 110
    ref = sys.argv[3] if len(sys.argv) > 3 else os.path.join(ROOT, 'src2', f'f_{frame:03d}.jpg')
    ps = run(shot, frame, 270)
    sheet(ps, ref, os.path.join(OUT, f'grid_{shot}_{frame}.jpg'), frame)
