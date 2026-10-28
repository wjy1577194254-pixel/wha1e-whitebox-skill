# -*- coding: utf-8 -*-
"""
wb_char —— 参考片同款白模角色生成器

造型（逐条对着参考片量的）：
  · 头      = 一个 UV 球，没有五官、没有脖子
  · 面罩    = 球面上贴一条横带（真几何，随头一起转）
  · 躯干    = 一个带锥度、倒了小角的方盒
  · 胸牌    = 胸前一薄片矩形（同样随躯干转）
  · 四肢    = 每节一个刚性方盒，关节处留缝、不做蒙皮变形
  · 材质    = 哑光塑料，rough≈0.5，不透明

用法：
    import sys; sys.path.append('/.../whitebox/lib')
    import wb_common as C, wb_char as CH
    C.clear_scene()
    rig, body = CH.build_character('hero', color_key='hero')
    CH.apply_pose(rig, {'spine': {'pitch': 6}, 'thigh.L': {'pitch': 25}})
"""
import bpy
import bmesh
import math
from mathutils import Vector, Matrix, Euler

import wb_common as C

#: 头身比预设 —— 验收标准原文：
#:   「写实（接近真人解剖，约 7 头身）占比不低于 30%」「比例非写实占比不得超过 20%」
#: 头直径 = 1 / 头身数。选错档会被判「头部比例异常」。
PROPORTIONS = {
    'realistic': 0.143,   # 7 头身，真人解剖比例
    'stylized':  0.182,   # 5.5-5.9 头身，动画/卡通片
    'chibi':     0.250,   # 4 头身，极少数夸张角色（慎用）
}

#: 默认比例（相对身高的倍数），改这里就能改体型
PROP = {
    'head_d':      0.182,   # 头直径 / 身高   -> 5.9 头身（参考片就是这么大的头）
    'torso_top':   0.830,
    'torso_bot':   0.465,
    'shoulder_w':  0.226,
    'torso_depth': 0.150,
    'hips_w':      0.150,
    'hips_d':      0.128,
    'hips_top':    0.520,
    'hips_bot':    0.455,
    'arm_x':       0.112,
    'elbow_z':     0.660,
    'wrist_z':     0.500,
    'arm_w':       0.066,
    'arm_d':       0.072,
    'forearm_w':   0.058,
    'hand_w':      0.052,
    'hand_l':      0.052,
    'hip_x':       0.052,
    'knee_z':      0.300,
    'ankle_z':     0.068,
    'thigh_w':     0.090,
    'shin_w':      0.076,
    'foot_w':      0.074,
    'foot_l':      0.135,
    'foot_h':      0.044,
    'bevel':       0.0050,
    'visor':       (48.0, 7.2),    # 面罩半张角（方位°, 仰俯°）
    'plate':       (0.50, 0.17),   # 胸牌 宽/胸宽, 高/躯干高
}

#: 物种剪影 —— 光靠颜色分不出野猪和鬣狗，必须靠耳朵/嘴/冠。
#: 尺寸都以「头直径」为单位；ears 是 (dx, dz, r)，muzzle 是 (w, h, depth)。
SPECIES = {
    'human':     dict(ears=[], muzzle=None),
    'panda':     dict(ears=[(-0.33, 0.30, 0.24), (0.33, 0.30, 0.24)], muzzle=(0.44, 0.26, 0.18), round=True),
    'bear':      dict(ears=[(-0.35, 0.33, 0.21), (0.35, 0.33, 0.21)], muzzle=(0.48, 0.30, 0.22), round=True),
    'boar':      dict(ears=[(-0.36, 0.32, 0.17), (0.36, 0.32, 0.17)], muzzle=(0.40, 0.24, 0.32), tusk=True),
    'badger':    dict(ears=[(-0.37, 0.27, 0.15), (0.37, 0.27, 0.15)], muzzle=(0.38, 0.22, 0.28)),
    'hyena':     dict(ears=[(-0.30, 0.44, 0.15), (0.30, 0.44, 0.15)], muzzle=(0.34, 0.20, 0.26)),
    'toad':      dict(ears=[], muzzle=(0.78, 0.22, 0.14), eyes=[(-0.34, 0.16, 0.19), (0.34, 0.16, 0.19)]),
    'chameleon': dict(ears=[], muzzle=(0.30, 0.18, 0.16), eyes=[(-0.42, 0.02, 0.22), (0.42, 0.02, 0.22)], crest=True),
}

#: 骨骼（相对身高），格式 name, head, tail, parent
BONES = [
    ('root',       (0, 0, 0.000),        (0, 0, 0.100),          None),
    ('hips',       (0, 0, 0.455),        (0, 0, 0.560),          'root'),
    ('spine',      (0, 0, 0.560),        (0, 0, 0.700),          'hips'),
    ('chest',      (0, 0, 0.700),        (0, 0, 0.828),          'spine'),
    ('head',       (0, 0, 0.828),        (0, 0, 1.000),          'chest'),
    ('shoulder.L', (0.035, 0, 0.800),    (0.115, 0, 0.800),      'chest'),
    ('upperarm.L', (0.115, 0, 0.800),    (0.120, 0, 0.635),      'shoulder.L'),
    ('forearm.L',  (0.120, 0, 0.635),    (0.122, 0, 0.470),      'upperarm.L'),
    ('hand.L',     (0.122, 0, 0.470),    (0.122, 0, 0.415),      'forearm.L'),
    ('thigh.L',    (0.055, 0, 0.500),    (0.060, 0, 0.285),      'hips'),
    ('shin.L',     (0.060, 0, 0.285),    (0.062, 0, 0.065),      'thigh.L'),
    ('foot.L',     (0.062, 0, 0.065),    (0.062, -0.135, 0.028), 'shin.L'),
]

#: 部件名 -> 骨骼名
PART_BONE = {
    'head': 'head', 'visor': 'head', 'torso': 'chest', 'plate': 'chest',
    'hips': 'hips', 'upperarm': None, 'forearm': None, 'hand': None,
    'thigh': None, 'shin': None, 'foot': None,
}


# ----------------------------------------------------------------------------
# 基础图元
# ----------------------------------------------------------------------------
def _link(ob):
    bpy.context.collection.objects.link(ob)
    return ob


def _box(name, center, size, taper=1.0, material=None):
    w, d, h = size
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        k = taper if v.co.z < 0 else 1.0
        v.co.x *= w * k
        v.co.y *= d * k
        v.co.z *= h
    bm.to_mesh(me)
    bm.free()
    ob = _link(bpy.data.objects.new(name, me))
    ob.location = Vector(center)
    if material:
        ob.data.materials.append(material)
    return ob


def _limb(name, a, b, w, d, material, taper=0.95, extend=0.0):
    """a→b 一节方盒，原点在 a 端。extend 让盒子越过 b 端一点，关节处才不裂缝。"""
    a, b = Vector(a), Vector(b)
    dvec = b - a
    length = dvec.length + extend
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        k = taper if v.co.z < 0 else 1.0
        v.co.x *= w * k
        v.co.y *= d * k
        v.co.z = v.co.z * length + length / 2.0
    bm.to_mesh(me)
    bm.free()
    ob = _link(bpy.data.objects.new(name, me))
    ob.location = a
    ob.rotation_euler = dvec.to_track_quat('Z', 'Y').to_euler()
    if material:
        ob.data.materials.append(material)
    return ob


def _sphere(name, center, radius, material, segs=32, rings=16):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=radius)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    ob = _link(bpy.data.objects.new(name, me))
    ob.location = Vector(center)
    if material:
        ob.data.materials.append(material)
    return ob


def _sphere_patch(name, center, radius, az_deg, el_deg, material=None,
                  inset=0.004, thick=0.007, tilt_deg=0.0, nu=20, nv=4):
    """球面上的一块矩形带（面罩）。以 -Y 为正前方。"""
    az, el = math.radians(az_deg), math.radians(el_deg)
    r0 = radius + inset
    bm = bmesh.new()
    grid = []
    for j in range(nv + 1):
        row = []
        for i in range(nu + 1):
            u = -1.0 + 2.0 * i / nu
            v = -1.0 + 2.0 * j / nv
            a, e = u * az, v * el
            row.append(bm.verts.new(Vector((math.sin(a) * math.cos(e),
                                            -math.cos(a) * math.cos(e),
                                            math.sin(e))) * r0))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    bm.normal_update()
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = _link(bpy.data.objects.new(name, me))
    ob.location = Vector(center)
    if tilt_deg:
        ob.rotation_euler = Euler((0.0, 0.0, math.radians(tilt_deg)))
    if material:
        ob.data.materials.append(material)
    md = ob.modifiers.new('solid', 'SOLIDIFY')
    md.thickness = thick
    md.offset = 0.0
    md.use_even_offset = True
    return ob


# ----------------------------------------------------------------------------
def _mirror(n):
    return n[:-2] + '.R' if n.endswith('.L') else n


def build_rig(name, H, prop=None, bone_scale=1.0):
    P = dict(PROP)
    if prop:
        P.update(prop)
    ad = bpy.data.armatures.new(name + '_arm')
    rig = _link(bpy.data.objects.new(name + '_rig', ad))
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    eb = ad.edit_bones

    def add(bn, h, t, parent):
        b = eb.new(bn)
        b.head = Vector((h[0], h[1], h[2])) * H
        b.tail = Vector((t[0], t[1], t[2])) * H
        if parent and parent in eb:
            b.parent = eb[parent]
        return b

    for bn, h, t, par in BONES:
        add(bn, h, t, par)
        if bn.endswith('.L'):
            add(_mirror(bn), (-h[0], h[1], h[2]), (-t[0], t[1], t[2]),
                _mirror(par) if par and par.endswith('.L') else par)
    # roll：让"世界轴"换算稳定（apply_pose 自己会换算，这里只是让手工摆骨头也顺手）
    for b in eb:
        b.align_roll(Vector((0, 1, 0)))
    bpy.ops.object.mode_set(mode='OBJECT')
    return rig


def build_body(name, color_key, accent_key, H, P, bevels=True, species='human'):
    body_hex = C.PALETTE.get(color_key, color_key)
    acc_hex = C.ACCENT.get(accent_key, accent_key)
    m_body = C.mat(f'char_{color_key}', body_hex, rough=0.52, spec=0.30)
    m_acc = C.mat(f'char_{color_key}_acc', acc_hex, rough=0.40, spec=0.45)

    parts = []          # (obj, bone)

    hd = P['head_d'] * H
    head_c = Vector((0, 0, H - hd / 2.0))
    parts.append((_sphere(f'{name}_head', head_c, hd / 2.0, m_body), 'head'))
    parts.append((_sphere_patch(f'{name}_visor', head_c, hd / 2.0,
                                P['visor'][0], P['visor'][1], material=m_acc), 'head'))

    tw, td = P['shoulder_w'] * H, P['torso_depth'] * H
    ttop, tbot = P['torso_top'] * H, P['torso_bot'] * H
    parts.append((_box(f'{name}_torso', (0, 0, (ttop + tbot) / 2.0),
                       (tw, td, ttop - tbot), taper=0.72, material=m_body), 'chest'))

    pw = P['plate'][0] * tw
    ph = P['plate'][1] * (ttop - tbot)
    pz = tbot + 0.70 * (ttop - tbot)
    parts.append((_box(f'{name}_plate', (0, -td / 2.0 - 0.002, pz),
                       (pw, 0.010, ph), material=m_acc), 'chest'))

    # ---- 物种剪影：耳朵 / 嘴 / 眼 / 冠，全部挂在头骨上 ----
    sp = SPECIES.get(species, SPECIES['human'])
    for (dx, dz, r) in sp.get('ears', []):
        ear = _sphere(f'{name}_ear{dx:+.2f}', head_c + Vector((dx * hd, 0.02 * hd, dz * hd)),
                      r * hd, m_body, segs=16, rings=10)
        ear.scale = (1.0, 0.55, 1.15)
        parts.append((ear, 'head'))
    for (dx, dz, r) in sp.get('eyes', []):
        parts.append((_sphere(f'{name}_eye{dx:+.2f}', head_c + Vector((dx * hd, -0.34 * hd, dz * hd)),
                              r * hd, m_acc, segs=16, rings=10), 'head'))
    mz = sp.get('muzzle')
    if mz:
        mw, mh, md = mz[0] * hd, mz[1] * hd, mz[2] * hd
        parts.append((_box(f'{name}_muzzle',
                           head_c + Vector((0, -(hd * 0.50 + md * 0.34), -hd * 0.12)),
                           (mw, md, mh), material=m_body), 'head'))
    if sp.get('tusk'):
        for sx2 in (-1, 1):
            parts.append((_box(f'{name}_tusk{sx2:+.1f}',
                               head_c + Vector((sx2 * hd * 0.30, -(hd * 0.50 + mz[2] * hd * 0.75), -hd * 0.22)),
                               (0.10 * hd, 0.10 * hd, 0.30 * hd), material=m_body), 'head'))
    if sp.get('crest'):
        parts.append((_sphere(f'{name}_crest', head_c + Vector((0, 0.10 * hd, 0.62 * hd)),
                              0.34 * hd, m_body, segs=12, rings=8), 'head'))

    for s in ('L', 'R'):
        sx = 1.0 if s == 'L' else -1.0
        ax = P['arm_x'] * H * sx
        parts.append((_limb(f'{name}_upperarm.{s}', (ax, 0, 0.800 * H), (ax, 0, P['elbow_z'] * H),
                            P['arm_w'] * H, P['arm_d'] * H, m_body,
                            extend=P['arm_w'] * H * 0.55), f'upperarm.{s}'))
        parts.append((_limb(f'{name}_forearm.{s}', (ax, 0, P['elbow_z'] * H), (ax, 0, P['wrist_z'] * H),
                            P['forearm_w'] * H, P['forearm_w'] * H, m_body,
                            extend=P['forearm_w'] * H * 0.55), f'forearm.{s}'))
        parts.append((_limb(f'{name}_hand.{s}', (ax, 0, P['wrist_z'] * H),
                            (ax, 0, (P['wrist_z'] - P['hand_l']) * H),
                            P['hand_w'] * H, P['hand_w'] * 1.2 * H, m_body), f'hand.{s}'))
        hx = P['hip_x'] * H * sx
        kx = P['hip_x'] * 1.09 * H * sx
        parts.append((_limb(f'{name}_thigh.{s}', (hx, 0, 0.500 * H), (kx, 0, P['knee_z'] * H),
                            P['thigh_w'] * H, P['thigh_w'] * 1.02 * H, m_body,
                            extend=P['thigh_w'] * H * 0.55), f'thigh.{s}'))
        parts.append((_limb(f'{name}_shin.{s}', (kx, 0, P['knee_z'] * H), (kx, 0, P['ankle_z'] * H),
                            P['shin_w'] * H, P['shin_w'] * 0.98 * H, m_body,
                            extend=P['shin_w'] * H * 0.55), f'shin.{s}'))
        fz = P['ankle_z'] * 0.5 * H
        parts.append((_limb(f'{name}_foot.{s}', (kx, 0.030 * H, fz),
                            (kx, 0.030 * H - P['foot_l'] * H, fz),
                            P['foot_w'] * H, P['ankle_z'] * H, m_body), f'foot.{s}'))

    if bevels:
        for ob, _ in parts:
            if ob.name.endswith('_visor'):
                continue
            md = ob.modifiers.new('bev', 'BEVEL')
            md.width = P['bevel'] * H
            md.segments = 2
            md.limit_method = 'ANGLE'
            md.angle_limit = math.radians(40)

    # 每个部件一个顶点组（刚性 100% 权重），合并后关节处不会塌陷 —— 正是参考片的硬切块感
    for ob, bone in parts:
        vg = ob.vertex_groups.new(name=bone)
        vg.add(range(len(ob.data.vertices)), 1.0, 'REPLACE')

    bpy.ops.object.select_all(action='DESELECT')
    for ob, _ in parts:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = parts[0][0]
    bpy.ops.object.convert(target='MESH')     # 烘掉 bevel / solidify

    bpy.ops.object.select_all(action='DESELECT')
    for ob, _ in parts:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = parts[0][0]
    bpy.ops.object.join()
    body = bpy.context.view_layer.objects.active
    body.name = name + '_body'
    body.data.name = name + '_body'
    return body


def build_character(name='hero', color_key='hero', accent_key='cyan',
                    height=1.75, prop=None, bevels=True, location=(0, 0, 0),
                    species='human', proportion=None):
    """造一个白模角色，返回 (rig, body)。rig 是骨架根物体，body 是网格。

    proportion: 'realistic'(7 头身) / 'stylized'(5.5-5.9) / 'chibi'(4)。
    一条片子里所有角色的 proportion 必须一致 —— 验收标准要求「角色精度/比例/风格
    跨镜头统一」，混用会被判不合格。
    """
    P = dict(PROP)
    if proportion:
        if proportion not in PROPORTIONS:
            raise ValueError(f"未知头身比 {proportion!r}，可选 {list(PROPORTIONS)}")
        P['head_d'] = PROPORTIONS[proportion]
    if prop:
        P.update(prop)
    H = height
    rig = build_rig(name, H, P)
    body = build_body(name, color_key, accent_key, H, P, bevels=bevels, species=species)

    md = body.modifiers.new('Armature', 'ARMATURE')
    md.object = rig
    md.use_vertex_groups = True
    body.parent = rig
    rig.location = Vector(location)
    return rig, body


# ----------------------------------------------------------------------------
def apply_pose(rig, spec):
    """
    spec = {'spine': {'pitch': 6, 'yaw': 0, 'roll': 0}, ...}
      pitch > 0 = 前倾（往角色正前方 -Y 倒）
      yaw   > 0 = 向左转（绕世界 Z，俯视逆时针）
      roll  > 0 = 向右侧倾（绕世界 Y，右手法则）
    全部按世界坐标轴理解，不折腾骨骼局部轴。
    """
    for bone, ang in spec.items():
        pb = rig.pose.bones.get(bone)
        if pb is None:
            continue
        p = math.radians(ang.get('pitch', 0.0))
        y = math.radians(ang.get('yaw', 0.0))
        r = math.radians(-ang.get('roll', 0.0))
        R = Euler((p, r, y), 'XYZ').to_matrix()
        M = pb.bone.matrix_local.to_3x3()
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (M.inverted() @ R @ M).to_quaternion()


def reset_pose(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)


def insert_pose_key(rig, frame, spec=None, loc=None):
    """在指定帧打关键帧（spec 为 None 就只打当前姿态）。"""
    if spec is not None:
        reset_pose(rig)
        apply_pose(rig, spec)
    bpy.context.scene.frame_set(frame)
    for pb in rig.pose.bones:
        pb.keyframe_insert('rotation_quaternion', frame=frame)
        pb.keyframe_insert('location', frame=frame)
    if loc is not None:
        rig.location = Vector(loc)
        rig.keyframe_insert('location', frame=frame)
