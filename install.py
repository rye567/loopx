#!/usr/bin/env python3
import argparse
import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "loopx"
HOME = Path.home()


def default_bin_dir():
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "LoopX" / "bin"
        return HOME / "AppData" / "Local" / "LoopX" / "bin"
    return HOME / ".local" / "bin"


def copy_source(target):
    if target.exists():
        shutil.rmtree(target)
    ignore = shutil.ignore_patterns(".DS_Store", "__pycache__", "*.pyc")
    shutil.copytree(SOURCE, target, ignore=ignore)
    print(f"copy source {SOURCE} -> {target}")


def ensure_windows_path(bin_dir):
    if os.name != "nt":
        return False
    import winreg

    path_text = str(bin_dir)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            current, value_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current, value_type = "", winreg.REG_EXPAND_SZ
        parts = [part for part in current.split(";") if part]
        normalized = {os.path.normcase(os.path.normpath(part)) for part in parts}
        if os.path.normcase(os.path.normpath(path_text)) in normalized:
            return False
        updated = ";".join([*parts, path_text])
        winreg.SetValueEx(key, "Path", 0, value_type, updated)

    try:
        hwnd_broadcast = 0xFFFF
        wm_settingchange = 0x001A
        ctypes.windll.user32.SendMessageTimeoutW(hwnd_broadcast, wm_settingchange, 0, "Environment", 0, 5000, None)
    except Exception:
        pass
    return True


def run_sync(loopx_home, target, cwd):
    sync_script = loopx_home / "tools" / "sync_loopx.py"
    subprocess.check_call([sys.executable, str(sync_script), target], cwd=str(cwd))


def main():
    parser = argparse.ArgumentParser(description="Install LoopX for Codex and Claude Code.")
    parser.add_argument("--project", action="store_true", help="Also generate project adapters in the current directory.")
    args = parser.parse_args()

    if not (SOURCE / "tools" / "sync_loopx.py").exists():
        raise SystemExit(f"缺少 {SOURCE / 'tools' / 'sync_loopx.py'}，安装包不完整。")

    loopx_home = Path(os.environ.get("LOOPX_HOME", HOME / ".loopx"))
    bin_dir = Path(os.environ.get("LOOPX_BIN_DIR", default_bin_dir()))
    bin_dir.mkdir(parents=True, exist_ok=True)

    copy_source(loopx_home)

    env = os.environ.copy()
    env["LOOPX_BIN_DIR"] = str(bin_dir)
    subprocess.check_call([sys.executable, str(loopx_home / "tools" / "sync_loopx.py"), "global"], cwd=str(ROOT), env=env)

    if args.project:
        run_sync(loopx_home, "project", Path.cwd())

    changed_path = ensure_windows_path(bin_dir)
    if os.name == "nt":
        if changed_path:
            print(f"已自动加入用户 PATH：{bin_dir}")
            print("当前终端可能需要重开后才能直接使用 loopx-sync。")
    elif str(bin_dir) not in os.environ.get("PATH", "").split(os.pathsep):
        print(f"提示：{bin_dir} 不在 PATH 中；可直接运行 {bin_dir / 'loopx-sync'}。")

    print("LoopX 安装完成。可运行：loopx-sync doctor")


if __name__ == "__main__":
    main()
