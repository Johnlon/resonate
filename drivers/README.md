# Driver library & federation

Resonate's driver data is meant to be an open commons — but a commons doesn't
have to live in one place. Two ways drivers reach the tool:

1. **Bundled** — `.wdr` files in subfolders here. Each subfolder has a `meta.json` with provenance. The `mtg90/` collection (~429 files) is from [mtg90's AVS Forum post](https://www.avsforum.com/threads/common-sub-driver-winisd-files.2928258/).
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

---

# Agent rules — importing and fixing `.wdr` files

The sections below apply to **all** bundled driver collections. Per-collection READMEs may add collection-specific rules on top.

## Known multi-word brands

When splitting a full name into `Brand=` and `Model=`, check this list first. If the brand appears here, use the canonical form listed — do not split on the first space.

| Filename prefix | Canonical `Brand=` |
|---|---|
| `Aurum Cantus` | `Aurum Cantus` |
| `Dayton` / `Dayton Audio` | `Dayton Audio` |
| `EAW` | `EAW (Eastern Acoustic Works)` |
| `eighteensound` / `18 Sound` | `Eighteen Sound` |
| `Faital Pro` / `Fatial Pro` | `Faital Pro` |
| `mcm` / `MCM` | `MCM (MCM Audio Select)` |
| `Peerless` | `Peerless by Tymphany` |
| `PRV Audio` | `PRV Audio` |
| `SB Acoustics` / `SB acoustics` | `SB Acoustics` |
| `Silver Flute` | `Silver Flute` |
| `Stereo Integrity` | `Stereo Integrity` |
| `TC Sounds` | `TC Sounds` |
| `Tang Band` / `Tand Band` | `Tang Band` |

If the brand is not in this list, split on the first space as a fallback and add quality **M** for a human to verify.

---

## Standard fixes — apply without raising a quality issue

These are mechanical, deterministic corrections. Apply them silently; note them in the collection-level `meta.json` transformations log, not in per-file `_meta.json` scores.

| Problem | Fix |
|---|---|
| `Brand=` or `Model=` has leading or trailing whitespace | Trim it |
| `Brand=` or `Model=` has leading numeric like `00` that isn't a genuine part or manufacturer prefix | Trim it |
| `Brand=` empty, full name is in `Model=` | Check the known multi-word brands list above. Use the canonical brand name if found; otherwise split on first space and add quality **M** |
| `Brand=` and `Model=` both empty, but filename unambiguously contains both (e.g. `Dayton Audio DCS205-4.wdr`) | Derive `Brand=` and `Model=` from the filename using the known multi-word brands list. Fill in silently — no meta needed if the derivation is unambiguous. If ambiguous, add quality **M** |
| `Model=` contains extra description after the model number (e.g. `DS115-8 4in Designer Series`) | Strip everything after the model number |
| Inch mark `"` in `Model=` or `Brand=` (e.g. `8"`) | Use the manufacturer's code verbatim — CHECK THE MANU WEBSITE. Do not substitute `in` for `"` or vice versa. Filenames only: replace `"` with `in` (OS constraint) |
| Filename separator mismatch (`_`, `-`, `/`) | Use the manufacturer's own separator from their datasheet or website — CHECK THE MANU WEBSITE. `/` becomes `_` in filenames only (OS constraint). If the correct separator cannot be confirmed: add quality **M** |
| `Brand=` empty or `00`, no name recoverable from fields | Attempt to derive the canonical manufacturer name from the filename. If derivable: set `Brand=` and `Model=` correctly, add quality **M** for human verification. If manufacturer cannot be derived: add quality **L** |
| Any source (datasheet, manufacturer page, aggregator) was consulted to verify or correct data | Add a `"datasheet"` field to the `_meta.json` with the URL. Prefer the manufacturer's own website over aggregators like speakerboxlite |
| `Model=` is a size/type description rather than a part number (e.g. `18in pro`) | Search the manufacturer's site or a reliable aggregator to identify the part number by matching T/S parameters. If confirmed: update `Model=` and add `"datasheet"`. If unconfirmed: add quality **M** with detail |
| Filename contains a year or version marker (e.g. `v2015`, `(2017)`) | Add a `_meta.json` with quality **H** and a `"community"` field explaining the marker, e.g. `"v2015 in filename = 2015 revision"` |
| Filename contains extra description beyond the model number (series name, size, `-subwoofer` suffix, etc.) | Not an issue — filenames are source identifiers only, not used in the UI. No meta needed unless there is a separate data problem |

---

## Quality review

Per-file discrepancies are documented in `<filename>_meta.json` files alongside each `.wdr` file.
Quality scores: **H** = filename convention difference only, **M** = naming inconsistency, **L** = data integrity issue.

Create a `_meta.json` for any file where:
- a datasheet or manufacturer page has been found — always record the URL, even if the data is correct and there is no issue, **or**
- there is a discrepancy requiring human judgment (wrong model number, ambiguous data, missing T/S parameters).

### Meta file schema

```json
{
  "file": "<filename>.wdr",
  "quality": "H | M | L",
  "issue": "<short_snake_case_tag>",
  "detail": "Human-readable description of the discrepancy.",
  "datasheet": "<url>",
  "community": "Optional: notes about version markers or community provenance.",
  "obsolete": true,
  "reviewedBy": null
}
```

- `datasheet` — link to the manufacturer's product page or datasheet. Prefer the manufacturer's own website over third-party aggregators. Add whenever a source was consulted to verify or correct the data. Omit the field entirely if no source was consulted.
- `community` — add when a filename contains a version marker or the data comes from community measurement rather than a datasheet.
- `obsolete` — set to `true` when the driver is confirmed discontinued. Omit otherwise.
- `reviewedBy` — set to the reviewer's name when the issue has been signed off.
