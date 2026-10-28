#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_cuts.py —— 拆镜头 + 量运镜，把"镜头运动还原"变成可以抄的数字

每个 shot 输出：
  · 起止帧号（直接拿去对关键帧）
  · 推拉 %/s、横移 %/s、升降 %/s（都是占画幅宽的比例）
  · 加减速（起幅慢落幅快 还是 匀速）
  · 一句人话

用法：
  python3 tools/probe_cuts.py 片子.mp4                    # 整幅看
  python3 tools/probe_cuts.py 片子.mp4 --half bottom      # 只看下半（对比视频里白模那半）
  python3 tools/probe_cuts.py 片子.mp4 --json --save-json cuts.json
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ffinfo


# --------------------------------------------------------------------------
def decode(path, half, width, tmpdir):
    if half == 'top':
        vf = f"crop=iw:ih/2:0:0,scale={width}:-1,format=gray"
    elif half == 'bottom':
        vf = f"crop=iw:ih/2:0:ih/2,scale={width}:-1,format=gray"
    else:
        vf = f"scale={width}:-1,format=gray"
    out = os.path.join(tmpdir, 'f_%05d.png')
    subprocess.run([ffinfo.FFMPEG, '-v', 'error', '-i', path, '-vf', vf,
                    '-vsync', '0', out], check=True)
    return [np.array(Image.open(os.path.join(tmpdir, n)), dtype=np.float32)
            for n in sorted(os.listdir(tmpdir))]


def _prep(a):
    a = a - a.mean()
    s = a.std()
    return a / s if s > 1e-6 else a


def phase_shift(a, b):
    """加窗 + 抛物线插值的相位相关 -> (dx, dy, 峰值)。"""
    h, w = a.shape
    win = np.outer(np.hanning(h), np.hanning(w)).astype(np.float32)
    A = np.fft.rfft2(_prep(a) * win)
    B = np.fft.rfft2(_prep(b) * win)
    R = A * np.conj(B)
    R /= (np.abs(R) + 1e-9)
    c = np.fft.irfft2(R, s=(h, w))
    iy, ix = np.unravel_index(np.argmax(c), c.shape)

    def sub(p0, pm, pp):
        den = pm - 2 * p0 + pp
        return 0.5 * (pm - pp) / den if abs(den) > 1e-12 else 0.0

    y = iy + sub(c[iy, ix], c[(iy - 1) % h, ix], c[(iy + 1) % h, ix])
    x = ix + sub(c[iy, ix], c[iy, (ix - 1) % w], c[iy, (ix + 1) % w])
    if y > h / 2:
        y -= h
    if x > w / 2:
        x -= w
    return float(x), float(y), float(c.max())


def zoom_ratio(a, b, cand=(0.94, 0.96, 0.98, 0.99, 0.995, 1.0, 1.005, 1.01, 1.02, 1.04, 1.06)):
    """b 相对 a 放大了多少（>1 = 推近）。把 b 按候选比例缩回 a 的尺寸，看哪个最对得上。"""
    h, w = a.shape
    bestp, best = -1.0, 1.0
    for s in cand:
        nh, nw = int(round(h * s)), int(round(w * s))
        if nh < 24 or nw < 24:
            continue
        crop = b[(h - nh) // 2:(h - nh) // 2 + nh, (w - nw) // 2:(w - nw) // 2 + nw]
        crop = np.array(Image.fromarray(crop.astype(np.uint8)).resize((w, h), Image.BILINEAR),
                        dtype=np.float32)
        _, _, p = phase_shift(a, crop)
        if p > bestp:
            bestp, best = p, s
    return 1.0 / best if best else 1.0


def detect_cuts(frames, k=8.0, floor=1.2):
    d = np.array([float(np.abs(frames[i] - frames[i - 1]).mean())
                  for i in range(1, len(frames))])
    med = np.array([np.median(d[max(0, i - 8):i + 9]) for i in range(len(d))])
    score = d / (med + 1e-3)
    cuts = [i + 1 for i in range(len(d)) if score[i] > k and d[i] > floor]
    merged = []
    for c in cuts:
        if merged and c - merged[-1] <= 2:
            continue
        merged.append(c)
    return merged


def analyse(frames, f0, f1, fps, W):
    """用 gap 帧的间隔测速度（间隔放大，慢推才测得出来），再算首尾 1/3 的加减速。"""
    n = f1 - f0
    if n < 4:
        return None
    gap = int(np.clip(round(n / 8), 2, 12))
    starts = list(range(f0, max(f0 + 1, f1 - gap), gap))
    if len(starts) < 2:
        starts = [f0, max(f0 + 1, f1 - gap - 1)]
    vx, vy, vz = [], [], []
    for i in starts:
        a, b = frames[i], frames[min(i + gap, len(frames) - 1)]
        dx, dy, _ = phase_shift(a, b)
        vx.append(dx / W * 100.0 / (gap / fps))
        vy.append(dy / W * 100.0 / (gap / fps))
        vz.append((zoom_ratio(a, b) - 1.0) * 100.0 / (gap / fps))
    vx, vy, vz = np.array(vx), np.array(vy), np.array(vz)
    t = max(1, len(vx) // 3)
    spd = lambda arr: float(np.mean(np.abs(arr)))
    accel = (spd(vx[-t:]) + spd(vy[-t:]) + spd(vz[-t:]) * 3) - \
            (spd(vx[:t]) + spd(vy[:t]) + spd(vz[:t]) * 3)
    return {'pan_pct_s': float(np.median(vx)), 'tilt_pct_s': float(np.median(vy)),
            'zoom_pct_s': float(np.median(vz)), 'accel': float(accel)}


def describe(m):
    if m is None:
        return '太短，量不出来'
    out = []
    z = m['zoom_pct_s']
    if abs(z) > 0.03:
        out.append(f"{'推近' if z > 0 else '拉远'} {abs(z):.2f}%/s")
    if abs(m['pan_pct_s']) > 0.03:
        out.append(f"{'右' if m['pan_pct_s'] > 0 else '左'}移 {abs(m['pan_pct_s']):.2f}%/s")
    if abs(m['tilt_pct_s']) > 0.03:
        out.append(f"{'上' if m['tilt_pct_s'] > 0 else '下'}摇 {abs(m['tilt_pct_s']):.2f}%/s")
    if not out:
        out.append('死机位（<0.03%/s）')
    if abs(m['accel']) > 0.05:
        out.append('变速（起落幅速度不同，要打缓入缓出）')
    return '，'.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--half', choices=['top', 'bottom', 'all'], default='all')
    ap.add_argument('--width', type=int, default=640)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--save-json', default=None)
    a = ap.parse_args()

    info = ffinfo.probe_json(a.video)
    v = [s for s in info['streams'] if s.get('codec_type') == 'video'][0]
    num, den = v['r_frame_rate'].split('/')
    fps = float(num) / float(den) if float(den) else 30.0
    SW, SH = int(v['width']), int(v['height'])

    tmp = tempfile.mkdtemp()
    frames = decode(a.video, a.half, a.width, tmp)
    W = frames[0].shape[1]
    cuts = detect_cuts(frames)

    bounds = [0] + cuts + [len(frames)]
    shots = []
    for i in range(len(bounds) - 1):
        f0, f1 = bounds[i], bounds[i + 1]
        if f1 - f0 < 2:
            continue
        m = analyse(frames, f0, f1, fps, W)
        shots.append({'shot': i + 1,
                      'start_frame': f0 + 1, 'end_frame': f1,
                      'start_s': round(f0 / fps, 3), 'end_s': round(f1 / fps, 3),
                      'frames': f1 - f0,
                      'motion': None if m is None else {kk: round(vv, 3) for kk, vv in m.items()},
                      'motion_text': describe(m)})
    result = {'file': a.video, 'size': [SW, SH], 'fps': fps,
              'total_frames': len(frames), 'half': a.half, 'shots': shots}
    if a.save_json:
        json.dump(result, open(a.save_json, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{os.path.basename(a.video)}  {SW}x{SH}  {fps:g}fps  {len(frames)}帧  "
              f"(运动量在 {W}px 宽上算)")
        print('-' * 86)
        for s in shots:
            print(f" 镜{s['shot']}  帧 {s['start_frame']:>4}–{s['end_frame']:<4}"
                  f" ({s['start_s']:>6.2f}–{s['end_s']:>6.2f}s, {s['frames']:>3}帧)  {s['motion_text']}")
        print('-' * 86)
        print(f"切点帧号: {', '.join(str(s['start_frame']) for s in shots[1:]) or '无（一镜到底）'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
