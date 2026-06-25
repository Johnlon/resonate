#!/usr/bin/env python3
"""
Scrape PE product pages (Playwright headless) to extract:
  boxbench_datasheet = specs PDF URL
  boxbench_frd       = FRD/ZMA data ZIP URL

Rules enforced:
  - Timestamp on every progress line (HH:MM:SS)
  - Resumes: skips files that already have BOTH fields set
  - Hard per-page asyncio timeout prevents hangs

Usage:
  python scripts/backfill-pe-pedocs.py [--workers N] [--force]
  --force : re-scrape even files that already have both fields
"""
import asyncio, os, re, sys, io, argparse, time, threading
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

ROOT   = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PE_DIR = os.path.join(ROOT, 'drivers', 'parts-express')

print_lock = threading.Lock()

def ts():
    return datetime.now().strftime('%H:%M:%S')

def pprint(*a):
    with print_lock:
        print(f'[{ts()}]', *a, flush=True)

def get_field(text, key):
    m = re.search(r'^' + re.escape(key) + r'=(.*)$', text, re.M)
    return m.group(1).strip() if m else ''

def set_field(text, key, value):
    pat = r'^' + re.escape(key) + r'=.*$'
    if re.search(pat, text, re.M):
        return re.sub(pat, f'{key}={value}', text, flags=re.M)
    insert = f'{key}={value}\n'
    m = re.search(r'^ParState=.*\n?', text, re.M)
    return (text[:m.end()] + insert + text[m.end():]) if m else (text.rstrip('\n') + '\n' + insert)

write_lock = threading.Lock()

async def scrape(page, i, total, fname, src_url, force):
    fpath = os.path.join(PE_DIR, fname)
    text  = open(fpath, encoding='utf-8', errors='ignore').read()

    has_ds  = bool(get_field(text, 'boxbench_datasheet'))
    has_frd = bool(get_field(text, 'boxbench_frd'))
    if has_ds and has_frd and not force:
        pprint(f'[{i}/{total}] SKIP  {fname[:60]}')
        return

    pprint(f'[{i}/{total}] fetch {fname[:70]}')
    try:
        await page.goto(src_url, wait_until='domcontentloaded', timeout=20000)
        try:
            await page.wait_for_selector('a[href*="pedocs"]', timeout=7000)
        except PWTimeout:
            pass
        links = await page.eval_on_selector_all(
            'a[href]',
            'els => els.map(e => e.href).filter(h => h.includes("pedocs"))'
        )
    except Exception as e:
        pprint(f'[{i}/{total}] ERR   {str(e)[:80]}')
        return

    if not links:
        pprint(f'[{i}/{total}] NO-LINKS')
        return

    specs_pdf = ''
    data_zip  = ''
    for href in links:
        lo = href.lower()
        if '/pedocs/specs/' in lo and lo.endswith('.pdf') and 'warranty' not in lo:
            if not specs_pdf:
                specs_pdf = href
        elif '/pedocs/tech-docs/' in lo and lo.endswith('.zip'):
            if not data_zip:
                data_zip = href

    orig = text
    tags = []
    if specs_pdf and (not has_ds or force):
        text = set_field(text, 'boxbench_datasheet', specs_pdf)
        tags.append(f'ds=…{specs_pdf[-35:]}')
    if data_zip and (not has_frd or force):
        text = set_field(text, 'boxbench_frd', data_zip)
        tags.append('frd=SET')

    if text != orig:
        with write_lock:
            open(fpath, 'w', encoding='utf-8').write(text)
        pprint(f'[{i}/{total}] OK    {" | ".join(tags)}')
    else:
        pprint(f'[{i}/{total}] --    (no new links found)')

async def run_one(browser, sem, task, force):
    i, total, fname, src = task
    async with sem:
        page = await browser.new_page()
        try:
            # Hard 35-second timeout per page — prevents any page hanging forever
            await asyncio.wait_for(
                scrape(page, i, total, fname, src, force),
                timeout=35
            )
        except asyncio.TimeoutError:
            pprint(f'[{i}/{total}] TIMEOUT — skipping {fname[:50]}')
        except Exception as e:
            pprint(f'[{i}/{total}] FATAL  {str(e)[:80]}')
        finally:
            await page.close()

async def main(workers, force):
    wdr_files = sorted(f for f in os.listdir(PE_DIR) if f.endswith('.wdr'))
    total = len(wdr_files)

    tasks = []
    skipped_complete = 0
    for i, fname in enumerate(wdr_files, 1):
        fpath = os.path.join(PE_DIR, fname)
        text  = open(fpath, encoding='utf-8', errors='ignore').read()
        has_ds  = bool(get_field(text, 'boxbench_datasheet'))
        has_frd = bool(get_field(text, 'boxbench_frd'))
        if has_ds and has_frd and not force:
            skipped_complete += 1
            continue
        src = get_field(text, 'boxbench_source')
        if not src or not src.startswith('http'):
            comment = get_field(text, 'Comment')
            m = re.search(r'https?://www\.parts-express\.com/\S+', comment)
            src = m.group(0).split()[0] if m else ''
        if src:
            tasks.append((i, total, fname, src))
        else:
            pprint(f'[{i}/{total}] NO-SRC {fname[:60]}')

    remaining = len(tasks)
    pprint(f'── {remaining} files to scrape ({skipped_complete} already complete), {workers} workers ──')

    t0 = time.time()
    sem = asyncio.Semaphore(workers)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        await asyncio.gather(*[run_one(browser, sem, t, force) for t in tasks])
        await browser.close()

    elapsed = time.time() - t0
    pprint(f'── Done in {elapsed:.0f}s ──')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=20)
    parser.add_argument('--force',   action='store_true')
    args = parser.parse_args()
    asyncio.run(main(args.workers, args.force))
