# EpicFiber Maps — Privatization Runbook (Cloudflare Pages + Access)

**Goal:** Move the map off public GitHub Pages onto **Cloudflare Pages** behind **Cloudflare Access**, so only approved people can view it — while keeping one stable, bookmarkable URL. Then make the GitHub repo private and turn GitHub Pages off.

**Time:** ~20–30 min. **Cost:** $0 (Cloudflare Pages + Access free tiers cover this; Access free = up to 50 users).

**Why this order:** stand up the private Cloudflare site FIRST and confirm it works, THEN disable GitHub Pages and privatize the repo — so the map is never offline in between.

---

## Phase 1 — Cloudflare Pages (get the map on a Cloudflare URL)

1. Create a free Cloudflare account at **dash.cloudflare.com** (skip adding a domain — not needed for a `pages.dev` URL).
2. In the dashboard: **Workers & Pages → Create → Pages → Connect to Git**.
3. Authorize Cloudflare's GitHub app and grant it access to **`LegacyEpicFiber/epicfiber-repo`** (you can scope it to just that one repo).
4. Select the repo, then set build settings:
   - Framework preset: **None**
   - Build command: **(leave empty)**
   - Build output directory: **`docs`**
   - Production branch: **`main`**
5. **Save and Deploy.** After ~30s you get a URL like **`https://epicfiber-maps.pages.dev`**.
6. Open it — you should see your landing page, with maps at `…pages.dev/map-bury--dwb.html` and `…pages.dev/map-temporary-locates.html`. (Still public for the moment — we gate it in Phase 2.)

## Phase 2 — Cloudflare Access (require login)

7. Go to **Zero Trust** in the dashboard (accept the free plan if prompted — no card needed for the free tier).
8. **Access → Applications → Add an application → Self-hosted.**
9. Application config:
   - Name: `EpicFiber Maps`
   - Session duration: your choice (e.g. **1 month**, so crews rarely re-login)
   - Public hostname: **`epicfiber-maps.pages.dev`** (the subdomain from step 5)
10. Add a policy:
    - Name: `Allowed crew`
    - Action: **Allow**
    - Include → **Emails** → **`legacy.buryandbore@gmail.com`** (just you for now — add crew here later)
11. Login methods: enable **Google** (one-tap for Gmail) and/or **One-time PIN** (emails a code). **Save.**
12. **Test in a private/incognito window:** open the `pages.dev` URL → you're redirected to a Cloudflare login → sign in as `legacy.buryandbore@gmail.com` → the map loads. Try any other email → access denied. ✅

## Phase 3 — Lock down GitHub (only after Phase 2 works)

13. GitHub repo → **Settings → Pages → Source: None** — turns off the public `github.io` site.
14. GitHub repo → **Settings → General → Danger Zone → Change visibility → Make private.** (Cloudflare's GitHub app keeps its access because you authorized it in step 3, so deploys keep working.)
15. Confirm the old URL **`https://legacyepicfiber.github.io/epicfiber-repo/`** now returns **404**.

## Phase 4 — Bookmarks

16. Update your bookmark to the **`…pages.dev`** URL. When you add crew later (step 10), have them bookmark the same URL — first visit asks for login once, then it's seamless.

---

## Notes

- **Deploys keep working:** every push to `main` auto-redeploys to Cloudflare in ~30s. Once the live-sync work lands, a new address in the sheet flows all the way through to this private URL automatically.
- **Custom domain (optional, later):** you can attach e.g. `maps.legacyepicfiber.com` under the Pages project → *Custom domains*, and point the Access policy at it instead. Not required.
- **GitHub Actions minutes:** private repos meter Actions minutes (public was free). The live-sync plan cuts the hourly cron to on-demand + a daily safety net, keeping you well inside the free allotment.
- **Adding crew later:** Zero Trust → Access → Applications → *EpicFiber Maps* → Policies → add their emails. No redeploy needed.
- **Order matters:** do NOT privatize the repo before Phase 2 is verified — on GitHub Free a private repo can't serve Pages at all, and on Pro it would still serve the addresses publicly. Cloudflare Access is what actually makes it private.
