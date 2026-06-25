"""
migrate-boxbench-after-parstate.py

Move all boxbench_* fields to after ParState= in every WDR file.
WinISD-native block (everything up to and including ParState=) must be
uninterrupted by our custom metadata fields.

Run: python scripts/migrate-boxbench-after-parstate.py [--dry-run]
"""
import sys, pathlib, argparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DRIVERS_DIR = pathlib.Path(__file__).parent.parent / "drivers"


def migrate(text: str) -> tuple[str, int]:
    """Return (new_text, n_fields_moved). Returns original if nothing to move."""
    lines = text.splitlines(keepends=True)

    parstate_idx = next(
        (i for i, l in enumerate(lines) if l.startswith("ParState=")), None
    )
    if parstate_idx is None:
        return text, 0

    # Collect boxbench_ lines that appear before ParState
    before = [(i, l) for i, l in enumerate(lines[:parstate_idx])
              if l.startswith("boxbench_")]
    if not before:
        return text, 0

    # Build output: remove boxbench_ lines from before ParState,
    # then append them (in original order) immediately after ParState line.
    indices_to_remove = {i for i, _ in before}
    bb_lines = [l for _, l in before]

    out = []
    for i, line in enumerate(lines):
        if i in indices_to_remove:
            continue
        out.append(line)
        if i == parstate_idx:
            out.extend(bb_lines)

    return "".join(out), len(before)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    total_files = total_fields = 0

    for wdr in sorted(DRIVERS_DIR.rglob("*.wdr")):
        text = wdr.read_text(encoding="utf-8", errors="replace")
        new_text, n = migrate(text)
        if n == 0:
            continue
        total_files += 1
        total_fields += n
        rel = wdr.relative_to(DRIVERS_DIR)
        print(f"{'[DRY] ' if args.dry_run else ''}moved {n} field(s): {rel}")
        if not args.dry_run:
            wdr.write_text(new_text, encoding="utf-8")

    tag = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{tag}Migrated {total_fields} boxbench_ fields in {total_files} files.")


if __name__ == "__main__":
    main()
