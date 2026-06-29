"""
scrape_pe.py — Parts Express driver catalog scraper

Fetches T/S data from the Parts Express internal JSON API and writes
WDR + _meta.yml sidecar pairs to drivers/parts-express/.

API: GET https://www.parts-express.com/api/items
     ?q={brand}&fieldset=details&offset={N}&limit=50
     NetSuite SuiteCommerce Advanced REST API — no auth required.

Usage:
  python scrape_pe.py                         # add new, skip existing
  python scrape_pe.py --refresh               # re-scrape all brands
  python scrape_pe.py --limit 20              # first N new items only
  python scrape_pe.py --workers 4             # parallel brand fetches
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='ascii', errors='replace')

import argparse, json, re, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml

# Import shared schema/DQ/manifest helpers from scraper_lib
sys.path.insert(0, str(Path(__file__).parent))
from scraper_lib import to_wdr, check_fields, safe_filename, load_manifest, save_manifest

VENDOR    = "Parts Express"
OUT_DIR   = Path(__file__).parent.parent / "drivers" / "parts-express"
API_URL   = "https://www.parts-express.com/api/items"
DELAY_S   = 0.1
DEFAULT_DELAY_S = 0.1

BRANDS = [
    "Aurum Cantus", "B&C Speakers", "Beston", "Beyma", "Celestion",
    "Ciare", "Coast Buyouts", "CSS", "Dayton Audio", "Eminence Speaker",
    "EPIQUE by Dayton Audio", "Factory Buyouts", "FaitalPRO", "Fountek",
    "Goldwood", "GRS", "HiVi", "JBL Professional", "Lavoce", "Morel",
    "Peerless by Tymphany", "PRV Audio", "Pyramid", "Quam", "Selenium",
    "Tang Band", "Tectonic", "Timpano Audio", "Visaton", "Wavecor",
]

INCLUDE_CATS = {
    "Woofers", "Subwoofer Drivers", "Tweeters",
    "Midrange / Midbass Drivers & Full-Range Speakers",
    "Planar / Ribbon Transducers", "Passive Radiators",
    "Car Audio Tweeters", "Car Audio Midbass Speakers",
    "Car Subwoofer Speakers",
    "Pro Woofers, Subwoofers & Midrange Speakers",
    "Horn Loaded Tweeters & Midranges", "Horn Drivers",
    "Pro Coaxial Full-Range Speakers",
}


# ── Unit conversions: API → SI ────────────────────────────────────────────────

def _safe(v):
    """Return float or None."""
    try:
        f = float(v)
        return f if f == f else None   # NaN guard
    except (TypeError, ValueError):
        return None

def _parse_item(it):
    """Map one PE API item dict → fields dict in SI units."""
    def g(key): return _safe(it.get(key))

    Fs   = g("custitem_pe_resonant_frequency_fs")
    Qts  = g("custitem_pe_total_q_qts")
    Qes  = g("custitem_pe_electromagnetic_q_qes")
    Qms  = g("custitem_pe_mechanical_q_qms")
    Re   = g("custitem_pe_dc_resistance_re")
    Znom = g("custitem_pe_impedance")
    Pe   = g("custitem_pe_power_handling_rms")
    BL   = g("custitem_pe_bl_product_bl")

    Le_raw = g("custitem_pe_voice_coil_inductance_le")
    Le = Le_raw / 1000 if Le_raw is not None else None          # mH → H

    Mms_raw = g("custitem_pe_diaphragm_mass_airload")
    Mms = Mms_raw / 1000 if Mms_raw is not None else None       # g → kg

    Sd_raw = g("custitem_pe_surface_area_of_cone_sd")
    Sd = Sd_raw / 10000 if Sd_raw is not None else None         # cm² → m²

    Vas_raw = g("custitem_pe_compliance_equiv_volume")
    Vas = Vas_raw * 0.0283168 if Vas_raw is not None else None  # ft³ → m³

    Xmax_raw = g("custitem_pe_max_linear_excursion")
    Xmax = Xmax_raw / 1000 if Xmax_raw is not None else None    # mm one-way → m

    # Cms: reject implausible values ≥ 100 mm/N (API bug — kHz parsing error)
    Cms_raw = g("custitem_pe_mech_comp_suspension")
    Cms = Cms_raw / 1000 if (Cms_raw is not None and Cms_raw < 100) else None  # mm/N → m/N

    # Rms: derived from T/S identity Qms = 2π·Fs·Mms / Rms
    Rms = (2 * 3.141592653589793 * Fs * Mms / Qms
           if (Fs and Mms and Qms) else None)

    fields = {}
    for k, v in [
        ("Fs", Fs), ("Qts", Qts), ("Qes", Qes), ("Qms", Qms),
        ("Re", Re), ("Le", Le), ("BL", BL), ("Mms", Mms), ("Cms", Cms),
        ("Rms", Rms), ("Sd", Sd), ("Vas", Vas), ("Xmax", Xmax),
        ("Znom", Znom), ("Pe", Pe),
    ]:
        if v is not None:
            fields[k] = v
    return fields


def _fetch_brand(brand, delay_s=DELAY_S, cache_dir=None):
    """Fetch all API pages for one brand; return list of item dicts.
    Caches each page as JSON in cache_dir/_json/ so re-runs skip the network."""
    items, offset = [], 0
    while True:
        params = urllib.parse.urlencode({
            "q": brand, "fieldset": "details",
            "offset": offset, "limit": 50,
        })
        cache_file = None
        if cache_dir:
            safe_brand = re.sub(r"[^\w\-]", "_", brand)
            cache_file = cache_dir / f"{safe_brand}_{offset:04d}.json"

        if cache_file and cache_file.exists():
            data = json.loads(cache_file.read_text(encoding="utf-8"))
        else:
            req = urllib.request.Request(
                f"{API_URL}?{params}",
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode()
            data = json.loads(raw)
            if cache_file:
                cache_file.write_text(raw, encoding="utf-8")
            time.sleep(delay_s)

        page = data.get("items", [])
        items.extend(page)
        if len(items) >= (data.get("total") or 0) or not page:
            break
        offset += 50
    return items


# ── Main ──────────────────────────────────────────────────────────────────────

def ts():
    return datetime.now().strftime("%H:%M:%S")


def main():
    parser = argparse.ArgumentParser(description="Scrape Parts Express → WDR files")
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    parser.add_argument("--limit", type=int, default=0,
                        help="Max new items to write (0 = all)")
    parser.add_argument("--refresh", action="store_true",
                        help="Re-scrape all items, not just new ones")
    parser.add_argument("--workers", type=int, default=4,
                        help="Parallel brand fetch workers (default 4)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_S)
    args = parser.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_cache = out / "_html"   # named _html for consistency with other scrapers
    json_cache.mkdir(exist_ok=True)
    manifest = load_manifest(out)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    start = datetime.now()

    # ── Collect all items from API (using JSON cache) ─────────────────────────
    print(f"[{ts()}] [{VENDOR}] Fetching {len(BRANDS)} brands from API ...", flush=True)

    all_items = []
    seen_ids = set()

    def fetch_one_brand(brand):
        try:
            items = _fetch_brand(brand, args.delay, cache_dir=json_cache)
            print(f"[{ts()}]   {brand}: {len(items)} items", flush=True)
            return items
        except Exception as e:
            print(f"[{ts()}]   {brand}: ERROR {e}", flush=True)
            return []

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for brand_items in ex.map(fetch_one_brand, BRANDS):
            for it in brand_items:
                iid = it.get("itemid")
                if iid and iid not in seen_ids:
                    seen_ids.add(iid)
                    all_items.append(it)

    print(f"[{ts()}] [{VENDOR}] {len(all_items)} unique items from API", flush=True)

    # ── Filter ────────────────────────────────────────────────────────────────
    drivers = [
        it for it in all_items
        if it.get("custitem_itemcategoryfacet") in INCLUDE_CATS
        and it.get("custitem_pe_resonant_frequency_fs")
    ]
    print(f"[{ts()}] [{VENDOR}] {len(drivers)} with T/S data in driver categories", flush=True)

    already_scraped = set(manifest.get("scraped", {}).keys())
    if not args.refresh:
        to_write = [it for it in drivers
                    if it.get("itemid") not in already_scraped]
    else:
        to_write = drivers
    print(f"[{ts()}] [{VENDOR}] {len(to_write)} new (not yet scraped)", flush=True)

    if args.limit:
        to_write = to_write[:args.limit]

    # ── Write WDRs ────────────────────────────────────────────────────────────
    ok = dq_warned = skipped = 0
    total = len(to_write)

    for i, it in enumerate(to_write, 1):
        brand = it.get("custitem_pe_brand", "")
        display = it.get("storedisplayname2") or it.get("itemid", "")
        model = display[len(brand)+1:] if display.startswith(brand + " ") else display
        sku = it.get("itemid", "")
        urlcomp = it.get("urlcomponent", "")
        url = f"https://www.parts-express.com/{urlcomp}" if urlcomp else ""

        # PE pedocs URLs (datasheet, FRD) require product-page HTML scraping to derive
        # correctly — the slug and trailing ID in pedocs/specs/ and pedocs/tech-docs/
        # paths are not predictable from the API response. Leave null; use
        # backfill_pe_frd.py to populate from cached product HTML.
        pdf_url = ""
        frd_url = ""

        fields = _parse_item(it)

        # DQ check
        for rule_id, desc, detail in check_fields(fields):
            print(f"[{ts()}]   [{i}/{total}] {model} DQ {rule_id}: {detail} — {desc}", flush=True)
            dq_warned += 1

        wdr_text = to_wdr(
            brand=brand, model=model,
            fields=fields,
            provided_by=f"Parts Express (fetched {today})",
            comment=f"Source: {url}" + (f" | Datasheet: {pdf_url}" if pdf_url else ""),
            manufacturer=brand,
            date_added=today, date_modified=today,
        )
        wdr_name = safe_filename(f"{brand} {model}".strip())
        (out / wdr_name).write_text(wdr_text, encoding="utf-8")

        meta = {
            "quality": "M",
            "issue": "scraped_not_human_verified",
            "detail": (f"Automatically scraped from Parts Express API. "
                       "T/S parameters have not been verified by a human against the datasheet."),
            "corrections": None,
            "reviewed_by": None,
            "datasheet_url": pdf_url or None,
            "manu_page_url": None,
            "vendor_page_url": url or None,
            "source": url or None,
            "frd_url": frd_url or None,
            "zma_url": None,
            "obsolete": None,
            "dq_issue": None,
            "community": None,
            "fetched_sku": None,
        }
        (out / wdr_name.replace(".wdr", "_meta.yml")).write_text(
            yaml.dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

        manifest.setdefault("scraped", {})[it.get("itemid", wdr_name)] = {
            "file": wdr_name, "status": "ok"
        }
        ok += 1
        print(f"[{ts()}]   [{i}/{total}] {brand} {model} OK", flush=True)

        if i % 50 == 0:
            save_manifest(out, manifest)
        if i % 100 == 0:
            elapsed = (datetime.now() - start).seconds
            pct = 100 * i // total
            print(f"[{ts()}] [{VENDOR}] {i}/{total} ({pct}%) — {ok} WDRs, {dq_warned} DQ warnings — {elapsed}s", flush=True)

    save_manifest(out, manifest)
    elapsed = (datetime.now() - start).seconds
    print(f"\n[{ts()}] [{VENDOR}] Done: {ok} WDRs written, {dq_warned} DQ warnings — {elapsed}s", flush=True)
    print(f"  Output: {out.resolve()}", flush=True)


if __name__ == "__main__":
    main()
