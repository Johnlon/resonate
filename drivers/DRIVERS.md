# Driver library data model

## File format — WDR

Each driver is a single `.wdr` file (WinISD Driver Record). The format is plain
`key=value`, one field per line, with a `[Driver]` section header. Standard fields
are defined by WinISD; unknown fields are silently ignored by WinISD and other
parsers, making the format safely extensible.

### Standard T/S fields

| Field | Unit | Notes |
|---|---|---|
| `Brand` | — | Manufacturer name |
| `Model` | — | Model number |
| `Fs` | Hz | Free-air resonant frequency |
| `Qts` | — | Total Q |
| `Qes` | — | Electrical Q |
| `Qms` | — | Mechanical Q |
| `Vas` | m³ | Equivalent acoustic compliance volume |
| `Sd` | m² | Effective piston area |
| `Re` | Ω | DC voice-coil resistance |
| `Le` | H | Voice-coil inductance |
| `BL` | T·m | Force factor |
| `Xmax` | m | Linear peak excursion (one-way) |
| `Mms` | kg | Moving mass including air load |
| `Cms` | m/N | Mechanical compliance |
| `Rms` | kg/s | Mechanical resistance |
| `Pe` | W | Rated power (RMS) |
| `Znom` | Ω | Nominal impedance |
| `Vd` | m³ | Peak displacement volume (= Sd × Xmax) |
| `Dd` | m | Effective piston diameter |
| `ProvidedBy` | — | Free-text credit for who supplied the data |
| `Comment` | — | Free-text notes |

---

## Extension fields — `boxbench_` prefix

All Resonate-specific metadata is stored in the same `.wdr` file using a
`boxbench_` prefix so it is clearly namespaced away from WinISD fields.
WinISD and other parsers ignore these lines.

### Defined `boxbench_` fields

| Field | Type | Description |
|---|---|---|
| `boxbench_datasheet` | URL | Direct link to the manufacturer datasheet (PDF or product page). Shown as a clickable link in the driver panel. |
| `boxbench_source` | URL | Product or listing page from which T/S data was fetched. |
| `boxbench_quality` | `H` / `M` / `L` | Data confidence level: **H** = full T/S from manufacturer with exact SKU match; **M** = fetched from a related/successor SKU or cross-checked; **L** = estimated (Re = 0.85 × Znom, Sd from baffle cutout, secondary parameters blank). |
| `boxbench_issue` | string | Short code for a known data issue (e.g. `scraped_not_human_verified`, `model_corrected`, `filename_convention`). |
| `boxbench_detail` | string | Human-readable explanation of the issue or quality note. |
| `boxbench_dq_issue` | string | Data-quality problem flagged during automated DQ review (e.g. `Qts=97.33: physically impossible value`). Drivers with this field should not be used without first looking up the correct value. |
| `boxbench_corrections` | string | Notes on automated corrections applied post-scrape (e.g. HTML entity decoding bugs fixed). |
| `boxbench_community` | string | Community-contributed notes (e.g. filename conventions, revision history). |
| `boxbench_fetched_sku` | string | SKU actually used when the original SKU was discontinued and data was fetched from a successor product. |
| `boxbench_obsolete` | `true` | Marks a driver as discontinued / no longer available. |
| `boxbench_reviewedBy` | string | Name or handle of person who verified the T/S data against the datasheet. Empty until reviewed. |

### Adding new fields

Use the `boxbench_` prefix and a snake_case name. Values must be single-line
(newlines collapse to ` | `). Keep values concise — WDR files are plain text
and should remain human-readable.

---

## Provenance rules

- Every driver file must have `ProvidedBy=` set to the collection or individual
  that supplied the data.
- If the data was scraped automatically, set `boxbench_quality=M` and
  `boxbench_issue=scraped_not_human_verified` until a human verifies it.
- If a `boxbench_dq_issue` is present, the file is flagged for correction and
  must not be treated as authoritative.

---

## What replaced `_meta.json` files

Prior to 2026-06-25 each driver had a companion `DriverName_meta.json` file
holding quality, issue, detail, and datasheet URL. These were merged into the
`.wdr` file itself as `boxbench_*` fields and the JSON files deleted.
Benefits: one file per driver, no synchronisation risk, works with any WDR-aware
tool, and the bundle script only needs to read `.wdr` files.
