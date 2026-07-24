# radiantmirror — handoff

Last session: 2026-07-24. Shop: etsy.com/shop/radiantmirror. 138 active listings.

## What's live and correct right now

- **138 listings** across Birth Flower Prints, Quiet Bloom Atlas, New Wing,
  comma harvest, and hermes vault harvest. All Eye-gated (see below).
- **Category fixed**: all 138 under Giclée (taxonomy 121) — was wrongly under
  Digital Prints (2078), likely hiding the shop from physical-wall-art search
  entirely. Verified via API.
- **Titles fixed**: trailing disambiguation numbers ("Portal Dreamscape 11")
  stripped from all 138.
- **Descriptions fixed**: a `seen[:120]` character-slice bug was cutting
  sentences mid-clause ("...between a shadowed, overgrown grove and a —").
  Rebuilt to truncate at sentence boundaries. All 138 fixed.
- **Free worldwide shipping** on everything, price ladders shipping-inclusive.
- **Mockup Factory v2** (`make_mockups_v2.py`): perspective-correct compositing.
  v1 pasted art as a flat rectangle even into tilted frames (scene4-desk-vignette
  genuinely leans — confirmed via OpenCV corner detection). v2 stores each
  scene as a 4-corner quad (`mockup-scenes/frame_quads.json`) and warps art
  onto it via homography. Regenerated all 930 mockups across every collection,
  pushed to the asset repo. **Not yet re-uploaded to live Etsy listings** —
  see open items.

## Open items, in priority order

1. **Etsy daily API rate limit was hit** ("Exceeded daily rate limit") mid
   photo-cleanup. Before doing ANY Etsy API work next session: test with one
   cheap call (`GET /shops?shop_name=radiantmirror`) before running anything
   at scale. Don't guess the reset window — just check.
2. **Photo-count cleanup** — ~40-50 listings carry 14-15 images instead of the
   correct 7 (1 flat art + 6 mockups), from an earlier flawed delete/reupload
   pass. Not broken data, just redundant photos. Root cause found: **Etsy
   refuses to let a listing drop to zero images** ("must have at least 1"), so
   naive delete-all-then-upload always leaves a straggler, and repeated fixes
   pile up duplicates. Correct algorithm is written in `fix_photo_cleanup.py`:
   delete down to one survivor → upload the fresh 7 → delete the survivor last.
   Tested once on `ink-garden` before the rate limit hit; needs a real run.
3. **Combine with mockup v2 rollout** — do the photo-cleanup fix AND the v2
   mockup swap in the SAME upload pass per listing (don't touch each
   listing's photos twice). `fix_photo_cleanup.py` currently points at
   `mockups/` — just make sure it's reading the v2-regenerated files (it will,
   since v2 wrote into the same `mockups/<stem>/sceneN.jpg` paths).
4. **Vault swap approvals already executed**: aether-glass-refined,
   midnight-opaline, nocturne-bloom were swapped for stronger vault-champion
   art per user approval — done, no action needed.
5. **13 held landscape pieces** from the hermes census (true 4:3/3:2 ratio,
   not square or 2:3 portrait) — sitting unshipped, listed in
   `eye_manifest_hermes.json` (family field, aspect ratio ~1.33). Would need a
   third Gelato template (landscape) to ship. Not started.
6. **Devotional line canon** — the "blue-buddha" family (5 pieces, 1 passed
   under the wrong botanical canon originally) needs its own written canon in
   `ethereal_eye.py`-style, separate from the botanical Quiet Bloom Atlas
   canon. User wants to think about this — ties into Tara/devotional work.
   Not started, no manifest built yet.
7. **Brand-identity question** (from Etsy front-end review): 124 of 138
   listings are cosmic/dreamscape/devotional; only 14 are birth-flower/atlas
   botanical, but shop announcement + About section lead with "minimalist
   botanical." User hasn't decided whether to reposition, add a second
   distinct shop identity, or leave as-is. Worth a conversation, not a fix.
8. **~4 Higgsfield credits remain.** Comma + hermes masters are 2048px
   (~102dpi at 20×20 — thin but printable; painterly work is forgiving at wall
   distance). Plan: just-in-time 4K upscale (2 credits/piece) only if/when a
   large-size order actually comes in, rather than pre-spending on unproven
   demand.

## Key scripts (all in this folder)

- `ethereal_eye.py <collection>` — the essence gate. Every piece that reaches
  the shop passes through this first. Judges PRESENCE/CHORUS/VESSEL against a
  canon; verdicts in `eye_verdicts.json`. Collections: atlas, flowers, vault,
  comma, hermes. Supports per-piece canons (see `eye_manifest_hermes.json` for
  the pattern — each family can carry its own canon string).
- `make_mockups_v2.py <art_dir>` — the compositor. Needs
  `./venv-mockup/bin/python` (has opencv-python-headless; system python is
  externally-managed, don't `--break-system-packages`).
- `make_videos.py <stem or --all>` — ffmpeg ken-burns art zoom + 3 mockup
  crossfades, 1080², free. Fixed a real bug 2026-07-24: zoompan used `in`
  (input frame count) instead of `on` (output frame count), producing frozen
  stills. Now has genuine motion.
- `push_to_gelato.py --manifest X --template Y --pushed-file Z [--eye-gate collection]`
  — creates Gelato products, auto-publishes to Etsy. Idempotent.
- `dress_wave.py` — post-creation dressing: media, free shipping, sections,
  announcement, retiring old listings. Idempotent via `dress_state.json`.
- `fix_listings.py` / `fix_photo_cleanup.py` — the corrective passes described
  above. Idempotent via `fix_state.json` / `photo_cleanup_state.json`.
- `etsy_mockups.py auth` — re-run if the OAuth token in
  `~/.hermes/etsy_tokens.json` ever needs a fresh grant (rare; refresh_token
  handles normal expiry automatically).

## Hard-won lessons (don't repeat these)

- **Etsy's real photo display order is upload/insertion order, NOT the `rank`
  field returned by GET.** Never pass an explicit `rank` param on upload.
- **Etsy won't let a listing have zero images.** Any bulk photo-replace must
  keep one survivor until the new set exists, then delete the survivor last.
- **New Etsy personal apps need `"keystring:shared_secret"` in the `x-api-key`
  header**, not just the keystring — a plain keystring 403s with "Shared
  secret is required."
- **NEVER confirm "Developer Mode" in Etsy's dev console** — it makes the
  shop unsearchable, irreversibly without Etsy support. User correctly backed
  out of this once already.
- **Judge every art family against its OWN canon.** A single global botanical
  canon silently misjudged the goddesses/dreamscape families early on — always
  write a per-family canon before running the Eye on a new archive.
- **Large git pushes (900+ new files) can time out in the foreground** — run
  `git push` with `run_in_background: true` for any big media commit.
- Gelato API needs a real `User-Agent` header (Cloudflare blocks bare
  `python-urllib`) and taxonomy-safe tags (alnum + space only, no punctuation).

## Credentials

All in `~/.hermes/.env`: `GELATO_API_KEY`, `ETSY_API_KEY`, `ETSY_SHARED_SECRET`.
OAuth tokens: `~/.hermes/etsy_tokens.json` (0600, auto-refreshes).
Gelato store: `4c983914-3f7a-4810-9dcb-562d2e92ea81`.
Templates: square `ce27535a-c442-42ff-9450-94ccc870f992`,
2:3 portrait `0b116bef-6579-430d-bb43-74586f0eb88e`.
