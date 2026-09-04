"""Generate the deterministic README terminal walkthrough.

Install the optional dependency first: pip install -e ".[demo]"
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "lea-demo.gif"
WIDTH, HEIGHT = 1000, 563

BG = "#090d18"
PANEL = "#0e1424"
BORDER = "#303b61"
WHITE = "#f6f7ff"
MUTED = "#9ca7c4"
PURPLE = "#8b7cff"
CYAN = "#63c5ff"
GREEN = "#58d6a9"
YELLOW = "#f3c969"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    windows = Path("C:/Windows/Fonts") / name
    try:
        return ImageFont.truetype(str(windows), size)
    except OSError:
        return ImageFont.truetype("DejaVuSansMono.ttf", size)


MONO = font("consola.ttf", 22)
MONO_BOLD = font("consolab.ttf", 22)
SMALL = font("consola.ttf", 17)
TITLE = font("seguisb.ttf", 22)


def base_frame() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.ellipse((620, -330, 1250, 300), fill="#171a3d")
    draw.rounded_rectangle((28, 24, 972, 539), radius=16, fill=PANEL, outline=BORDER, width=2)
    draw.ellipse((52, 47, 67, 62), fill="#ff6b72")
    draw.ellipse((77, 47, 92, 62), fill=YELLOW)
    draw.ellipse((102, 47, 117, 62), fill=GREEN)
    draw.text((142, 42), "LEA  /  budget-native route", font=TITLE, fill=WHITE)
    draw.line((50, 80, 950, 80), fill=BORDER, width=2)
    return image, draw


def render(command: str, visible: int, *, steer: bool = False, cursor: bool = False) -> Image.Image:
    image, draw = base_frame()
    prompt = "$ " + command + ("_" if cursor else "")
    draw.text((58, 104), prompt, font=MONO_BOLD, fill=WHITE)

    rows = [
        ("classify", "fix · standard · backend", MUTED, WHITE, "local"),
        ("plan", "grok-4.6", PURPLE, WHITE, "$0.036"),
        ("code", "ollama · qwen3-coder:30b", CYAN, WHITE, "$0.000 API"),
        ("review", "claude-sonnet-5", GREEN, WHITE, "$0.034"),
        ("fix", "ollama · qwen3-coder:30b", CYAN, WHITE, "$0.000 API"),
    ]
    y = 165
    for role, model, role_color, model_color, cost in rows[:visible]:
        draw.text((64, y), role.ljust(10), font=MONO, fill=role_color)
        draw.text((230, y), model, font=MONO, fill=model_color)
        draw.text((790, y), cost, font=SMALL, fill=GREEN if "0.000" in cost else MUTED)
        y += 52

    if visible >= len(rows):
        draw.text((64, 443), "API budget", font=SMALL, fill=MUTED)
        draw.rounded_rectangle((230, 448, 770, 464), radius=8, fill="#1d2843")
        draw.rounded_rectangle((230, 448, 304, 464), radius=8, fill=GREEN)
        draw.text((790, 440), "$0.070 / $1.39", font=SMALL, fill=WHITE)
        draw.text((64, 487), "55.7% lower catalog estimate vs one flagship model", font=SMALL, fill=PURPLE)

    if steer:
        draw.rounded_rectangle((49, 389, 949, 520), radius=10, fill="#141c31", outline=PURPLE)
        draw.text((68, 408), "steer > prioritize tests before refactoring", font=MONO_BOLD, fill=YELLOW)
        draw.text((68, 459), "active request cancelled  ·  next turn starts now", font=MONO, fill=GREEN)
    return image


def main() -> None:
    command = 'lea route --budget 10cny "Refactor the auth cache"'
    # Lead with the complete value proposition so static/slow previews are useful.
    frames: list[Image.Image] = [render(command, 5)]
    durations: list[int] = [1400]

    for chars in range(0, len(command) + 1, 3):
        frames.append(render(command[:chars], 0, cursor=True))
        durations.append(65)
    frames.append(render(command, 0))
    durations.append(450)

    for visible in range(1, 6):
        frames.append(render(command, visible))
        durations.append(650)

    frames.append(render(command, 5))
    durations.append(1600)
    frames.append(render(command, 5, steer=True))
    durations.append(1900)
    frames.append(render(command, 5))
    durations.append(1800)

    palette_frames = [frame.quantize(colors=96) for frame in frames]
    palette_frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=palette_frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
