# Commodity Capital Cycle — auto-refreshing dashboard

A seven-model commodity research dashboard that rebuilds itself from public data
on a schedule and publishes to GitHub Pages.

| Tab | Model | Refreshes automatically |
|---|---|---|
| Supply + Demand | Capital cycle (QFR) + growth/liquidity | ✅ |
| Supply · capex cycle | Capex/Assets, inverted, read forward | ✅ |
| Demand · lead index | Global growth LEI + China credit impulse | ⚠️ partly (see below) |
| Fin. conditions · lead | Growth-tax composite (dollar, commodities, rates) | ✅ |
| Contango · carry | Energy term structure | ❌ static snapshot |
| Positioning · money managers | CFTC managed money | ✅ |
| Positioning · speculative | CFTC non-commercial | ✅ |

---

## Setup — 6 steps

### 1. Create the repository

```bash
# from the unzipped folder
git init
git add .
git commit -m "Commodity capital cycle dashboard"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

The repo can be public or private. GitHub Pages on private repos requires a paid plan;
if you're on Free, either make the repo public or skip the Pages job and just read
`site/index.html` from the repo.

### 2. Get a FRED API key

Free, instant: <https://fredaccount.stlouisfed.org/apikeys>. It's a 32-character string.

### 3. Add the key as a repository secret

Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

- Name: `FRED_API_KEY`
- Value: your key

**Do not commit the key to the repo.** The scripts read it from the environment only.
If a key has ever been committed anywhere, revoke and reissue it.

### 4. Enable GitHub Pages

Repo → **Settings** → **Pages** → **Source: GitHub Actions**.
(Not "Deploy from a branch" — this workflow publishes via the Actions pipeline.)

### 5. Enable write permissions for Actions

Repo → **Settings** → **Actions** → **General** → **Workflow permissions** →
select **Read and write permissions** → Save.
This lets the workflow commit refreshed payloads back to the repo.

### 6. Run it once by hand

Repo → **Actions** → **Refresh dashboards** → **Run workflow**.

First run takes 3–6 minutes. When it's green, your dashboard is live at
`https://<you>.github.io/<repo>/`.

---

## Schedule

Defined in `.github/workflows/refresh.yml`:

- **Saturday 02:00 UTC** — the important one; CFTC COT publishes Friday ~20:30 UTC.
- **Wednesday 02:00 UTC** — catch-up for monthly releases (IMF, OECD, BIS, Census QFR).
- **Manual** — the *Run workflow* button, any time.

To change it, edit the `cron` lines (they are UTC). Melbourne is UTC+10/+11, so
`0 2 * * 6` UTC is Saturday lunchtime your time.

> GitHub disables scheduled workflows in repos with no activity for 60 days.
> A manual run or any commit re-arms it.

---

## How the refresh works

Each dashboard is a self-contained HTML file with one JSON payload assigned to a JS
variable. Refreshing never touches the dashboard's code — it only swaps the payload:

```
extract payload  ->  recompute series from live sources  ->  inject payload back
```

`scripts/common.py` holds the extractor/injector plus FRED, Yahoo and transform helpers.
`scripts/refresh_all.py` runs every model, then `build_combined.py` embeds all seven
dashboards base64 into isolated iframes in `site/index.html`.

**Failure isolation:** if one source is down, the other models still refresh and publish.
The run only fails if *every* refresh failed, or the rendered page fails verification.

**Verification gate:** `scripts/verify_site.py` opens the built page in headless Chromium
and fails the build if any tab renders zero charts or throws a console error — so a bad
payload never reaches the live site.

### Methodology notes worth knowing

- **Positioning** is *appended*, not regenerated, so validated history is never rewritten.
  The formulas were reverse-engineered against the full baked history to a mean absolute
  error of 0.00: managed money = `sum(long−short)/sum(long+short)` (disaggregated,
  futures-only); non-commercial = `sum(long−short)/sum(open interest)` (legacy,
  futures-only). Both unweighted; the `weights` block drives only the price overlay.
- **Supply** reconstructs capex from the Census QFR balance sheet
  (`ΔNet PP&E + depreciation`) because multi-decade Capex/Assets isn't published directly.
  QFR is quarterly, so this only moves ~4 times a year.
- **FCI** legs are deviations from a 36-month moving average (the *level* of tightness
  leads; raw YoY changes are coincident), standardised and inverted so high = loose.

---

## Known limits — read before trusting a green run

1. **The demand model's growth LEI is a static input.**
   `data/international-growth-leading-indicators.html` is a build artefact of the separate
   six-country growth-LEI project. The China credit impulse, OECD CLIs, Korea exports and
   the price targets all refresh live, but the LEI block moves only when you re-export that
   file from its own project and drop the new copy into `data/`. Same filename, commit, done.

2. **The contango dashboard is a static snapshot.**
   It was built elsewhere and has no pipeline here, so it publishes as-is. To automate it,
   add `scripts/refresh_contango.py` following the same extract/recompute/inject pattern
   and register it in `refresh_all.py`'s `STEPS` list.

3. **The positioning price overlay drifts slightly.**
   New weeks chain off Yahoo's roll-adjusted continuous futures rather than raw front
   prices, so the notional overlay can drift ~1–2% from the original method. The
   positioning series itself — the actual signal — is exact.

4. **Yahoo is unofficial.** It occasionally rate-limits or changes shape. The helpers retry
   with backoff; a persistent failure shows up in the run summary rather than silently
   publishing stale numbers.

5. **Standardisation is full-sample**, so z-scores of the distant past shift very slightly
   as new data arrives. That's inherent to the method, not a bug in the refresh.

---

## Local development

```bash
pip install -r requirements.txt
export FRED_API_KEY=your_key_here          # Windows: set FRED_API_KEY=...
python scripts/refresh_all.py              # refresh everything + build site/
python -m http.server -d site 8000         # open http://localhost:8000
```

Run a single model: `python scripts/refresh_fci.py` (scripts import each other by name,
so run them from inside `scripts/`, or `python -m scripts.refresh_fci` from the root).

---

## Adding another model

1. Drop the self-contained HTML into `dashboards/`.
2. Write `scripts/refresh_<name>.py` using the extract → recompute → inject pattern.
3. Add it to `STEPS` in `refresh_all.py` and to `TABS` in `build_combined.py`.

---

*Independent reconstructions for research use. Frameworks after Variant Perception, GMI /
Alpine Macro and 3Fourteen; not affiliated with or endorsed by any of them. Built from
public data (Census QFR, IMF, BIS, OECD, CFTC, market data). Not investment advice.*
