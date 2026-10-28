#!/bin/bash
set -e
cd "$(dirname "$0")/.."
BL=/Applications/Blender.app/Contents/MacOS/Blender
echo "=== shot1 f1-110 @2160x1080 ==="
$BL -b --factory-startup -P scenes/panda_scene.py -- --shot=1 --anim --res=1080 --tag=anim 2>&1 | tail -2
echo "=== shot2 f111-176 @2160x1080 ==="
$BL -b --factory-startup -P scenes/panda_scene.py -- --shot=2 --anim --res=1080 --tag=anim 2>&1 | tail -2
echo "=== done ==="
ls out/shot1_anim | wc -l
ls out/shot2_anim | wc -l
