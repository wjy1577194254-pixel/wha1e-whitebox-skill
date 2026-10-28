# -*- coding: utf-8 -*-
"""
ffinfo —— 找一个能用的 ffprobe，找不到就用 `ffmpeg -i` 的横幅将就一下

这台机器上 .tools/bin 里只有 ffmpeg，没有 ffprobe。查找顺序：
  1. $FFPROBE
  2. <工作区>/.tools/bin/ffprobe
  3. PATH
  4. 剪映 App 包里自带的那个（开发机上恰好有）
  5. 退化成解析 `ffmpeg -i` 的输出
"""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(os.path.dirname(HERE))

_CANDIDATES = [
    os.environ.get('FFPROBE', ''),
    os.path.join(WS, '.tools', 'bin', 'ffprobe'),
    shutil.which('ffprobe') or '',
    '/Applications/剪映专业版 2.app/Contents/Resources/ffprobe',
]


def find_bin(name):
    if name == 'ffmpeg':
        for c in (os.environ.get('FFMPEG', ''), os.path.join(WS, '.tools', 'bin', 'ffmpeg'),
                  shutil.which('ffmpeg') or ''):
            if c and os.path.exists(c):
                return c
        sys.exit('找不到 ffmpeg')
    for c in _CANDIDATES:
        if c and os.path.exists(c):
            return c
    return None


FFMPEG = find_bin('ffmpeg')
FFPROBE = find_bin('ffprobe')


def probe_json(path):
    """返回 ffprobe 的 JSON；没有 ffprobe 时用 ffmpeg 横幅拼一个近似结构。"""
    if FFPROBE:
        r = subprocess.run([FFPROBE, '-v', 'error', '-print_format', 'json',
                            '-show_format', '-show_streams', path],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout)
    return _probe_from_ffmpeg(path)


def _probe_from_ffmpeg(path):
    r = subprocess.run([FFMPEG, '-hide_banner', '-i', path],
                       capture_output=True, text=True)
    txt = r.stderr
    streams, fmt = [], {}
    m = re.search(r'Duration:\s*(\d+):(\d+):([\d.]+)', txt)
    if m:
        hh, mm, ss = m.groups()
        fmt['duration'] = str(int(hh) * 3600 + int(mm) * 60 + float(ss))
    m = re.search(r'bitrate:\s*(\d+)\s*kb/s', txt)
    if m:
        fmt['bit_rate'] = str(int(m.group(1)) * 1000)
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith('Stream #') and 'Video:' in s:
            d = {'codec_type': 'video'}
            mm = re.search(r'Video:\s*(\w+)', s)
            if mm:
                d['codec_name'] = mm.group(1)
            mm = re.search(r'(\d{2,5})x(\d{2,5})', s)
            if mm:
                d['width'], d['height'] = mm.group(1), mm.group(2)
            mm = re.search(r'([\d.]+)\s*fps', s)
            if mm:
                d['r_frame_rate'] = f"{mm.group(1)}/1"
            mm = re.search(r'(\d+)\s*kb/s', s)
            if mm:
                d['bit_rate'] = str(int(mm.group(1)) * 1000)
            streams.append(d)
        elif s.startswith('Stream #') and 'Audio:' in s:
            d = {'codec_type': 'audio'}
            mm = re.search(r'Audio:\s*(\w+)', s)
            if mm:
                d['codec_name'] = mm.group(1)
            mm = re.search(r'(\d+)\s*Hz', s)
            if mm:
                d['sample_rate'] = mm.group(1)
            d['channels'] = '2' if 'stereo' in s else ('1' if 'mono' in s else '0')
            mm = re.search(r'(\d+)\s*kb/s', s)
            if mm:
                d['bit_rate'] = str(int(mm.group(1)) * 1000)
            streams.append(d)
    return {'streams': streams, 'format': fmt}


def count_frames(path, stream='v:0'):
    """数真实帧数（nb_frames 有的封装不写）。"""
    r = subprocess.run([FFMPEG, '-hide_banner', '-i', path, '-map', f'0:{stream}',
                        '-c', 'copy', '-f', 'null', '-'],
                       capture_output=True, text=True)
    m = re.findall(r'frame=\s*(\d+)', r.stderr)
    return int(m[-1]) if m else 0
