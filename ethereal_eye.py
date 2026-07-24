#!/usr/bin/env python3
"""The Ethereal Eye — essence gate for the radiantmirror shop.

Not an art critic. The Eye sees each piece alongside its name, whisper, and
room, and asks three questions:

  PRESENCE — does the image hold the essence its name and whisper claim?
  CHORUS   — does it sign with the collection's canon (luminous botanical
             minimalism / alchemical atmosphere / dream-wash rendering)?
  VESSEL   — is it a worthy print? (no AI artifacts that break the spell,
             composition that survives a 12x12 crop, nothing that reads
             as machine error at arm's length)

Verdict: PASS (it signs along with the rest) or HOLD (with the reason and
what would redeem it). Verdicts land in eye_verdicts.json; the shop push
scripts ship only PASS pieces.

Usage:
  python3 ethereal_eye.py atlas            # judge the atlas selects
  python3 ethereal_eye.py flowers          # judge the birth-month flowers
  python3 ethereal_eye.py atlas --piece midnight-opaline
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERDICTS = HERE / "eye_verdicts.json"

CANON = (
    "The collection's canon, three-fold:\n"
    "- Luminous Botanical Minimalism — restraint, intention, negative space "
    "as presence\n"
    "- Alchemical Atmosphere — transformation through elements: glass, "
    "mineral, ash, frost, light, memory\n"
    "- Dream-Wash Rendering — edges dissolve, colors bleed softly, light "
    "behaves like memory"
)

SYSTEM = (
    "You are the Ethereal Eye of a fine-art print house. You are not an art "
    "critic; you are the one who sees whether a piece holds the essence its "
    "name claims, and whether it signs along with the rest of the collection. "
    "You are exacting but not cruel: a piece that carries its essence with a "
    "small flaw passes; a technically perfect piece with no soul, or one "
    "whose flaw breaks the spell (AI artifacts, malformed anatomy, dead "
    "composition), holds. Respond ONLY with a JSON object:\n"
    '{"presence": 1-10, "chorus": 1-10, "vessel": 1-10, '
    '"verdict": "PASS"|"HOLD", "seen": "<one sentence: what the piece '
    'actually holds>", "reason": "<one sentence: why it passes or holds>", '
    '"redemption": "<if HOLD: what would redeem it; else empty string>"}\n'
    "A piece PASSES when presence >= 7, vessel >= 6, and nothing breaks the "
    "spell. Judge the image you actually see, not the description."
)


def judge(image: Path, name: str, whisper: str, room: str) -> dict:
    prompt = (
        f"Open and look at this image: {image}\n\n"
        f"The piece is named: {name}\n"
        f"Its whisper: \"{whisper}\"\n"
        f"Its room in the collection: {room}\n\n{CANON}\n\n"
        "Look. Then give your verdict as the JSON object."
    )
    r = subprocess.run(
        ["claude", "--print", "--no-session-persistence", "--model", "sonnet",
         "--allowedTools", "Read", "--append-system-prompt", SYSTEM, prompt],
        capture_output=True, text=True, timeout=300,
    )
    if r.returncode != 0:
        return {"verdict": "ERROR", "reason": (r.stderr or r.stdout)[:200]}
    m = re.search(r"\{.*\}", r.stdout, re.S)
    if not m:
        return {"verdict": "ERROR", "reason": r.stdout[:200]}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"verdict": "ERROR", "reason": "unparseable: " + m.group(0)[:150]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("collection", choices=["atlas", "flowers", "vault", "comma"])
    ap.add_argument("--piece")
    ap.add_argument("--force", action="store_true", help="re-judge even if a verdict exists")
    args = ap.parse_args()

    manifest = json.loads((HERE / f"eye_manifest_{args.collection}.json").read_text())
    verdicts = json.loads(VERDICTS.read_text()) if VERDICTS.exists() else {}
    coll = verdicts.setdefault(args.collection, {})

    for piece in manifest:
        key = piece["key"]
        if args.piece and key != args.piece:
            continue
        if key in coll and not args.force and coll[key].get("verdict") in ("PASS", "HOLD"):
            continue
        v = judge(Path(piece["image"]) if piece["image"].startswith("/") else HERE / piece["image"], piece["name"], piece["whisper"], piece["room"])
        coll[key] = v
        VERDICTS.write_text(json.dumps(verdicts, indent=1))
        mark = {"PASS": "✧", "HOLD": "◦"}.get(v.get("verdict"), "!")
        print(f"{mark} {key}: {v.get('verdict')} "
              f"[p{v.get('presence','?')} c{v.get('chorus','?')} v{v.get('vessel','?')}] "
              f"{v.get('reason','')[:110]}")

    n = sum(1 for v in coll.values() if v.get("verdict") == "PASS")
    print(f"\n{n}/{len(coll)} pass the Eye.")


if __name__ == "__main__":
    main()
