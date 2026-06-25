#!/usr/bin/env python3
"""
Rebuild manifest.json from cached _html/ files + sitemap.
Run this after killing a mid-run scraper to recover progress before restarting.
"""
import json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from scraper_lib import fetch_product_urls, safe_filename, to_wdr
from scrape_soundimports import parse_product, _extract_category

out      = Path(__file__).parent
html_dir = out / "_html"
manifest_path = out / "manifest.json"
SITEMAP_URL = "https://www.soundimports.eu/en/sitemap.xml"

# Load existing manifest (keep already-saved entries)
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
else:
    manifest = {"scraped": {}}

# Get all sitemap URLs (uses cached copy if available, otherwise fetches)
print("Loading sitemap...")
all_urls = fetch_product_urls(SITEMAP_URL, delay_s=0.2)
print(f"{len(all_urls)} sitemap URLs")

def cache_path(url):
    slug = url.rstrip("/").split("/")[-1]
    return html_dir / (re.sub(r"[^\w\-.]", "_", slug) + ".html")

already_done = set(manifest.get("scraped", {}).keys())
rebuilt = 0
print("Rebuilding from cache...")
for url in all_urls:
    if url in already_done:
        continue
    cp = cache_path(url)
    if not cp.exists():
        continue

    html = cp.read_text(encoding="utf-8", errors="replace")
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    page_title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else ""
    category = _extract_category(html)

    try:
        product = parse_product(html, url)
    except Exception:
        product = None

    is_skip = product is None or (isinstance(product, dict) and product.get("skip"))
    if is_skip:
        manifest.setdefault("scraped", {})[url] = {
            "scraped_at": "rebuilt",
            "wdr": None,
            "status": "skipped",
            "title": page_title,
            "category": category,
        }
    else:
        brand = product.get("brand", "")
        model = product.get("model", "")
        wdr_name = safe_filename(f"{brand} {model}".strip())
        manifest.setdefault("scraped", {})[url] = {
            "scraped_at": "rebuilt",
            "wdr": wdr_name,
            "status": "ok",
            "title": page_title,
            "category": category,
        }
    rebuilt += 1

manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
total = len(manifest["scraped"])
print(f"Rebuilt {rebuilt} entries from cache. Manifest total: {total}")
