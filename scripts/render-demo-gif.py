#!/usr/bin/env python3
"""Render a terminal-replay GIF of the LoopX LIGHT demo.

The frames are generated with Pillow from the real demo run output, so no
external recorder (asciinema/agg/ffmpeg) is needed. Run:

    python3 scripts/render-demo-gif.py

Output: docs/assets/loopx-demo.gif
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "loopx-demo.gif"

W, H = 980, 620
BG = "#0d1117"
PADDING_X = 24
PADDING_Y = 64
LINE_HEIGHT = 26
TITLE_BAR_H = 40

COLORS = {
    "cmd": "#7ee787",     # commands
    "ok": "#3fb950",      # PASS lines
    "warn": "#d29922",    # NEED_HUMAN / SKIPPED
    "dim": "#8b949e",     # comments
    "text": "#c9d1d9",    # normal output
    "accent": "#58a6ff",  # highlights
}

# Each line: (kind, text). Content is condensed from the real demo run
# (docs/demo.md) so every line matches actual controller output.
LINES = [
    ("cmd", "$ python3 loopx_controller.py init \"Add dark mode toggle\" --run-id demo"),
    ("text", "created run demo"),
    ("text", "mode: LIGHT   recommended mode: LIGHT"),
    ("ok", "environment_check: PASS"),
    ("blank", ""),
    ("cmd", "$ record-stage --stage requirement_interview --status PASS ..."),
    ("warn", "NEED_HUMAN requirement_interview    # human gate"),
    ("text", "next_action: confirm-stage --stage requirement_interview"),
    ("blank", ""),
    ("cmd", "$ confirm-stage --stage requirement_interview ..."),
    ("ok", "PASS confirmed requirement_interview"),
    ("blank", ""),
    ("cmd", "$ record-stage --stage spec_review --status SKIPPED ..."),
    ("warn", "SKIPPED spec_review    # LIGHT mode may skip review gates"),
    ("blank", ""),
    ("cmd", "$ mode demo --select LIGHT"),
    ("text", "mode selected: LIGHT   stage_status: PASS"),
    ("blank", ""),
    ("cmd", "$ advance --to development"),
    ("ok", "PASS advanced to development"),
    ("blank", ""),
    ("cmd", "$ can-write --kind business"),
    ("ok", "PASS business writes unlocked    # writes locked until gates pass"),
    ("blank", ""),
    ("cmd", "$ record-stage development, code_review, test_execution, ..."),
    ("ok", "PASS development    PASS code_review    PASS test_execution"),
    ("ok", "PASS health_gate"),
    ("blank", ""),
    ("cmd", "$ git-gate demo && gate demo"),
    ("ok", "PASS git gate demo"),
    ("ok", "strict validation: PASS"),
    ("blank", ""),
    ("cmd", "$ close demo"),
    ("ok", "PASS close demo    status: PASS"),
    ("accent", "run archived -> docs/loopx/runs/demo/artifacts/close-evidence.json"),
]


def load_font(size=20):
    for path in (
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/Library/Fonts/Courier New.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_title_bar(draw):
    draw.rectangle((0, 0, W, TITLE_BAR_H), fill="#161b22")
    for i, color in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        x = 18 + i * 22
        draw.ellipse((x, 14, x + 12, 26), fill=color)
    draw.text((90, 10), "loopx demo — LIGHT mode", font=FONT_TITLE, fill="#8b949e")


def render_frame(lines):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw_title_bar(draw)
    for i, (kind, text) in enumerate(lines):
        y = PADDING_Y + i * LINE_HEIGHT
        color = COLORS.get(kind, COLORS["text"])
        draw.text((PADDING_X, y), text, font=FONT, fill=color)
    return img


def main():
    frames = []
    durations = []
    visible = []
    for kind, text in LINES:
        if kind == "blank":
            visible.append((kind, text))
            continue
        visible.append((kind, text))
        frames.append(render_frame(visible))
        # Pause longer on meaningful lines so the viewer can read them.
        if kind == "cmd":
            durations.append(900)
        elif kind == "warn":
            durations.append(1400)
        else:
            durations.append(700)
    frames.append(render_frame(visible))
    durations.append(2200)  # hold on the final close result

    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    print(f"wrote {OUT} ({len(frames)} frames, {OUT.stat().st_size / 1024:.0f} KB)")


FONT = load_font(20)
FONT_TITLE = load_font(15)

if __name__ == "__main__":
    main()
