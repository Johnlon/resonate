# WinISD Help File Evidence Index

All 21 HTML files in `C:\ProgramData\winisd\help\` have been read in full.
This document summarises each file and records the facts that are authoritative
for WinISD behaviour (as opposed to general acoustics background).

**Source path:** `C:\ProgramData\winisd\help\`  
**Version:** WinISD Pro 0.7 (Linearteam)  
**Read date:** 2026-06-26

---

## Index

| File | Section | Key authoritative content |
|------|---------|--------------------------|
| `index.html` | — | Directory listing only |
| `usingwinisd/gettingstarted.html` | Using WinISD | Project workflow, driver selection, EBP bar |
| `usingwinisd/boxdesign.html` | Using WinISD | All box-design tabs; loss params (Ql/Qa/Qp); PR tab |
| `usingwinisd/newdriver.html` | Using WinISD | Driver entry, ParState colours, entry order |
| `usingwinisd/graphs.html` | Using WinISD | Every graph type, excursion convention, port velocity limit |
| `usingwinisd/plottypes.html` | Using WinISD | Duplicate of graphs.html (shorter form) |
| `usingwinisd/options.html` | Using WinISD | Options dialog, env defaults, user name |
| `usingwinisd/filtersimulator.html` | Using WinISD | All filter types, parameters, behavioural sim |
| `usingwinisd/fsimexample.html` | Using WinISD | Subsonic filter for ported box; plate-amp filter params example (SOS with Q=1.5811) |
| `faq/faq.html` | FAQ | Net vs gross box volume; port end correction; Vas air-dependence |
| `articles/thielesmall.html` | Articles | Authoritative definitions of every T/S field |
| `articles/boxtypes.html` | Articles | Sealed/vented/PR/bandpass trade-offs |
| `articles/portterminology.html` | Articles | Acoustical/physical port length; end correction table |
| `articles/crossovers.html` | Articles | Passive/active crossover theory; cap/inductor formulas |
| `articles/db_oct_hertz.html` | Articles | dB, octave, hearing background |
| `technical/aboutequivalentcircuits.html` | Technical | Equivalent circuit model; all key formulas |
| `technical/closed.html` | Technical | Image only (closed eq circuit diagram) |
| `technical/vented.html` | Technical | Image only (vented eq circuit diagram) |
| `technical/pr.html` | Technical | Image only (passive radiator eq circuit diagram) |
| `technical/bp4.html` | Technical | Image only (4th-order bandpass eq circuit diagram) |
| `technical/bp6a.html` | Technical | Image only (6th-order bandpass type A eq circuit diagram) |

---

## File summaries

### `usingwinisd/newdriver.html` — Entering your own drivers

The most important file for WDR field mapping and ParState reverse-engineering.

**ParState colour coding (authoritative):**
- Green = user entered (E in ParState)
- Blue = calculated (C in ParState)
- Black = not entered / not calculated (N in ParState)

**Recommended entry order:**
1. Enter Mms + Cms (computes Fs)
2. Enter Sd, BL, Re (computes Qes, Qms, Qts, Vas, no, EBP, etc.)
3. Enter Rms or Qms directly if known
4. Enter Hc + Hg + Pe
5. Enter numVC
6. Correct Znom last

**Vcd (voice coil diameter):** "Only one which is not illustrated, is the voice coil diameter, VCd." — confirms Vcd is a dimension field, not a volume field.

**DVol:** Computed from the physical dimension fields (Thick/Depth/MagDepth/Magnet/Basket/Outer/Vcd). "It shows then approximate displacement volume DVol."

**Xmax entry (Scan-Speak example):** WinISD shows `Excursion, lin./max. ±6.5/±12 mm` from a Scan-Speak datasheet and takes the linear (one-way) value = 6.5 mm. Xmax in WinISD is a **peak (one-way)** value.

**Dia field:** The help uses "put a speaker diameter of 8.0 in." in the units-change example. This is likely what Dia represents — the nominal diaphragm/speaker diameter. It is always 0 in scraped WDR files because no scraper populates it and WinISD does not compute it from other fields.

**"Auto calculate unknowns"** checkbox controls whether WinISD cascades computed fields. Must be enabled for single-param probe methodology to produce clean E→C cascade.

---

### `articles/thielesmall.html` — T/S parameter definitions

Authoritative definitions for all WDR fields, written by Claus Futtrup (credited).

| Field | Definition |
|-------|-----------|
| Qes | Electrical Q (electrical damping at Fs). Lower = higher damping. |
| Qms | Mechanical Q (mechanical damping at Fs). Lower = higher damping. |
| Qts | Total Q = parallel coupling of Qms and Qes. |
| Vas | Equivalent volume of air to Cms (compliance equivalent). |
| Fs | Free-air resonance frequency. |
| Mms | Mechanical mass of vibrating assembly **including air load**. |
| Cms | Compliance (inverse of spring stiffness). |
| Rms | Mechanical damping including resistive part of radiation load. |
| Re | DC resistance of voice coil. |
| BL | B × L (magnetic flux density × wire length in gap). |
| Dd | Diameter of diaphragm. |
| Le | Voice coil inductance. |
| Sd | Surface area of diaphragm. |
| fLe | Frequency at which Le and KLe are determined. |
| KLe | Voice coil semi-inductance [H·sqrt(Hz)], Vanderkooy model. |
| Xmax | "Max linear excursion, usually calculated as abs(Hc-Hg)/2 … **WinISD needs this as peak value.**" Some manufacturers give it as damage limit (Xlim); WinISD does not apply the 1.15/0.87 multiplication factor. |
| Xlim | Damage-limit excursion, also peak value. |
| Hc | Height of voice coil. |
| Hg | Height of airgap. |
| Vd | Volume displacement (air moved in linear range). |
| Pe | Thermal max continuous electrical power handling. |
| no | Efficiency η₀ in percent [%]. |
| Znom | Nominal impedance — "**not used in simulation**". |
| USPL | Voltage sensitivity [dB/2.83V]. Different from SPL (power sensitivity) for non-8Ω drivers. |
| SPL | Power sensitivity [dB/W] at 1m, half-space (2π), voltage drive. "Do not use manufacturer's stated SPL value unless needed to compute T/S params." |
| Voicecoils (numVC) | Descriptive only. 1 = standard; 2 = DVC. |
| alfaVC | Resistance temperature coefficient [1/K]. Copper ≈ 0.0039 1/K at +20°C. |
| Rt | Thermal resistance, voice coil to ambient [K/W]. **Not yet used in simulation.** |
| Ct | Thermal capacity of VC assembly [J/K]. **Not yet used in simulation.** |
| SPLmaxLF | Max SPL at 20 Hz in closed/IB half-space at Xmax. "Feeling" for Vd. Does not apply to vented or other assisted enclosures. |
| SPLmax | Max thermal SPL [dB] at Pe, assuming 3 dB power compression, 2π space. |
| Rme | Electromagnetic damping [N·s/m] — motor system control. Related to Qes (like Rms/Qms). |
| Gamma | Acceleration factor [m/(s²·A)]. |
| Mpow | Motor power-factor [N/sqrt(W)]. sqrt(Rme). Impedance-independent. |
| Mcost | Motor cost-factor [N·s/m] — motor power weighted by Xmax excursion efficiency. |
| EBP | Efficiency-Bandwidth-Product [Hz]. |
| Gloss | Cone sag [%] when mounted horizontally. g = 9.80665 m/s². >5% = avoid horizontal mount. |
| Thick | Basket plate thickness (dimension). |
| Depth | Driver mounting depth (dimension). |
| Magnet Depth (MagDepth) | Magnet depth/height/thickness (cylinder height). |
| Magnet | Magnet diameter. |
| Basket | Basket diameter — "the hole to cut in the baffle". |
| Outer | Outer diameter — "the space to make room for on the baffle". |
| VCd (Vcd) | Voice coil diameter. |
| Dvol (DVol) | "Driver displacement volume. Approx. the box volume occupied by the driver, when mounted with magnet pointing into the box." Computed from physical dims. |

**Key Xmax fact:** "WinISD needs this as peak value." — the one-way (peak) excursion, not p-p and not the damage limit (Xlim). This confirms the SB Acoustics scraper's 0.5e-3 factor for p-p mm → one-way m is correct.

---

### `usingwinisd/boxdesign.html` — Box design

**Box losses** (under Advanced→ in Box tab):
- **Ql** (leakage losses): leaks in enclosure or driver. Most dominant in vented. Typical 5–20. WinISD Pro default = **10**.
- **Qa** (absorption losses): enclosure stuffing. No stuffing ≈ 100. Heavily stuffed ≈ 3–5.
- **Qp** (port losses): port friction. Very small value → turns vented into closed.

**Net volume:** WinISD shows net (internal) volume. User must add driver/port/brace displacements manually.

**Signal Tab:** "Power" = P = Eg²/Re where Eg is RMS amplifier output voltage and Re is DC resistance. This is "not the power taken from the amplifier" (impedance varies). Series resistance default = 0.1 Ω.

**PR tab:** Mass can be added per PR unit. WinISD shows new resonance frequency with added mass.

---

### `faq/faq.html` — FAQ

**Box volume:** "WinISD doesn't do guessing, and therefore shows **net volume** for your box." User must add displacements manually. (Confirmed from boxdesign.html.)

**Port length:** Assumes one flanged + one free end. End correction factor = 0.732 (i.e. 0.42441 + 0.30665 × diameter). Port length includes the wall thickness.

**Vas air-dependence:** "Since Vas depends on current air properties, there is no absolutely 'correct' Vas value existing. So every time you'll adjust your room temperature, air properties will change, and your Vas will be different. My advice is to avoid entering Vas whenever possible." This explains why Janne recommends entering Mms/Cms/Sd/BL/Re rather than Vas directly.

---

### `usingwinisd/graphs.html` — Graph types

**Cone excursion:** Three configurable display modes — RMS, Peak, Peak-to-peak (p-p). "The peak value is perhaps a most practical expression, because driver parameter Xmax indicates how much cone can be deflected from its rest position linearly, in either direction." Many programs show RMS excursion but label the limit as peak — over-optimistic; WinISD avoids this.

**Port air velocity limit:** 5% of sound velocity ≈ 17 m/s (peak). Also configurable as RMS/peak/p-p.

**SPL graph:** Sound pressure at specified distance at specified power, radiated to half-space (2π). "To get the full-space value, subtract 6 dB."

**Transfer function magnitude:** Gain relative to driver's limit efficiency η₀.

**Group delay:** Derivative of negative phase vs frequency [rad/s]. Flat = good. "If you are wondering why the group delay of vented box is very different from WinISD version 0.43 and below, the reason is that it calculated it wrong."

---

### `technical/aboutequivalentcircuits.html` — Equivalent circuit formulas

The simulation model (all circuits reduced to acoustical side):

```
Ccas = Vas / (roo · c²)                          # driver compliance
Lmas = 1 / ((2π·Fs)² · Ccas)                    # driver mass
Rae  = 1 / (2π·Fs · Qes · Ccas)                  # electrical damping
Ram  = 1 / (2π·Fs · Qms · Ccas)                  # mechanical damping
```

Box volume modelled as capacitor Ccab (same formula as Ccas).

Far-field pressure: `p(r) = roo·s·U0(ω)/(2π·r) · exp(-j·k·r)` where k=ω/c, r=distance. Phase factor `exp(...)` is neglected in WinISD for cleaner graphs.

**Cone excursion:** Volume velocity through driver → integrate → divide by Sd → scale by sqrt(2) for peak or 2·sqrt(2) for p-p.

**Impedance:** `Ze = Re + jω·Le + Bl²/(Sd²·Za)` where Za is acoustical impedance.

Reference: *Introduction to electroacoustics and audio amplifier design*, W. Marshall Leach Jr., Kendall/Hunt, ISBN 0-7872-7861-0.

---

### `articles/portterminology.html` — Port end corrections

End correction factors (multiply by port effective diameter to get extension beyond port end):

| Configuration | End 1 | End 2 | Total |
|--------------|-------|-------|-------|
| Two free ends | 0.30665 | 0.30665 | 0.6133 |
| One flanged + one free | 0.42441 | 0.30665 | **0.7311** |
| Two flanged ends | 0.42441 | 0.42441 | 0.8488 |

**WinISD default:** one flanged (baffle) + one free (inside box) = 0.7311. The FAQ confirms this is 0.732 (rounded).

Physical port length = acoustical length − (effective diameter × end correction).

---

### `usingwinisd/filtersimulator.html` — Filter simulator

Filter types supported:
- Butterworth LP/HP, orders 1–10
- Linkwitz-Riley LP/HP (4th order only) — -6 dB at fc (not -3 dB like Butterworth)
- Bessel LP/HP, orders 1–10 — maximally flat group delay
- Second-order section (user Q + fc)
- Allpass (phase correction only, unity gain)
- Linkwitz transform (closed-box equalizer, no excess phase shift)
- Parametric EQ (fc, Q, gain)
- Peaking 2nd-order HP (subwoofer EQ)
- Static gain

Filter chain is at electrical side; 0 dB = driver terminal voltage = signal tab voltage.

**Linkwitz transform:** f0/Q0 = original closed box Fsc/Qtc; fp/Qp = target. "Keep Qp below 0.707, or otherwise peaking will occur." WinISD autofills f0/Q0 for closed box projects.

---

### `usingwinisd/options.html` — Options dialog

Alt+O opens options. Three tabs:
- **Graph:** colours, plot limits, frequency range
- **General:** environment defaults (temperature, pressure → c and roo); user name (used as default ProvidedBy when entering new drivers)
- **Joystick:** joystick for signal generator

---

### `usingwinisd/gettingstarted.html` — Getting started

EBP bar in "New Project" dialog is a guide to box type:
- High EBP → vented (or 6th-order BP)
- Low EBP → sealed (or 4th-order BP)
- Mid → either

Box type chosen at project creation cannot be changed. Load same driver multiple times for comparison.

---

### `articles/boxtypes.html` — Box type trade-offs

| Type | Pros | Cons |
|------|------|------|
| Sealed | Easiest; handles ultra-low (<30 Hz) well; best transient; supports motion feedback | Less low bass extension; lower efficiency |
| Vented | Better LF extension; higher efficiency; better power handling near Fb | Complex; long ports for small-box low-Fb; driver overextends below Fb |
| Passive radiator | Very low Fb in small boxes; no port noise | PR can run out of excursion; notch at PR Fs impairs transient; not suitable for horizontal mounting |
| Bandpass | Very selective frequency range | Most difficult; always needs a second speaker system for mid-bass |

---

### `technical/closed.html`, `technical/vented.html`, `technical/pr.html`

Image-only pages showing equivalent circuit diagrams (GIF files). No text content beyond the title.

---

## Key cross-references for scraper and WDR writer

| Fact | Source | Implication |
|------|--------|-------------|
| Xmax = peak (one-way) value | thielesmall.html | SB Acoustics p-p÷2 factor is correct |
| Znom "not used in simulation" | thielesmall.html | Safe to omit from Resonate circuit model |
| Rt and Ct "not yet used in simulations" | thielesmall.html | Thermal fields are metadata only |
| Vas is air-property dependent | faq.html | Recommend entering Mms/Cms instead of Vas where possible |
| Net box volume (no driver/port displacement) | faq.html + boxdesign.html | Vb input = net internal volume |
| Default port end correction = 0.732 (one flanged + one free) | faq.html + portterminology.html | Matches Resonate end-correction default |
| Ql default = 10 | boxdesign.html | Matches Resonate vented loss default |
| Vcd = voice coil diameter (not volume) | newdriver.html + thielesmall.html | Field name confirmed |
| DVol = computed displacement volume | newdriver.html + thielesmall.html | Do not scrape from datasheet; leave 0 |
| E = Green, C = Blue, N = Black | newdriver.html | Confirms ParState char mapping |
| WinISD "power" = Eg²/Re not true watts | boxdesign.html + graphs.html | Resonate power input convention matches |
