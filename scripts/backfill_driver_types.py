#!/usr/bin/env python3
"""
backfill_driver_types.py

Scans every WDR file in drivers/ (excluding matt/ and _backup_*) and derives
driver_type from the WDR filename using the same classification rules as the
app's classifyTypes() function. Writes driver_type to the corresponding
_meta.yml sidecar when one exists.

Run after any change to the classification rules to re-derive all types.
Idempotent: safe to re-run at any time.

    python scripts/backfill_driver_types.py
    python scripts/backfill_driver_types.py --dry-run   # preview without writing
    python scripts/backfill_driver_types.py --collection parts-express
"""

import re
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
DRIVERS_DIR = ROOT / 'drivers'
LOG_PATH = DRIVERS_DIR / '_backfill_driver_types.log'

SKIP_DIRS = {'_backup_2026-06-26', '_html', 'datasheets', 'sample'}

# ── Classification patterns (must mirror classifyTypes() in DriverBrowser.vue) ─

PR_PAT        = re.compile(r'\bpassive[_ ]?radiator\b|\bP\.?R\.?\b', re.I)
COAX_PAT      = re.compile(r'\bcoax(ial)?\b', re.I)
TWEET_PAT     = re.compile(r'\btweet(er)?\b|dome[- ]tweeter|ribbon[- ]tweeter|\bplanar\b|\bAMT\b|air[- ]motion', re.I)
SUB_PAT       = re.compile(r'\bsub(woofer)?\b|sub[-_ ]', re.I)
MIDBASS_PAT   = re.compile(r'\bmid[-_ ]?(bass|woof(er)?)\b|\bmidbass\b', re.I)
WOOFER_PAT    = re.compile(r'\bwoofer\b', re.I)
MIDRANGE_PAT  = re.compile(r'\bmid[-_ ]?range\b|\bmidrange\b', re.I)
FULLRANGE_PAT = re.compile(r'\bfull[-_ ]?range\b|\bfullrange\b', re.I)
BMR_PAT       = re.compile(r'\bBMR\b|balanced[- ]mode', re.I)


def ts():
    return datetime.now().strftime('%H:%M:%S')


def parse_wdr_num(content, key):
    m = re.search(rf'^{key}=(.+)$', content, re.M)
    if not m:
        return None
    try:
        return float(m.group(1).strip())
    except ValueError:
        return None


def classify(name_str, fs=None, sd=None):
    """
    Returns (driver_type_str, canonical_label) using the same logic as
    classifyTypes() in src/components/DriverBrowser.vue.
    driver_type_str is the value written to _meta.yml.
    Returns (None, 'Unclassified') when no signal is found.
    """
    nm = name_str or ''

    if PR_PAT.search(nm):
        return 'pr', 'Passive Radiator'
    if COAX_PAT.search(nm):
        return 'coaxial', 'Coaxial'

    types = []
    labels = []

    if TWEET_PAT.search(nm):
        types.append('tweeter')
        if re.search(r'\bAMT\b|air[- ]motion', nm, re.I):
            labels.append('AMT')
        elif re.search(r'\bribbon\b', nm, re.I):
            labels.append('Ribbon Tweeter')
        elif re.search(r'\bplanar\b', nm, re.I):
            labels.append('Planar Tweeter')
        else:
            labels.append('Tweeter')

    if SUB_PAT.search(nm):
        types.append('subwoofer')
        labels.append('Subwoofer')

    if MIDBASS_PAT.search(nm):
        types.append('mid-bass')
        labels.append('Mid-bass')

    if WOOFER_PAT.search(nm) and not MIDBASS_PAT.search(nm):
        types.append('woofer')
        labels.append('Woofer')

    if MIDRANGE_PAT.search(nm):
        types.append('midrange')
        labels.append('Midrange')

    if FULLRANGE_PAT.search(nm):
        types.append('fullrange')
        labels.append('Full-range')

    if BMR_PAT.search(nm):
        types.append('bmr')
        labels.append('BMR')

    if types:
        # Primary type = first matched (most specific)
        return types[0], ' / '.join(labels)

    # T/S parameter fallbacks
    sd_cm2 = sd * 1e4 if sd is not None else None
    if sd_cm2 is not None and sd_cm2 < 12:
        return 'tweeter', 'Tweeter'
    if fs is not None and fs < 40:
        return 'subwoofer', 'Subwoofer'

    return None, 'Unclassified'


def update_sidecar(yml_path, driver_type, dry_run):
    """
    Write driver_type to the sidecar. Updates existing field or appends it.
    Returns True if the file was (or would be) changed.
    """
    text = yml_path.read_text(encoding='utf-8')
    value = driver_type if driver_type is not None else 'null'

    if re.search(r'^driver_type:', text, re.M):
        new_text = re.sub(r'^driver_type:.*$', f'driver_type: {value}', text, flags=re.M)
    else:
        new_text = text.rstrip('\n') + f'\ndriver_type: {value}\n'

    if new_text == text:
        return False
    if not dry_run:
        yml_path.write_text(new_text, encoding='utf-8')
    return True


def process_collection(col_dir, dry_run, log_fh):
    name = col_dir.name
    wdr_files = sorted(col_dir.rglob('*.wdr'))
    wdr_files = [f for f in wdr_files if not any(p in SKIP_DIRS for p in f.parts)]

    updated = skipped_no_sidecar = skipped_no_change = errors = 0

    for wdr in wdr_files:
        yml = wdr.with_name(wdr.stem + '_meta.yml')
        if not yml.exists():
            skipped_no_sidecar += 1
            log_fh.write(f'[{ts()}] NO_SIDECAR  {wdr.relative_to(DRIVERS_DIR)}\n')
            continue

        try:
            content = wdr.read_text(encoding='utf-8', errors='replace')
            wdr_name = wdr.stem  # filename without extension — same as bundler uses
            fs = parse_wdr_num(content, 'Fs')
            sd = parse_wdr_num(content, 'Sd')
            driver_type, canonical = classify(wdr_name, fs, sd)

            changed = update_sidecar(yml, driver_type, dry_run)
            if changed:
                updated += 1
                log_fh.write(f'[{ts()}] UPDATED     {wdr.relative_to(DRIVERS_DIR)}  →  driver_type: {driver_type}  ({canonical})\n')
            else:
                skipped_no_change += 1
        except Exception as e:
            errors += 1
            log_fh.write(f'[{ts()}] ERROR       {wdr.relative_to(DRIVERS_DIR)}  {e}\n')

    print(f'[{ts()}] {name}: {len(wdr_files)} WDRs — updated {updated}, unchanged {skipped_no_change}, no sidecar {skipped_no_sidecar}, errors {errors}')
    return updated, skipped_no_sidecar, skipped_no_change, errors


def main():
    ap = argparse.ArgumentParser(description='Backfill driver_type in _meta.yml sidecars')
    ap.add_argument('--dry-run', action='store_true', help='Print what would change without writing')
    ap.add_argument('--collection', help='Process one collection only (directory name)')
    args = ap.parse_args()

    run_dt = datetime.now().isoformat(timespec='seconds')
    print(f'[{ts()}] backfill_driver_types  run={run_dt}  dry_run={args.dry_run}')

    if args.collection:
        col_dirs = [DRIVERS_DIR / args.collection]
        if not col_dirs[0].is_dir():
            print(f'[{ts()}] ERROR: no such collection: {args.collection}')
            sys.exit(1)
    else:
        col_dirs = sorted(
            d for d in DRIVERS_DIR.iterdir()
            if d.is_dir() and d.name not in SKIP_DIRS and not d.name.startswith('_')
        )

    start = time.time()
    totals = [0, 0, 0, 0]  # updated, no_sidecar, unchanged, errors

    with LOG_PATH.open('a', encoding='utf-8') as log_fh:
        log_fh.write(f'\n[{ts()}] RUN {run_dt}  dry_run={args.dry_run}\n')

        for col_dir in col_dirs:
            r = process_collection(col_dir, args.dry_run, log_fh)
            for i, v in enumerate(r):
                totals[i] += v

        elapsed = time.time() - start
        summary = (f'[{ts()}] DONE  elapsed={elapsed:.1f}s  '
                   f'updated={totals[0]}  no_sidecar={totals[1]}  '
                   f'unchanged={totals[2]}  errors={totals[3]}')
        print(summary)
        log_fh.write(summary + '\n')


if __name__ == '__main__':
    main()
