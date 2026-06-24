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
import re
from scraper_lib import run_scraper, parse_number

VENDOR      = "SoundImports"
SITEMAP_URL = "https://www.soundimports.eu/en/sitemap.xml"
OUT_DIR     = "drivers/soundimports"

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


def parse_product(html: str, url: str) -> dict | None:
    specs_raw = _extract_specs(html)

    # Article number is the manufacturer model code
    model = (specs_raw.get("Article number")
             or specs_raw.get("Article Number")
             or specs_raw.get("Artikelnummer")
             or "").strip()
    if not model:
        return None

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
        # Remove model slug from end of URL slug to get brand portion
        brand_slug = re.sub(re.escape(model_slug) + r".*$", "", slug).strip("-")
        brand = " ".join(w.capitalize() for w in brand_slug.split("-"))

    if not brand:
        return None

    # Map labels → WDR fields with SI conversions
    fields: dict[str, float] = {}
    for label, value_str in specs_raw.items():
        label_l = label.lower()
        for fragment, (key, factor) in FIELD_MAP.items():
            if fragment in label_l:
                val = parse_number(value_str)
                if val is not None:
                    fields[key] = round(val * factor, 9)
                break

    if not fields.get("Fs"):
        return None  # skip pages with no resonant frequency

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
    """Keep product .html pages; drop categories, blogs, service, brand pages."""
    if not url.endswith(".html"):
        return False
    skip = ("/audio-components/", "/brands/", "/blogs/", "/service/",
            "/collections/", "/page", "/sitemap", "/cart", "/checkout")
    return not any(s in url for s in skip)


if __name__ == "__main__":
    run_scraper(VENDOR, SITEMAP_URL, parse_product, OUT_DIR,
                url_filter=url_filter, delay_s=0.5)
