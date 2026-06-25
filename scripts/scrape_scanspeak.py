#!/usr/bin/env python3
"""
Scrape Scan-Speak product pages → WDR files + PDF datasheets.

Usage:
    python scrape_scanspeak.py [--out-dir drivers/scan-speak] [--limit N] [--refresh]

Sitemap: https://www.scan-speak.dk/sitemap.xml (WooCommerce, 7 sub-sitemaps)
Product URL pattern: https://www.scan-speak.dk/product/{slug}/

NOTE: HTML structure not yet verified. Run with --limit 3 first, inspect
      drivers/scan-speak/_html/ to confirm field labels, then update FIELD_MAP.
"""

import re
from pathlib import Path
from scraper_lib import run_scraper, parse_number

VENDOR      = "Scan-Speak"
SITEMAP_URL = "https://www.scan-speak.dk/sitemap.xml"
OUT_DIR     = str(Path(__file__).resolve().parent.parent / "drivers" / "scan-speak")

# TODO: verify label text against actual page HTML in _html/ before relying on these
FIELD_MAP = {
    "resonance frequency":   ("Fs",   1.0),
    "total q":               ("Qts",  1.0),
    "electrical q":          ("Qes",  1.0),
    "mechanical q":          ("Qms",  1.0),
    "dc resistance":         ("Re",   1.0),
    "voice coil inductance": ("Le",   1e-3),   # mH → H
    "force factor":          ("Bl",   1.0),
    "moving mass":           ("Mms",  1e-3),   # g → kg
    "compliance":            ("Cms",  1e-3),   # mm/N → m/N
    "piston area":           ("Sd",   1e-4),   # cm² → m²
    "equivalent volume":     ("Vas",  1e-3),   # litres → m³
    "excursion":             ("Xmax", 0.5e-3), # mm p-p → m one-way
    "power":                 ("Pe",   1.0),
    "nominal impedance":     ("Z",    1.0),
}


def parse_product(html: str, url: str) -> dict | None:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    name = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else url.rstrip("/").split("/")[-1]

    # WooCommerce typically puts specs in a table or dl — try both
    fields: dict[str, float] = {}

    # Try <li> items
    for li_raw in re.findall(r"<li>(.*?)</li>", html, re.S | re.I):
        text = re.sub(r"<[^>]+>", "", li_raw).strip()
        for fragment, (key, factor) in FIELD_MAP.items():
            if fragment in text.lower():
                val = parse_number(text)
                if val is not None:
                    fields[key] = round(val * factor, 9)
                break

    # Try <tr><td> table rows
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)
        if len(cells) < 2:
            continue
        label = re.sub(r"<[^>]+>", "", cells[0]).strip().lower()
        value_text = re.sub(r"<[^>]+>", "", cells[1]).strip()
        for fragment, (key, factor) in FIELD_MAP.items():
            if fragment in label:
                val = parse_number(value_text)
                if val is not None:
                    fields[key] = round(val * factor, 9)
                break

    if not fields.get("Fs"):
        return None

    pdf_matches = re.findall(r'"(https://[^"]+\.pdf)"', html, re.I)
    pdf_url = next((p for p in pdf_matches if "scan-speak" in p), None)

    extra = re.findall(r'"(https://[^"]+\.(frd|zma|zip|txt))"', html, re.I)

    return {
        "name":        name,
        "fields":      fields,
        "pdf_url":     pdf_url,
        "extra_links": [l[0] for l in extra],
    }


def url_filter(url: str) -> bool:
    return "/product/" in url and "/product-category/" not in url


if __name__ == "__main__":
    run_scraper(VENDOR, SITEMAP_URL, parse_product, OUT_DIR,
                url_filter=url_filter)
