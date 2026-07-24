#!/usr/bin/env python3
"""Listing videos: slow push into the artwork, then crossfade through mockups.

Etsy spec: 5-15s, >=720p, muted playback, max 100MB. We render 1080x1080,
12s, no audio.

Usage:
  python3 make_videos.py 01-january-carnation           # one
  python3 make_videos.py --all                          # every art with mockups
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE / "originals-2048"
ATLAS = HERE / "atlas-selects"
MOCKUPS = HERE / "mockups"
OUT = HERE / "videos"

# scenes used in the crossfade tail, chosen for contrast variety
TAIL_SCENES = ["scene1-reading-nook", "scene5-gallery-wall", "scene2-minimal-bedroom"]


def build(stem: str) -> Path | None:
    art = ART / f"{stem}.png"
    if not art.exists():
        art = ATLAS / f"{stem}.png"
    mocks = [MOCKUPS / stem / f"{s}.jpg" for s in TAIL_SCENES]
    if not art.exists() or not all(m.exists() for m in mocks):
        print(f"[skip] {stem}: missing art or mockups")
        return None
    OUT.mkdir(exist_ok=True)
    out = OUT / f"{stem}.mp4"

    # Segment 1 (6s): slow zoom into the artwork (zoompan on stills).
    # Segments 2-4 (2s each): mockup crossfades.
    inputs = ["-loop", "1", "-t", "6", "-i", str(art)]
    for m in mocks:
        inputs += ["-loop", "1", "-t", "2.5", "-i", str(m)]

    fc = (
        "[0:v]scale=2160:2160,zoompan=z='1+0.18*on/150':x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':d=150:s=1080x1080:fps=25,setsar=1[a];"
        "[1:v]scale=1250:1250:force_original_aspect_ratio=increase,crop=1250:1250,"
        "zoompan=z='1.04':x='(iw-iw/zoom)*on/63':y='(ih-ih/zoom)/2':d=63:s=1080x1080:fps=25,setsar=1[b];"
        "[2:v]scale=1250:1250:force_original_aspect_ratio=increase,crop=1250:1250,"
        "zoompan=z='1.10-0.06*on/63':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d=63:s=1080x1080:fps=25,setsar=1[c];"
        "[3:v]scale=1250:1250:force_original_aspect_ratio=increase,crop=1250:1250,"
        "zoompan=z='1.04':y='(ih-ih/zoom)*on/63':x='(iw-iw/zoom)/2':d=63:s=1080x1080:fps=25,setsar=1[d];"
        "[a][b]xfade=transition=fade:duration=0.6:offset=5.4[ab];"
        "[ab][c]xfade=transition=fade:duration=0.6:offset=7.3[abc];"
        "[abc][d]xfade=transition=fade:duration=0.6:offset=9.2[v]"
    )
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", fc, "-map", "[v]",
           "-t", "11.5", "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-preset", "medium", "-crf", "20", "-an", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[fail] {stem}: {r.stderr[-300:]}")
        return None
    print(f"[ok] {out.name} ({out.stat().st_size // 1024} KB)")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stem", nargs="?")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.all:
        stems = sorted(d.name for d in MOCKUPS.iterdir() if d.is_dir())
        for s in stems:
            build(s)
    elif a.stem:
        build(a.stem)
    else:
        sys.exit("give a stem or --all")


if __name__ == "__main__":
    main()
