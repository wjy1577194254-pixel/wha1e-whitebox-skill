#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
solve_camera.py —— 从「3D 点 + 该点在图上的像素位置」反解机位

为什么需要：白模这活最贵的环节就是机位。靠肉眼调一堆参数是在解 7 维非线性方程，
一轮一轮凑，十分钟也未必收敛。只要有 6 个以上能对上号的点（山门内角、桌面四角、
柱子根部……），DLT 一次就能解出投影矩阵，再分解成 焦距 / 旋转 / 位置。

用法：
  python3 tools/solve_camera.py --w 1280 --h 640 --pts marks.json
  marks.json = [{"name":"gate_L_base","p3":[x,y,z], "p2":[u,v]}, ...]

输出：
  · Blender 可直接用的 (location, rotation_euler, lens) —— 位置先按「米」给，场景单位自己换算
  · 重投影误差（每个点差多少像素）—— 这个数就是「对位准不准」的硬指标

原理：x ~ P X，P 是 3x4。每个对应点给两个线性方程，≥6 点就能用 SVD 解出 P；
      P = K [R|t]，K 用 RQ 分解剥出来（用上三角的假设），再取焦距。
"""
import argparse
import json
import math
import sys

import numpy as np


def _rq(M):
    """RQ 分解：M = R @ Q，R 上三角、Q 正交（numpy 标准写法：翻转后做 QR 再翻回来）。"""
    Q, R = np.linalg.qr(np.flipud(M).T)
    R = np.flipud(R.T)
    R = np.fliplr(R)
    Q = Q.T
    Q = np.flipud(Q)
    return R, Q


def dlt(p3, p2, normalize=True):
    """多点 DLT。p3: (N,3)，p2: (N,2)，返回 3x4 投影矩阵。"""
    p3 = np.asarray(p3, dtype=np.float64)
    p2 = np.asarray(p2, dtype=np.float64)
    n = len(p3)
    if n < 6:
        raise SystemExit(f"至少需要 6 个点，现在只有 {n}")

    if normalize:
        c3 = p3.mean(0)
        s3 = np.sqrt(((p3 - c3) ** 2).sum(1).mean())
        s3 = s3 if s3 > 1e-9 else 1.0
        T3 = np.eye(4)
        T3[:3, :3] *= math.sqrt(3) / s3
        T3[:3, 3] = -T3[:3, :3] @ c3
        h3 = np.hstack([p3, np.ones((n, 1))]) @ T3.T
        h3 = h3[:, :3]

        c2 = p2.mean(0)
        s2 = np.sqrt(((p2 - c2) ** 2).sum(1).mean())
        s2 = s2 if s2 > 1e-9 else 1.0
        T2 = np.eye(3)
        T2[:2, :2] *= math.sqrt(2) / s2
        T2[:2, 2] = -T2[:2, :2] @ c2
        h2 = np.hstack([p2, np.ones((n, 1))]) @ T2.T
        h2 = h2[:, :2]
    else:
        T3 = np.eye(4)
        T2 = np.eye(3)
        h3 = p3
        h2 = p2

    A = []
    for (X, Y, Z), (u, v) in zip(h3, h2):
        A.append([X, Y, Z, 1, 0, 0, 0, 0, -u * X, -u * Y, -u * Z, -u])
        A.append([0, 0, 0, 0, X, Y, Z, 1, -v * X, -v * Y, -v * Z, -v])
    A = np.asarray(A)
    _, _, vt = np.linalg.svd(A)
    P = vt[-1].reshape(3, 4)

    if normalize:
        P = np.linalg.inv(T2) @ P @ T3
    return P / np.linalg.norm(P[2, :3])


def decompose(P, w, h):
    """P -> (K, R, C)。假设无偏斜、像素长宽比 1。"""
    M = P[:, :3]
    C = -np.linalg.inv(M) @ P[:, 3]
    K, R = _rq(M)
    # 规范化：K 的对角必须为正
    D = np.diag(np.sign(np.diag(K)))
    K = K @ D
    R = D @ R
    if np.linalg.det(R) < 0:
        K = -K
        R = -R
    K = K / K[2, 2]
    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]
    return K, R, C, (fx, fy, cx, cy)


def to_blender(R, C, fx, w, sensor=36.0):
    """转成 Blender 相机：位置 + 欧拉角 + 焦距(mm)。"""
    # Blender 相机朝 -Z、上为 +Y；相机系里 x 右、y 上、z 后
    Rc = R
    # 转成 Blender 的 (right, up, back) 三轴
    # OpenCV: x 右 / y 下 / z 朝前    Blender: x 右 / y 上 / z 朝后
    right = Rc[0]
    up = -Rc[1]
    back = -Rc[2]
    M = np.column_stack([right, up, back])
    eul = _mat_to_euler_xyz(M)
    lens = fx * sensor / w
    return C, eul, lens


def _mat_to_euler_xyz(M):
    """把 3x3 旋转矩阵转成 Blender 的 XYZ 欧拉（弧度）。"""
    sy = math.sqrt(M[0, 0] ** 2 + M[1, 0] ** 2)
    if sy > 1e-6:
        x = math.atan2(M[2, 1], M[2, 2])
        y = math.atan2(-M[2, 0], sy)
        z = math.atan2(M[1, 0], M[0, 0])
    else:
        x = math.atan2(-M[1, 2], M[1, 1])
        y = math.atan2(-M[2, 0], sy)
        z = 0.0
    return (x, y, z)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pts', required=True)
    ap.add_argument('--w', type=int, required=True, help='图上宽（像素，抽帧后的）')
    ap.add_argument('--h', type=int, required=True)
    ap.add_argument('--sensor', type=float, default=36.0)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    marks = json.load(open(a.pts, encoding='utf-8'))
    p3 = [m['p3'] for m in marks]
    p2 = [m['p2'] for m in marks]

    # 稳健化：一轮轮把重投影最差的点踢掉，直到 RMS 达标或只剩 6 点
    keep = list(range(len(p3)))
    best = None
    while len(keep) >= 6:
        Pk = dlt([p3[i] for i in keep], [p2[i] for i in keep])
        Xk = np.hstack([np.asarray([p3[i] for i in keep], float), np.ones((len(keep), 1))])
        pr = (Pk @ Xk.T).T
        pr = pr[:, :2] / pr[:, 2:3]
        ek = np.linalg.norm(pr - np.asarray([p2[i] for i in keep], float), axis=1)
        rms = float(np.sqrt((ek ** 2).mean()))
        best = (Pk, keep, ek, rms)
        if rms < 8.0:
            break
        worst = keep[int(np.argmax(ek))]
        keep = [i for i in keep if i != worst]
    P, keep, ek, _ = best
    dropped = [i for i in range(len(p3)) if i not in keep]
    if dropped:
        print(f"!! 踢掉了 {len(dropped)} 个对不上的点：" +
              ", ".join(marks[i].get('name', str(i)) for i in dropped))
        p3 = [p3[i] for i in keep]
        p2 = [p2[i] for i in keep]
        marks = [marks[i] for i in keep]
    K, R, C, (fx, fy, cx, cy) = decompose(P, a.w, a.h)

    # 重投影误差
    X = np.hstack([np.asarray(p3, float), np.ones((len(p3), 1))])
    proj = (P @ X.T).T
    proj = proj[:, :2] / proj[:, 2:3]
    err = np.linalg.norm(proj - np.asarray(p2, float), axis=1)

    # 自检：用分解出来的 K/R/C 重建 P，跟 DLT 的 P 比 —— 这一步能抓出分解写错
    P_rec = K @ np.hstack([R, (-R @ C).reshape(3, 1)])
    proj2 = (P_rec @ X.T).T
    proj2 = proj2[:, :2] / proj2[:, 2:3]
    decomp_err = float(np.abs(proj2 - np.asarray(p2, float)).max())

    loc, eul, lens = to_blender(R, C, fx, a.w, a.sensor)
    deg = [math.degrees(v) for v in eul]
    out = {
        'location': [round(float(v), 4) for v in loc],
        'rotation_euler_deg': [round(v, 3) for v in deg],
        'lens_mm': round(float(lens), 2),
        'focal_px': [round(float(fx), 2), round(float(fy), 2)],
        'principal_point': [round(float(cx), 2), round(float(cy), 2)],
        'reproj_px': [round(float(e), 2) for e in err],
        'reproj_rms_px': round(float(np.sqrt((err ** 2).mean())), 3),
        'reproj_max_px': round(float(err.max()), 3),
        'decomp_sanity_px': round(decomp_err, 2),
    }
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"重投影 RMS = {out['reproj_rms_px']} px  最大 = {out['reproj_max_px']} px"
              f"   （K/R/C 自检差 {out['decomp_sanity_px']} px）")
        print(f"  焦距   {out['lens_mm']} mm（{a.w}px 宽 / {a.sensor}mm 传感器）")
        print(f"  位置   {out['location']}")
        print(f"  欧拉角 {out['rotation_euler_deg']} 度")
        print("  逐点：")
        for m, e in zip(marks, err):
            flag = '  ' if e < 6 else ' !'
            print(f"   {flag}{m.get('name', '?'):18s} 误差 {e:6.2f} px")
        if out['reproj_rms_px'] > 8:
            print("\n  !! RMS 偏大：要么 3D 坐标给错了，要么点选歪了。先修最大的那个点。")
    return 0


if __name__ == '__main__':
    sys.exit(main())
