#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_delivery.py —— 交付前自检，一条条对着《视频交付自检规范》和《参数验收标准》打勾

用法：
  python3 tools/check_delivery.py ./123            # 传文件夹（推荐，连命名/多余文件一起查）
  python3 tools/check_delivery.py 123.mp4 123白模.mp4 123对比.mp4
  python3 tools/check_delivery.py ./123 --json     # 机器可读

退出码 0 = 全过；1 = 有硬伤（甲方会退的那种）
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

OK, BAD, WARN = 'PASS', 'FAIL', 'WARN'
FFPROBE = ffinfo.FFPROBE
FFMPEG = ffinfo.FFMPEG


def probe(path):
    return ffinfo.probe_json(path)


def info(path):
    d = probe(path)
    if not d:
        return None
    v = next((s for s in d['streams'] if s['codec_type'] == 'video'), None)
    a = next((s for s in d['streams'] if s['codec_type'] == 'audio'), None)
    if not v:
        return None
    num, den = v['r_frame_rate'].split('/')
    fps = float(num) / float(den)
    dur = float(d['format'].get('duration') or 0)
    nbf = v.get('nb_frames')
    if nbf:
        frames = int(nbf)
    else:
        frames = int(round(dur * fps))
    sar = v.get('sample_aspect_ratio', '1:1')
    w = int(v['width'])
    if sar and sar not in ('0:1', '1:1'):
        p, q = sar.split(':')
        if int(q):
            w = int(round(w * int(p) / int(q)))
    br = int(d['format'].get('bit_rate') or 0)
    return {
        'w': w, 'h': int(v['height']),
        'short': min(w, int(v['height'])),
        'fps': fps, 'frames': frames, 'dur': dur,
        'vcodec': v['codec_name'], 'container': os.path.splitext(path)[1].lstrip('.').lower(),
        'vbitrate': int(v.get('bit_rate') or 0) or br,
        'acodec': a['codec_name'] if a else None,
        'arate': int(a['sample_rate']) if a else 0,
        'achan': int(a['channels']) if a else 0,
        'abitrate': int(a.get('bit_rate') or 0) if a else 0,
        'a_bits': a.get('bits_per_raw_sample') if a else None,
        'has_audio': a is not None,
    }


def black_tail(path, last_seconds=1.0):
    """片尾最后一秒有没有纯黑帧（规范里点名要逐帧查的东西）"""
    i = info(path)
    if not i:
        return None
    ss = max(0.0, i['dur'] - last_seconds)
    r = subprocess.run([FFMPEG, '-loglevel', 'info', '-ss', f'{ss:.3f}', '-i', path,
                        '-an', '-vf', 'signalstats,metadata=print:key=lavfi.signalstats.YAVG',
                        '-f', 'null', '-'], capture_output=True, text=True)
    vals = [float(m) for m in re.findall(r'YAVG=([\d.]+)', r.stdout + r.stderr)]
    if not vals:
        return None
    return min(vals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('target', nargs='+')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--skip-black', action='store_true')
    a = ap.parse_args()

    if not FFPROBE:
        sys.exit("找不到 ffprobe")

    rows = []
    extras = []

    def add(name, level, detail=''):
        rows.append({'check': name, 'level': level, 'detail': detail})

    # 目标既可以是一个文件夹，也可以是一串文件
    files = []
    if len(a.target) == 1 and os.path.isdir(a.target[0]):
        d = a.target[0]
        entries = sorted(os.listdir(d))
        allowed = ('.mp4', '.mov', '.mkv', '.blend', '.zip', '.meta', '.json', '.txt')
        for e in entries:
            p = os.path.join(d, e)
            if os.path.isdir(p):
                add('包内不应有子文件夹', BAD, e + '/（规范要求平铺）')
                continue
            if os.path.splitext(e)[1].lower() not in allowed:
                if e.lower().endswith(('.blend1', '.blend2')):
                    add('不能夹带 .blend1 备份文件', BAD, e)
                else:
                    add('包内有多余文件', BAD, e)
            files.append(p)
        # 命名统一
        stems = {}
        for p in files:
            b = os.path.basename(p)
            ext = os.path.splitext(b)[1].lower()
            if ext in ('.mp4', '.mov', '.mkv'):
                stem = os.path.splitext(b)[0]
                for suf in ('白模', '对比', '_wb', '_cmp', '_compare'):
                    if stem.endswith(suf):
                        stem = stem[:-len(suf)]
                stems.setdefault(stem, []).append(b)
            elif ext == '.blend':
                stems.setdefault(os.path.splitext(b)[0], []).append(b)
        if len(stems) != 1:
            add('文件名不统一（除 meta 外必须同名）', BAD, ' | '.join(f'{k}->{v}' for k, v in stems.items()))
        files = [p for p in files if os.path.splitext(p)[1].lower() in ('.mp4', '.mov', '.mkv', '.blend')]

    if not files:
        sys.exit("没有可检查的文件")

    infos = {os.path.basename(p): info(p) for p in files}
    vids = {k: v for k, v in infos.items() if v and k.lower().endswith(('.mp4', '.mov', '.mkv'))}

    if not vids:
        sys.exit("没有视频文件")

    # --- 单条视频参数 ---
    for name, i in vids.items():
        if i['short'] < 1080:
            add(f'{name} 分辨率', BAD, f"{i['w']}x{i['h']}，短边 {i['short']} < 1080")
        else:
            add(f'{name} 分辨率', OK, f"{i['w']}x{i['h']}（短边 {i['short']}）")
        if i['fps'] < 24:
            add(f'{name} 帧率', BAD, f"{i['fps']:.3f} < 24")
        elif abs(i['fps'] - round(i['fps'])) > 0.001:
            add(f'{name} 帧率', WARN, f"{i['fps']:.3f} 不是整数帧")
        else:
            add(f'{name} 帧率', OK, f"{i['fps']:.0f}fps")
        if i['vcodec'] != 'h264':
            add(f'{name} 编码', BAD if i['vcodec'] not in ('hevc',) else WARN,
                f"{i['vcodec']}（规范 H.264，H.265 可选）")
        else:
            add(f'{name} 编码', OK, 'h264')
        if i['container'] != 'mp4':
            add(f'{name} 封装', BAD, i['container'])
        if i['vbitrate'] < 18_000_000:
            add(f'{name} 码率', BAD, f"{i['vbitrate']/1e6:.1f} Mbps < 18")
        elif i['vbitrate'] < 28_000_000:
            add(f'{name} 码率', WARN, f"{i['vbitrate']/1e6:.1f} Mbps（够线，建议 30）")
        else:
            add(f'{name} 码率', OK, f"{i['vbitrate']/1e6:.1f} Mbps")
        if not i['has_audio']:
            add(f'{name} 音轨', BAD, '没有声音（规范：白模与对比必须带声）')
        else:
            if i['acodec'] != 'aac':
                add(f'{name} 音频编码', WARN, i['acodec'])
            if i['arate'] < 44100:
                add(f'{name} 采样率', BAD, f"{i['arate']} < 44.1k")
            if i['achan'] < 2:
                add(f'{name} 声道', BAD, f"{i['achan']}ch（要立体声）")
            if i['abitrate'] and i['abitrate'] < 300_000:
                add(f'{name} 音频码率', BAD, f"{i['abitrate']/1000:.0f}kbps < 320k")
            else:
                add(f'{name} 音频', OK, f"{i['acodec']} {i['arate']}Hz {i['achan']}ch {i['abitrate']/1000:.0f}kbps")
        if i['dur'] < 5:
            add(f'{name} 时长', BAD, f"{i['dur']:.2f}s < 5s")
        if i['dur'] > 60:
            add(f'{name} 时长', WARN, f"{i['dur']:.2f}s > 60s（规范建议 5–60s）")

    # --- 跨文件一致性 ---
    keys = list(vids)
    fps_set = {round(v['fps'], 3) for v in vids.values()}
    if len(fps_set) > 1:
        add('三条帧率一致', BAD, str(sorted(fps_set)))
    else:
        add('三条帧率一致', OK, f"{fps_set.pop():.3f}")

    durs = {k: v['dur'] for k, v in vids.items()}
    if max(durs.values()) - min(durs.values()) > (1.0 / max(fps_set or {30})):
        add('时长一致', BAD, ' | '.join(f'{k}={v:.3f}s' for k, v in durs.items()))
    else:
        add('时长一致', OK, ' | '.join(f'{k}={v:.3f}s' for k, v in durs.items()))

    frames = {k: v['frames'] for k, v in vids.items()}
    wb = [v for k, v in frames.items() if '白模' in k]
    cmp_ = [v for k, v in frames.items() if '对比' in k]
    if wb and cmp_ and wb[0] != cmp_[0]:
        add('白模/对比总帧数一致', BAD, f"{wb[0]} vs {cmp_[0]}")
    elif wb and cmp_:
        add('白模/对比总帧数一致', OK, str(wb[0]))

    # --- 黑帧 ---
    if not a.skip_black:
        for k, v in vids.items():
            y = black_tail(os.path.join(a.target[0], k) if len(a.target) == 1 and os.path.isdir(a.target[0]) else k)
            if y is None:
                add(f'{k} 片尾黑帧', WARN, '取不到亮度数据，需人工逐帧看片尾')
            else:
                if y < 8:
                    add(f'{k} 片尾黑帧', BAD, f"最后一秒最低亮度 {y:.1f}（疑纯黑）")
                else:
                    add(f'{k} 片尾黑帧', OK, f"最低亮度 {y:.1f}")

    fails = [r for r in rows if r['level'] == BAD]
    if a.json:
        print(json.dumps({'rows': rows, 'fails': len(fails)}, ensure_ascii=False, indent=2))
    else:
        width = max(len(r['check']) for r in rows) + 2
        for r in rows:
            mark = {'PASS': ' ok ', 'FAIL': 'FAIL', 'WARN': 'warn'}[r['level']]
            print(f"[{mark}] {r['check']:<{width}} {r['detail']}")
        print()
        print(f"合计 {len(rows)} 项，硬伤 {len(fails)} 项")
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
