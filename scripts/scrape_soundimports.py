#!/usr/bin/env python3
"""
Scrape SoundImports (soundimports.eu) product pages → WDR files.

SoundImports is a Lightspeed eCom (Webshopapp) store. Product specs are
rendered server-side in <dt>Label</dt><dd>Value</dd> pairs — no JS needed.
NOTE: SI's HTML is malformed — many <dt> tags have no </dt> closing tag;
the regex below handles both forms with an optional (?:</dt>)?.

Usage:
    cd scripts/
    python scrape_soundimports.py                      # all new products
    python scrape_soundimports.py --limit 5            # test run
    python scrape_soundimports.py --refresh            # re-scrape all

The manifest (drivers/soundimports/manifest.json) tracks scraped URLs so
subsequent runs only fetch pages not yet seen.

Sitemap: https://www.soundimports.eu/en/sitemap.xml — 8000+ URLs covering
woofers, tweeters, midrange, passive radiators, and accessories. Only pages
with a speaker driver article number and Fs are written to WDR.
"""

import html as html_module
import json
from pathlib import Path
import re
import sys
import time
from scraper_lib import run_scraper, parse_number, fetch

VENDOR      = "SoundImports"
SITEMAP_URL = "https://www.soundimports.eu/en/sitemap.xml"
OUT_DIR     = str(Path(__file__).resolve().parent.parent / "drivers" / "soundimports")
BASE        = "https://www.soundimports.eu"

# Driver category pages (verified from /en/audio-components/ on 2026-06-24).
# Each URL is the "View all" parent page that includes all subcategories.
# Excluded: Exciters, Bass shakers, Plate amplifiers, Amplifier modules,
#           Single board computers — these have no T/S parameters.
DRIVER_CATEGORIES = [
    f"{BASE}/en/audio-components/woofers/",   # full-range, sub, bass-mid, mid, coaxial, PR
    f"{BASE}/en/audio-components/tweeters/",  # dome, ring-rad, AMT, horn, planar, ribbon, etc.
]
DELAY_S = 0.1

# <dt> label substring (lowercase) → (wdr_key, SI conversion factor)
# Verified against: SB Acoustics SB20FRPC30-8, Purifi PTT5.25X08-NFA-01,
#                   SEAS W18NX003 (2026-06-24).
# Vas: SI publishes in litres → ÷1000 → m³.
# Xmax: SI publishes one-way mm → ÷1000 → m.
# Rms: SI publishes in kg/s — already SI, factor 1.0.
FIELD_MAP = {
    "resonant frequency":             ("Fs",   1.0),    # Hz
    "total q":                        ("Qts",  1.0),
    "electromagnetic q":              ("Qes",  1.0),
    "mechanical q":                   ("Qms",  1.0),
    "dc resistance":                  ("Re",   1.0),    # Ω
    "voice coil inductance":          ("Le",   1e-3),   # mH → H
    "bl product":                     ("BL",   1.0),    # T·m
    "diaphragm mass":                 ("Mms",  1e-3),   # g → kg
    "mechanical compliance":          ("Cms",  1e-3),   # mm/N → m/N
    "surface area of cone":           ("Sd",   1e-4),   # cm² → m²
    "compliance equivalent volume":   ("Vas",  1e-3),   # litres → m³
    "maximum linear excursion":       ("Xmax", 1e-3),   # mm one-way → m
    "mechanical losses":              ("Rms",  1.0),    # kg/s (already SI)
    "power handling":                 ("Pe",   1.0),    # W
    "impedance":                      ("Znom", 1.0),    # Ω — matches "Impedance (Z)"
}



def _collect_urls() -> list[str]:
    """
    Paginate through each driver category listing page and return all product URLs.
    SI pagination: page 1 = /en/audio-components/woofers/
                   page N = /en/audio-components/woofers/pageN.html
    Product links are absolute: href="https://www.soundimports.eu/en/brand-model.html"
    """
    seen: set[str] = set()
    urls: list[str] = []

    for cat_url in DRIVER_CATEGORIES:
        page = 1
        while True:
            url = cat_url if page == 1 else f"{cat_url.rstrip('/')}page{page}.html"
            try:
                html = fetch(url)
            except Exception as e:
                print(f"  [SI] WARN: could not fetch {url}: {e}")
                break

            # Product links: absolute URLs ending in .html that are not category/service pages
            skip = ("/audio-components/", "/brands/", "/blogs/", "/service/",
                    "/collections/", "/page", "/cart", "/checkout")
            for m in re.finditer(
                r'href="(https://www\.soundimports\.eu/en/[a-z0-9][a-z0-9._\-]+\.html)"',
                html, re.I
            ):
                link = m.group(1)
                if not any(s in link for s in skip) and link not in seen:
                    seen.add(link)
                    urls.append(link)

            # Find last page number from pagination links
            page_nums = [int(m) for m in re.findall(
                r'soundimports\.eu/en/audio-components/[^"]+?page(\d+)\.html', html
            )]
            last_page = max(page_nums) if page_nums else 1

            print(f"  [SI] {cat_url.split('/')[-2]}: page {page}/{last_page} "
                  f"({len(urls)} total so far)")
            if page >= last_page:
                break
            page += 1
            time.sleep(DELAY_S * 0.5)

    return urls


def _extract_specs(html: str) -> dict[str, str]:
    """
    Extract <dt>Label</dt><dd>Value</dd> pairs.
    Handles SI's malformed HTML where many <dt> tags lack a closing </dt>.
    Also decodes HTML entities in both label and value.
    """
    specs: dict[str, str] = {}
    pattern = re.compile(
        r"<dt[^>]*>([\s\S]*?)(?:</dt>)?\s*<dd[^>]*>([\s\S]*?)</dd>", re.I
    )
    for m in pattern.finditer(html):
        label = html_module.unescape(
            re.sub(r"<[^>]+>", "", m.group(1))
        ).replace("\xa0", " ").strip()
        value = html_module.unescape(
            re.sub(r"<[^>]+>", "", m.group(2))
        ).replace("\xa0", " ").strip()
        if label and value:
            specs[label] = value
    return specs


def _extract_category(html: str) -> str:
    """
    Extract product category from JSON-LD BreadcrumbList (position 3).
    Example: position 3 = {"name": "Tweeters"} → "Tweeters".
    Falls back to "Show all <Category>" link text if JSON-LD is absent.
    Verified against SI tweeter page (2026-06-24): position 2 = Audio components,
    position 3 = Tweeters.
    """
    # JSON-LD: "position": 3 , "item": { ... "name": "Tweeters" }
    m = re.search(
        r'"position"\s*:\s*3\s*,\s*"item"\s*:\s*\{[^}]*?"name"\s*:\s*"([^"]+)"',
        html, re.S
    )
    if m:
        return m.group(1)
    # Fallback: <a ...>Show all Tweeters</a>
    m = re.search(r"Show all ([A-Z][a-zA-Z &/\-]+)", html)
    if m:
        return m.group(1).strip()
    return ""


def parse_product(html: str, url: str) -> dict | None:
    category = _extract_category(html)
    specs_raw = _extract_specs(html)

    # Article number is the manufacturer model code
    model = (specs_raw.get("Article number")
             or specs_raw.get("Article Number")
             or specs_raw.get("Artikelnummer")
             or "").strip()
    if not model:
        return {"skip": True, "category": category} if category else None

    # Brand: H1 is "<span>Brand</span> ArticleNumber Description"
    # Strip all tags from H1, then take everything before the article number.
    h1_m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", html, re.I)
    h1_text = html_module.unescape(
        re.sub(r"<[^>]+>", "", h1_m.group(1))
    ).strip() if h1_m else ""

    if model in h1_text:
        brand = h1_text[:h1_text.index(model)].strip()
    else:
        # Fallback: derive from URL slug — "sb-acoustics-sb20frpc30-8" → "Sb Acoustics"
        slug = url.rstrip("/").split("/")[-1].replace(".html", "")
        model_slug = re.sub(r"[^a-z0-9]", "-", model.lower())
        brand_slug = re.sub(re.escape(model_slug) + r".*$", "", slug).strip("-")
        brand = " ".join(w.capitalize() for w in brand_slug.split("-"))

    if not brand:
        return {"skip": True, "category": category}

    # Map labels → WDR fields with SI conversions.
    # Some brands publish Mms in kg, Cms in µm/N, or Sd in m² rather than
    # the assumed g/mm·N⁻¹/cm² — detect the unit in the value string and
    # override the default conversion factor where needed.
    fields: dict[str, float] = {}
    for label, value_str in specs_raw.items():
        label_l = label.lower()
        for fragment, (key, default_factor) in FIELD_MAP.items():
            if fragment in label_l:
                val = parse_number(value_str)
                if val is None or key in fields:  # first match wins (RMS before max)
                    break
                v = value_str.lower()
                if key == "Mms":
                    factor = 1.0 if "kg" in v else 1e-3        # kg already SI; else g→kg
                elif key == "Cms":
                    if "µm" in value_str or "um/" in v or "μm" in v:
                        factor = 1e-6                           # µm/N → m/N
                    elif "mm" in v:
                        factor = 1e-3                           # mm/N → m/N
                    else:
                        factor = default_factor
                elif key == "Sd":
                    # "0,038 m²" → already m²; "216 cm2" → need ×1e-4
                    if "cm" not in v:
                        factor = 1.0                            # published in m²
                    else:
                        factor = 1e-4                           # cm² → m²
                else:
                    factor = default_factor
                fields[key] = round(val * factor, 9)
                break

    if not fields.get("Fs"):
        return {"skip": True, "category": category}  # product but not a driver

    # PDF / measurement file links
    pdf_matches = re.findall(r'"(https?://[^"]+\.pdf)"', html, re.I)
    pdf_url = pdf_matches[0] if pdf_matches else None
    extra = re.findall(r'"(https?://[^"]+\.(frd|zma|zip|txt))"', html, re.I)

    return {
        "brand":        brand,
        "model":        model,
        "manufacturer": brand,
        "provided_by":  "SoundImports (scraped via soundimports.eu)",
        "fields":       fields,
        "pdf_url":      pdf_url,
        "extra_links":  [lnk[0] for lnk in extra],
    }


def url_filter(url: str) -> bool:
    """
    Fast pre-filter applied before fetching any page.
    Drops navigation/service pages (no HTTP fetch needed).
    Brand-slug exclusions (e.g. 'audyn-', 'arylic-') are maintained in
    drivers/soundimports/excluded_brands.json — generated by build_exclusions.py
    after a full scan so future runs skip known-accessory brands instantly.
    """
    if not url.endswith(".html"):
        return False
    skip_paths = ("/audio-components/", "/brands/", "/blogs/", "/service/",
                  "/collections/", "/page", "/sitemap", "/cart", "/checkout")
    if any(s in url for s in skip_paths):
        return False
    slug = url.rstrip("/").split("/")[-1]
    for prefix in _EXCLUDED_SLUG_PREFIXES:
        if slug.startswith(prefix):
            return False
    return True


# Learned brand-slug prefixes that are 100% non-driver pages.
# Generated by build_exclusions.py after a full scan; empty on first run.
_excl_path = Path(__file__).parent.parent / "drivers" / "soundimports" / "excluded_brands.json"
_EXCLUDED_SLUG_PREFIXES: list[str] = (
    json.loads(_excl_path.read_text(encoding="utf-8")) if _excl_path.exists() else []
)


if __name__ == "__main__":
    # Default: full sitemap scan — exhaustive, builds the manifest.
    # Subsequent runs are fast: manifested URLs skipped without fetching,
    # known-accessory slug prefixes fast-failed before any HTTP request.
    # Pass --categories-only to crawl only driver category pages (faster refresh).
    if "--categories-only" in sys.argv:
        sys.argv.remove("--categories-only")
        url_source = _collect_urls
    else:
        url_source = SITEMAP_URL
    run_scraper(VENDOR, url_source, parse_product, OUT_DIR,
                url_filter=url_filter, delay_s=DELAY_S)
