# Driver library & federation

Resonate's driver data is meant to be an open commons — but a commons doesn't
have to live in one place. Two ways drivers reach the tool:

1. **Bundled** — `.wdr` files in subfolders here. Each subfolder has a `meta.json` with provenance. The `mtg90/`
   collection (~429 files) is
   from [mtg90's AVS Forum post](https://www.avsforum.com/threads/common-sub-driver-winisd-files.2928258/).
2. **Federated** — links to *other people's* driver libraries, listed in
   [`sources.json`](sources.json). Resonate's in-app **driver browser** reads
   those sources and fetches `.wdr` files on demand, so we link instead of copy.
   No re-hosting, no staleness, the original maintainer stays in control.

You can also paste **any** GitHub repo of `.wdr` files into the browser to read
it ad hoc, without it being in the list.

## Add a federated source

Open a PR appending an entry to [`sources.json`](sources.json):

```json
{
  "name": "Your Library Name",
  "type": "github",
  "repo": "owner/repo",
  "branch": "main",
  "path": "subfolder-or-empty-string",
  "fileExtension": ".wdr",
  "url": "https://github.com/owner/repo",
  "description": "What's in it.",
  "license": "the source's license"
}
```

- `type` — currently `github` (the browser enumerates files via the GitHub API
  and fetches raw content; both allow cross-origin reads).
- `path` — `""` for repo root, or a subfolder like `"drivers"`.
- Only metadata lives here — the driver files stay in the source repo.

## Add a bundled driver

Create or use an appropriate subfolder (or `drivers/` root for one-offs), drop a
`.wdr` file there, add provenance to the subfolder's `meta.json`, and open a PR.
Import the spec sheet in the app first and sanity-check the curves.

## File format

`.wdr` is WinISD's driver format: INI-style text, a `[Driver]` section of
`Key=Value` lines in SI units. Resonate imports the core T/S set and re-derives a
self-consistent parameter set (scraped files are often internally inconsistent).

Spotted a wrong number? Open a PR — the point of an open commons is that anyone
can correct it.

### WDR field schema (derived from all bundled collections, 2026-06-24)

Every generated or scraped `.wdr` file **must** follow this schema exactly.
Wrong field names (e.g. `Z=` instead of `Znom=`, `Bl=` instead of `BL=`) will
cause silent import failures or wrong values in Resonate.

#### Provenance fields (always present — use empty string if unknown)

| Field           | Type     | Notes                                                                     |
|-----------------|----------|---------------------------------------------------------------------------|
| `Brand=`        | string   | Canonical manufacturer brand — see multi-word brands list below           |
| `Model=`        | string   | Manufacturer model number/name, verbatim from datasheet                   |
| `Manufacturer=` | string   | Full legal manufacturer name; often same as Brand; leave empty if unknown |
| `ProvidedBy=`   | string   | Data source, e.g. `SB Acoustics website (scraped 2026-06-24)`             |
| `Comment=`      | string   | Free text; include source URL and any caveats                             |
| `DateAdded=`    | YYYYMMDD | Date first added; empty if unknown                                        |
| `DateModified=` | YYYYMMDD | Date last changed; empty if unknown                                       |

#### Core T/S parameters — SI units throughout

| Field   | Unit | Notes                                                                                 |
|---------|------|---------------------------------------------------------------------------------------|
| `Fs=`   | Hz   | Free-air resonance                                                                    |
| `Qts=`  | —    | Total Q factor                                                                        |
| `Qes=`  | —    | Electrical Q factor                                                                   |
| `Qms=`  | —    | Mechanical Q factor                                                                   |
| `Znom=` | Ω    | **Nominal impedance — `Znom=` NOT `Z=`**                                              |
| `Re=`   | Ω    | DC voice coil resistance                                                              |
| `Le=`   | H    | Voice coil inductance — **H not mH** (e.g. `0.0006` not `0.6`)                        |
| `BL=`   | T·m  | Force factor — **`BL=` NOT `Bl=`**                                                    |
| `Mms=`  | kg   | Moving mass — **kg not grams** (e.g. `0.0245` not `24.5`)                             |
| `Cms=`  | m/N  | Mechanical compliance — **m/N not mm/N** (e.g. `0.00142` not `1.42`)                  |
| `Rms=`  | kg/s | Mechanical resistance                                                                 |
| `Sd=`   | m²   | Effective piston area — **m² not cm²** (e.g. `0.0216` not `216`)                      |
| `Vas=`  | m³   | Equivalent compliance volume — **m³ not litres** (e.g. `0.094` not `94`)              |
| `Xmax=` | m    | **One-way** linear excursion — **m not mm, one-way not p-p** (e.g. `0.0065` not `13`) |
| `Pe=`   | W    | Rated power handling (RMS)                                                            |
| `SPL=`  | dB   | Sensitivity at 2.83 V/1 m; `0` if unknown                                             |

#### Extended WinISD fields (set to `0` if not available — do NOT omit)

| Field       | Notes                                                                                     |
|-------------|-------------------------------------------------------------------------------------------|
| `fLe=`      | Frequency for Le measurement; `0`                                                         |
| `KLe=`      | Le constant; `0`                                                                          |
| `Dia=`      | Nominal diaphragm diameter (m); `0` if unknown                                            |
| `Vd=`       | Peak volume displacement = Sd × Xmax (m³); compute if possible                            |
| `no=`       | Reference efficiency (dimensionless); `0` if unknown                                      |
| `Dd=`       | Effective diameter derived from Sd = π(Dd/2)²; `0` if unknown                             |
| `EBP=`      | Efficiency bandwidth product = Fs/Qes; `0` if unknown                                     |
| `numVC=`    | Number of voice coils; `1` unless specified otherwise                                     |
| `Hc=`       | Voice coil height (m); `0`                                                                |
| `Hg=`       | Gap height (m); `0`                                                                       |
| `SPLmax=`   | Maximum SPL (dB); `0` if unknown                                                          |
| `SPLmaxLF=` | Max low-frequency SPL (dB); `0`                                                           |
| `USPL=`     | Unweighted SPL; `0`                                                                       |
| `alfaVC=`   | Voice coil alpha; `0`                                                                     |
| `Rt=`       | Thermal resistance; `0`                                                                   |
| `Ct=`       | Thermal capacitance; `0`                                                                  |
| `gamma=`    | Computed WinISD parameter; `0`                                                            |
| `Rme=`      | Computed WinISD parameter; `0`                                                            |
| `Mpow=`     | Computed WinISD parameter; `0`                                                            |
| `Mcost=`    | `0`                                                                                       |
| `Gloss=`    | `0`                                                                                       |
| `VCCon=`    | Voice coil connection: `1`=series, `2`=parallel; use `2` as default                       |
| `c=`        | Speed of sound (m/s); use `343.68275625794`                                               |
| `roo=`      | Air density (kg/m³); use `1.20096171470853`                                               |
| `Thick=`    | `0`                                                                                       |
| `Depth=`    | `0`                                                                                       |
| `MagDepth=` | `0`                                                                                       |
| `Magnet=`   | `0`                                                                                       |
| `Basket=`   | `0`                                                                                       |
| `Outer=`    | `0`                                                                                       |
| `Vcd=`      | `0`                                                                                       |
| `DVol=`     | `0`                                                                                       |
| `ParState=` | WinISD bitmask string; use `EEECEENNEENEEEEEEEEEEECENNCCCNNNCCCCECNNNNNNNNECC` as default |

#### CRITICAL rule — never fabricate values

**Only write a field if the source document contained a value for it.**

- If the datasheet/webpage says `0` for a field → write `0`.
- If the datasheet/webpage doesn't mention the field at all → **omit it entirely**. Do NOT substitute `0`, a computed estimate, a "typical" value, or any other placeholder.
- This applies to T/S parameters AND to extended WinISD fields. Missing fields are preferable to fabricated ones — Resonate can handle missing data; it cannot detect silent fabrication.

#### Common mistakes — scrapers and AI agents must avoid these

| Wrong                    | Correct                   | Why                                           |
|--------------------------|---------------------------|-----------------------------------------------|
| `Z=8`                    | `Znom=8`                  | WinISD uses `Znom`; `Z=` is silently ignored  |
| `Bl=7.5`                 | `BL=7.5`                  | Case-sensitive; `Bl=` is not imported         |
| `Le=0.6`                 | `Le=0.0006`               | Must be in H not mH                           |
| `Mms=24.5`               | `Mms=0.0245`              | Must be in kg not grams                       |
| `Cms=1.42`               | `Cms=0.00142`             | Must be in m/N not mm/N                       |
| `Sd=216`                 | `Sd=0.0216`               | Must be in m² not cm²                         |
| `Vas=94`                 | `Vas=0.094`               | Must be in m³ not litres                      |
| `Xmax=13`                | `Xmax=0.0065`             | Must be in m, one-way (÷2 if p-p, then ÷1000) |
| `Name=foo`               | `Brand=foo` + `Model=bar` | No `Name=` field exists in WDR                |
| Omitting extended fields | Set to `0`                | Missing fields break WinISD compatibility     |

---

# Agent rules — importing and fixing `.wdr` files

The sections below apply to **all** bundled driver collections. Per-collection READMEs may add collection-specific rules
on top.

## Known multi-word brands

When splitting a full name into `Brand=` and `Model=`, check this list first. If the brand appears here, use the
canonical form listed — do not split on the first space.

| Filename prefix                 | Canonical `Brand=`             |
|---------------------------------|--------------------------------|
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

If the brand is not in this list, split on the first space as a fallback and add quality **M** for a human to verify.

---

## Standard fixes — apply without raising a quality issue

These are mechanical, deterministic corrections. Apply them silently; note them in the collection-level `meta.json`
transformations log, not in per-file `_meta.json` scores.

| Problem                                                                                                       | Fix                                                                                                                                                                                                                    |
|---------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `Brand=` or `Model=` has leading or trailing whitespace                                                       | Trim it                                                                                                                                                                                                                |
| `Brand=` or `Model=` has leading numeric like `00` that isn't a genuine part or manufacturer prefix           | Trim it                                                                                                                                                                                                                |
| `Brand=` empty, full name is in `Model=`                                                                      | Check the known multi-word brands list above. Use the canonical brand name if found; otherwise split on first space and add quality **M**                                                                              |
| `Brand=` and `Model=` both empty, but filename unambiguously contains both (e.g. `Dayton Audio DCS205-4.wdr`) | Derive `Brand=` and `Model=` from the filename using the known multi-word brands list. Fill in silently — no meta needed if the derivation is unambiguous. If ambiguous, add quality **M**                             |
| `Model=` contains extra description after the model number (e.g. `DS115-8 4in Designer Series`)               | Strip everything after the model number                                                                                                                                                                                |
| Inch mark `"` in `Model=` or `Brand=` (e.g. `8"`)                                                             | Use the manufacturer's code verbatim — CHECK THE MANU WEBSITE. Do not substitute `in` for `"` or vice versa. Filenames only: replace `"` with `in` (OS constraint)                                                     |
| Filename separator mismatch (`_`, `-`, `/`)                                                                   | Use the manufacturer's own separator from their datasheet or website — CHECK THE MANU WEBSITE. `/` becomes `_` in filenames only (OS constraint). If the correct separator cannot be confirmed: add quality **M**      |
| `Brand=` empty or `00`, no name recoverable from fields                                                       | Attempt to derive the canonical manufacturer name from the filename. If derivable: set `Brand=` and `Model=` correctly, add quality **M** for human verification. If manufacturer cannot be derived: add quality **L** |
| Any source (datasheet, manufacturer page, aggregator) was consulted to verify or correct data                 | Add a `"datasheet"` field to the `_meta.json` with the URL. Prefer the manufacturer's own website over aggregators like speakerboxlite                                                                                 |
| `Model=` is a size/type description rather than a part number (e.g. `18in pro`)                               | Search the manufacturer's site or a reliable aggregator to identify the part number by matching T/S parameters. If confirmed: update `Model=` and add `"datasheet"`. If unconfirmed: add quality **M** with detail     |
| Filename contains a year or version marker (e.g. `v2015`, `(2017)`)                                           | Add a `_meta.json` with quality **H** and a `"community"` field explaining the marker, e.g. `"v2015 in filename = 2015 revision"`                                                                                      |
| Filename contains extra description beyond the model number (series name, size, `-subwoofer` suffix, etc.)    | Not an issue — filenames are source identifiers only, not used in the UI. No meta needed unless there is a separate data problem                                                                                       |

---

## Quality review and meta files

Every `.wdr` file **must** have a matching `<filename>_meta.json` file alongside it. This is not optional — the meta
file is how a human reviewer knows whether to trust the data, where to check it, and whether it has been signed off.

**Why the datasheet link is critical:** The T/S parameters in a `.wdr` file are only as trustworthy as the source they
came from. Without the datasheet URL a reviewer has no way to sanity-check the values, catch a unit-conversion error,
or confirm the model number. The datasheet link is the chain of custody for the data. Always record it — even if you
believe the data is correct.

### When to create a meta file

- **Always** — for every scraped or generated `.wdr` file, create a meta file at the same time. Do not wait.
- **Always** — when a datasheet or manufacturer page was discovered or consulted, record the URL even if the data is correct and there
  is no other issue. We MUST have the datasheet link for every file so that we can check manually and/or automate verification later and/or show it on the website.
- **Always** — when human judgment is needed: wrong model number, ambiguous naming, missing T/S parameters.

### Quality scores

| Score | Meaning |
|-------|---------|
| **H** | Filename or naming convention difference only — data is believed correct |
| **M** | Naming inconsistency, scraper-generated (not human-verified), or other uncertainty |
| **L** | Data integrity issue — values are suspected wrong, incomplete, or internally inconsistent |

**Scraped files are always quality M until a human reviews them.** Automated extraction cannot confirm that the page
correctly reflected the datasheet, that units were converted correctly, or that the model number matches the data.

### Meta file schema

```json
{
  "file": "<filename>.wdr",
  "quality": "H | M | L",
  "issue": "<short_snake_case_tag>",
  "detail": "Human-readable description of the issue or provenance.",
  "datasheet": "<url to manufacturer PDF or product page>",
  "community": "Optional: notes about version markers or community provenance.",
  "obsolete": true,
  "reviewedBy": null
}
```

Field notes:

- `file` — basename of the `.wdr` file this meta describes; must match exactly.
- `quality` — always set; use **M** for scraped/unverified, **H** for cosmetic-only issues, **L** for data problems.
- `issue` — short snake_case tag identifying the issue type, e.g. `scraped_not_human_verified`, `model_name_uncertain`,
  `missing_ts_params`. Omit if quality is H and there is no issue beyond the naming convention.
- `detail` — free-text explanation a human reviewer can act on. For scrapers, include the source URL and what was
  extracted. For manual edits, explain what was changed and why.
- `datasheet` — **primary field**. URL of the manufacturer's datasheet PDF or product page. Prefer the manufacturer's
  own website over aggregators (speakerboxlite, parts-express, etc.). Include this field whenever you have a source —
  omit only if no source was found at all.
- `community` — add when the data comes from community measurement, a forum post, or a file with a version/date marker.
- `obsolete` — set to `true` when the driver is confirmed discontinued. Omit otherwise.
- `reviewedBy` — set to the reviewer's name or handle when the data has been manually verified. `null` until then.

### Scraper obligation

Every scraper script **must** write a `_meta.json` alongside every `.wdr` it creates, containing at minimum:

```json
{
  "file": "Brand Model.wdr",
  "quality": "M",
  "issue": "scraped_not_human_verified",
  "detail": "Automatically scraped from <vendor> website on <date>. Parameters not verified by a human.",
  "datasheet": "<pdf url if found>",
  "reviewedBy": null
}
```

The `datasheet` field must be set to the PDF URL whenever the scraper finds one — this is the primary purpose of
downloading the PDF link. The PDF itself can be downloaded to `datasheets/` for local reference, but the URL in the
meta file is what matters for reviewers.
