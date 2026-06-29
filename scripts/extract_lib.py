"""
extract_lib.py — shared driver-data extraction helpers.

Extracts driver_type, freq_low_hz, freq_high_hz (and in future, full spec
blocks) from cached HTML product pages and PDF datasheets.

This module is imported by:
  - enrich_drivers.py       (one-off backfill of existing sidecars)
  - vendor scrapers          (enrich sidecar at scrape time, going forward)

Public API
----------
  extract_from_pe_html(html)          -> ExtractResult
  extract_from_si_html(html)          -> ExtractResult
  extract_from_wavecor_html(html)     -> ExtractResult
  extract_from_pdf(pdf_path)          -> ExtractResult
  find_cached_html(collection_dir, meta_dict) -> Path | None
  find_cached_pdf(collection_dir, meta_dict)  -> Path | None
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, unquote

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ExtractResult:
    source: str = "none"            # 'pe_html', 'si_html', 'wavecor_html', 'pdf', 'none'
    driver_type: Optional[str] = None
    freq_low_hz: Optional[float] = None
    freq_high_hz: Optional[float] = None
    problems: list = field(default_factory=list)

    def has_data(self) -> bool:
        return (self.driver_type is not None
                or self.freq_low_hz is not None
                or self.freq_high_hz is not None)


# ---------------------------------------------------------------------------
# Category → driver_type mappings
# ---------------------------------------------------------------------------

# Ordered most-specific first so the first match wins.
_CATEGORY_PATTERNS: list[tuple] = [
    (re.compile(r"coaxial|coax\b", re.I),             "coaxial"),
    (re.compile(r"passive.?radiator|PR\b", re.I),      "pr"),
    (re.compile(r"compression.?driver|horn.?driver", re.I), "tweeter"),
    (re.compile(r"subwoofer", re.I),                   "subwoofer"),
    (re.compile(r"mid.?bass|midbass|bass.?mid", re.I), "mid-bass"),
    (re.compile(r"midrange|mid.range", re.I),          "midrange"),
    (re.compile(r"tweeter|dome.?tweeter|ribbon.?tweeter|planar.?tweeter|amt", re.I), "tweeter"),
    (re.compile(r"full.?range|fullrange", re.I),       "fullrange"),
    (re.compile(r"woofer|low.?frequency|lf.?driver", re.I), "woofer"),
]


def _category_to_driver_type(category_str: str) -> Optional[str]:
    """Map a breadcrumb category string to a canonical driver_type."""
    for pat, dtype in _CATEGORY_PATTERNS:
        if pat.search(category_str):
            return dtype
    return None


# ---------------------------------------------------------------------------
# Frequency range parsing
# ---------------------------------------------------------------------------

# Patterns in rough priority order
_FREQ_PATTERNS = [
    # "60 Hz – 17 kHz" or "60Hz-17kHz" or "60 to 17,000Hz"
    re.compile(
        r"(\d[\d\s,\.]*)\s*(?:Hz)?\s*[-–—~to]+\s*(\d[\d\s,\.]*)\s*(kHz|KHz|khz|KHZ|Hz|hz|HZ)",
        re.I,
    ),
    # "Frequency range: 60 - 17000 Hz"
    re.compile(
        r"(?:freq[a-z\s]*(?:range|resp[a-z]*)[:\s]+)"
        r"(\d[\d\s,\.]*)\s*(?:Hz)?\s*[-–—~]\s*(\d[\d\s,\.]*)\s*(kHz|KHz|Hz|hz)",
        re.I,
    ),
]


def _clean_num(s: str) -> float:
    """Strip spaces/commas and convert to float."""
    cleaned = s.replace(" ", "").replace(",", "")
    return float(cleaned)


def parse_freq_range(text: str) -> tuple[Optional[float], Optional[float]]:
    """
    Extract (freq_low_hz, freq_high_hz) from arbitrary text.
    Returns (None, None) when no plausible range is found.
    Applies sanity bounds: lo >= 1 Hz, hi <= 100 kHz, hi > lo * 2.
    """
    for pat in _FREQ_PATTERNS:
        for m in pat.finditer(text):
            try:
                lo = _clean_num(m.group(1))
                hi = _clean_num(m.group(2))
                unit = m.group(3).lower()
                if "k" in unit:
                    hi *= 1000
                # Sanity: lo must look like a plausible bass-end, hi must be above
                if lo < 1 or hi > 100_000 or hi <= lo * 2:
                    continue
                return lo, hi
            except (ValueError, IndexError):
                continue
    return None, None


# ---------------------------------------------------------------------------
# Parts Express HTML extraction
# ---------------------------------------------------------------------------

def extract_from_pe_html(html: str) -> ExtractResult:
    """
    Extract driver_type and freq range from a Parts Express product page.
    Uses JSON-LD BreadcrumbList (category) and the PDP specifications table.
    """
    result = ExtractResult(source="pe_html")

    # 1. Category from JSON-LD breadcrumb (second-to-last item)
    for m in re.finditer(
        r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S
    ):
        try:
            d = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if d.get("@type") != "BreadcrumbList":
            continue
        items = d.get("itemListElement", [])
        # Walk items in reverse; last item is the product itself, skip it
        for item in reversed(items[:-1]):
            cat = item.get("name", "")
            dt = _category_to_driver_type(cat)
            if dt:
                result.driver_type = dt
                break
        break  # use only first BreadcrumbList block

    # 2. Frequency Response from PDP specs table
    m = re.search(
        r'<td>Frequency Response</td>\s*<td>([^<]+)</td>', html, re.I
    )
    if m:
        lo, hi = parse_freq_range(m.group(1))
        if lo is not None:
            result.freq_low_hz = lo
            result.freq_high_hz = hi
        else:
            result.problems.append(
                f"PE HTML: could not parse Frequency Response: {m.group(1)!r}"
            )
    else:
        result.problems.append("PE HTML: no Frequency Response row in specs table")

    return result


# ---------------------------------------------------------------------------
# SoundImports HTML extraction
# ---------------------------------------------------------------------------

def extract_from_si_html(html: str) -> ExtractResult:
    """
    Extract driver_type from the SoundImports breadcrumb.
    SI pages do not reliably publish a structured frequency range in HTML.
    """
    result = ExtractResult(source="si_html")

    # Breadcrumb: <ol class="d-flex hide-575"><li>...<li>Category<li>Product</ol>
    m = re.search(
        r'<ol\s[^>]*class="[^"]*d-flex hide-575[^"]*"[^>]*>(.*?)</ol>',
        html, re.S | re.I
    )
    if not m:
        result.problems.append("SI HTML: breadcrumb not found")
        return result

    # Extract all anchor text segments — second-to-last is usually the category
    links = re.findall(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', m.group(1), re.S | re.I)
    if len(links) >= 2:
        # Last link before the product name is the category
        # links[-1] is typically the second-to-last breadcrumb (category)
        cat_text = re.sub(r"<[^>]+>", "", links[-1][1]).strip()
        dt = _category_to_driver_type(cat_text)
        if dt:
            result.driver_type = dt
        else:
            result.problems.append(f"SI HTML: unrecognised category: {cat_text!r}")
    else:
        result.problems.append("SI HTML: breadcrumb has fewer than 2 links")

    return result


# ---------------------------------------------------------------------------
# Wavecor HTML extraction
# ---------------------------------------------------------------------------

def extract_from_wavecor_html(html: str) -> ExtractResult:
    """
    Extract driver_type and freq range from a Wavecor product page.
    Wavecor pages use HTML tables with labelled rows.
    """
    result = ExtractResult(source="wavecor_html")

    # Driver type from page title or URL reference
    # Wavecor page <title> is typically "FR040WA01/02 - Full Range Speaker"
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if title_m:
        title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
        dt = _category_to_driver_type(title)
        if dt:
            result.driver_type = dt

    # Wavecor tables: look for "Recommended max. upper frequency limit" row
    # The value follows in the next table cell as a plain number (kHz)
    m = re.search(
        r"Recommended max\.?\s+upper\s+frequency\s+limit.{0,400}?(\d+(?:\.\d+)?)\s*(?:\[kHz\]|kHz)",
        html, re.S | re.I
    )
    if m:
        try:
            hi = float(m.group(1)) * 1000.0
            if 1000 <= hi <= 100_000:
                result.freq_high_hz = hi
        except ValueError:
            pass

    # Also try Fs row for lower bound estimate (less reliable as freq_low)
    # Usually Wavecor datasheets are more reliable than HTML for this

    if result.freq_high_hz is None:
        result.problems.append("Wavecor HTML: could not extract upper frequency limit")

    return result


# ---------------------------------------------------------------------------
# Scan-Speak HTML extraction
# ---------------------------------------------------------------------------

# Scan-Speak model naming: {digits}{TYPE}{more} or {LETTER}{digits}{more}
# TYPE letters: W/WE = woofer, M = midrange, F = full-range, H = horn (tweeter)
# Leading letters: R = ring-radiator tweeter, D = dome tweeter, C = coaxial/compression
# Examples: R1904, D2905, 12M, 16W, 16WE, 10F, 5F, H2606
_SS_LETTER_PREFIX = re.compile(r"^([rdc])\d", re.I)   # R/D/C prefix → tweeter
_SS_DIGIT_SUFFIX  = re.compile(r"^\d+([mwf])[a-z]*", re.I)  # digit + M/W/F + optional variant suffix (U=underhung, E=extended)
_SS_H_PREFIX      = re.compile(r"^h\d", re.I)           # H = horn driver (tweeter)


def _ss_type_from_model(model: str) -> Optional[str]:
    """
    Derive driver_type from a Scan-Speak model number.

    Scan-Speak uses a consistent naming scheme:
      {size}{type_char}_{series}   e.g. 16W_4434G00, 12M_4631G05, 10F_8422T01
      {prefix}{digits}_{series}   e.g. R1904_613001, D2905_970000, H2606_920000
    """
    slug = model.lower().strip().split("-")[0]  # "r1904-613001" → "r1904"
    m = _SS_LETTER_PREFIX.match(slug)
    if m:
        letter = m.group(1).lower()
        return {"r": "tweeter", "d": "tweeter", "c": "tweeter"}[letter]
    if _SS_H_PREFIX.match(slug):
        return "tweeter"  # horn = compression driver = tweeter category
    m = _SS_DIGIT_SUFFIX.match(slug)
    if m:
        letter = m.group(1).lower()
        return {"m": "midrange", "w": "woofer", "f": "fullrange"}[letter]
    return None


def extract_from_scanspeak_html(html: str) -> ExtractResult:
    """
    Extract driver_type from a Scan-Speak product page.
    Source: WooCommerce breadcrumb category (e.g. Home > Tweeter).
    This is direct evidence from the manufacturer's website — no inference.
    """
    result = ExtractResult(source="scanspeak_html")

    # Breadcrumb category — the only reliable signal on the product page.
    # Scan-Speak breadcrumb: Home > {Category} > {Product}
    # We want the second-to-last link (the category).
    m = re.search(
        r"<(?:nav|ol|ul)[^>]*(?:breadcrumb|woocommerce-breadcrumb)[^>]*>(.*?)</(?:nav|ol|ul)>",
        html, re.S | re.I
    )
    if m:
        # Product name is plain text (not a link), so all <a> tags are categories.
        # Scan-Speak breadcrumb: Home > {Category} > ProductName(plain text)
        cats = re.findall(r"<a[^>]*>(.*?)</a>", m.group(1), re.I | re.S)
        for cat in reversed(cats):
            cat_text = re.sub(r"<[^>]+>", "", cat).strip()
            dt = _category_to_driver_type(cat_text)
            if dt:
                result.driver_type = dt
                break
    else:
        result.problems.append("scanspeak_html: no breadcrumb nav found")

    # 3. Frequency range from specs table (if present)
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)
        if len(cells) < 2:
            continue
        label = re.sub(r"<[^>]+>", "", cells[0]).strip().lower()
        val = re.sub(r"<[^>]+>", "", cells[1]).strip()
        if "freq" in label and "Hz" in val:
            lo, hi = parse_freq_range(val)
            if lo is not None:
                result.freq_low_hz = lo
                result.freq_high_hz = hi
                break

    return result


# ---------------------------------------------------------------------------
# PDF extraction (pypdf-based)
# ---------------------------------------------------------------------------

# Detect PDFs with custom Type1 font encoding that pypdf cannot decode.
# These produce token sequences like "/0/1/2/i255/3/4" instead of readable text.
_GARBLED_PAT = re.compile(r"^(\s*/[0-9a-fA-F]{1,4}){5,}", re.M)


def _is_garbled(text: str) -> bool:
    """Return True when pypdf extracted custom-encoded tokens, not real text."""
    if not text.strip():
        return True
    # Custom Type1 encoding: sequences of /digit tokens
    if _GARBLED_PAT.search(text):
        return True
    # Low ASCII-printable ratio (< 30%) means encoding is garbled
    printable = sum(1 for c in text if 32 <= ord(c) < 127)
    return printable / max(len(text), 1) < 0.30


def extract_from_pdf(pdf_path: Path) -> ExtractResult:
    """
    Extract freq_low_hz / freq_high_hz from a PDF datasheet.
    Uses pypdf text extraction + regex patterns.
    Returns source='pdf'. driver_type not extracted here (comes from HTML/name).

    Garbled-encoding PDFs (Scan-Speak, some wavecor) are detected and logged
    as pdf_encoding=garbled — no false "no frequency range" problem is raised.
    """
    result = ExtractResult(source="pdf")

    try:
        import pypdf
    except ImportError:
        result.problems.append("PDF: pypdf not installed")
        return result

    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except Exception as e:
        result.problems.append(f"PDF: could not open {pdf_path.name}: {e}")
        return result

    text_parts: list[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        except Exception:
            pass

    if not text_parts:
        result.problems.append(
            f"PDF: pdf_encoding=image_or_empty  file={pdf_path.name}"
            "  — no text layer; needs OCR or use product-page HTML instead"
        )
        return result

    full_text = "\n".join(text_parts)

    if _is_garbled(full_text):
        result.problems.append(
            f"PDF: pdf_encoding=garbled  file={pdf_path.name}"
            "  — custom Type1 font encoding; pypdf cannot decode"
            "  — use product-page HTML for data extraction instead"
        )
        return result

    lo, hi = parse_freq_range(full_text)
    if lo is not None:
        result.freq_low_hz = lo
        result.freq_high_hz = hi
    else:
        result.problems.append(
            f"PDF: no frequency range pattern found in {pdf_path.name}"
        )

    return result


# ---------------------------------------------------------------------------
# Cache lookup helpers
# ---------------------------------------------------------------------------

def _url_to_filename(url: str) -> str:
    """Extract a safe filename from a URL path."""
    path = urlparse(unquote(url)).path
    name = path.rstrip("/").split("/")[-1]
    return name


def find_cached_html(collection_dir: Path, meta: dict) -> Optional[Path]:
    """
    Find the cached HTML file for a driver given its _meta.yml contents.

    Tries manu_page and vendor_page URLs in order, mapping the URL to the
    filename convention used by each collection's _html/ cache.

    Returns a Path if the file exists, else None.
    """
    html_dir = collection_dir / "_html"
    if not html_dir.is_dir():
        return None

    col_name = collection_dir.name

    for url_key in ("vendor_page", "manu_page"):
        url = (meta.get(url_key) or "").strip()
        if not url:
            continue

        base = _url_to_filename(url)
        if not base:
            continue

        # Parts Express: {sku}.html (SKU is the last numeric segment of the URL)
        if col_name == "parts-express":
            sku_m = re.search(r"(\d{3}-\d{3,4})(?:$|\?)", url)
            if sku_m:
                candidate = html_dir / (sku_m.group(1) + ".html")
                if candidate.exists():
                    return candidate

        # SoundImports: {slug}.html.html (slug from URL, strip trailing .html)
        if col_name == "soundimports":
            slug = base
            # vendor_page like https://www.soundimports.eu/en/seas-27tfc-h1889.html
            candidate = html_dir / (slug + ".html")
            if candidate.exists():
                return candidate
            # Double extension variant
            candidate2 = html_dir / (slug.rstrip(".html") + ".html.html")
            if candidate2.exists():
                return candidate2

        # Wavecor: {page}.html.html (page from URL path e.g. fr040wa01_02.html)
        if col_name == "wavecor":
            candidate = html_dir / (base + ".html")
            if candidate.exists():
                return candidate

        # Generic fallback
        for ext in ("", ".html", ".html.html"):
            candidate = html_dir / (base + ext)
            if candidate.exists():
                return candidate

    return None


def find_cached_pdf(collection_dir: Path, meta: dict) -> Optional[Path]:
    """
    Find a cached PDF datasheet for a driver given its _meta.yml contents.
    Checks drivers/<collection>/datasheets/ first using the datasheet URL filename.
    """
    ds_dir = collection_dir / "datasheets"
    if not ds_dir.is_dir():
        return None

    url = (meta.get("datasheet") or "").strip()
    if not url:
        return None

    pdf_name = _url_to_filename(url)
    if not pdf_name:
        return None

    candidate = ds_dir / pdf_name
    if candidate.exists():
        return candidate

    # Try case-insensitive match as fallback
    pdf_lower = pdf_name.lower()
    for f in ds_dir.iterdir():
        if f.name.lower() == pdf_lower:
            return f

    return None


# ---------------------------------------------------------------------------
# Top-level dispatch: try all available sources for a driver
# ---------------------------------------------------------------------------

def extract_driver(collection_dir: Path, meta: dict) -> ExtractResult:
    """
    Try all available data sources for a driver and return the best result.
    Priority: HTML (richer category data) → PDF (freq range).
    Merges results when both contribute different fields.
    """
    col_name = collection_dir.name
    merged = ExtractResult(source="none")

    # 1. Try HTML
    html_path = find_cached_html(collection_dir, meta)
    if html_path:
        html = html_path.read_text(encoding="utf-8", errors="replace")
        if col_name == "parts-express":
            html_result = extract_from_pe_html(html)
        elif col_name == "soundimports":
            html_result = extract_from_si_html(html)
        elif col_name == "wavecor":
            html_result = extract_from_wavecor_html(html)
        elif col_name == "scan-speak":
            html_result = extract_from_scanspeak_html(html)
        else:
            html_result = ExtractResult(source="html_unknown",
                                        problems=[f"No HTML parser for {col_name}"])

        if html_result.driver_type:
            merged.driver_type = html_result.driver_type
        if html_result.freq_low_hz is not None:
            merged.freq_low_hz = html_result.freq_low_hz
            merged.freq_high_hz = html_result.freq_high_hz
        merged.problems.extend(html_result.problems)
        merged.source = html_result.source

    # 2. Try PDF — supplements freq range if HTML didn't provide it
    if merged.freq_low_hz is None:
        pdf_path = find_cached_pdf(collection_dir, meta)
        if pdf_path:
            pdf_result = extract_from_pdf(pdf_path)
            if pdf_result.freq_low_hz is not None:
                merged.freq_low_hz = pdf_result.freq_low_hz
                merged.freq_high_hz = pdf_result.freq_high_hz
                merged.source = (
                    merged.source + "+pdf"
                    if merged.source != "none" else "pdf"
                )
            merged.problems.extend(pdf_result.problems)

    return merged
