#!/usr/bin/env python3
"""
Scrape Dayton Audio product pages → WDR files + PDF datasheets.

Usage:
    python scrape_dayton.py [--out-dir drivers/dayton-audio] [--limit N] [--refresh]

Site: https://www.daytonaudio.com (AspDotNetStorefront, not Shopify)
Product URL pattern: https://www.daytonaudio.com/product/{id}/{slug}
Category pages: https://www.daytonaudio.com/category/{id}/{name}?pagenum={n}
Pagination: 20 products per page, use ?pagenum=N to advance.

Verified against actual product pages 2026-06-29 (DA175-8 woofer, AMT-mini-8 tweeter).
"""

import re
import time
from datetime import datetime
from pathlib import Path
from scraper_lib import run_scraper, parse_number, fetch

VENDOR  = "Dayton Audio"
BASE    = "https://www.daytonaudio.com"
OUT_DIR = str(Path(__file__).resolve().parent.parent / "drivers" / "dayton-audio")

# Category IDs that contain speaker drivers (verified 2026-06-29).
# Broader categories are included safely — parse_product returns None if no Fs found.
DRIVER_CATEGORY_IDS = [
    118,  # Woofers (full-range, bass-mid, coaxial, passive radiators)
    119,  # Tweeters
    121,  # Subwoofers
    178,  # Mini/micro speakers
]

# HTML table label fragments (lowercase) → (wdr_key, SI factor).
# Verified against https://www.daytonaudio.com/product/11/da175-8-7-aluminum-cone-woofer
# (DA175-8 woofer page, 2026-06-29). Dayton Audio uses AspDotNetStorefront two-column
# <tr> tables: [label-cell, value-cell]. All label matching uses substring (in).
FIELD_MAP = {
    "resonant frequency":    ("Fs",   1.0),     # "Resonant Frequency (Fs)"
    "total q":               ("Qts",  1.0),     # "Total Q (Qts)"
    "electromagnetic q":     ("Qes",  1.0),     # "Electromagnetic Q (Qes)" — NOT "Electrical Q"
    "mechanical q":          ("Qms",  1.0),     # "Mechanical Q (Qms)"
    "dc resistance":         ("Re",   1.0),     # "DC Resistance (Re)"
    "voice coil inductance": ("Le",   1e-3),    # "Voice Coil Inductance (Le)"  mH → H
    "bl product":            ("BL",   1.0),     # "BL Product (BL)"  T·m
    "diaphragm mass":        ("Mms",  1e-3),    # "Diaphragm Mass Inc. Airload (Mms)"  g → kg
    "compliance":            ("Cms",  1e-3),    # "Mechanical Compliance of Suspension (Cms)"  mm/N → m/N
    "surface area":          ("Sd",   1e-4),    # "Surface Area Of Cone (Sd)"  cm² → m²
    "equivalent volume":     ("Vas",  1e-3),    # "Compliance Equivalent Volume (Vas)"  litres → m³
    "linear excursion":      ("Xmax", 1e-3),    # "Maximum Linear Excursion (Xmax)"  mm one-way → m
    "power handling":        ("Pe",   1.0),     # "Power Handling (RMS)"  W — first match wins
    "impedance":             ("Znom", 1.0),     # "Impedance"  Ω
}


def _collect_urls() -> list[str]:
    """
    Enumerate all product URLs by paginating through DRIVER_CATEGORY_IDS.
    Each category page returns 20 products; stop when a page repeats the same URLs.
    """
    seen: set[str] = set()
    all_urls: list[str] = []
    for cat_id in DRIVER_CATEGORY_IDS:
        page = 1
        while True:
            if page > 1:
                time.sleep(0.5)
            html = fetch(f"{BASE}/category/{cat_id}?pagenum={page}")
            raw_links = re.findall(r'href="(/product/\d+/[^"]+)"', html)
            # Filter out icon/image paths (e.g. /product/icon/123.jpg)
            links = [
                BASE + l
                for l in raw_links
                if not re.search(r"/(?:icon|image|thumb)/", l)
            ]
            new = [u for u in links if u not in seen]
            if not new:
                break
            for u in new:
                seen.add(u)
                all_urls.append(u)
            page += 1
    return all_urls


def _extract_model(h1_text: str, url: str) -> str:
    """
    Extract the manufacturer model code from the H1 title and/or URL slug.

    Most Dayton products start with the model: "DA175-8 7in Aluminum Cone Woofer".
    A few product titles lead with a descriptor: "High Resolution... EC30-4" or
    "Pro 18 in. ... Odeum 18F" — in those cases the model is the last H1 token.
    """
    tokens = h1_text.split() if h1_text else []
    # Most Dayton model codes start with 2+ uppercase letters (DA, MX, HTS, DC, CF...)
    if tokens and re.match(r"^[A-Z][A-Z0-9-]*\d", tokens[0]):
        return tokens[0]
    # Scan from the right for the first token that contains a digit
    for i in range(len(tokens) - 1, -1, -1):
        t = tokens[i]
        if not re.search(r"\d", t):
            continue
        if t[0].isalpha():
            # e.g. "EC30-4" — alphanumeric model code
            return t
        if t[0].isdigit() and i > 0:
            # e.g. "18F" — product line + variant, combine: "Odeum-18F"
            return f"{tokens[i - 1]}-{t}"
    # Last resort: last hyphen-segment of URL slug uppercased
    slug = url.rstrip("/").split("/")[-1]
    return slug.split("-")[-1].upper() or ""


def parse_product(html: str, url: str) -> dict | None:
    # Extract model from H1: "DA175-8 7" Aluminum Cone Woofer" → "DA175-8"
    h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    h1_text = re.sub(r"<[^>]+>", "", h1_m.group(1)).strip() if h1_m else ""
    model = _extract_model(h1_text, url)
    if not model:
        return None

    # T/S parameters from <tr> table rows
    fields: dict[str, float] = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)
        if len(cells) < 2:
            continue
        label = re.sub(r"<[^>]+>", "", cells[0]).strip().lower()
        value_text = re.sub(r"<[^>]+>", "", cells[1]).strip()
        for fragment, (key, factor) in FIELD_MAP.items():
            if fragment in label and key not in fields:
                val = parse_number(value_text)
                if val is not None:
                    v = value_text.lower()
                    if key == "Vas" and "ft" in v:
                        factor = 28.3168e-3     # ft³ → m³
                    fields[key] = round(val * factor, 9)
                break

    if not fields.get("Fs"):
        return None

    # PDF: Dayton pages use relative /images/resources/... links
    pdf_matches = re.findall(r'href="(/images/resources/[^"]+\.pdf)"', html, re.I)
    if not pdf_matches:
        # Fallback: any absolute PDF link mentioning dayton
        abs_pdfs = re.findall(r'"(https?://[^"]+\.pdf)"', html, re.I)
        pdf_matches = [p for p in abs_pdfs if "dayton" in p.lower()]
    pdf_url = BASE + pdf_matches[0] if (pdf_matches and pdf_matches[0].startswith("/")) else (pdf_matches[0] if pdf_matches else None)

    extra = re.findall(r'"(https?://[^"]+\.(frd|zma|zip|txt))"', html, re.I)

    today = datetime.now().strftime("%Y%m%d")
    return {
        "brand":         "Dayton Audio",
        "model":         model,
        "manufacturer":  "Dayton Audio",
        "provided_by":   f"Dayton Audio website (scraped {today})",
        "fields":        fields,
        "datasheet_url": pdf_url,
        "extra_links":   [l[0] for l in extra],
    }


def url_filter(url: str) -> bool:
    return "/product/" in url and re.search(r"/product/\d+/", url) is not None


if __name__ == "__main__":
    run_scraper(VENDOR, _collect_urls, parse_product, OUT_DIR,
                url_filter=url_filter)
