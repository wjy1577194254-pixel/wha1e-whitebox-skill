#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_pair.py —— 把「原片」和「白模」合成甲方要的对比视频（上原片 / 下白模）

规范出处：《白膜验收标准》p4「采用"上方原片、下方白模"的对比形式」、
         《渲染与打包规范1020》「1080p 指短边 ≥1080px，不是长边 ≥1920」

用法：
  python3 tools/compare_pair.py 123.mp4 123白模.mp4 -o 123对比.mp4
  python3 tools/compare_pair.py 123.mp4 123白模.mp4 -o 123对比.mp4 --width 1920
  python3 tools/compare_pair.py ... --audio-from whitebox     # 声音取白模轨
  python3 tools/compare_pair.py ... --qa                      # 只出低码率审片版

默认输出 1920 宽、每条片源按原画幅缩放后上下堆叠，短边一定 ≥1080。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ffinfo

FFMPEG = ffinfo.FFMPEG
FFPROBE = ffinfo.FFPROBE


def find_tool(name, env):
    if env:
        return env
    if name == 'ffmpeg' and ffinfo.FFMPEG:
        return ffinfo.FFMPEG
    if name == 'ffprobe' and ffinfo.FFPROBE:
        return ffinfo.FFPROBE
    p = os.path.join(WS, '.tools', 'bin', name)
    if os.path.exists(p):
        return p
    p = shutil.which(name)
    if p:
        return p
    sys.exit(f"找不到 {name}，用 --{name} 指一下路径")


def aac_encoder(ffmpeg):
    """
    甲方要 AAC 立体声 ≥320kbps。ffmpeg 自带的 aac 编码器在语音素材上怎么给都只到 ~175k，
    必须用 AudioToolbox 的 aac_at（macOS 自带）才真的能顶到 320k。
    """
    r = subprocess.run([ffmpeg, '-hide_banner', '-encoders'], capture_output=True, text=True)
    return 'aac_at' if 'aac_at' in r.stdout else 'aac'


def probe(ffprobe, path):
    out = subprocess.run(
        [ffprobe, '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', path],
        capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"ffprobe 读不了 {path}:\n{out.stderr}")
    return json.loads(out.stdout)


def video_info(info):
    v = next(s for s in info['streams'] if s['codec_type'] == 'video')
    w, h = int(v['width']), int(v['height'])
    sar = v.get('sample_aspect_ratio', '1:1')
    if sar and sar not in ('0:1', '1:1'):
        a, b = sar.split(':')
        if int(b):
            w = int(round(w * int(a) / int(b)))
    num, den = v['r_frame_rate'].split('/')
    fps = float(num) / float(den) if float(den) else 0.0
    return {'w': w, 'h': h, 'fps': fps, 'codec': v['codec_name'],
            'frames': int(v.get('nb_frames') or 0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('orig')
    ap.add_argument('white')
    ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--width', type=int, default=1920, help='合成后宽度（默认 1920）')
    ap.add_argument('--bitrate', default='30M', help='视频码率，规范建议 30M，最低 18M')
    ap.add_argument('--audio-bitrate', default='320k')
    ap.add_argument('--audio-from', choices=['orig', 'white'], default='orig')
    ap.add_argument('--qa', action='store_true', help='审片版：低码率小体积')
    ap.add_argument('--ffmpeg', default=None)
    ap.add_argument('--ffprobe', default=None)
    a = ap.parse_args()

    ffmpeg = find_tool('ffmpeg', a.ffmpeg)
    ffprobe = find_tool('ffprobe', a.ffprobe)

    oi = probe(ffprobe, a.orig)
    wi = probe(ffprobe, a.white)
    o, w = video_info(oi), video_info(wi)

    print(f"原片  {a.orig}  {o['w']}x{o['h']}  {o['fps']:.3f}fps  帧数 {o['frames']}")
    print(f"白模  {a.white}  {w['w']}x{w['h']}  {w['fps']:.3f}fps  帧数 {w['frames']}")

    # 帧率必须一致；不一致就当场叫停，别默默把切镜搞歪
    if abs(o['fps'] - w['fps']) > 0.01:
        print(f"!! 帧率不一致 {o['fps']} vs {w['fps']}，先修好再合成", file=sys.stderr)
        sys.exit(2)
    if o['frames'] and w['frames'] and o['frames'] != w['frames']:
        print(f"!! 总帧数不一致 {o['frames']} vs {w['frames']}（会导致切镜错位）", file=sys.stderr)

    W = a.width
    oh = int(round(o['h'] * W / o['w'] / 2.0)) * 2
    wh = int(round(w['h'] * W / w['w'] / 2.0)) * 2
    if oh != wh:
        print(f"!! 画幅不一致：原片折合 {oh}px 高、白模 {wh}px 高；按原片对齐白模会被拉伸")
    half = oh
    total_h = half * 2

    filt = (f"[0:v]scale={W}:{half}:flags=lanczos,setsar=1[top];"
            f"[1:v]scale={W}:{half}:flags=lanczos,setsar=1[bot];"
            f"[top][bot]vstack=inputs=2[v]")

    args = [ffmpeg, '-y', '-i', a.orig, '-i', a.white,
            '-filter_complex', filt, '-map', '[v]']
    src = 0 if a.audio_from == 'orig' else 1
    enc = aac_encoder(ffmpeg)
    print(f"音频编码器: {enc}  {a.audio_bitrate}  48kHz 立体声")
    args += ['-map', f'{src}:a?', '-c:a', enc, '-b:a', a.audio_bitrate,
             '-ar', '48000', '-ac', '2']
    if a.qa:
        args += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '30', '-pix_fmt', 'yuv420p']
    else:
        br = int(a.bitrate.rstrip('M')) * 1000000
        args += ['-c:v', 'libx264', '-preset', 'slow', '-profile:v', 'high', '-level', '4.2',
                 '-b:v', a.bitrate, '-maxrate', str(br), '-bufsize', str(br * 2),
                 '-pix_fmt', 'yuv420p', '-g', str(int(o['fps']) * 2),
                 '-movflags', '+faststart']
    args += ['-r', f"{o['fps']:.6f}", a.out]

    print("合成:", a.out, f"{W}x{total_h}  (每格 {W}x{half})")
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ffmpeg 失败:\n" + r.stderr[-3000:])
    print("OK")


if __name__ == '__main__':
    main()
