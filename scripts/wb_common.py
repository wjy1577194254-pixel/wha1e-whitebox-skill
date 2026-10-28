# -*- coding: utf-8 -*-
"""
wb_common —— 白模工程公共件
跑法：Blender -b -P your_script.py   （脚本里 import sys; sys.path.append(.../whitebox/lib)）

包含：
  · 语义色板（甲方《配色语义规范》里那四个色 + 参考片里实测的冷暖）
  · 材质 / 相机 / 渲染设置 / 参考帧对位背景板
"""
import bpy
import math
from mathutils import Vector, Euler


# ----------------------------------------------------------------------------
# 色板
# ----------------------------------------------------------------------------
def srgb_to_linear(c):
    """sRGB 0..1 -> 线性 0..1（Blender 的 base_color / light color 都吃线性）"""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexcol(h, alpha=1.0):
    """'#C62828' -> (r,g,b,a) 线性"""
    if isinstance(h, (tuple, list)):
        return tuple(h) + (alpha,) if len(h) == 3 else tuple(h)
    if not isinstance(h, str) or len(h.lstrip('#')) != 6:
        raise ValueError(f"hexcol 要 '#RRGGBB' 或 (r,g,b)，拿到的是 {h!r}")
    h = h.lstrip('#')
    rgb = tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return tuple(srgb_to_linear(c) for c in rgb) + (alpha,)


#: 角色语义色 —— 跨镜头一律用这一张表，不许中途改
PALETTE = {
    'hero':      '#B31E1E',   # 主角     红
    'second':    '#1E40AF',   # 第二角色 蓝
    'third':     '#3E9B1F',   # 第三角色 绿
    'fourth':    '#D4B31A',   # 第四角色 黄
    'fifth':     '#8E44AD',   # 第五角色 紫（备用）
    'sixth':     '#E67E22',   # 第六角色 橙（备用，黄色太亮时换这个）
}

#: 直白别名 —— 按颜色叫也能用
PALETTE.update({
    'red': PALETTE['hero'], 'blue': PALETTE['second'], 'green': PALETTE['third'],
    'yellow': PALETTE['fourth'], 'purple': PALETTE['fifth'], 'orange': PALETTE['sixth'],
})

#: 面罩/胸牌的辅助色 —— 只为了让"正面朝向"一眼看出来，不参与角色区分
ACCENT = {
    'cyan':  '#35C4D8',
    'lime':  '#C6DC8A',
    'sun':   '#F2E14C',
}

#: 场景/道具中性色（不受色板限制，按原片色调走）
NEUTRAL = {
    'wall':    '#B9BEB6',   # 墙 浅灰
    'wall_dk': '#6E756C',   # 背墙 中灰
    'wall_wm': '#8A7F73',   # 暖墙
    'floor':   '#8C8F80',   # 地面
    'floor_dk':'#5E6255',
    'prop':    '#D8DAD2',   # 道具 白
    'prop_dk': '#3A3C38',   # 深色道具（桌面/椅垫）
    'rack':    '#4A5450',   # 金属货架/机房那种暗绿灰
    'green':   '#2E4A2A',   # 参考片里那些墨绿隔板
    'maroon':  '#3E2426',   # 参考片里的暗红墙面
}


def mat(name, color_hex, rough=0.5, metal=0.0, spec=0.35, emit=0.0):
    """建/取一个哑光材质。白模统一 rough≈0.5，不要透明、不要 SSP。"""
    key = f"WB_{name}"
    m = bpy.data.materials.get(key)
    if m is None:
        m = bpy.data.materials.new(key)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    col = hexcol(color_hex) if isinstance(color_hex, str) else color_hex
    bsdf.inputs['Base Color'].default_value = col
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    # 4.x 的 Specular 改名 IOR Level
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = spec
    elif 'Specular' in bsdf.inputs:
        bsdf.inputs['Specular'].default_value = spec
    if emit > 0:
        bsdf.inputs['Emission Color'].default_value = col
        bsdf.inputs['Emission Strength'].default_value = emit
    m.diffuse_color = col          # 视口 solid 模式也显示对色
    return m


# ----------------------------------------------------------------------------
# 相机
# ----------------------------------------------------------------------------
#: 参考片实测画幅 = 2.39:1（1280x536 一半）
ASPECT_239 = 2.39


def make_camera(name='Cam', lens=35.0, aspect=ASPECT_239, sensor=36.0):
    """建相机。sensor_fit=HORIZONTAL，纵向视野由画幅自动推出来。"""
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam_data.sensor_width = sensor
    cam_data.sensor_fit = 'HORIZONTAL'
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.collection.objects.link(cam)
    cam_data.clip_start = 0.05
    cam_data.clip_end = 500.0
    return cam


def look_at(obj, target, up=Vector((0, 0, 1))):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def cam_place(cam, loc, target=None, lens=None, roll=0.0):
    cam.location = Vector(loc)
    if target is not None:
        look_at(cam, target)
    if lens is not None:
        cam.data.lens = lens
    if roll:
        cam.rotation_euler.rotate_axis('Z', roll)


# ----------------------------------------------------------------------------
# 渲染设置
# ----------------------------------------------------------------------------
#: 交付规格常量（来自《参数验收标准》+《渲染与打包规范1020》）
SPEC = {
    'fps': 30,              # 原片若是 24/25 就跟原片，绝不自己改
    'short_side_min': 1080,
    'codec': 'H.264',
    'bitrate_min': '18M',
    'bitrate_rec': '30M',
    'audio': 'AAC 立体声 44.1kHz 320kbps 16/32bit',
}


def setup_render(aspect=ASPECT_239, short_side=536, samples=16, out_dir=None):
    """
    白模渲染设置。short_side 给纵向像素；分辨率缩放用 percentage，方便出低清审核版。
    对照规范：对比版可以 crop 到 30% 出审片，最终打包前改回 100%。
    """
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE_NEXT'
    ee = sc.eevee
    ee.taa_render_samples = samples
    try:
        ee.use_raytracing = False
    except Exception:
        pass
    sc.render.resolution_x = int(round(short_side * aspect))
    sc.render.resolution_y = int(round(short_side))
    sc.render.resolution_percentage = 100
    sc.render.fps = SPEC['fps']
    sc.render.film_transparent = False
    # AgX 是 4.x 默认，白模要压住高光、别爆白
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Punchy'
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    if out_dir:
        sc.render.filepath = out_dir
    return sc


def grade_compositor(lift=0.010, gamma=1.0, gain=1.0, saturation=1.06, contrast_pivot=0.45):
    """
    渲染后的调子。样板片的白模是「暗部抬起来 + 不压死黑」（最暗 20 左右，不是 0），
    直接在渲染里压暗部会得到一片死黑，所以在合成里做：
      ColorBalance(lift/gamma/gain) -> HueSaturation -> Composite
    全部在场景线性空间里做，AgX 之后再出图。
    """
    sc = bpy.context.scene
    sc.use_nodes = True
    nt = sc.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new('CompositorNodeRLayers')
    cb = nt.nodes.new('CompositorNodeColorBalance')
    cb.correction_method = 'LIFT_GAMMA_GAIN'
    cb.lift = (lift, lift, lift * 1.06)
    cb.gamma = (gamma, gamma, gamma)
    cb.gain = (gain, gain, gain)
    hs = nt.nodes.new('CompositorNodeHueSat')
    hs.inputs['Saturation'].default_value = saturation
    out = nt.nodes.new('CompositorNodeComposite')
    nt.links.new(rl.outputs['Image'], cb.inputs['Image'])
    nt.links.new(cb.outputs['Image'], hs.inputs['Image'])
    nt.links.new(hs.outputs['Image'], out.inputs['Image'])
    return [cb, hs]


def add_area_light(name, loc, target, size=3.0, energy=300.0, color=(1, 1, 1)):
    """柔性面光 —— 白模靠 3 点柔光读出体积，别用点光（一票否决里的'灯光异常'多来自硬光闪烁）"""
    d = bpy.data.lights.new(name, 'AREA')
    d.shape = 'RECTANGLE'
    d.size = size
    d.energy = energy
    d.color = color
    ob = bpy.data.objects.new(name, d)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    look_at(ob, target)
    return ob


def world_gradient(top='#FFFFFF', bottom='#E5E5E2', strength=1.0):
    """竖直渐变天幕 —— 比纯白背景有空间感，参考片也是这个套路"""
    w = bpy.context.scene.world or bpy.data.worlds.new('World')
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[0].color = hexcol(bottom)
    ramp.color_ramp.elements[1].color = hexcol(top)
    nt.links.new(tc.outputs['Generated'], sep.inputs['Vector'])
    nt.links.new(sep.outputs['Z'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = strength
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    return w


# ----------------------------------------------------------------------------
# 参考帧对位 —— 把原片一帧贴到相机背景上，照着描
# ----------------------------------------------------------------------------
def add_ref_background(cam, image_path, opacity=1.0, as_render=False):
    """
    相机背景板：Viewport/渲染都能看到原片那一帧，用来对透视、对位置。
    as_render=False 时只影响视口，渲染出图是干净白模。
    """
    img = bpy.data.images.load(image_path, check_existing=True)
    bg = cam.data.background_images.new()
    bg.image = img
    bg.alpha = opacity
    bg.display_depth = 'BACK'
    bg.frame_method = 'FIT'
    cam.data.show_background_images = True
    if not as_render:
        # 让背景只在视口出现：Blender 没有直接开关，用 'FRONT' 深度的做法在渲染里仍会出现，
        # 所以默认把它设为不参与渲染 —— 用 hide_render 做不到，只能靠前端合成。
        pass
    return bg


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures,
                  bpy.data.cameras, bpy.data.lights):
        for b in list(block):
            if b.users == 0:
                block.remove(b)
