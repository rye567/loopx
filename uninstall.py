#!/usr/bin/env python3
import argparse
import ctypes
import os
import shutil
from pathlib import Path


HOME = Path.home()


def default_bin_dir():
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "LoopX" / "bin"
        return HOME / "AppData" / "Local" / "LoopX" / "bin"
    return HOME / ".local" / "bin"


def remove_path(path):
    if path.is_dir():
        shutil.rmtree(path)
        print(f"remove {path}")
    elif path.exists():
        path.unlink()
        print(f"remove {path}")


def remove_windows_path(bin_dir):
    if os.name != "nt":
        return False
    import winreg

    path_text = str(bin_dir)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            current, value_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            return False
        parts = [part for part in current.split(";") if part]
        filtered = [
            part for part in parts
            if os.path.normcase(os.path.normpath(part)) != os.path.normcase(os.path.normpath(path_text))
        ]
        if len(filtered) == len(parts):
            return False
        winreg.SetValueEx(key, "Path", 0, value_type, ";".join(filtered))

    try:
        hwnd_broadcast = 0xFFFF
        wm_settingchange = 0x001A
        ctypes.windll.user32.SendMessageTimeoutW(hwnd_broadcast, wm_settingchange, 0, "Environment", 0, 5000, None)
    except Exception:
        pass
    return True


def main():
    parser = argparse.ArgumentParser(description="Uninstall LoopX global files.")
    parser.add_argument("--yes", action="store_true", help="Confirm uninstall.")
    args = parser.parse_args()
    if not args.yes:
        raise SystemExit("确认卸载请执行：python uninstall.py --yes")

    bin_dir = Path(os.environ.get("LOOPX_BIN_DIR", default_bin_dir()))
    remove_path(HOME / ".loopx")
    for name in ("loopx-sync", "loopx-sync.cmd", "loopx-sync.ps1"):
        remove_path(bin_dir / name)
    remove_path(HOME / ".codex" / "skills" / "loopx")
    for path in (HOME / ".codex" / "agents").glob("quality-*.toml"):
        remove_path(path)
    remove_path(HOME / ".claude" / "skills" / "loopx")
    for path in (HOME / ".claude" / "agents").glob("quality-*.md"):
        remove_path(path)
    if remove_windows_path(bin_dir):
        print(f"已从用户 PATH 移除：{bin_dir}")
    print("LoopX 已卸载。项目内 AGENTS.md、CLAUDE.md、.codex、.claude 不会被自动删除。")


if __name__ == "__main__":
    main()
