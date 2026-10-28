# -*- coding: utf-8 -*-
"""
panda_scene.py —— 素材 3a9726… 的白模场景（Kung Fu Panda 4 石台场景）

片子：4320x2160 / 24fps / 176 帧 / 7.33s / 两个镜头
  镜1  f1-110  (0.00-4.58s)  石台，镜头从主角背后一路后拉上升
  镜2  f111-176 (4.63-7.33s)  大台阶，变色龙坐轿，两个蟾蜍力士，背景巨型石面具

跑法：
  Blender -b --factory-startup -P scenes/panda_scene.py -- --shot 1 --frames 1 55 110
  Blender -b --factory-startup -P scenes/panda_scene.py -- --shot 1 --anim          # 全片
"""
import sys
import os
import math
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.append(os.path.join(ROOT, 'lib'))

import bpy
from mathutils import Vector, Euler
import wb_common as C
import wb_char as CH
sys.path.insert(0, HERE)
from wb_prim import box, cyl, sphere

# 命令行（Blender 用 -- 后面才是自己的参数）
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--shot', type=int, default=1)
ap.add_argument('--frames', type=int, nargs='*', default=[])
ap.add_argument('--anim', action='store_true')
ap.add_argument('--scale', type=float, default=1.0)
ap.add_argument('--tag', default='v1')
ap.add_argument('--res', type=int, default=1080, help='渲染短边')
ap.add_argument('--cam', default=None, help='覆盖机位 x,y,z;tx,ty,tz;lens')
ap.add_argument('--save-blend', default=None)
ARGS = ap.parse_args(argv)

FPS = 24
RES_X, RES_Y = 2160, 1080          # 2:1，短边正好 1080

# ---------------------------------------------------------------- 场景尺度
# 单位：米。整场按「桌子 2.1m 宽」这个锚点定，比对着 1280 宽的抽帧量的。
S = dict(
    plat_w=30.0, plat_y0=-18.0, plat_y1=26.0,
    tab_w=2.2, tab_y0=-3.2, tab_y1=3.2, tab_h=0.86, rim=0.09,
    gate_gap=8.0, gate_w=6.0, gate_y=7.0, gate_h=26.0,
)


def build_set():
    m_stone = C.mat('s_plat', '#948B7C', rough=0.92)
    m_stone_d = C.mat('s_plat_d', '#6E665A', rough=0.92)
    m_table = C.mat('s_table', '#2C2825', rough=0.80)
    m_gold = C.mat('s_gold', '#C39A3E', rough=0.40, metal=0.55, spec=0.6)
    m_gate = C.mat('s_gate', '#A87F5F', rough=0.95)
    m_band = C.mat('s_band', '#9C3B2E', rough=0.9)
    m_dark = C.mat('s_dark', '#33302C', rough=0.9)
    m_shrine = C.mat('s_shrine', '#6E7A5E', rough=0.72)

    # 石台
    box('plat', 0, (S['plat_y0'] + S['plat_y1']) / 2, -0.5,
        S['plat_w'] * 2, S['plat_y1'] - S['plat_y0'], 1.0, m_stone)

    # 石台铺装缝：横向每 3m、纵向每 3m 一条细暗线
    for i in range(-9, 10):
        box(f'pave_x{i}', i * 3.0, (S['plat_y0'] + S['plat_y1']) / 2, 0.005,
            0.06, S['plat_y1'] - S['plat_y0'], 0.02, m_stone_d)
    for j in range(-8, 9):
        yy = j * 3.0
        if S['plat_y0'] < yy < S['plat_y1']:
            box(f'pave_y{j}', 0, yy, 0.005, S['plat_w'] * 2, 0.06, 0.02, m_stone_d)

    # 长桌 / 祭台
    tw, ty0, ty1, th = S['tab_w'], S['tab_y0'], S['tab_y1'], S['tab_h']
    box('table', 0, (ty0 + ty1) / 2, th / 2, tw, ty1 - ty0, th, m_table)
    for sx in (-1, 1):
        box('tab_edge', sx * (tw / 2 - 0.05), (ty0 + ty1) / 2, th + 0.02,
            0.07, ty1 - ty0, 0.04, m_gold)
    box('tab_end', 0, ty1 - 0.05, th + 0.02, tw, 0.07, 0.04, m_gold)

    # 桌面：一圈抬高的床沿 + 三道大回纹带（不再用密集横纹，那看着像马路）
    rim = S['rim']
    for sx in (-1, 1):
        box('tab_rim_x', sx * (tw / 2 - 0.09), (ty0 + ty1) / 2, th + rim / 2,
            0.18, ty1 - ty0, rim, m_gold)
    for sy3 in (ty0 + 0.09, ty1 - 0.09):
        box('tab_rim_y', 0, sy3, th + rim / 2, tw, 0.18, rim, m_gold)
    # 桌头龙首（近端那坨带刺的）
    sphere('dragon', 0, ty0 + 0.75, th + 0.10, 0.30, m_table, sz=0.48)
    for a in range(7):
        ang = math.radians(-66 + a * 22)
        box('spike', 0.30 * math.sin(ang), ty0 + 0.75 + 0.30 * math.cos(ang),
            th + 0.14, 0.04, 0.04, 0.22, m_table, rot=(math.radians(30), 0, 0))

    # 两座山门
    for sx in (-1, 1):
        cx = sx * (S['gate_gap'] + S['gate_w'] / 2)
        box(f'gate_{sx}', cx, S['gate_y'], S['gate_h'] / 2,
            S['gate_w'], 7.0, S['gate_h'], m_gate)
        box(f'gate_band_{sx}', cx, S['gate_y'] - 3.5 - 0.05, 12.0,
            S['gate_w'] - 0.5, 0.10, 1.7, m_band)
        box(f'gate_plinth_{sx}', cx, S['gate_y'] - 3.4, 0.55,
            S['gate_w'] + 1.0, 0.8, 1.1, m_stone_d)
        box(f'gate_cap_{sx}', cx, S['gate_y'], 12.6, S['gate_w'] + 0.7, 7.6, 0.5, m_band)
        # 正面浮雕带：上下各一条，中间一排方块
        for bi, bz in ((0, 2.6), (1, 3.4), (2, 4.2), (3, 9.0)):
            box(f'gate_relief{sx}_{bi}', cx, S['gate_y'] - 3.55, bz,
                S['gate_w'] - 0.6, 0.12, 0.42, m_stone_d)
        for ci in range(5):
            box(f'gate_dentil{sx}_{ci}', cx - 2.2 + ci * 1.1, S['gate_y'] - 3.6, 1.1,
                0.55, 0.14, 0.9, m_stone_d)

    # 长矛 / 旗杆
    for sx in (-1, 1):
        for yy, hh in ((6.8, 4.8), (10.6, 5.2)):
            cyl('pole', sx * 7.2, yy, hh / 2, 0.06, hh, m_dark, verts=8)
            box('blade', sx * 7.2, yy, hh + 0.45, 0.05, 0.34, 0.60, m_gold)

    # 两侧远端矮墙
    for sx in (-1, 1):
        box(f'wall_{sx}', sx * 14.0, 6.0, 1.1, 1.2, 40.0, 2.2, m_gate)


def animate_idle(cast):
    """每人一条错峰的微小呼吸/点头曲线，全程不静止。"""
    for i, (nm, r) in enumerate(sorted(cast.items())):
        phase = i * 1.7
        base = {'po': 2.0}.get(nm, 3.0)
        for fr in range(1, 177, 12):
            t = (fr - 1) / 24.0
            amp = 1.6 + (0.9 if nm in ('boar', 'bear') else 0.0)
            pitch = base + amp * math.sin(t * 1.9 + phase)
            yaw = 4.0 * math.sin(t * 1.1 + phase * 2)
            gest = 14 * max(0.0, math.sin(t * 0.9 + phase))   # 隔一阵抬一次手
            CH.apply_pose(r, {'spine': {'pitch': pitch},
                              'chest': {'yaw': yaw * 0.5},
                              'head': {'pitch': -pitch * 0.6, 'yaw': yaw},
                              'upperarm.L': {'pitch': gest, 'roll': 2},
                              'forearm.L': {'pitch': gest * 0.6}})
            bpy.context.scene.frame_set(fr)
            for bn in ('spine', 'chest', 'head', 'upperarm.L', 'forearm.L'):
                pb = r.pose.bones.get(bn)
                if pb:
                    pb.keyframe_insert('rotation_quaternion', frame=fr)


def add_guard(x, y, h=1.35, col='#6E7266'):
    rig, body = CH.build_character(f'guard_{x:.0f}_{y:.0f}', color_key=col,
                                   accent_key='cyan', height=h, location=(x, y, 0), species='human')
    CH.apply_pose(rig, {'upperarm.L': {'pitch': -6}, 'upperarm.R': {'pitch': 40}})
    return rig


def build_cast():
    """石台那一圈人。颜色按语义色板分，体型按片子里的物种调。"""
    cast = {}

    # 主角熊猫（背对镜头，桌头，绿袍 + 高冠）
    rig, _ = CH.build_character('po', color_key='hero', accent_key='cyan',
                                height=1.74, location=(0, -1.9, 0.86))
    # 逆光：他背对镜头、身后是亮天空，所以整体压暗，头几乎成剪影
    m_po = C.mat('char_hero_dark', '#6E1414', rough=0.62, spec=0.18)
    m_po_h = C.mat('char_hero_head', '#4A0E0E', rough=0.70, spec=0.12)
    for slot in rig.children[0].material_slots:
        mm = slot.material
        if mm and mm.name.endswith('_acc'):
            continue
        slot.material = m_po_h if (mm and '_head' in rig.children[0].name) else m_po
    body = rig.children[0]
    for poly in body.data.polygons:
        pass
    # 按材质名替换：头/脸/躯干统一压暗，面罩和胸牌保留亮色（那是朝向标记，必须看得见）
    body.data.materials.clear()
    body.data.materials.append(m_po)
    body.data.materials.append(C.mat('char_hero_acc', C.ACCENT['cyan'], rough=0.40, spec=0.45))

    rig.rotation_euler = (0, 0, math.pi)          # 背对镜头，脸朝向那一圈人
    # 变身：开场是个巨人，一路缩回正常身高。镜头同时后拉，把画面里的大小"锁"住
    # 变身前：巨人站在**地面**上；变身后：正常人站在**桌面**上（桌面高 0.86）。
    # 中间靠镜头的变焦 + 前推把这段高度变化藏住，观众不会发现脚换了地方。
    for fr, k, z in ((1, 1.55, 0.00), (30, 1.42, 0.00), (55, 1.28, 0.30),
                     (85, 1.12, 0.70), (110, 1.00, 0.86)):
        bpy.context.scene.frame_set(fr)
        rig.scale = (k, k, k)
        rig.location = (rig.location.x, rig.location.y, z)
        rig.keyframe_insert('scale', frame=fr)
        rig.keyframe_insert('location', frame=fr)
    CH.apply_pose(rig, {'spine': {'pitch': 2}, 'head': {'pitch': -4}})
    cast['po'] = rig

    # 野猪（左，橄榄袍，圆胖）
    rig, _ = CH.build_character('boar', color_key='yellow', accent_key='cyan', height=2.00,
                                location=(-1.55, -1.55, 0),
                                prop={'shoulder_w': 0.31, 'head_d': 0.21, 'torso_depth': 0.20})
    rig.rotation_euler = (0, 0, math.radians(34))
    CH.apply_pose(rig, {'spine': {'pitch': 4, 'roll': -3},
                        'upperarm.L': {'pitch': 34, 'roll': 14}})
    cast['boar'] = rig

    # 大熊（后中，最大，蓝灰袍）
    rig, _ = CH.build_character('bear', color_key='second', accent_key='lime', height=2.60,
                                location=(0.86, 3.20, 0),
                                prop={'shoulder_w': 0.30, 'head_d': 0.20})
    CH.apply_pose(rig, {'spine': {'pitch': 3},
                        'upperarm.L': {'pitch': 26}, 'upperarm.R': {'pitch': 26}})
    cast['bear'] = rig

    # 鬣狗（右，紫袍，瘦高）
    rig, _ = CH.build_character('hyena', color_key='fifth', accent_key='lime', height=2.20,
                                location=(1.72, 0.28, 0),
                                prop={'shoulder_w': 0.23, 'head_d': 0.17, 'thigh_w': 0.08})
    rig.rotation_euler = (0, 0, math.radians(-34))
    CH.apply_pose(rig, {'spine': {'pitch': 6}, 'head': {'yaw': -10}})
    cast['hyena'] = rig

    # 蜜獾（右前，红袍，矮壮）
    rig, _ = CH.build_character('badger', color_key='green', accent_key='cyan', height=1.62,
                                location=(2.14, 0.30, 0),
                                prop={'shoulder_w': 0.31, 'head_d': 0.22, 'torso_bot': 0.42})
    rig.rotation_euler = (0, 0, math.radians(-46))
    CH.apply_pose(rig, {'spine': {'pitch': 8}, 'upperarm.R': {'pitch': 42}})
    cast['badger'] = rig

    # 朝向桌心，并给一点持续的 Idle 微动 —— 规范里"镜头后段人物静止"是硬伤
    for nm, r in cast.items():
        if nm == 'po':
            continue
        tgt = Vector((0, -2.45, 1.5))   # 看主角；主角在镜头这侧，所以脸朝向镜头
        d = tgt - r.location
        r.rotation_euler = (0, 0, math.atan2(d.x, -d.y))
    animate_idle(cast)

    # 背景卫兵
    for i, (x, y) in enumerate([(-8.6, 1.0), (-8.8, 4.4), (8.6, 1.2), (8.8, 4.8),
                                (-5.6, 7.4), (5.6, 7.4)]):
        add_guard(x, y)
    return cast


# ---------------------------------------------------------------- 相机
def set_camera(cam, loc, target, lens):
    C.cam_place(cam, loc, target, lens)


SHOT1_KEYS = [
    # frame, loc, target, lens
    # 关键：机位要**高过主角的头**（2.4m 以上）再往下看。
    # 只有这样，站得更远的熊才会在画面里比主角的头"更高"，从头顶露出来；
    # 机位低于头就会变成仰拍，熊被主角完全挡住 —— 这是我之前一直调不出来的原因。
    (1,   (0.0, -6.35, 3.05), (0.0, 0.60, 1.55), 30.0),
    (30,  (0.0, -6.05, 2.95), (0.0, 0.62, 1.50), 27.0),
    (55,  (0.0, -5.65, 2.80), (0.0, 0.66, 1.45), 23.0),
    (85,  (0.0, -5.45, 2.72), (0.0, 0.70, 1.42), 20.0),
    (110, (0.0, -5.30, 2.66), (0.0, 0.74, 1.40), 18.0),
]

SHOT2_KEYS = [
    (111, (0.0, -10.2, 2.15), (0.0, 8.0, 5.30), 26.0),
    (176, (0.0, -9.30, 2.20), (0.0, 8.0, 5.45), 26.0),
]


def build_camera(shot):
    cam = C.make_camera('Cam', lens=26.0)
    keys = SHOT1_KEYS if shot == 1 else SHOT2_KEYS
    f0 = keys[0][0]
    for (fr, loc, tgt, lens) in keys:
        bpy.context.scene.frame_set(fr)
        set_camera(cam, loc, tgt, lens)
        cam.keyframe_insert('location', frame=fr)
        cam.keyframe_insert('rotation_euler', frame=fr)
        cam.data.keyframe_insert('lens', frame=fr)
    # 匀速一点，别让 Bezier 在中间冲过头
    if cam.animation_data and cam.animation_data.action:
        for fc in cam.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'
                kp.handle_left_type = 'AUTO_CLAMPED'
                kp.handle_right_type = 'AUTO_CLAMPED'
    bpy.context.scene.frame_set(f0)
    return cam


def setup_lights():
    C.world_gradient('#7FAEC6', '#9AA894', strength=0.90)
    C.add_area_light('key', (-15, -7, 21), (0, 6, 2), size=15.0, energy=9500,
                     color=(1.0, 0.92, 0.80))
    C.add_area_light('fill', (16, -10, 9), (0, 6, 2), size=18.0, energy=2400,
                     color=(0.80, 0.88, 1.0))
    C.add_area_light('rim', (6, 26, 26), (0, 8, 2), size=14.0, energy=5200)


def main():
    C.clear_scene()
    short = ARGS.res
    sc = C.setup_render(aspect=2.0, short_side=short, samples=ARGS.res < 700 and 8 or 16)
    sc.render.fps = FPS
    sc.render.resolution_x = short * 2
    sc.render.resolution_y = short

    if ARGS.shot == 1:
        build_set()
        build_cast()
    else:
        sys.path.insert(0, HERE)
        import panda_shot2 as S2
        S2.build()

    if ARGS.shot == 1:
        setup_lights()
    else:
        C.world_gradient('#6E7C86', '#2A3038', strength=0.55)
        C.add_area_light('k2', (-8, -6, 14), (0, 6, 6), size=12.0, energy=9000)
        C.add_area_light('f2', (9, -10, 4), (0, 6, 5), size=14.0, energy=2200)
        C.add_area_light('r2', (0, 18, 20), (0, 6, 6), size=12.0, energy=6000)
    if ARGS.cam:
        cam = C.make_camera('Cam', lens=26.0)
        loc, tgt, lens = ARGS.cam.split(';')
        loc = [float(v) for v in loc.split(',')]
        tgt = [float(v) for v in tgt.split(',')]
        C.cam_place(cam, loc, tgt, float(lens))
    else:
        cam = build_camera(ARGS.shot)
    sc.camera = cam

    if ARGS.save_blend:
        sc.name = f'SHOT{ARGS.shot}'
        # 交付用的 .blend 要能直接打开就渲：尺寸、帧范围、采样都给对
        sc.render.resolution_x = 2160
        sc.render.resolution_y = 1080
        sc.render.resolution_percentage = 100
        sc.frame_start = 1 if ARGS.shot == 1 else 111
        sc.frame_end = 110 if ARGS.shot == 1 else 176
        sc.eevee.taa_render_samples = 16
        sc.render.fps = 24
        bpy.context.preferences.filepaths.save_version = 0   # 别生成 .blend1 备份
        bpy.ops.wm.save_as_mainfile(filepath=ARGS.save_blend)
        print("SAVED", ARGS.save_blend)

    out = os.path.join(ROOT, 'out', f'shot{ARGS.shot}_{ARGS.tag}')
    os.makedirs(out, exist_ok=True)
    if ARGS.anim:
        sc.frame_start = 1 if ARGS.shot == 1 else 111
        sc.frame_end = 110 if ARGS.shot == 1 else 176
        sc.render.filepath = os.path.join(out, 'f_')
        sc.render.image_settings.file_format = 'PNG'
        bpy.ops.render.render(animation=True)
    else:
        for fr in (ARGS.frames or [1, 55, 110]):
            sc.frame_set(fr)
            sc.render.filepath = os.path.join(out, f'shot{ARGS.shot}_{ARGS.tag}_f{fr:04d}.png')
            bpy.ops.render.render(write_still=True)
            print("WROTE", sc.render.filepath)


main()
