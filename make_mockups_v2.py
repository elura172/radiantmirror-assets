#!/usr/bin/env python3
"""Mockup factory v2 — perspective-correct compositing.

The v1 compositor (make_mockups.py) stored each scene's frame as an
axis-aligned bounding box and pasted the artwork as a flat rectangle. That
"drops the image in the canvas" but never actually "sets" it: any frame that
isn't perfectly square-on to the camera (see scene4-desk-vignette, which
leans against a wall at a real angle) gets a rectangular patch that ignores
the frame's true perspective — edges don't line up, the art looks stuck on
top rather than inside the frame.

v2 stores each frame as a QUADRILATERAL (4 corners, TL/TR/BR/BL) in
mockup-scenes/frame_quads.json, and warps the artwork onto that exact quad
with a homography (cv2.getPerspectiveTransform + warpPerspective) before
compositing. A perfectly square-on frame is just a degenerate rectangular
quad, so this one path handles both straight and angled scenes correctly —
no separate code path needed, and future tilted scenes "just work" once
their 4 corners are recorded.

Usage:
  python3 make_mockups_v2.py originals-2048            # all art in a dir
  python3 make_mockups_v2.py originals-2048 --art 05-may-lilyvalley.png

Run with: ./venv-mockup/bin/python make_mockups_v2.py ...
(needs opencv-python-headless, installed only in that venv)
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
SCENES = HERE / "mockup-scenes"
QUADS = json.loads((SCENES / "frame_quads.json").read_text())
OUT = HERE / "mockups"


def composite(scene_path: Path, quad: list, art_path: Path, out_path: Path) -> None:
    scene = cv2.imread(str(scene_path))
    art = cv2.imread(str(art_path))
    sh, sw = scene.shape[:2]
    ah, aw = art.shape[:2]

    dst = np.array(quad, dtype=np.float32)
    src = np.array([[0, 0], [aw, 0], [aw, ah], [0, ah]], dtype=np.float32)

    matrix = cv2.getPerspectiveTransform(src, dst)

    # Match the room's light: sample mean luminance inside the quad and
    # nudge the art's brightness toward it before warping, same intent as
    # v1's per-pixel tint but computed once here.
    mask_full = np.zeros((sh, sw), dtype=np.uint8)
    cv2.fillConvexPoly(mask_full, dst.astype(np.int32), 255)
    scene_gray = cv2.cvtColor(scene, cv2.COLOR_BGR2GRAY)
    region_lum = cv2.mean(scene_gray, mask=mask_full)[0] / 255.0
    art = np.clip(art.astype(np.float32) * (0.82 + 0.28 * region_lum), 0, 255).astype(np.uint8)

    warped = cv2.warpPerspective(art, matrix, (sw, sh))

    # Soft inner shadow hugging the true quad edges (not axis-aligned lines):
    # erode the fill mask progressively and darken toward the boundary.
    shadow = scene.astype(np.float32)
    mask_f = mask_full.astype(np.float32) / 255.0
    kernel = np.ones((3, 3), np.uint8)
    ring = mask_full.copy()
    for i, strength in enumerate((0.35, 0.24, 0.14, 0.07)):
        eroded = cv2.erode(ring, kernel, iterations=3)
        edge = cv2.subtract(ring, eroded)
        edge_blur = cv2.GaussianBlur(edge, (9, 9), 0).astype(np.float32) / 255.0
        shadow = shadow * (1 - edge_blur[..., None] * strength)
        ring = eroded

    composed = shadow.astype(np.uint8)
    composed = np.where(mask_full[..., None] > 0, warped, composed)

    cv2.imwrite(str(out_path), composed, [cv2.IMWRITE_JPEG_QUALITY, 92])


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
        for scene_name, quad in QUADS.items():
            out = dest / f"{scene_name}.jpg"
            composite(SCENES / f"{scene_name}.png", quad, art, out)
            made += 1
    print(f"{made} mockups -> {OUT}")


if __name__ == "__main__":
    main()
