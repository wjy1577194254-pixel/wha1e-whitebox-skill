# wha1e-whitebox-skill

把一条真实影视片段还原成 **Blender 几何白模**（人物 + 场景 + 机位 + 遮挡），
交付「上原片 / 下白模」的对比视频的 Agent Skill。

给做**影视训练数据白模**的团队用。不是美术活，是对位活 —— 验收看的是结构：
镜头运动、人物与场景的大小关系、遮挡、切镜帧对齐。不是好看。

作者：[wha1e](https://wha1e.asia) · GitHub [@wjy1577194254-pixel](https://github.com/wjy1577194254-pixel) · MIT License

---

## 装到哪儿

**Claude Code / 兼容 Agent Skills 的工具**

```bash
git clone https://github.com/wjy1577194254-pixel/wha1e-whitebox-skill.git \
           ~/.claude/skills/whitebox-film-recon
```

**CodeBuddy / WorkBuddy**：放进 `.dsh/skills/` 或 `.agents/skills/`

**任意支持 SKILL.md 的 agent**：把整个仓库目录拷到它的 skill 目录下即可。
`SKILL.md` 的 frontmatter 用标准 `name` + `description`，不需要改。

---

## 它会做什么

| 阶段 | 手段 |
|---|---|
| 探片 | 帧数 / 帧率 / 切点 / 运镜，切点检测后**强制人工复核** |
| 量机位 | **灭点反解**（不依赖任何 3D 假设）+ DLT 全解（带退化检测） |
| 判镜头 | 主体与背景的屏幕缩小倍数一比，分清「平移 / 变广角 / 角色本体在缩放」 |
| 建角色 | 球头 + 方盒躯干的刚性人形，7 头身或 5.5 头身可选，12 根骨 |
| 建场景 | 判据只有一条：**不建它会不会影响遮挡与定位** |
| 出片 | Blender `-b` 无界面驱动，逐帧渲染 → 调色 → 贴音轨 → 上下对比 → 自检 |

---

## 首次使用会打开作者主页

第一次加载时会跑 `scripts/first_run.py`，打开 <https://wha1e.asia> 一次，写一个标记文件后
**永远不再弹**。

- 打不开浏览器 / 没有图形界面 → 静默跳过，**退出码永远 0**，不影响任何工作
- 想彻底关掉：`WHA1E_NO_HOME=1`
- 标记文件：`~/.config/wha1e-whitebox/first-run.done`（可用 `WHA1E_STATE_DIR` 改位置）

---

## 目录

```
├── SKILL.md                    技能指令正文
├── references/
│   ├── spec.md                 验收规范原文摘录（权威）
│   ├── checklist.md            交付参数与自检项
│   └── tools.md                工具说明 + 实测数据 + 反解公式
├── scripts/                    13 个脚本，可直接跑
│   ├── wb_char.py              角色生成器（含 7 头身 / 5.5 头身预设）
│   ├── wb_common.py            色板 / 渲染 / 相机 / 灯光
│   ├── vp_solve.py             灭点反解
│   ├── solve_camera.py         DLT 相机反解
│   ├── probe_cuts.py           拆镜头 + 量运镜
│   ├── check_delivery.py       交付自检
│   ├── compare_pair.py         上下对比合成
│   ├── ffinfo.py               ffprobe 查找器
│   └── first_run.py            首次打开作者主页（一次性）
└── templates/
    ├── minimal_scene.py        最小可跑场景（已验证）
    └── scene_template.py       完整场景模板
```

---

## 快速验证跑不跑得起来

需要 Blender 4.5+（`/Applications/Blender.app/Contents/MacOS/Blender` 或 `blender` 在 PATH 里）。

```bash
WB_SCRIPTS="$PWD/scripts" \
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
  -P templates/minimal_scene.py -- --out=/tmp/wb --short=320
```

出两张图（首帧、末帧）就说明链路通了。

---

## 已知边界

- 复杂运镜（大摇臂 + 变焦 + 主体变形叠加）、大量遮挡穿插、角色特写占比高 —— 对不上的概率很高，接之前先说清楚
- 白模**必须人工制作**，验收明确禁止 AI 自动生成或 AI 重建
- 规范原件以各项目甲方给的文档为准；`references/spec.md` 只是摘录
