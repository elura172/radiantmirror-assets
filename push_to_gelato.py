#!/usr/bin/env python3
"""Push the Birth Month Flower Collection to Gelato → Etsy (radiantmirror).

Reads GELATO_API_KEY from ~/.hermes/.env, per-month template UUIDs from
~/.hermes/gelato_config.yaml, and titles/descriptions/tags from
listings_manifest.json (extracted from the obsidian production doc).

Usage:
  python3 push_to_gelato.py --dry-run     # show what would be created
  python3 push_to_gelato.py               # create all 12 products
  python3 push_to_gelato.py --month may   # create one month only

Idempotence: writes created product IDs to gelato_pushed.json and skips
months already present there.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "listings_manifest.json"
PUSHED = HERE / "gelato_pushed.json"
CONFIG = Path.home() / ".hermes" / "gelato_config.yaml"
ENV = Path.home() / ".hermes" / ".env"
BASE = "https://ecommerce.gelatoapis.com"  # products API host per Gelato docs
BASE_FALLBACK = "https://order.gelatoapis.com"  # host named in the hermes skill


def load_env_key() -> str:
    if os.environ.get("GELATO_API_KEY"):
        return os.environ["GELATO_API_KEY"]
    for line in ENV.read_text().splitlines():
        if line.strip().startswith("GELATO_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("GELATO_API_KEY not found in ~/.hermes/.env — add it first.")


def load_templates() -> dict:
    """Minimal YAML walk: birth_month_collections.<month>.template."""
    months, cur = {}, None
    in_block = False
    for raw in CONFIG.read_text().splitlines():
        if raw.startswith("birth_month_collections:"):
            in_block = True
            continue
        if in_block:
            if raw and not raw.startswith(" "):
                break
            m = raw.strip()
            if m.endswith(":") and raw.startswith("  ") and not raw.startswith("    "):
                cur = m[:-1]
            elif cur and m.startswith("template:"):
                months[cur] = m.split(":", 1)[1].strip().strip('"')
    return months


def api(key: str, method: str, path: str, body: dict | None = None,
        base: str = BASE) -> tuple[int, dict]:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode() if body else None,
        headers={"X-API-KEY": key, "Content-Type": "application/json",
                 "User-Agent": "radiantmirror-push/1.0 (python-urllib)"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            detail = json.load(e)
        except Exception:
            detail = {"raw": e.read().decode(errors="replace")[:400]}
        return e.code, detail


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--month")
    args = ap.parse_args()

    key = load_env_key()
    templates = load_templates()
    listings = json.loads(MANIFEST.read_text())
    pushed = json.loads(PUSHED.read_text()) if PUSHED.exists() else {}
    store = "4c983914-3f7a-4810-9dcb-562d2e92ea81"

    for item in listings:
        month = item["month"]
        if args.month and month != args.month:
            continue
        if month in pushed:
            print(f"[skip] {month} already pushed: {pushed[month]}")
            continue
        template_id = templates.get(month)
        if not template_id:
            print(f"[skip] {month}: no template id in config")
            continue

        if args.dry_run:
            print(f"[dry] {month}: '{item['title']}' template={template_id}")
            print(f"      image={item['url']}")
            continue

        # Resolve template variants (try both API hosts)
        status, tpl = api(key, "GET", f"/v1/templates/{template_id}")
        if status == 404:
            status, tpl = api(key, "GET",
                              f"/v1/stores/{store}/templates/{template_id}",
                              base=BASE_FALLBACK)
        if status != 200:
            print(f"[fail] {month}: template fetch {status} {str(tpl)[:200]}")
            continue

        variants = []
        for v in tpl.get("variants", []):
            placeholders = [
                {"name": p.get("name", "Artwork"), "fileUrl": item["url"],
                 "fitMethod": "slice"}
                for p in v.get("imagePlaceholders", [{"name": "Artwork"}])
            ] or [{"name": "Artwork", "fileUrl": item["url"], "fitMethod": "slice"}]
            variants.append({"templateVariantId": v["id"],
                             "imagePlaceholders": placeholders})

        body = {
            "templateId": template_id,
            "title": item["title"],
            "description": "<p>" + item["description"].replace("\n\n", "</p><p>").replace("\n", " ") + "</p>",
            "isVisibleInTheOnlineStore": True,
            "variants": variants,
            "tags": [re.sub(r"[^A-Za-z0-9 ]", " ", t).strip()
                     for t in item["tags"]][:13],
            "productType": "Printable Material",
            "vendor": "Mirai Studio",
        }
        status, resp = api(key, "POST",
                           f"/v1/stores/{store}/products:create-from-template",
                           body)
        if status in (200, 201):
            pid = resp.get("id", "?")
            pushed[month] = pid
            PUSHED.write_text(json.dumps(pushed, indent=1))
            print(f"[ok] {month}: product {pid} status={resp.get('status')}")
        else:
            print(f"[fail] {month}: {status} {str(resp)[:300]}")
        time.sleep(2)  # be polite; 429 backoff is 'retry next run' by design

    print("\ndone.", len(pushed), "products recorded in gelato_pushed.json")


if __name__ == "__main__":
    main()
