# -*- coding: utf-8 -*-
"""wb_prim —— 白模场景用的三个基础图元（盒子 / 圆柱 / 球）"""
import bpy


def box(name, cx, cy, cz, sx, sy, sz, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, cz), rotation=rot)
    o = bpy.context.object
    o.name = name
    o.scale = (sx, sy, sz)
    o.data.materials.append(mat)
    return o


def cyl(name, cx, cy, cz, r, h, mat, verts=24, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=h,
                                        location=(cx, cy, cz), rotation=rot)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(mat)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def sphere(name, cx, cy, cz, r, mat, segs=24, rings=12, sz=1.0):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segs, ring_count=rings, radius=r,
                                         location=(cx, cy, cz))
    o = bpy.context.object
    o.name = name
    o.scale = (1, 1, sz)
    o.data.materials.append(mat)
    for p in o.data.polygons:
        p.use_smooth = True
    return o
