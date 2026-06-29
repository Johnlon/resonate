#!/usr/bin/env python3
"""
enrich_drivers.py

One-off enrichment script for existing driver sidecars.

Reads every _meta.yml in scraped collections, tries to extract
driver_type / freq_low_hz / freq_high_hz from cached HTML or PDF,
writes the raw extraction output to a new _extract.yml sidecar, then
merges any non-null values back into _meta.yml if the field is currently
absent or null.

Collections processed: all under drivers/ except matt/ and winisd/.
matt/ is human-curated and must not be written.

Usage:
    python scripts/enrich_drivers.py
    python scripts/enrich_drivers.py --dry-run
    python scripts/enrich_drivers.py --collection parts-express
    python scripts/enrich_drivers.py --force          # re-extract even if _extract.yml exists
    python scripts/enrich_drivers.py --limit 50       # process at most N drivers per collection

Resume: by default skips drivers whose _extract.yml already exists (created today).
Use --force to override.

Script rules compliance (CLAUDE.md):
  - Every output line is timestamped.
  - Progress line printed every 100 drivers.
  - Final summary line with totals and elapsed time.
  - _problems.log written per collection (appended, never overwritten).
  - Log-and-continue: errors are logged, never raised.
"""

import re
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT       = Path(__file__).resolve().parent.parent
DRIVERS    = ROOT / "drivers"
SKIP_COLS  = {"matt", "winisd", "loudspeakerdatabase", "sample", "dayton-audio"}
SKIP_PARTS = {"_html", "_backup", "datasheets", "sample"}

sys.path.insert(0, str(Path(__file__).parent))
from extract_lib import extract_driver


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def read_meta(yml_path: Path) -> dict:
    """Parse a _meta.yml into a flat dict of key: value strings."""
    meta: dict = {}
    for line in yml_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^(\w+):\s*(.*)", line)
        if m:
            val = m.group(2).strip()
            if val in ("null", "~", ""):
                val = None
            meta[m.group(1)] = val
    return meta


def write_extract(path: Path, result) -> None:
    """Write _extract.yml from an ExtractResult."""
    run_dt = datetime.now().isoformat(timespec="seconds")
    lines = [
        f"extracted_at: {run_dt}",
        f"source: {result.source}",
        f"driver_type: {result.driver_type if result.driver_type is not None else 'null'}",
        f"freq_low_hz: {result.freq_low_hz if result.freq_low_hz is not None else 'null'}",
        f"freq_high_hz: {result.freq_high_hz if result.freq_high_hz is not None else 'null'}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_meta_field(yml_path: Path, key: str, value, dry_run: bool) -> bool:
    """
    Set a field in _meta.yml to value if it is currently null/absent.
    Returns True if (would be) changed.
    """
    text = yml_path.read_text(encoding="utf-8", errors="replace")
    str_value = str(value) if value is not None else "null"

    # Match existing key: null or key: ~ or key: (empty)
    pat = re.compile(rf"^({re.escape(key)}:)\s*(null|~|)\s*$", re.M)
    if pat.search(text):
        new_text = pat.sub(rf"\1 {str_value}", text)
        if new_text != text:
            if not dry_run:
                yml_path.write_text(new_text, encoding="utf-8")
            return True
        return False

    # Field absent entirely — append
    new_text = text.rstrip("\n") + f"\n{key}: {str_value}\n"
    if not dry_run:
        yml_path.write_text(new_text, encoding="utf-8")
    return True


def process_collection(
    col_dir: Path,
    dry_run: bool,
    force: bool,
    limit: int,
    log_fh,
) -> dict:
    name = col_dir.name
    today = datetime.now().strftime("%Y-%m-%d")

    yml_files = [
        f for f in sorted(col_dir.rglob("*_meta.yml"))
        if not any(p in SKIP_PARTS for p in f.parts)
    ]
    if limit:
        yml_files = yml_files[:limit]

    counters = {
        "total": len(yml_files),
        "extracted": 0,
        "skipped_existing": 0,
        "meta_updated": 0,
        "no_data": 0,
        "errors": 0,
    }

    for i, yml_path in enumerate(yml_files, 1):
        extract_path = yml_path.with_name(yml_path.stem.replace("_meta", "_extract") + ".yml")

        # Resume: skip if _extract.yml exists and was written today (unless --force)
        if not force and extract_path.exists():
            content = extract_path.read_text(encoding="utf-8", errors="replace")
            if today in content:
                counters["skipped_existing"] += 1
                if i % 100 == 0:
                    print(f"[{ts()}] {name}: {i}/{counters['total']} processed", flush=True)
                continue

        try:
            meta = read_meta(yml_path)
            result = extract_driver(col_dir, meta)
            write_extract(extract_path, result)

            if result.problems:
                for prob in result.problems:
                    log_fh.write(
                        f"[{ts()}] PROBLEM  file={yml_path.name}\n"
                        f"         reason={prob}\n"
                    )

            if result.has_data():
                counters["extracted"] += 1
                changed = False
                # Only write fields that are currently absent/null
                if result.driver_type and not meta.get("driver_type"):
                    if update_meta_field(yml_path, "driver_type", result.driver_type, dry_run):
                        changed = True
                        log_fh.write(
                            f"[{ts()}] META_UPDATE file={yml_path.name}"
                            f" driver_type={result.driver_type}\n"
                        )
                if result.freq_low_hz is not None and not meta.get("freq_low_hz"):
                    if update_meta_field(yml_path, "freq_low_hz", result.freq_low_hz, dry_run):
                        changed = True
                if result.freq_high_hz is not None and not meta.get("freq_high_hz"):
                    if update_meta_field(yml_path, "freq_high_hz", result.freq_high_hz, dry_run):
                        changed = True
                if changed:
                    counters["meta_updated"] += 1
            else:
                counters["no_data"] += 1

        except Exception as e:
            counters["errors"] += 1
            log_fh.write(
                f"[{ts()}] ERROR  file={yml_path.name}  exception={e}\n"
            )

        if i % 100 == 0:
            print(
                f"[{ts()}] {name}: {i}/{counters['total']} — "
                f"extracted={counters['extracted']} "
                f"updated={counters['meta_updated']} "
                f"no_data={counters['no_data']} "
                f"errors={counters['errors']}",
                flush=True,
            )

    return counters


def main() -> None:
    ap = argparse.ArgumentParser(description="Enrich driver sidecars from cached HTML/PDF")
    ap.add_argument("--dry-run", action="store_true",
                    help="Extract and write _extract.yml but do not modify _meta.yml")
    ap.add_argument("--force", action="store_true",
                    help="Re-extract even if _extract.yml already exists today")
    ap.add_argument("--collection", metavar="NAME",
                    help="Process one collection only")
    ap.add_argument("--limit", type=int, default=0,
                    help="Process at most N drivers per collection (0 = all)")
    args = ap.parse_args()

    run_dt = datetime.now().isoformat(timespec="seconds")
    print(f"[{ts()}] enrich_drivers  run={run_dt}  dry_run={args.dry_run}  force={args.force}")

    if args.collection:
        col_dirs = [DRIVERS / args.collection]
        if not col_dirs[0].is_dir():
            print(f"[{ts()}] ERROR: unknown collection: {args.collection}")
            sys.exit(1)
        if args.collection in SKIP_COLS:
            print(f"[{ts()}] ERROR: {args.collection} is in SKIP_COLS (protected)")
            sys.exit(1)
    else:
        col_dirs = sorted(
            d for d in DRIVERS.iterdir()
            if d.is_dir()
            and d.name not in SKIP_COLS
            and not d.name.startswith("_")
        )

    start = time.time()
    grand: dict = {
        "total": 0, "extracted": 0, "skipped_existing": 0,
        "meta_updated": 0, "no_data": 0, "errors": 0,
    }

    for col_dir in col_dirs:
        log_path = col_dir / "_problems.log"
        with log_path.open("a", encoding="utf-8") as log_fh:
            log_fh.write(
                f"\n[{ts()}] RUN {run_dt} scraper=enrich_drivers collection={col_dir.name}"
                f" dry_run={args.dry_run}\n"
            )
            print(f"[{ts()}] {col_dir.name}: starting", flush=True)
            c = process_collection(col_dir, args.dry_run, args.force, args.limit, log_fh)
            for k, v in c.items():
                grand[k] += v
            log_fh.write(
                f"[{ts()}] DONE  collection={col_dir.name} "
                f"total={c['total']} extracted={c['extracted']} "
                f"updated={c['meta_updated']} no_data={c['no_data']} errors={c['errors']}\n"
            )
            print(
                f"[{ts()}] {col_dir.name}: DONE  "
                f"total={c['total']} extracted={c['extracted']} "
                f"updated={c['meta_updated']} no_data={c['no_data']} "
                f"errors={c['errors']}",
                flush=True,
            )

    elapsed = time.time() - start
    summary = (
        f"[{ts()}] DONE  elapsed={elapsed:.1f}s  "
        f"total={grand['total']}  extracted={grand['extracted']}  "
        f"skipped_existing={grand['skipped_existing']}  "
        f"meta_updated={grand['meta_updated']}  "
        f"no_data={grand['no_data']}  errors={grand['errors']}"
    )
    print(summary, flush=True)


if __name__ == "__main__":
    main()
