#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
minimal_scene.py —— 最小可跑的白模场景（已验证）

  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      -P minimal_scene.py -- --out=/tmp/wb --short=320

这是起点，不是成品。改这三处就能对上一条新片子：
  ① CAST / 角色的位置、身高、头身比、颜色
  ② SET  / 场景（只建"影响遮挡和定位"的物体）
  ③ SHOT / 机位关键帧
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get('WB_SCRIPTS', os.path.join(HERE, '..', 'scripts')))

import bpy                       # noqa: E402
import wb_common as C            # noqa: E402
import wb_char as CH             # noqa: E402
import wb_prim as P              # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--out', default='/tmp/wb')
ap.add_argument('--short', type=int, default=320, help='渲染短边，测试用 320，交付用 1080')
ap.add_argument('--samples', type=int, default=8)
a, _ = ap.parse_known_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

# ---------------------------------------------------------------- 场景
C.clear_scene()
C.setup_render(short_side=a.short, samples=a.samples)
C.world_gradient('#A9C8D2', '#8E9C8C', strength=0.95)

m_ground = C.mat('ground', '#6B6B6B')
m_prop = C.mat('prop', '#3A3A3A')

# 地面 + 桌子。判据：它影响遮挡/定位就建，纯花纹不建。
P.box('ground', 0, 0, -0.05, 12, 12, 0.1, m_ground)
P.box('table', 0, 1.2, 0.45, 2.2, 1.0, 0.9, m_prop)
# 桌沿是"结构件"不是花纹 —— 有它才读得出是桌子而不是地面
P.box('table_rim', 0, 0.7, 0.92, 2.2, 0.08, 0.06, C.mat('rim', '#D4B31A'))

# ---------------------------------------------------------------- 角色
# 一条片子里所有角色必须同一档 proportion：
#   'realistic' 7 头身（写实题材）／'stylized' 5.5-5.9（动画）／'chibi' 4
PROP = 'realistic'
CAST = [
    # name, color_key, accent, height, location
    ('po',   'hero',   'cyan', 1.74, (0.0, -1.0, 0.0)),
    ('mate', 'second', 'lime', 1.70, (-1.2, 1.2, 0.0)),
    ('other','third',  'cyan', 1.68, (1.2, 1.2, 0.0)),
]
rigs = {}
for name, col, acc, h, loc in CAST:
    rigs[name], _ = CH.build_character(name, col, acc, height=h,
                                       proportion=PROP, location=loc)

# 主角背对镜头（面罩/胸牌看不见 = 背对），其余人转向他
import math                                       # noqa: E402
for name, rig in rigs.items():
    tgt = (0.0, -1.0, 1.5)
    if name == 'po':
        rig.rotation_euler = (0, 0, math.pi)
    else:
        d = (tgt[0] - rig.location.x, tgt[1] - rig.location.y)
        rig.rotation_euler = (0, 0, math.atan2(d[0], -d[1]))

# ---------------------------------------------------------------- 动作
# 每帧都要有动作，否则判「镜头后段人物静止」。这里用呼吸 + 错峰抬手。
FRAMES = 48
for f in range(1, FRAMES + 1):
    t = (f - 1) / 24.0
    for i, (name, rig) in enumerate(rigs.items()):
        ph = i * 1.9
        gest = 14.0 * max(0.0, math.sin(t * 0.9 + ph))
        CH.apply_pose(rig, {
            'spine': {'pitch': 2.0 + 1.2 * math.sin(t * 1.7 + ph)},
            'head':  {'pitch': -2.0 + 1.0 * math.sin(t * 1.3 + ph),
                      'yaw': 4.0 * math.sin(t * 0.7 + ph)},
            'upperarm.L': {'pitch': gest, 'roll': 2.0},
            'forearm.L':  {'pitch': gest * 0.6},
        })
        CH.insert_pose_key(rig, f)

# ---------------------------------------------------------------- 机位
# (frame, loc, target, lens)。广角就**固定**一颗超广角，别做焦距动画。
SHOT = [
    (1,         (0.0, -4.6, 1.62), (0.0, 0.6, 1.30), 18.0),
    (FRAMES,    (0.0, -3.9, 1.58), (0.0, 0.6, 1.34), 18.0),
]
cam = C.make_camera('Cam', lens=SHOT[0][3])
bpy.context.scene.camera = cam
for f, loc, tgt, lens in SHOT:
    C.cam_place(cam, loc, tgt, lens=lens)
    cam.keyframe_insert('location', frame=f)
    cam.keyframe_insert('rotation_euler', frame=f)
    cam.data.keyframe_insert('lens', frame=f)

C.add_area_light('key', (-6, -4, 8), (0, 1, 1), size=8, energy=3000)
C.add_area_light('fill', (6, -2, 4), (0, 1, 1), size=10, energy=900)

# ---------------------------------------------------------------- 出图
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, FRAMES
os.makedirs(a.out, exist_ok=True)
for f in (1, FRAMES):
    sc.frame_set(f)
    sc.render.filepath = os.path.join(a.out, f'f_{f:04d}.png')
    bpy.ops.render.render(write_still=True)
    print('WROTE', sc.render.filepath)
print('OK 帧数', FRAMES, '短边', a.short)
