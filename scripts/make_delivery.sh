#!/bin/bash
# 序列 -> 调色 -> 白模.mp4 -> 对比.mp4 -> 自检
set -e
cd "$(dirname "$0")/.."
FF=../.tools/bin/ffmpeg
PY=/Users/wangjingyu/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
SRC="/Users/wangjingyu/Downloads/白模要求/3a972614820c8f414aa60c4c86d143ab_raw.mp4"
NAME=3a972614820c8f414aa60c4c86d143ab
OUT=../delivery/$NAME
mkdir -p "$OUT"

# 样板片的白模是「暗部抬到 0.078、中间调压下来、高光保住」的胶片调子。
# 实测：不加这条中位 91/最暗 5、饱和 30，样板是 83/20、饱和 59；
#       加完之后中位 82/最暗 19/饱和 51，基本对上。
GRADE="curves=all='0/0.075 0.36/0.325 0.51/0.59 0.80/0.85 1/1',eq=saturation=1.5"

echo "--- 1) 两段序列 调色 -> 无声白模"
$FF -v error -y -framerate 24 -i out/shot1_anim/f_%04d.png -vf "$GRADE,setsar=1" \
    -c:v libx264 -preset slow -profile:v high -crf 14 -pix_fmt yuv420p /tmp/wb_part1.mp4
$FF -v error -y -framerate 24 -start_number 111 -i out/shot2_anim/f_%04d.png -vf "$GRADE,setsar=1" \
    -c:v libx264 -preset slow -profile:v high -crf 14 -pix_fmt yuv420p /tmp/wb_part2.mp4
printf "file '/tmp/wb_part1.mp4'\nfile '/tmp/wb_part2.mp4'\n" > /tmp/wb_concat.txt
$FF -v error -y -f concat -safe 0 -i /tmp/wb_concat.txt -c copy /tmp/wb_silent.mp4

echo "--- 2) 贴原片音轨 -> 白模.mp4（30Mbps / AAC 320k）"
$FF -v error -y -i /tmp/wb_silent.mp4 -i "$SRC" -map 0:v:0 -map 1:a:0 \
    -c:v libx264 -preset slow -profile:v high -level 4.2 -b:v 30M -maxrate 30M -bufsize 60M \
    -pix_fmt yuv420p -g 48 -r 24 -c:a aac_at -b:a 320k -ar 48000 -ac 2 \
    -shortest -movflags +faststart "$OUT/${NAME}白模.mp4"

echo "--- 3) 上原片 / 下白模 -> 对比.mp4"
$PY tools/compare_pair.py "$SRC" "$OUT/${NAME}白模.mp4" -o "$OUT/${NAME}对比.mp4" --width 2160

echo "--- 4) 原片进包"
cp "$SRC" "$OUT/${NAME}.mp4"

echo "--- 5) blend（以用户手工调过的版本为准，不再从脚本重生成）"
USER_BLEND="$HOME/Desktop/白模_试做片.blend"
if [ -f "$USER_BLEND" ]; then
    cp "$USER_BLEND" "$OUT/${NAME}.blend"
    echo "    用用户版: $USER_BLEND"
else
    $PY - <<'PYBLEND'
import subprocess
BL = "/Applications/Blender.app/Contents/MacOS/Blender"
for s in (1, 2):
    subprocess.run([BL, '-b', '--factory-startup', '-P', 'scenes/panda_scene.py', '--',
                    f'--shot={s}', '--frames=1', '--res=270', '--tag=BL',
                    f'--save-blend=/tmp/blend/s{s}.blend'], check=True,
                   capture_output=True)
subprocess.run([BL, '-b', '--factory-startup', '-P', '/tmp/merge_blend.py', '--',
                '/tmp/blend/s1.blend', '/tmp/blend/s2.blend',
                '../delivery/3a972614820c8f414aa60c4c86d143ab/3a972614820c8f414aa60c4c86d143ab.blend'],
               check=True, capture_output=True)
PYBLEND
fi

rm -f "$OUT"/*.blend1

echo "--- 6) 自检"
$PY tools/check_delivery.py "$OUT" || true
ls -la "$OUT"
