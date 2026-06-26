# drivers/sample — WinISD experiment files

This directory contains WDR files created directly in the real WinISD application
to reverse-engineer its internal behaviour. These are **not real drivers** — they use
dummy parameter values chosen to isolate specific WinISD behaviours.

## Files

| File | Purpose |
|------|---------|
| `john all defaults.wdr` | Blank driver — only Brand/Model/Comment set, nothing else entered |
| `John all-manu-populated.wdr` | All enterable (black) fields manually filled with sequential values |
| `John all-manu-populated-init.wdr` | Intermediate save of the above |
| `John all-manu-populated-ex.wdr` | Same, then Fs and Qms knocked out and Xmax deleted |
| `john all set.wdr` | Sequential values typed into every visible field; physical dims left at 0 |
| `john all entered + driver dims.wdr` | Same as above with physical dimension fields also filled |
| `john all entered + driver dim123s.wdr` | Same, with `no` explicitly set to 123 (stored as 1.23) |
| `john-all-noncalc-fields-manually-entered.wdr` | Same scenario as all-manu-populated |

## What was learned

See **[PARSTATE_FINDINGS.md](PARSTATE_FINDINGS.md)** for the full analysis.

Summary: the `ParState=` field is a fixed 49-character WinISD-internal state string.
Each character is `E` (entered by user), `C` (calculated by WinISD), or `N` (not active).
It maps to WinISD's fixed internal 49-parameter list, not to the lines present in the file.

## Authoritative sources

Only two sources are authoritative for WinISD behaviour:

1. **WinISD.exe itself** — behaviour observed by running the application.
2. **WinISD help files** — `research/winisd/help/`.

Do not infer WinISD behaviour from Resonate source code, forum posts, or third-party docs
without cross-checking against one of these two sources.
