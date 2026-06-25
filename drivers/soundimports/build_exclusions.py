#!/usr/bin/env python3
"""
Build drivers/soundimports/exclusions.md from the manifest + cached HTML.
Run any time to regenerate. Safe to re-run — reads manifest and _html/ cache.

Categories and page titles are populated from:
  1. manifest.json (stored at scrape time for runs after 2026-06-24)
  2. cached _html/ files (backfill for earlier runs)
"""
import json, re, sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

out = Path(__file__).parent
manifest_path = out / "manifest.json"
html_dir = out / "_html"

if not manifest_path.exists():
    print("No manifest.json found — run the scraper first.")
    raise SystemExit(1)

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
scraped = manifest.get("scraped", {})


def _cached_html(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    html_path = html_dir / (re.sub(r"[^\w\-.]", "_", slug) + ".html")
    return html_path.read_text(encoding="utf-8", errors="replace") if html_path.exists() else ""


def get_title(url: str, entry: dict) -> str:
    if entry.get("title"):
        return entry["title"]
    html = _cached_html(url)
    if html:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        if m:
            return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return ""


def get_category(url: str, entry: dict) -> str:
    if entry.get("category"):
        return entry["category"]
    html = _cached_html(url)
    if not html:
        return ""
    # JSON-LD BreadcrumbList position 3 (verified 2026-06-24 on SI tweeter page)
    m = re.search(
        r'"position"\s*:\s*3\s*,\s*"item"\s*:\s*\{[^}]*?"name"\s*:\s*"([^"]+)"',
        html, re.S
    )
    if m:
        return m.group(1)
    # Fallback: "Show all <Category>" link
    m = re.search(r"Show all ([A-Z][a-zA-Z &/\-]+)", html)
    if m:
        return m.group(1).strip()
    return ""


rows = []
for url, entry in sorted(scraped.items()):
    status = entry.get("status", "")
    wdr = entry.get("wdr") or ""
    title = get_title(url, entry)
    category = get_category(url, entry)
    rows.append((url, status, wdr, title, category))

excluded = [(u, t, c) for u, s, w, t, c in rows if s == "skipped"]
drivers  = [(u, w, t) for u, s, w, t, c in rows if s == "ok"]
errors   = [(u, s, t) for u, s, w, t, c in rows if s.startswith("error")]

cat_counts = Counter(c or "Unknown" for _, _, c in excluded)

lines = [
    "# SoundImports — URL exclusions log",
    "",
    "Generated from `manifest.json` + `_html/` cache. Re-run `build_exclusions.py` to refresh.",
    "",
    f"Sitemap total: {len(rows)} | Drivers: {len(drivers)} | Excluded: {len(excluded)} | Errors: {len(errors)}",
    "",
    "## Excluded by category",
    "",
    "| Category | Count |",
    "|----------|-------|",
]
for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
    lines.append(f"| {cat} | {count} |")

lines += [
    "",
    "---",
    "",
    "## Excluded pages (no T/S data)",
    "",
    "| URL slug | Category | Page title |",
    "|----------|----------|------------|",
]
for url, title, category in excluded:
    slug = url.rstrip("/").split("/")[-1]
    lines.append(f"| `{slug}` | {category} | {title} |")

lines += [
    "",
    "---",
    "",
    "## Drivers written",
    "",
    "| URL slug | WDR file |",
    "|----------|----------|",
]
for url, wdr, title in drivers:
    slug = url.rstrip("/").split("/")[-1]
    lines.append(f"| `{slug}` | `{wdr}` |")

if errors:
    lines += ["", "---", "", "## Errors", "", "| URL slug | Error |", "|----------|-------|"]
    for url, status, title in errors:
        slug = url.rstrip("/").split("/")[-1]
        lines.append(f"| `{slug}` | {status} |")

out_path = out / "exclusions.md"
out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Written {out_path} ({len(excluded)} excluded, {len(drivers)} drivers)")
print("Category breakdown:")
for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1])[:15]:
    print(f"  {count:4d}  {cat}")

# ── Generate excluded_brands.json ────────────────────────────────────────────
# Find URL slug prefixes (brand portion) where every observed URL was a skip.
# These become fast-fail patterns in scrape_soundimports.py — no HTTP fetch needed.
from collections import defaultdict

driver_slugs = {u.rstrip("/").split("/")[-1] for u, w, t in drivers}

def brand_prefix(slug: str) -> str:
    """First hyphen-separated word(s) that look like a brand, not a model number."""
    parts = slug.replace(".html", "").split("-")
    # Take leading alphabetic parts until we hit something that looks like a model number
    prefix_parts = []
    for p in parts:
        if re.match(r"^\d", p):  # starts with digit → model number begins
            break
        prefix_parts.append(p)
        if len(prefix_parts) >= 2:  # max 2-word brand slugs
            break
    return "-".join(prefix_parts) + "-" if prefix_parts else ""

# Map prefix → sets of excluded and driver URLs
prefix_excluded: dict[str, set] = defaultdict(set)
prefix_drivers:  dict[str, set] = defaultdict(set)

for url, t, c in excluded:
    slug = url.rstrip("/").split("/")[-1]
    p = brand_prefix(slug)
    if p:
        prefix_excluded[p].add(slug)

for url, w, t in drivers:
    slug = url.rstrip("/").split("/")[-1]
    p = brand_prefix(slug)
    if p:
        prefix_drivers[p].add(slug)

# A prefix is safe to exclude only if it has zero driver pages
safe_prefixes = sorted(
    p for p, excl in prefix_excluded.items()
    if len(excl) >= 3 and p not in prefix_drivers  # ≥3 observed exclusions, no drivers seen
)

excl_path = out / "excluded_brands.json"
excl_path.write_text(json.dumps(safe_prefixes, indent=2), encoding="utf-8")
print(f"\nWritten {excl_path} ({len(safe_prefixes)} fast-fail slug prefixes)")
print("Sample prefixes:", safe_prefixes[:10])
