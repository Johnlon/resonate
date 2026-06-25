#!/usr/bin/env python3
"""
Scrape Wavecor product pages → WDR files + PDF datasheets + SPL/impedance TXT files.

Usage:
    python scrape_wavecor.py [--out-dir drivers/wavecor] [--limit N] [--refresh]

URL patterns (verified 2026-06-24):
  HTML:  http://www.wavecor.com/html/{model}.html
  PDF:   https://www.wavecor.com/Driver%20specifications%20PDF/{MODEL}_specifications.pdf
  SPL:   https://www.wavecor.com/Driver%20measurements%20TXT/SPL%20response/{MODEL}_SPL_response.txt
  Imp:   https://www.wavecor.com/Driver%20measurements%20TXT/Impedance%20response/{MODEL}_impedance_response.txt

Note: sitemap TXT entries use %20 in filenames — incorrect. Working URLs use underscores.
"""

import re
import urllib.parse
from scraper_lib import run_scraper, parse_number, fetch_binary
from pathlib import Path

VENDOR      = "Wavecor"
SITEMAP_URL = "http://www.wavecor.com/sitemap.xml"
OUT_DIR     = str(Path(__file__).resolve().parent.parent / "drivers" / "wavecor")

# HTML table row label (lowercase) → (wdr_key, SI conversion factor)
# Labels observed in Wavecor product HTML tables.
FIELD_MAP = {
    "resonance frequency":   ("Fs",   1.0),    # Hz
    "total q":               ("Qts",  1.0),
    "electrical q":          ("Qes",  1.0),
    "mechanical q":          ("Qms",  1.0),
    "dc resistance":         ("Re",   1.0),    # Ω
    "voice coil inductance": ("Le",   1e-3),   # mH → H
    "force factor":          ("BL",   1.0),    # T·m — BL not Bl
    "moving mass":           ("Mms",  1e-3),   # g → kg
    "mechanical compliance": ("Cms",  1e-3),   # mm/N → m/N
    "piston area":           ("Sd",   1e-4),   # cm² → m²
    "equivalent volume":     ("Vas",  1e-3),   # litres → m³
    "maximum excursion":     ("Xmax", 0.5e-3), # mm p-p → m one-way
    "power handling":        ("Pe",   1.0),    # W
    "nominal impedance":     ("Znom", 1.0),    # Ω — Znom not Z
}


def _model_from_url(url: str) -> str:
    """Extract model string from URL, e.g. wf146wa01_02 → WF146WA01_02"""
    slug = url.rstrip("/").split("/")[-1]
    slug = re.sub(r"\.html$", "", slug, flags=re.I)
    return slug.upper()


def parse_product(html: str, url: str) -> dict | None:
    # Product name from <title> or <h1>
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    if not m:
        m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    name = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else _model_from_url(url)

    # T/S params: Wavecor pages use an HTML table with two-column rows
    # <tr><td>Label</td><td>value unit</td></tr>
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I)
    fields: dict[str, float] = {}
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)
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

    model = _model_from_url(url)

    # PDF datasheet URL (HTTPS, underscores in filename)
    pdf_url = (f"https://www.wavecor.com/Driver%20specifications%20PDF/"
               f"{model}_specifications.pdf")

    # Measurement TXT files (directory uses %20, filename uses underscores)
    spl_url = (f"https://www.wavecor.com/Driver%20measurements%20TXT/"
               f"SPL%20response/{model}_SPL_response.txt")
    imp_url = (f"https://www.wavecor.com/Driver%20measurements%20TXT/"
               f"Impedance%20response/{model}_impedance_response.txt")

    return {
        "brand":         "Wavecor",
        "model":         model,
        "manufacturer":  "Wavecor",
        "provided_by":   f"Wavecor website (scraped {__import__('datetime').date.today()})",
        "fields":        fields,
        "pdf_url":       pdf_url,
        "extra_links":   [spl_url, imp_url],
    }


def url_filter(url: str) -> bool:
    return "/html/" in url and url.endswith(".html")


if __name__ == "__main__":
    run_scraper(VENDOR, SITEMAP_URL, parse_product, OUT_DIR,
                url_filter=url_filter)
