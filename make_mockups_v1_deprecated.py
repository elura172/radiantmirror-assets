#!/usr/bin/env python3
"""Mockup factory: composite artwork into the six generated room scenes.

Frame regions live in mockup-scenes/frame_rects.json (auto-detected).
The artwork is pasted pixel-perfect (no AI touching it), with a soft inner
shadow and a scene-tinted luminosity pass so it sits in the room's light.

Usage:
  python3 make_mockups.py originals-2048            # all art in a dir
  python3 make_mockups.py originals-2048 --art 05-may-lilyvalley.png
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

HERE = Path(__file__).resolve().parent
SCENES = HERE / "mockup-scenes"
RECTS = json.loads((SCENES / "frame_rects.json").read_text())
OUT = HERE / "mockups"


def composite(scene_path: Path, rect: tuple, art_path: Path, out_path: Path) -> None:
    scene = Image.open(scene_path).convert("RGB")
    art = Image.open(art_path).convert("RGB")
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0

    art = art.resize((w, h), Image.LANCZOS)

    # Match the room's light: tint the art slightly toward the average
    # luminance of the canvas area it replaces.
    canvas_region = scene.crop(rect)
    lum = sum(canvas_region.resize((1, 1)).getpixel((0, 0))) / 3 / 255
    art = ImageEnhance.Brightness(art).enhance(0.82 + 0.28 * lum)

    scene.paste(art, (x0, y0))

    # Soft inner shadow around the frame opening
    shadow = Image.new("L", scene.size, 0)
    d = ImageDraw.Draw(shadow)
    for i, alpha in ((0, 90), (2, 60), (5, 35), (9, 18)):
        d.rectangle([x0 + i, y0 + i, x1 - i, y1 - i], outline=alpha, width=2)
    shadow = shadow.filter(ImageFilter.GaussianBlur(3))
    black = Image.new("RGB", scene.size, (10, 8, 6))
    scene = Image.composite(black, scene, shadow.point(lambda p: min(p, 70)))

    scene.save(out_path, quality=92)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("art_dir")
    ap.add_argument("--art", help="single artwork filename")
    args = ap.parse_args()

    art_dir = HERE / args.art_dir
    arts = [art_dir / args.art] if args.art else sorted(art_dir.glob("*.png"))
    made = 0
    for art in arts:
        dest = OUT / art.stem
        dest.mkdir(parents=True, exist_ok=True)
        for scene_name, rect in RECTS.items():
            if not rect:
                continue
            out = dest / f"{scene_name}.jpg"
            composite(SCENES / f"{scene_name}.png", tuple(rect), art, out)
            made += 1
    print(f"{made} mockups -> {OUT}")


if __name__ == "__main__":
    main()
