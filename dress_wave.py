#!/usr/bin/env python3
"""Post-relaunch dressing wave (run with hermes venv python).

1. Collect Etsy listing ids for v2 squares + founders (Gelato externalId).
2. Attach media: squares get 6 mockups + flat art + motion video; founders get
   flat art (Gelato auto-mockups cover the rest until portrait scenes exist).
3. Switch every new listing to the free-shipping profile (template prices are
   already shipping-inclusive).
4. Create shop sections and assign listings.
5. Set the shop announcement.
6. Deactivate the 34 old single-size listings.

Idempotent via dress_state.json.
"""
import json
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
STORE = "4c983914-3f7a-4810-9dcb-562d2e92ea81"
FREE_SHIP = 284905550796
ANNOUNCEMENT = ("Minimalist botanical & birth flower art prints — luminous "
                "alchemical botanicals, made to order with free worldwide "
                "shipping from local print partners. Home of The Quiet Bloom Atlas.")
OLD_FLOWER_IDS = ["4542972899","4542985498","4542985382","4542986408","4542985624",
                  "4542973565","4542985036","4542973787","4542991012","4542985566",
                  "4542972801","4542987470"]
FLOWER_KEYS = {"january","february","march","april","may","june","july","august",
               "september","october","november","december"}

env = {l.split('=',1)[0]: l.split('=',1)[1].strip()
       for l in open(Path.home()/'.hermes'/'.env') if '=' in l}
XKEY = env['ETSY_API_KEY'] + ':' + env['ETSY_SHARED_SECRET']


def etsy_hdr():
    tok = json.loads((Path.home()/'.hermes'/'etsy_tokens.json').read_text())
    r = requests.post("https://api.etsy.com/v3/public/oauth/token", json={
        "grant_type": "refresh_token", "client_id": env['ETSY_API_KEY'],
        "refresh_token": tok["refresh_token"]}, timeout=30)
    r.raise_for_status()
    tok = r.json()
    (Path.home()/'.hermes'/'etsy_tokens.json').write_text(json.dumps(tok, indent=1))
    return {"x-api-key": XKEY, "Authorization": f"Bearer {tok['access_token']}"}


def gelato_external_ids(pushed_file: str, out: dict) -> None:
    pushed = json.loads((HERE/pushed_file).read_text())
    for key, pid in pushed.items():
        if key in out:
            continue
        for _ in range(10):
            p = requests.get(
                f"https://ecommerce.gelatoapis.com/v1/stores/{STORE}/products/{pid}",
                headers={"X-API-KEY": env['GELATO_API_KEY'],
                         "User-Agent": "radiantmirror-push/1.0"}, timeout=30).json()
            if p.get('externalId'):
                out[key] = p['externalId']
                break
            time.sleep(8)
        else:
            print(f"[pending] {key}")


def main() -> None:
    state_p = HERE/'dress_state.json'
    state = json.loads(state_p.read_text()) if state_p.exists() else {
        "ids": {}, "media": [], "shipped": [], "sectioned": [],
        "announced": False, "retired": []}

    def save():
        state_p.write_text(json.dumps(state, indent=1))

    gelato_external_ids('gelato_pushed_v2.json', state["ids"])
    gelato_external_ids('gelato_pushed_founders.json', state["ids"])
    if (HERE/'gelato_pushed_comma.json').exists():
        gelato_external_ids('gelato_pushed_comma.json', state["ids"])
    if (HERE/'gelato_pushed_hermes_sq.json').exists():
        gelato_external_ids('gelato_pushed_hermes_sq.json', state["ids"])
    if (HERE/'gelato_pushed_hermes_pt.json').exists():
        gelato_external_ids('gelato_pushed_hermes_pt.json', state["ids"])
    save()
    print(f"listings live: {len(state['ids'])}")

    hdr = etsy_hdr()
    shop_id = requests.get("https://api.etsy.com/v3/application/shops",
                           params={"shop_name": "radiantmirror"},
                           headers={"x-api-key": XKEY}, timeout=30
                           ).json()["results"][0]["shop_id"]

    seo = {x['month']: x for x in json.loads((HERE/'seo_relaunch_manifest.json').read_text())}
    founders = {x['month']: x for x in json.loads((HERE/'founders_manifest.json').read_text())}
    comma = {x['month']: x for x in json.loads((HERE/'comma_square_manifest.json').read_text())} if (HERE/'comma_square_manifest.json').exists() else {}
    hermes_sq = {x['month']: x for x in json.loads((HERE/'hermes_square_manifest.json').read_text())} if (HERE/'hermes_square_manifest.json').exists() else {}
    hermes_pt = {x['month']: x for x in json.loads((HERE/'hermes_portrait_manifest.json').read_text())} if (HERE/'hermes_portrait_manifest.json').exists() else {}

    # media
    for key, lid in state["ids"].items():
        if key in state["media"]:
            continue
        item = seo.get(key) or founders.get(key) or comma.get(key) or hermes_sq.get(key) or hermes_pt.get(key)
        stem = item['file']
        art_dir = ('originals-2048' if key in FLOWER_KEYS else
                   'founders' if key in founders else
                   'comma-selects' if key in comma else
                   'hermes-selects' if (key in hermes_sq or key in hermes_pt) else
                   'atlas-selects')
        art = HERE/art_dir/f"{stem}.png"
        ok = True
        # flat true-to-color art uploaded first — Etsy's real display order is
        # upload/insertion order, NOT the 'rank' field (verified 2026-07-24: an
        # explicit rank param caused this photo to be buried behind unranked
        # mockups instead of leading them). Never pass rank here.
        with art.open('rb') as f:
            r = requests.post(f"https://api.etsy.com/v3/application/shops/{shop_id}/listings/{lid}/images",
                              headers=hdr, files={"image": (art.name, f, "image/png")},
                              timeout=90)
        ok &= r.status_code in (200, 201)
        if key not in founders and key not in hermes_pt:
            for scene in sorted((HERE/'mockups'/stem).glob('scene*.jpg')):
                with scene.open('rb') as f:
                    r = requests.post(f"https://api.etsy.com/v3/application/shops/{shop_id}/listings/{lid}/images",
                                      headers=hdr, files={"image": (scene.name, f, "image/jpeg")}, timeout=90)
                ok &= r.status_code in (200, 201)
                time.sleep(0.3)
            vid = HERE/'videos'/f"{stem}.mp4"
            if vid.exists():
                with vid.open('rb') as f:
                    r = requests.post(f"https://api.etsy.com/v3/application/shops/{shop_id}/listings/{lid}/videos",
                                      headers=hdr, files={"video": (vid.name, f, "video/mp4")},
                                      data={"name": vid.name}, timeout=120)
                ok &= r.status_code in (200, 201)
        if ok:
            state["media"].append(key)
            save()
            print(f"[media] {key}")
        else:
            print(f"[media-partial] {key}")
        time.sleep(0.4)

    # free shipping
    for key, lid in state["ids"].items():
        if key in state["shipped"]:
            continue
        r = requests.patch(f"https://api.etsy.com/v3/application/shops/{shop_id}/listings/{lid}",
                           data={"shipping_profile_id": FREE_SHIP},
                           headers={**hdr, "Content-Type": "application/x-www-form-urlencoded"},
                           timeout=30)
        if r.status_code == 200:
            state["shipped"].append(key)
            save()
        time.sleep(0.3)
    print(f"free shipping: {len(state['shipped'])}")

    # sections
    if "sections" not in state:
        secs = {}
        for title in ("Birth Flower Prints", "The Quiet Bloom Atlas", "Digital Downloads"):
            r = requests.post(f"https://api.etsy.com/v3/application/shops/{shop_id}/sections",
                              data={"title": title},
                              headers={**hdr, "Content-Type": "application/x-www-form-urlencoded"},
                              timeout=30)
            if r.status_code in (200, 201):
                secs[title] = r.json()["shop_section_id"]
        state["sections"] = secs
        save()
    secs = state["sections"]
    for key, lid in state["ids"].items():
        if key in state["sectioned"] or not secs:
            continue
        title = "Birth Flower Prints" if key in FLOWER_KEYS else "The Quiet Bloom Atlas"
        r = requests.patch(f"https://api.etsy.com/v3/application/shops/{shop_id}/listings/{lid}",
                           data={"shop_section_id": secs.get(title, "")},
                           headers={**hdr, "Content-Type": "application/x-www-form-urlencoded"},
                           timeout=30)
        if r.status_code == 200:
            state["sectioned"].append(key)
            save()
        time.sleep(0.3)
    print(f"sectioned: {len(state['sectioned'])}")

    # announcement
    if not state["announced"]:
        r = requests.put(f"https://api.etsy.com/v3/application/shops/{shop_id}",
                         data={"announcement": ANNOUNCEMENT},
                         headers={**hdr, "Content-Type": "application/x-www-form-urlencoded"},
                         timeout=30)
        state["announced"] = r.status_code == 200
        save()
        print("announcement:", r.status_code)

    # retire old listings (only after their replacement is live with media)
    atlas_old = json.loads((HERE/'atlas_etsy_ids.json').read_text())
    old = OLD_FLOWER_IDS + list(atlas_old.values())
    if len(state["media"]) >= 30:
        for lid in old:
            if lid in state["retired"]:
                continue
            r = requests.patch(f"https://api.etsy.com/v3/application/shops/{shop_id}/listings/{lid}",
                               data={"state": "inactive"},
                               headers={**hdr, "Content-Type": "application/x-www-form-urlencoded"},
                               timeout=30)
            if r.status_code == 200:
                state["retired"].append(lid)
                save()
            time.sleep(0.3)
        print(f"retired old: {len(state['retired'])}")
    else:
        print("holding retirement — replacements not fully dressed yet")


if __name__ == "__main__":
    main()
