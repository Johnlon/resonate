# Matt (mtg90) driver collection

Contributor: Matt, known as mtg90 on AVS Forum
Source: https://www.avsforum.com/threads/common-sub-driver-winisd-files.2928258/

General import and fixing rules are in [`drivers/README.md`](../README.md). The sections below are specific to this collection.

---

## WT3 filename prefix

`WT3 ` is **not** a username — `WT3` is the Woofer Tester 3, a T/S measurement device. mtg90 stated (AVS Forum post #3, Oct 23 2017):

> "Anything with the WT3 prefix means I tested that driver on either the WT3 or DATS v2 at some point and those are the specs I measured."

These are real measured T/S parameters, not manufacturer spec-sheet data. Variance from published datasheets is expected and not a quality issue. The prefix is a measurement provenance marker:

- **Keep it in the filename** — it is the contributor's original file name and must not be changed.
- **Do not carry it into `Brand=` or `Model=`** — strip `WT3 ` from those fields.
- Every WT3 file has a `_meta.json` recording this provenance for display in the UI.

---

## Transformations applied and signed off by John Lonergan

The following changes were made to the original files before inclusion. The AI may use these for guidance, but should not apply them automatically without human review.

- Stripped the `00 ` sort-prefix from all filenames (original files used `00 <name>.wdr` as a WinISD sort trick — a personal hack to force entries to the top of a list; not a canonical name and interferes with duplicate detection, search, and filtering)
- Stripped the `00 ` sort-prefix from the `Brand=` field inside each file (same reason as above)
- Renamed `Dayton <model>.wdr` to `Dayton Audio <model>.wdr` for filename consistency
- Updated `Brand=Dayton` to `Brand=Dayton Audio` inside each affected file
- Fixed brand typo in `Faital Pro 15FH510.wdr`: `Failtal Pro` corrected to `Faital Pro`
- RCF `L10/568H` and `L15/554K`: manufacturer uses hyphen (`L10-568H`, `L15-554K`) — internal model fields use slash, filenames use underscore. Pending rename to correct hyphen form.
- Removed `Brand=00` from `Aura NS6-255-8A.wdr`, `B&C 8PE21 8in Woofer.wdr`, `WT3 Sony 5.25 Neo woofer buyout.wdr` — these had Brand set to the bare value `00` with the full name crammed into Model
- Stripped `Brand=WT3 <brand>` prefix from all 53 WT3 files — `WT3` belongs in the filename only, not in `Brand=`
