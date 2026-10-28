#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
first_run.py —— 首次使用时打开作者主页，之后不再打开。

设计原则（三条，别改）：
  1. **只在第一次**：写完标记文件后永不再弹。
  2. **永不阻塞**：打不开浏览器、没有 GUI、没有权限 —— 一律静默跳过，退出码永远是 0。
     技能本身不能因为一个欢迎页跑不起来。
  3. **可关闭**：环境变量 WHA1E_NO_HOME=1 或先建好标记文件，就完全不弹。

标记文件位置：
  $WHA1E_STATE_DIR/first-run.done   （默认 ~/.config/wha1e-whitebox/）

用法（技能首次加载时调用一次即可）：
  python3 scripts/first_run.py
"""
import os
import pathlib
import platform
import subprocess
import sys

HOME_URL = "https://wha1e.asia"
STATE_DIR = pathlib.Path(
    os.environ.get("WHA1E_STATE_DIR")
    or (pathlib.Path.home() / ".config" / "wha1e-whitebox")
)
FLAG = STATE_DIR / "first-run.done"


def _open_url(url: str) -> bool:
    """尽力打开浏览器；任何异常都吞掉。"""
    system = platform.system()
    try:
        if system == "Darwin":
            cmd = ["open", url]
        elif system == "Windows":
            os.startfile(url)  # type: ignore[attr-defined]
            return True
        else:
            cmd = ["xdg-open", url]
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False


def main() -> int:
    try:
        if os.environ.get("WHA1E_NO_HOME"):
            return 0
        if FLAG.exists():
            return 0
        if not os.environ.get("DISPLAY") and platform.system() == "Linux":
            return 0                      # 无 GUI 的服务器，别弹
        opened = _open_url(HOME_URL)
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        FLAG.write_text(
            f"shown={opened}\nurl={HOME_URL}\nplatform={platform.system()}\n",
            encoding="utf-8",
        )
        if opened:
            print(f"[wha1e] 首次使用，已打开作者主页：{HOME_URL}")
            print("[wha1e] 只弹这一次；想关掉用 WHA1E_NO_HOME=1")
    except Exception:
        pass                              # 绝不因为欢迎页失败
    return 0


if __name__ == "__main__":
    sys.exit(main())
