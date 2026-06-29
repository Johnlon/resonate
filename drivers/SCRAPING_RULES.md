# Scraping rules

Operational guidance for scrapers, batch scripts, and AI agents writing driver data.
Behavioral constraints on the AI itself live in `CLAUDE.md`.
WDR field definitions and canonical units live in `WDR_SCHEMA.md`.

## OCR — PDF extraction settings

Some manufacturer PDFs use Type3 (custom-encoded) fonts that fitz cannot decode
as text. For these, `pdf_lib.py` falls back to tesseract OCR via `_ocr_via_subprocess`.

### DPI: use 300, not higher

**Empirically tested on Scan-Speak 18WE/4542T00 (`drivers/new_ss_tool/datasheets/18we-4542t00.pdf`)
across five resolutions. 12 T/S fields compared against reference values.**

| DPI | Time  | Correct fields | Wrong | Missing | Notes                                    |
| --- | ----- | -------------- | ----- | ------- | ---------------------------------------- |
| 300 | 3.6 s | 8              | 4     | 0       | **Best overall — use this**              |
| 450 | 5.7 s | 6              | 4     | 2       | Ω glyph renders as digit `9` → Znom=49 ✗ |
| 600 | 7.6 s | 6              | 4     | 2       | 2× slower, more missing fields than 300  |
| 750 | 10.8s | 7              | 4     | 1       | 3× slower, no accuracy gain              |
| 900 | 19.2s | 7              | 4     | 1       | 5× slower, no accuracy gain              |

**Correction to the 300 DPI "4 wrong" count:** The test script used wrong reference values
for three fields. The following four fields were counted as "wrong" at 300 DPI, but all four
are OCR errors in the reference, not in the extraction:

| Field | OCR extracted (correct) | Reference used (wrong) | Actual PDF value |
| ----- | ----------------------- | ---------------------- | ---------------- |
| Qms   | 5.62                    | 3.8                    | 5.62             |
| Mms   | 0.01759 kg (17.59 g)    | 0.0615 kg (61.5 g)     | 0.01759 kg       |
| Xmax  | 0.0072 m (7.2 mm)       | 0.009 m (9 mm)         | 0.0072 m         |
| Qes   | 0.26                    | 0.28                   | 0.26             |

When judged against the actual datasheet, 300 DPI extracted all 12 fields correctly.
The key finding — that 450 DPI corrupts Znom via the Ω→9 glyph (Znom reported as 49,
rejected by the ≤32 Ω range gate → counted as "missing") — is independently confirmed
and unaffected by this correction.

**Why 450 DPI is worse than 300:** tesseract's LSTM was trained at ~30–33 px capital-letter
height (per tesseract-ocr/tessdoc ImproveQuality.md §Rescaling). At 300 DPI, A4 datasheet
capitals are ~35 px — right at the sweet spot. At 450 DPI they are ~52 px — above the
training distribution. The Ω glyph at 52 px happens to activate the digit `9` detector
after the LSTM's internal rescaling, whereas at 35 px it activates the letter `Q` detector.
`Q` is non-numeric and gets stripped by the number parser; `9` is a digit and corrupts the
extracted value. 600, 750, and 900 DPI are correct for the Ω glyph (Ω→Q again) but
progressively slower with no accuracy benefit over 300 DPI.

### Tesseract flags

```
--oem 1                    # LSTM engine only (not legacy)
--psm 3                    # auto page segmentation
-c load_system_dawg=0      # disable English dictionary
-c load_freq_dawg=0        # disable frequency dictionary
```

Dictionary flags are critical: T/S parameter tables are pure technical notation.
Without disabling them, tesseract's dictionary pressure "corrects" extracted tokens
toward English words, corrupting field values.
(Source: tesseract-ocr/tessdoc ImproveQuality.md §Dictionaries)

### Do not binarize before passing to tesseract

Adding PIL Otsu binarization (grayscale → threshold at 127) before the tesseract call
was tested and is harmful for T/S parameter tables: it causes tesseract to split the
two-column label|value layout into separate blocks, losing all label-value associations.
Pass the raw 300 DPI PNG directly to tesseract.
(Source: tesseract-ocr/tessdoc ImproveQuality.md §Tables — "tesseract has a problem to
recognize text/data from tables" when preprocessing alters the layout structure.)

## Unit conversions — datasheet → WDR

All WDR fields use SI units. Scrapers must convert from whatever unit the datasheet
or vendor page publishes. From analysis of 411 driver datasheets (WINISD.md §14):

| WDR field     | WDR unit | Typical datasheet unit            | Conversion to WDR                    |
| ------------- | -------- | --------------------------------- | ------------------------------------ |
| Fs            | Hz       | Hz                                | × 1                                  |
| Re            | Ω        | Ω                                 | × 1                                  |
| Znom          | Ω        | Ω                                 | × 1                                  |
| Pe            | W        | W                                 | × 1                                  |
| BL            | T·m      | Tm or T·m                         | × 1                                  |
| Qts, Qms, Qes | —        | —                                 | × 1                                  |
| SPL           | dB       | dB/W/m or dB/2.83V/m              | × 1 (WinISD uses dB/W/m)             |
| Le            | H        | mH                                | ÷ 1,000                              |
| Xmax          | m        | mm (one-way or p-p — see below)   | ÷ 1,000 if one-way; ÷ 2,000 if p-p   |
| Mms           | kg       | g                                 | ÷ 1,000                              |
| Vas           | m³       | L (litres)                        | ÷ 1,000                              |
| Sd            | m²       | cm² (most) or m² (Tang Band)      | ÷ 10,000 if cm²; × 1 if m²           |
| Cms           | m/N      | mm/N (some) or μm/N (Tang Band)   | ÷ 1,000 if mm/N; ÷ 1,000,000 if μm/N |
| Rms           | kg/s     | Rarely listed — usually derived   | —                                    |
| Dd            | m        | mm                                | ÷ 1,000                              |
| Vd            | m³       | Not listed — compute as Sd × Xmax | —                                    |

**Watch out for:**

- **Cms** — μm/N vs mm/N is a 1000× difference and both look plausible. SB Acoustics
  don't publish Cms; Tang Band uses μm/N.
- **Sd** — Tang Band publishes m² directly; SB Acoustics and most European brands use cm².

## Xmax — per-manufacturer conventions

`Xmax` in the WDR **must be stored as one-way peak excursion in metres** (WinISD rule).
Manufacturers publish it in different conventions; the scraper must convert correctly.

| Published convention               | Factor to reach WDR `Xmax=` (metres) |
| ---------------------------------- | ------------------------------------ |
| One-way mm (e.g. `±6.5 mm`)        | `× 0.001`                            |
| Peak-to-peak mm (e.g. `11 mm p-p`) | `× 0.0005` (÷2 then ÷1000)           |

**SoundImports** normalises to one-way before display, regardless of the manufacturer PDF.
The SoundImports scraper always uses `× 0.001` (never `× 0.0005`) even for SB Acoustics
and SEAS. Confirmed: SB17NRXC35-4 manufacturer PDF says "Linear coil travel (p-p) 11 mm";
SoundImports product page says "5.5 mm" (already halved).

**Per-brand evidence table** (applies to manufacturer PDFs and direct-manufacturer scrapers):

| Manufacturer            | Datasheet label                               | Convention         | WDR factor | Evidence                                                                                                                                                    |
| ----------------------- | --------------------------------------------- | ------------------ | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **SB Acoustics**        | "Linear coil travel (p-p)"                    | Peak-to-peak       | `× 0.0005` | Label explicit in every PDF. Confirmed SB17NRXC35-4: 11 mm p-p → 5.5 mm one-way → `Xmax=0.0055`.                                                            |
| **SEAS**                | "Linear Coil Travel (p-p)"                    | Peak-to-peak       | `× 0.0005` | Identical label to SB Acoustics; confirmed across 30+ SEAS PDFs.                                                                                            |
| **Satori**              | Same as SB Acoustics template                 | Peak-to-peak       | `× 0.0005` | Same parent company, same datasheet template.                                                                                                               |
| **Scan-Speak**          | "Linear excursion ±X mm"                      | One-way            | `× 0.001`  | `±` label explicit. Lists "Xdamage (peak to peak)" separately.                                                                                              |
| **Wavecor**             | "Theoretical linear motor stroke, Xmax ±X mm" | One-way            | `× 0.001`  | `±` label explicit in all Wavecor PDFs.                                                                                                                     |
| **Beyma**               | "Maximum Displacement, Xmax ±X mm"            | One-way            | `× 0.001`  | `±` label explicit. Lists "Xdamage (peak to peak)" separately.                                                                                              |
| **Peerless / Tymphany** | "Linear Excursion Xmax X mm"                  | One-way            | `× 0.001`  | Footnote formula `(Hvc − Hag)/2 + Hag/3` produces a one-way result.                                                                                         |
| **Morel**               | "Max. Linear Excursion X ±X mm"               | One-way            | `× 0.001`  | `±` label explicit across all Morel PDFs.                                                                                                                   |
| **Markaudio**           | "X mm (1-way) Xmax"                           | One-way            | `× 0.001`  | "1-way" explicitly written.                                                                                                                                 |
| **HiVi / Swans**        | "Linear Excursion (Xmax)(mm)"                 | ⚠ inferred one-way | `× 0.001`  | No qualifier; needs Hc/Hg cross-check.                                                                                                                      |
| **Dayton Audio**        | "X mm Xmax"                                   | ⚠ inferred one-way | `× 0.001`  | No explicit qualifier on woofer sheets; passive radiator sheets say "peak to peak" when they mean p-p — different labelling implies woofer Xmax is not p-p. |
| **Tang Band**           | "X-max X mm"                                  | ⚠ inferred one-way | `× 0.001`  | Underhung drivers with Hg=10 mm have Xmax=2.4–3 mm — as p-p this would be 1.2–1.5 mm in a 10 mm gap, physically inconsistent as one-way it is normal.       |

**Unlisted brand:** read the datasheet; look for `±`, "p-p", "one-way", or a geometry
formula footnote. If still ambiguous, store as-scraped and add `quality: M` and a
`corrections` note in the `_meta.yml` sidecar recording the uncertainty.

## Known multi-word brands

When splitting a full name into `Brand=` and `Model=`, check this list first. Use the
canonical form shown — do not split on the first space.

| Filename prefix                 | Canonical `Brand=`             |
| ------------------------------- | ------------------------------ |
| `Aurum Cantus`                  | `Aurum Cantus`                 |
| `Dayton` / `Dayton Audio`       | `Dayton Audio`                 |
| `EAW`                           | `EAW (Eastern Acoustic Works)` |
| `eighteensound` / `18 Sound`    | `Eighteen Sound`               |
| `Faital Pro` / `Fatial Pro`     | `Faital Pro`                   |
| `mcm` / `MCM`                   | `MCM (MCM Audio Select)`       |
| `Peerless`                      | `Peerless by Tymphany`         |
| `PRV Audio`                     | `PRV Audio`                    |
| `SB Acoustics` / `SB acoustics` | `SB Acoustics`                 |
| `Silver Flute`                  | `Silver Flute`                 |
| `Stereo Integrity`              | `Stereo Integrity`             |
| `TC Sounds`                     | `TC Sounds`                    |
| `Tang Band` / `Tand Band`       | `Tang Band`                    |

If the brand is not in this list, split on the first space as a fallback and set `quality: M`.

## Standard fixes — apply without raising a quality issue

Mechanical, deterministic corrections. Apply silently.

| Problem                                                       | Fix                                                                                                                                |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `Brand=` or `Model=` has leading/trailing whitespace          | Trim it                                                                                                                            |
| `Brand=` or `Model=` has spurious leading numeric (e.g. `00`) | Trim it                                                                                                                            |
| `Brand=` empty, full name in `Model=`                         | Check multi-word brands list; split on first space as fallback; set `quality: M`                                                   |
| Both empty, filename unambiguously contains both              | Derive from filename using multi-word brands list; if ambiguous set `quality: M`                                                   |
| `Model=` contains extra description after model number        | Strip the extra description                                                                                                        |
| Inch mark `"` in `Model=` or `Brand=`                         | Use manufacturer's verbatim form — check manufacturer website. In filenames only: replace `"` with `in`                            |
| Filename separator mismatch (`_`, `-`, `/`)                   | Use manufacturer's own separator — check manufacturer website. If unconfirmed: set `quality: M`                                    |
| `Brand=` unrecoverable from fields                            | Attempt to derive from filename. If derivable: set correctly, set `quality: M`. If not: set `quality: L`                           |
| Source consulted to verify/correct data                       | Record `datasheet_url: <url>` in `_meta.yml`. Prefer manufacturer's own site over aggregators                                      |
| `Model=` is a size/type description rather than a part number | Search manufacturer's site; if confirmed update `Model=` and set `datasheet_url`; if not: set `quality: M` with `corrections` note |
| Filename contains year or version marker                      | Set `quality: M`, add `community` note e.g. `"v2015 in filename = 2015 revision"`                                                  |

## Schema discipline — hard rule

`scripts/wdr_meta_schema.py` is the **single source of truth** for all fields
that may exist in `.wdr` and `_meta.yml` files.

**Rules for every scraper and every AI agent:**

1. **Never write a field not defined in the schema.** If a field name is not in
   `_WDR_FIELD_SPEC` (for WDR) or `MetaModel` (for `_meta.yml`), it must not be written.

2. **Never add, remove, or rename a field without schema approval.** Before any change:
   - Describe the proposed change to the human: the field name, type, allowed values, unit,
     and why it is needed.
   - Get explicit human approval in the current conversation.
   - Only then update `wdr_meta_schema.py`, then the scraper code, then `WDR_SCHEMA.md §9.1`.

3. **Strict validation runs after every write.** `scraper_lib._scrape_one()` calls
   `validate_driver(wdr_path, meta_path)` after writing each driver's files. If validation
   fails, the driver is counted as failed (`schema_fail` status) and errors are written to
   `_problems.log`. A schema violation is a bug — fix the scraper, not the schema, unless
   the schema itself is wrong.

4. **The schema is not changed unilaterally.** Even if a scraper is already writing an
   undocumented field, the correct fix is to stop writing it (or add it to the schema after
   approval), not to silently accept it.

## Field values and ParState policy

Every field in the WDR has a corresponding ParState character (E/C/N). The scraper must
set both the value and the character correctly according to this policy:

| Situation                                                                  | Value to write   | ParState |
| -------------------------------------------------------------------------- | ---------------- | -------- |
| Field is calculatable; datasheet value present and matches calculated      | calculated value | C        |
| Field is calculatable; datasheet value present but differs from calculated | datasheet value  | E        |
| Field is calculatable; no datasheet value                                  | calculated value | C        |
| Field is not calculatable; datasheet value present                         | datasheet value  | E        |
| Field is not calculatable; no datasheet value                              | `0`              | N        |

**When the datasheet value differs from the calculated value** (row 2): log a DQ alert in
`_problems.log` naming the field, the datasheet value, the calculated value, and the source.
Write the datasheet value with ParState=E — the manufacturer's measured value overrides the
derived one, but the discrepancy must be visible for review.

Do not fabricate or estimate values not supported by source data.

## Minimum scraper obligation

Every scraper must write at minimum these fields into every `_meta.yml` it creates:

```yaml
source: <URL where T/S data was read from>
vendor_page_url: <vendor product page URL>
datasheet_url: <manufacturer PDF URL — omit if not found>
quality: M
issue: scraped_not_human_verified
detail: Automatically scraped from <vendor> on <date>. Not human-verified.
```

For `frd_url` and `zma_url` — follow the inspection workflow in
`drivers/WDR_FILE_MODEL_AND_WORKFLOWS.md` before setting them. Never set `frd_url` to a
URL without verifying the content is Frequency Response Data.

## Quality scores

| Score | Meaning                                                                             |
| ----- | ----------------------------------------------------------------------------------- |
| `H`   | Manufacturer-sourced, human-verified                                                |
| `M`   | Scraped or otherwise unverified — default for all automated imports                 |
| `L`   | Known data problem — values suspected wrong, incomplete, or internally inconsistent |

Scraped files are always `M` until a human verifies T/S values against the datasheet.

**Why the datasheet link matters:** without it a reviewer has no way to sanity-check
values, catch a unit-conversion error, or confirm the model number. It is the chain of
custody for the data.
