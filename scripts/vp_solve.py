#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vp_solve.py —— 用灭点校验/反解机位

为什么：桌子长边一定收敛到「桌长方向的灭点」，而这个灭点永远落在**地平线**上。
把原片里桌子的两条长边量出来、求交点，就得到原片的灭点和地平线高度；
把白模同一处的两条边同样投到画面上、求交点，两边一比就知道机位差在哪：
  · 灭点 x 偏了 → 相机有偏航（yaw）
  · 灭点 y 偏了 → 相机俯仰（pitch）和焦距的组合不对
这一步不需要任何 3D 尺寸假设，所以不会像我上次那样被"场景比例猜错"带偏。

用法：
  # 1) 只求两条线的交点（灭点）
  python3 tools/vp_solve.py --line 180,640,555,445 --line 1095,620,700,440
  # 2) 拿去和 Blender 里的机位比：给相机参数 + 桌子四个角，直接算出我这边的灭点
  python3 tools/vp_solve.py --scene --w 1280 --h 640 --lens 16 \
      --loc 0,-4.05,1.38 --target 0,1.35,1.35 \
      --table 1.7,-2.1,0.86 1.7,3.6,0.86 -1.7,3.6,0.86 -1.7,-2.1,0.86
"""
import argparse
import math
import sys

import numpy as np


def line_from(a, b):
    """两点定一条线，返回齐次坐标 (a,b,c)，满足 ax+by+c=0。"""
    x1, y1 = a
    x2, y2 = b
    return np.array([y1 - y2, x2 - x1, x1 * y2 - x2 * y1], dtype=float)


def intersect(l1, l2):
    p = np.cross(l1, l2)
    if abs(p[2]) < 1e-9:
        return None                      # 平行，灭点在无穷远
    return np.array([p[0] / p[2], p[1] / p[2]])


def fit_line(pts):
    """一堆点最小二乘拟合一条线（总最小二乘，用 SVD）。"""
    P = np.asarray(pts, float)
    c = P.mean(0)
    u, s, vt = np.linalg.svd(P - c)
    d = vt[0]                            # 主方向
    n = np.array([-d[1], d[0]])          # 法向
    return np.array([n[0], n[1], -n @ c])


def project(p3, loc, euler_xyz, lens, w, h, sensor=36.0):
    """按 Blender 的相机约定把世界点投到像素。"""
    rx, ry, rz = [math.radians(v) for v in euler_xyz]
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    R = Rz @ Ry @ Rx
    p = R.T @ (np.asarray(p3, float) - np.asarray(loc, float))   # 世界->相机（R 是 局部->世界）
    if p[2] >= -1e-6:                    # 在相机背后
        return None
    f = lens * w / sensor
    u = w / 2 + f * (p[0] / -p[2])
    v = h / 2 - f * (p[1] / -p[2])
    return np.array([u, v])


def look_at_euler(loc, target):
    """Blender 的 look-at：-Z 指向目标，+Y 朝上。返回 XYZ 欧拉（度）。"""
    d = np.asarray(target, float) - np.asarray(loc, float)
    d = d / np.linalg.norm(d)
    up = np.array([0, 0, 1.0])
    if abs(d @ up) > 0.999:
        up = np.array([0, 1.0, 0])
    right = np.cross(d, up)
    right /= np.linalg.norm(right)
    up2 = np.cross(right, d)
    M = np.column_stack([right, up2, -d])      # 相机局部轴 -> 世界
    # 矩阵转 XYZ 欧拉
    sy = math.sqrt(M[0, 0] ** 2 + M[1, 0] ** 2)
    if sy > 1e-6:
        x = math.atan2(M[2, 1], M[2, 2])
        y = math.atan2(-M[2, 0], sy)
        z = math.atan2(M[1, 0], M[0, 0])
    else:
        x = math.atan2(-M[1, 2], M[1, 1])
        y = math.atan2(-M[2, 0], sy)
        z = 0.0
    return [math.degrees(x), math.degrees(y), math.degrees(z)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--line', action='append', default=[],
                    help='x1,y1,x2,y2（可给多次）')
    ap.add_argument('--scene', action='store_true', help='用相机参数+桌子四角算灭点')
    ap.add_argument('--w', type=int, default=1280)
    ap.add_argument('--h', type=int, default=640)
    ap.add_argument('--lens', type=float, default=16.0)
    ap.add_argument('--loc', default='0,-4.05,1.38')
    ap.add_argument('--target', default='0,1.35,1.35')
    ap.add_argument('--table', default=None,
                    help='12 个数：x1,y1,z1,x2,y2,z2,x3,y3,z3,x4,y4,z4（近左 近右 远右 远左）。'
                         '注意：这样写才不会把负号当参数。')
    a = ap.parse_args()

    if a.scene:
        loc = [float(v) for v in a.loc.split(',')]
        tgt = [float(v) for v in a.target.split(',')]
        eul = look_at_euler(loc, tgt)
        vals = [float(v) for v in a.table.split(',')]
        if len(vals) != 12:
            sys.exit('--table 要正好 12 个数')
        P = [vals[i * 3:i * 3 + 3] for i in range(4)]
        # 角点顺序：0 近左, 1 近右, 2 远右, 3 远左
        proj = [project(c, loc, eul, a.lens, a.w, a.h) for c in P]
        if any(p is None for p in proj):
            sys.exit("有角点在相机背后，检查机位")
        L = fit_line([proj[0], proj[3]])
        R = fit_line([proj[1], proj[2]])
        vp = intersect(L, R)
        print(f"相机欧拉（度）= {[round(v,3) for v in eul]}")
        for i, p in enumerate(proj):
            print(f"  角{i} -> ({p[0]:8.1f}, {p[1]:8.1f})")
        if vp is None:
            print("两条边平行，灭点在无穷远")
        else:
            print(f"桌面长边灭点 = ({vp[0]:.1f}, {vp[1]:.1f})   ← 这个数要和原片对上")
        return 0

    lines = []
    for s in a.line:
        x1, y1, x2, y2 = [float(v) for v in s.split(',')]
        lines.append(line_from((x1, y1), (x2, y2)))
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            vp = intersect(lines[i], lines[j])
            if vp is None:
                print(f"线{i+1} 与 线{j+1} 平行")
            else:
                print(f"线{i+1} × 线{j+1} 灭点 = ({vp[0]:.1f}, {vp[1]:.1f})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
