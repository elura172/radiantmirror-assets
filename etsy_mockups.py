#!/usr/bin/env python3
"""Etsy mockup attacher for radiantmirror.

Run with the hermes venv python (has requests):
  ~/.hermes/hermes-agent/venv/bin/python3 etsy_mockups.py auth
  ~/.hermes/hermes-agent/venv/bin/python3 etsy_mockups.py attach            # all months
  ~/.hermes/hermes-agent/venv/bin/python3 etsy_mockups.py attach --month february

auth: OAuth2 PKCE grant (opens browser, you click Grant Access once).
      Tokens stored in ~/.hermes/etsy_tokens.json, auto-refreshed after.
attach: uploads the 6 room mockups to each flower listing, skipping any
      (listing, scene) already recorded in etsy_attached.json. Throttled
      to ~2 req/s (limits are 10 QPS / 10K QPD).
"""
import argparse
import base64
import hashlib
import http.server
import json
import secrets
import threading
import time
import webbrowser
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ENV = Path.home() / ".hermes" / ".env"
TOKENS = Path.home() / ".hermes" / "etsy_tokens.json"
ATTACHED = HERE / "etsy_attached.json"
PUSHED = HERE / "gelato_pushed.json"
MOCKUPS = HERE / "mockups"
REDIRECT = "http://localhost:8443/callback"
SCOPES = "listings_r listings_w shops_r shops_w"
STORE = "4c983914-3f7a-4810-9dcb-562d2e92ea81"

MONTH_DIRS = {
    "january": "01-january-carnation", "february": "02-february-iris",
    "march": "03-march-daffodil", "april": "04-april-daisy",
    "may": "05-may-lilyvalley", "june": "06-june-rose",
    "july": "07-july-larkspur", "august": "08-august-poppy",
    "september": "09-september-morningglory", "october": "10-october-marigold",
    "november": "11-november-chrysanthemum", "december": "12-december-narcissus",
}


def env(key: str) -> str:
    for line in ENV.read_text().splitlines():
        if line.strip().startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"{key} not found in ~/.hermes/.env")


def cmd_auth() -> None:
    client_id = env("ETSY_API_KEY")
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_hex(12)
    url = ("https://www.etsy.com/oauth/connect"
           f"?response_type=code&client_id={client_id}"
           f"&redirect_uri={REDIRECT}&scope={SCOPES.replace(' ', '%20')}"
           f"&state={state}&code_challenge={challenge}&code_challenge_method=S256")

    result = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            if q.get("state", [""])[0] == state and "code" in q:
                result["code"] = q["code"][0]
                msg = b"Granted. You can close this tab and return to the terminal."
            else:
                msg = b"Missing/invalid code or state. Try again."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(msg)

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("localhost", 8443), H)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print("Opening Etsy grant page — click 'Grant Access'...")
    webbrowser.open(url)
    deadline = time.time() + 300
    while "code" not in result and time.time() < deadline:
        time.sleep(1)
    server.shutdown()
    if "code" not in result:
        raise SystemExit("Timed out waiting for the grant (5 min).")

    r = requests.post("https://api.etsy.com/v3/public/oauth/token", json={
        "grant_type": "authorization_code", "client_id": client_id,
        "redirect_uri": REDIRECT, "code": result["code"],
        "code_verifier": verifier,
    }, timeout=30)
    r.raise_for_status()
    TOKENS.write_text(json.dumps(r.json(), indent=1))
    TOKENS.chmod(0o600)
    print("Tokens saved to", TOKENS)


def api_key_header() -> str:
    """Newer Etsy personal apps require 'keystring:shared_secret' in x-api-key."""
    return env("ETSY_API_KEY") + ":" + env("ETSY_SHARED_SECRET")


def get_token() -> tuple[str, str]:
    client_id = env("ETSY_API_KEY")
    tok = json.loads(TOKENS.read_text())
    r = requests.post("https://api.etsy.com/v3/public/oauth/token", json={
        "grant_type": "refresh_token", "client_id": client_id,
        "refresh_token": tok["refresh_token"],
    }, timeout=30)
    r.raise_for_status()
    tok = r.json()
    TOKENS.write_text(json.dumps(tok, indent=1))
    return client_id, tok["access_token"]


def listing_ids() -> dict:
    """month -> etsy listing id, via Gelato externalId."""
    gkey = env("GELATO_API_KEY")
    pushed = json.loads(PUSHED.read_text())
    out = {}
    for month, pid in pushed.items():
        r = requests.get(
            f"https://ecommerce.gelatoapis.com/v1/stores/{STORE}/products/{pid}",
            headers={"X-API-KEY": gkey, "User-Agent": "radiantmirror-push/1.0"},
            timeout=30)
        r.raise_for_status()
        ext = r.json().get("externalId")
        if ext:
            out[month] = ext
        time.sleep(0.3)
    return out


def cmd_attach(only_month: str | None) -> None:
    client_id, access = get_token()
    headers = {"x-api-key": api_key_header(), "Authorization": f"Bearer {access}"}

    r = requests.get("https://api.etsy.com/v3/application/shops",
                     params={"shop_name": "radiantmirror"},
                     headers={"x-api-key": api_key_header()}, timeout=30)
    r.raise_for_status()
    shop_id = r.json()["results"][0]["shop_id"]
    print("shop_id:", shop_id)

    attached = json.loads(ATTACHED.read_text()) if ATTACHED.exists() else {}
    ids = listing_ids()
    for month, listing_id in ids.items():
        if only_month and month != only_month:
            continue
        scenes_done = attached.get(month, [])
        mock_dir = MOCKUPS / MONTH_DIRS[month]
        for scene in sorted(mock_dir.glob("scene*.jpg")):
            if scene.name in scenes_done:
                continue
            with scene.open("rb") as f:
                r = requests.post(
                    f"https://api.etsy.com/v3/application/shops/{shop_id}"
                    f"/listings/{listing_id}/images",
                    headers=headers, files={"image": (scene.name, f, "image/jpeg")},
                    timeout=60)
            if r.status_code in (200, 201):
                scenes_done.append(scene.name)
                attached[month] = scenes_done
                ATTACHED.write_text(json.dumps(attached, indent=1))
                print(f"[ok] {month} {scene.name}")
            else:
                print(f"[fail] {month} {scene.name}: {r.status_code} {r.text[:200]}")
            time.sleep(0.5)
    print("done.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["auth", "attach"])
    ap.add_argument("--month")
    a = ap.parse_args()
    cmd_auth() if a.cmd == "auth" else cmd_attach(a.month)
