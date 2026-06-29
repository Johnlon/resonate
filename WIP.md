# Work In Progress

Items completed this session and items still open. Pick up from the top of the open list.

---

## Completed this session

- **Option A URL rename** — all URL-typed `_meta.yml` fields renamed with `_url` suffix:
  `datasheet→datasheet_url`, `manu_page→manu_page_url`, `vendor_page→vendor_page_url`,
  `frd/frd_plot→frd_url`, `impedance/impedance_plot→zma_url`, etc.
  Applied across: `MetaModel`, all old + new scrapers, `populate_specs.py`,
  `bundle-drivers.mjs`, `src/core/driver.js`, `dq_check.py`, all docs.

- **4844 `_meta.yml` files migrated** — URL renames applied, orphaned Scan-Speak fields
  (`series`, `datasheet_fields`, `adv_datasheet_fields`, `manu_page_fields`) stripped.
  0 schema errors after migration.

- **Canonical field ordering** — `reorder_meta_for_save()` in `wdr_meta_schema.py` enforces
  fixed group order: source/URLs → quality/curation → classification → status flags →
  `_sources` → `specs`. All 4844 files rewritten. New scrapes write in this order on first
  write.

---

## Open — do these next

### 1. Parts-Express: 1346 WDR files with wrong date format + data quality issues

Root cause: `scripts/scrape_pe.py` (old scraper) used `strftime("%Y-%m-%d")` — **fixed** (now `"%Y%m%d"`).
But the 1346 already-written files still have `DateAdded=2026-06-27` format.
**Action needed**: rerun `scripts/scrapers/scrape_pe.py --refresh` to regenerate all PE files
with the new scraper (which also fixes Sd/Cms data quality issues from the old scraper).

Remaining hard DQ fails (after new-scraper regeneration, these should shrink):

- **458 Vas fails** — 5 are ft³ vs L; 47 have Cms ~1000× too large (PE API data quality);
  406 are smaller discrepancies. New scraper already handles ft³ (× 0.0283168).
- **3 Le fails** (B&C 10CXN64-8 + 2 others) — Le=8.0 H stored; PE API data quality issue.
  New scraper has Le_raw / 1000; likely bad API data.
- **Qts discrepancies** — INFO level only (within tolerance).

### 2. SoundImports: 1649 WDR files with wrong date format + Vas ft³ bug

Root cause A: `scripts/scraper_lib.py` used `%Y-%m-%d` when SoundImports was scraped — fixed
at commit bc222360. Already-written files need regeneration.
Root cause B: `scripts/scrape_soundimports.py` applied `× 1e-3` (L→m³) to ft³ values — **fixed**.
Now detects "ft" in value string and applies `× 28.3168e-3` instead.
The new `scripts/scrapers/scrape_soundimports.py` already had this fix.
**Action needed**: rerun `scripts/scrape_soundimports.py --refresh` to regenerate all SI files.
101 files had ft³ Vas (confirmed from HTML cache scan).

### 3. Dayton Audio scraper: **complete** — 47 WDRs in `drivers/dayton-audio/`

`scripts/scrape_dayton.py` fully rewritten and run (2026-06-30). 47 WDRs written.
32 products skipped (tweeters + buzzers lacking full T/S set — correct behaviour).
Remaining DQ flags (all logged in `_meta.yml dq_issue`):
- Vas discrepancy on DC200-8, DC300-8, DCS165-4, HTS545HE-4, MX15-22, Odeum-18F,
  Odeum-18N, PSS555-8, RSS210HF-4 — published Vas vs calculated from Cms+Sd, ≤10%.
- CE28MB-8: Qes=6.16 above max, Vas discrepancy — Dayton source data inconsistent.
- CE30P-4: Qts discrepancy (0.8 vs calc 0.92), Vas discrepancy — minor rounding.
- CE32A-4: Vas 10× off (page shows "0.15 L", should be "0.015 L") — Dayton page typo.
- CE38M-8: Pe=0.25 W below minimum — tiny driver, correct value per page.

### 4. `winner: "calculated"` source type — document and implement

The specs block supports `winner: "calculated"` for fields WinISD computes from
other T/S parameters (e.g. Vd = Sd × Xmax). Currently `_build_specs_provenance()`
only assigns `winner: <source_key>`. Add logic: if a field is in `_WDR_CALCULATABLE`
and no source has an explicit value, set `winner: "calculated"`.
Document this source key in `WDR_SCHEMA.md` §9 and `_sources` note.

### 5. `winner: "human"` source type — future manual verification path

Plan (not yet implemented): when a human verifies a field value directly against
a datasheet, the entry gets `winner: "human"` and `reviewed_by` is set.
This requires a small interactive tool or script (`verify_field.py`?) that:

1. Opens the cached datasheet PDF.
2. Prompts for the confirmed value.
3. Writes `winner: "human"`, updates `_sources["human"] = "human-reviewed"`,
   sets `reviewed_by` to the reviewer name.

No code written yet. Design approved in principle. Build when needed.

### 6. Enrich script: `driver_type` and `nominal_size_cm` still null for many drivers

Many `_meta.yml` files have `driver_type: null` and `nominal_size_cm: null`.
`enrich_drivers.py` is supposed to extract these from cached HTML. But:

- `_html/` cache may be missing for some collections (run scraper `--refresh` to rebuild).
- Enrichment script may not be running or may have extraction bugs.
  Run `py -3 scripts/enrich_drivers.py --force --collection sb-acoustics` as a test
  and check whether `driver_type` gets populated. Fix the extractor if not.

---

## Reference — architecture decisions made

- `_sources` keys stay as short identifiers (`datasheet`, `manu_page`, `vendor_page`,
  `human`) — they are NOT field names, they are provenance source keys.
- `populate_specs.py --force` is the canonical migration tool. Run it after any
  schema or field-order change.
- `matt/` collection is human-curated — never touch without explicit per-session
  permission.
- All calculation changes require explicit human approval before touching `src/core/`.
