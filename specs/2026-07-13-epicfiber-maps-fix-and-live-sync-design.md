# EpicFiber Maps — Correctness Fix + Live Sync + Private Hosting

- **Date:** 2026-07-13
- **Status:** Approved
- **Owner:** LegacyEpicFiber
- **Repo:** `LegacyEpicFiber/epicfiber-repo` (map tool)

> Spec lives in `specs/` (repo root), deliberately **outside** `docs/`, because `docs/`
> is the web-published output folder and this document should not be served.

---

## 1. Background & problem

The tool pulls addresses from the *BURIAL MASTER LIST* Google Sheet, geocodes them, and
publishes interactive Leaflet maps. It works, but a hands-on audit of the live committed
data (491 Bury pins) found the map does not "wholeheartedly" represent addresses:

| Finding (from audit of real data) | Count | Effect |
|---|---|---|
| `state` never attached to any pin | 491/491 | Search/popups can't disambiguate towns (e.g. Fremont) |
| Unit/lot addresses stripped after `/`, geocode to identical point | 5+ / 3 shared points | Distinct jobs stack on one wrong pin; search flies to the wrong spot |
| Missing county + township | 96/491 (~20%) | Blank popup metadata |
| Duplicate address rows | 24 extra | Same address shown twice in search |
| Rows that fail all geocoders | unknown (dropped) | Silently absent → "search finds nothing" |
| No HTML escaping of sheet data | 0 today | A future `<`/`"`/`&` corrupts rendering |

Two additional goals on top of the fixes:
1. **Live updates** — the map should refresh whenever a new, real, parseable address is
   added to the sheet, instead of on an hourly clock.
2. **Privacy** — customer addresses are currently on a public GitHub Pages site; move the
   map behind authentication while keeping a bookmarkable URL for field crews.

Security note: the previously-leaked Google Maps API key has already been **rotated and the
old key deleted**, and the GitHub secret updated. This spec covers scrubbing the dead value
from `CONTEXT.md` and preventing recurrence.

---

## 2. Goals / non-goals

**Goals**
- Every sheet row with a non-empty ADDRESS + CITY either becomes a correctly-placed pin or
  appears in an on-map "unplaced" list. Nothing is silently dropped.
- Co-located units render as individually visible, searchable pins.
- County/township coverage materially improved (target < 5% blank).
- `state` shown in search results and popups.
- Map refreshes ~1–2 min after a qualifying sheet edit (event-driven).
- Map served privately (Cloudflare Access) with a stable bookmarkable URL; repo private;
  GitHub Pages disabled.
- Hourly commit noise eliminated (commit only on real change + a daily safety-net run).
- No secrets in the repo.

**Non-goals**
- Rewriting the map UI framework (stay on Leaflet).
- Sub-30-second "instant" updates (needs an always-on server).
- Turn-by-turn routing (out of scope; this is a proximity/visualization tool).
- Migrating off the Google → Census → Nominatim geocoder waterfall.

---

## 3. Target architecture

```
Google Sheet (BURIAL MASTER LIST)
  │   edit / new row
  ▼
Apps Script onChange (bound to sheet)  — debounce ~60s, only if row has ADDRESS+CITY
  ▼
POST api.github.com/repos/.../dispatches  {event_type: "sheet-updated"}   (PAT in Script Properties)
  ▼
GitHub Actions  (on: repository_dispatch | workflow_dispatch | daily cron)
  │   gspread + service account → rows
  │   geocoder waterfall (Google → Census → Nominatim) + cache
  │   reverse county/township lookup from coords
  │   fan-out co-located pins; collect unplaced rows
  │   write docs/map-*.html + index.html + metadata.json  (only if changed)
  │   commit + push ONLY when map content changed
  ▼
Cloudflare Pages (Git integration on the private repo, output dir = docs/) → auto-deploy
  ▼
Cloudflare Access (Zero Trust, free ≤50 users) → crew Google login
  ▼
Field crew (bookmarked URL, phone or desktop)
```

---

## 4. Component design

### 4.1 Hosting & privatization (Cloudflare Pages + Access)
- Repo → **private**; **GitHub Pages disabled** so the old `*.github.io` URL stops serving addresses.
- **Cloudflare Pages** connected to the private repo: production branch `main`, no build command,
  output directory `docs`. Auto-deploys on push. URL: `epicfiber-maps.pages.dev`.
- **Cloudflare Access** self-hosted application over the Pages hostname. Policy: **initially
  allow only `legacy.buryandbore@gmail.com`**; the owner expands the allowlist later. Identity
  via Google or one-time email PIN.
- **Needed from user:** free Cloudflare account. Initial Access allowlist = a single email.

### 4.2 Live-update pipeline (sheet-triggered)
- **Apps Script** bound to the sheet, installable `onChange`; debounces ~60s; fires only when a
  row has non-empty ADDRESS+CITY; POSTs `repository_dispatch` with a fine-grained PAT in Script
  Properties (never in the sheet).
- **Workflow** gains `repository_dispatch`; keeps `workflow_dispatch`; hourly cron → once-daily
  safety net. **Commit-only-on-change**: only rewrite maps + bump `metadata.json` when a map
  actually changed, eliminating the ~730-commit hourly noise and conserving private-repo minutes.

### 4.3 Correctness fixes (`generate_map.py` + `map_template.html`)
- **State** — add `"state"` (IN/MI) to each pin; the template renders it.
- **Unit/lot fan-out** — keep the full string as displayed `address`, geocode a stripped base,
  and de-stack co-located pins deterministically; fix the regex so fractions (`123 1/2 Main St`)
  survive.
- **County/township** — replace the "geocode `1 Main St`" trick with a **coordinate reverse
  lookup** (Census); curated `CITY_META` first, else reverse lookup, cached.
- **De-dupe** — collapse exact `(address, city)` duplicates; note merged rows in the popup.
- **Unplaced list** — collect rows with address+city but no geocode; render an on-map
  "⚠ N couldn't be placed" panel; counts in `metadata.json`.
- **Escaping** — a JS `esc()` helper at innerHTML sites, and escape `<`,`>`,`&`,U+2028/9 in the
  injected JSON so data can't break out of the `<script>` block.

### 4.4 Cleanup (bundled review items)
Scrub the dead key + sheet ID from `CONTEXT.md`; remove the redundant macOS `launchd` install;
make `index.html` render its cards from `metadata.json`; reconcile "6 AM / hourly / daily" doc
contradictions; pin the Leaflet CDN with SRI hashes.

### 4.5 Mobile / field usability
Narrow-screen pass: below ~640px, collapse the four fixed panels into a single toggleable menu
or bottom sheet so they don't overlap; keep desktop layout unchanged.

---

## 5. Data model changes
Pin gains: `state` ("IN"|"MI"), `unit` (string|null), `offset_applied` (bool). New template input
`{{UNPLACED_JSON}}` = `[{address, city, row_num}]`. `metadata.json` gains (existing `tabs` = pin
counts stays as-is, so `index.html` keeps working): `unplaced`: `{ "<tab>": <count> }`.

## 6. Security
Secrets stay in GitHub Actions secrets; new Apps Script PAT in Script Properties only; Cloudflare
Git integration needs no repo token; rotated Maps key restricted to Geocoding API + budget/quota;
`CONTEXT.md` carries no secret values; map content access-gated by Cloudflare Access.

## 7. Testing strategy
Unit tests for the pure logic; a golden test running `generate_map`'s `build_pins` against a
fixture with mocked geocoder/meta (state present, offsets applied, no stacking, unplaced captured,
escaping correct); manual end-to-end for the live trigger behind Access.

## 8. Rollout / sequencing
- Phase 0 — done: rotate Maps key.
- Phase 1 — private hosting (Cloudflare Pages + Access; repo private; disable GitHub Pages).
- Phase 2 — correctness fixes (this PR).
- Phase 3 — live sync (workflow trigger + commit-on-change + Apps Script).
- Phase 4 — cleanup + mobile.

## 9. Success criteria
No valid row silently dropped; co-located units individually visible; county/township blanks
< 5%; state shown; ~2-min live refresh; no secrets in repo; commits only on real change.

## 10. Open items / needed from user
- Cloudflare account. Access allowlist starts at `legacy.buryandbore@gmail.com` only; owner adds
  crew later.
- Confirm daily safety-net time (default ~6am ET / `0 11 * * *`).
- Create the fine-grained GitHub PAT for Apps Script (guided; user creates it).
