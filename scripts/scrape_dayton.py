#!/usr/bin/env python3
"""
Scrape Dayton Audio product pages → WDR files + PDF datasheets.

Usage:
    python scrape_dayton.py [--out-dir drivers/dayton-audio] [--limit N] [--refresh]

Sitemap: https://www.dayton-audio.com/sitemap.xml (Shopify, 5 sub-sitemaps)
Product URL pattern: https://www.dayton-audio.com/products/{slug}

NOTE: HTML structure not yet verified. Run with --limit 3 first, inspect
      drivers/dayton-audio/_html/ to confirm field labels, then update FIELD_MAP.
"""

import re
from pathlib import Path
from scraper_lib import run_scraper, parse_number

VENDOR      = "Dayton Audio"
SITEMAP_URL = "https://www.dayton-audio.com/sitemap.xml"
OUT_DIR     = str(Path(__file__).resolve().parent.parent / "drivers" / "dayton-audio")

# TODO: verify label text against actual Shopify product page HTML in _html/
FIELD_MAP = {
    "resonant frequency":    ("Fs",   1.0),
    "total q":               ("Qts",  1.0),
    "electrical q":          ("Qes",  1.0),
    "mechanical q":          ("Qms",  1.0),
    "dc resistance":         ("Re",   1.0),
    "voice coil inductance": ("Le",   1e-3),   # mH → H
    "bl product":            ("BL",   1.0),    # BL not Bl
    "moving mass":           ("Mms",  1e-3),   # g → kg
    "compliance":            ("Cms",  1e-3),   # mm/N → m/N
    "effective piston area": ("Sd",   1e-4),   # cm² → m²
    "equivalent volume":     ("Vas",  1e-3),   # litres → m³
    "one-way linear":        ("Xmax", 1e-3),   # mm one-way → m  (Dayton uses one-way)
    "power handling":        ("Pe",   1.0),
    "impedance":             ("Znom", 1.0),    # Znom not Z
}


def parse_product(html: str, url: str) -> dict | None:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    name = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else url.rstrip("/").split("/")[-1]

    # Shopify product pages often put specs in a table or metafield list
    fields: dict[str, float] = {}

    # Try <tr> table rows
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

    # Also try <li> items (some Shopify themes use lists)
    for li_raw in re.findall(r"<li>(.*?)</li>", html, re.S | re.I):
        text = re.sub(r"<[^>]+>", "", li_raw).strip()
        for fragment, (key, factor) in FIELD_MAP.items():
            if fragment in text.lower() and key not in fields:
                val = parse_number(text)
                if val is not None:
                    fields[key] = round(val * factor, 9)
                break

    if not fields.get("Fs"):
        return None

    pdf_matches = re.findall(r'"(https://[^"]+\.pdf)"', html, re.I)
    pdf_url = next((p for p in pdf_matches if "dayton" in p.lower()), None)

    extra = re.findall(r'"(https://[^"]+\.(frd|zma|zip|txt))"', html, re.I)

    # Extract model from URL slug: dayton-audio-ds115-8 → DA-DS115-8
    # Dayton Audio slugs are kebab-case; last segment is model-like
    slug_part = url.rstrip("/").split("/")[-1]
    # Strip leading vendor slug (dayton-audio-) if present
    slug_part = re.sub(r'^dayton[-_]audio[-_]', '', slug_part, flags=re.I)
    # Uppercase and replace hyphens as-is for model
    model = slug_part.upper()

    return {
        "brand":         "Dayton Audio",
        "model":         model,
        "manufacturer":  "Dayton Audio",
        "provided_by":   f"Dayton Audio website (scraped {__import__('datetime').date.today()})",
        "fields":        fields,
        "datasheet_url":   pdf_url,
        "extra_links":   [l[0] for l in extra],
    }


def url_filter(url: str) -> bool:
    return "/products/" in url and url.count("/") >= 4


if __name__ == "__main__":
    run_scraper(VENDOR, SITEMAP_URL, parse_product, OUT_DIR,
                url_filter=url_filter)
