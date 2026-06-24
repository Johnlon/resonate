/**
 * Resonate — engine physics tests
 *
 * Every test describes a human-verifiable physical scenario:
 *   • WHY the expected value is what it is (which law / equation)
 *   • WHY the tolerance is what it is (measurement physics, not guesswork)
 *   • External citation for every non-obvious constant or formula
 *
 * Run: node --test test/engine.test.mjs
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  deriveDriver, sweep, parseWdr, toWdr,
  prTuning, prMassForFp,
  RHO, C,
  highPass, lowPass, linkwitz, peakingEQ, applyFilters,
  cx, cAbs,
} from '../src/core/index.js';

const here = dirname(fileURLToPath(import.meta.url));

// ---------------------------------------------------------------------------
// Reference test driver — a synthetic 6.5" mid-woofer, 8 Ω nominal.
// Values chosen to be representative of a real driver without depending on
// any specific commercial product.  All parameters are in SI units.
// ---------------------------------------------------------------------------
const REF_DRIVER = {
  Fs:   37,      // Hz  — free-air resonance
  Qts:  0.38,    // —   — total Q at Fs
  Qes:  0.40,    // —   — electrical Q at Fs
  Qms:  7.0,     // —   — mechanical Q at Fs
  Vas:  0.030,   // m³  — equivalent compliance volume (= 30 L)
  Sd:   0.0133,  // m²  — effective piston area (~130 cm²)
  Re:   5.6,     // Ω   — voice-coil DC resistance
  Le:   0.7e-3,  // H   — voice-coil inductance
  Xmax: 0.005,   // m   — maximum linear one-way excursion (= 5 mm)
  Pe:   60,      // W   — rated power
  Z:    8,       // Ω   — nominal impedance
};

// ---------------------------------------------------------------------------
// Tolerance constants — documented here so reviewers can challenge them.
// ---------------------------------------------------------------------------

// 0.1 dB: well within the ±0.5 dB uncertainty of calibrated speaker measurements
// (IEC 60268-5 §17 allows ±1 dB for sensitivity).  Used for closed-form comparisons
// where the same equation is used for both sides, so drift is purely numerical.
const SPL_CLOSED_FORM_TOLERANCE_DB = 0.1;

// 0.5 dB: used when comparing against an independent formula (e.g. efficiency formula)
// that has its own rounding path vs the circuit solver.
const SPL_FORMULA_TOLERANCE_DB = 0.5;

// 3 dB/oct: rolloff slope tolerance. The 24 dB/oct theoretical slope is for an ideal
// system; discrete frequency sampling and finite Ql introduce small deviations.
const ROLLOFF_SLOPE_TOLERANCE_DB_OCT = 3;

// 0.5 Hz: tuning frequency tolerance for auto-mass calculations.
const TUNING_FREQ_TOLERANCE_HZ = 0.5;

// 1e-9: floating-point round-trip tolerance (effectively exact).
const ROUNDTRIP_TOLERANCE = 1e-9;

// 1e-4 relative: .wdr round-trip allows tiny rounding from toPrecision(6) formatting.
const WDR_ROUNDTRIP_RELATIVE_TOLERANCE = 1e-4;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Index of the first frequency ≥ f in a sweep fs array */
const idxGe = (fs, f) => fs.findIndex(x => x >= f);

/** Maximum absolute difference between two same-length numeric arrays */
function maxAbsDiff(a, b) {
  let m = 0;
  for (let i = 0; i < a.length; i++) m = Math.max(m, Math.abs(a[i] - b[i]));
  return m;
}

/** dB magnitude of a complex transfer function value */
const dBmag = z => 20 * Math.log10(cAbs(z));


// ===========================================================================
// Sealed box
// ===========================================================================

describe('Sealed box simulation', () => {

  it('SPL curve matches the closed-form Thiele/Small transfer function to within 0.1 dB', () => {
    // The sealed-box SPL transfer function has a known closed form (Small 1972, eq. 9):
    //   G²(x) = x⁴ / ((1 − x²)² + x²/Qtc²),   x = f/fc
    // where fc = Fs·√(1 + Vas/Vb) and Qtc = Qts·√(1 + Vas/Vb).
    // We set Le = 0 to isolate the acoustic response from voice-coil inductance.
    // Ref: Small, R.H. "Closed-Box Loudspeaker Systems — Part I." JAES 20(10) 1972.
    const Vb_m3 = 0.020; // 20 L enclosure volume in m³
    const d = deriveDriver({ ...REF_DRIVER, Le: 0 });
    const fc  = d.Fs  * Math.sqrt(1 + d.Vas / Vb_m3);
    const Qtc = d.Qts * Math.sqrt(1 + d.Vas / Vb_m3);
    const { fs, spl } = sweep(d, 'sealed', {
      Vb: Vb_m3, Ql: 1e6, // Ql → ∞ = lossless box (isolates acoustic response)
      eg: 2.83, fmin: 10, fmax: 1000, N: 300,
    });
    const passbandRef = spl.at(-1); // HF asymptote — reference level
    let maxError = 0;
    for (let i = 0; i < fs.length; i++) {
      const x = fs[i] / fc;
      const closedFormGain = (x ** 4) / ((1 - x * x) ** 2 + (x * x) / (Qtc * Qtc));
      const predicted = passbandRef + 10 * Math.log10(closedFormGain);
      maxError = Math.max(maxError, Math.abs(spl[i] - predicted));
    }
    assert.ok(maxError < SPL_CLOSED_FORM_TOLERANCE_DB,
      `max deviation ${maxError.toFixed(4)} dB exceeds ${SPL_CLOSED_FORM_TOLERANCE_DB} dB limit`);
  });

  it('passband SPL matches the Thiele/Small radiation efficiency formula (Beranek 1954)', () => {
    // Efficiency η₀ = (4π²/c³)·(Fs³·Vas/Qes)
    // Reference sensitivity at 2.83 V (= 1 W into 8 Ω):
    //   Lref = 112.1 + 10·log₁₀(η₀) + 10·log₁₀(V²/Re)
    // Ref: Beranek, L.L. "Acoustics." McGraw-Hill 1954.  See also:
    //   https://en.wikipedia.org/wiki/Thiele/Small_parameters#Efficiency
    const Vb_m3 = 0.020;
    const EG    = 2.83; // V — IEC 60268-5 sensitivity reference voltage
    const d     = deriveDriver({ ...REF_DRIVER, Le: 0 });
    const eta0  = (4 * Math.PI ** 2 / C ** 3) * (d.Fs ** 3 * d.Vas / d.Qes);
    const predicted = 112.1 + 10 * Math.log10(eta0) + 10 * Math.log10(EG ** 2 / d.Re);
    const { fs, spl } = sweep(d, 'sealed', { Vb: Vb_m3, Ql: 1e6, eg: EG, fmin: 10, fmax: 1000, N: 300 });
    const passbandSPL = spl[idxGe(fs, 300)]; // 300 Hz — well above Fs, in the flat passband
    assert.ok(Math.abs(passbandSPL - predicted) < SPL_FORMULA_TOLERANCE_DB,
      `passband ${passbandSPL.toFixed(2)} dB vs predicted ${predicted.toFixed(2)} dB ` +
      `(limit ±${SPL_FORMULA_TOLERANCE_DB} dB)`);
  });

});


// ===========================================================================
// Vented (bass-reflex) box
// ===========================================================================

describe('Vented (bass-reflex) box simulation', () => {

  // Build a vented design tuned to Fb = 30 Hz.  Sp and Leff derived from the
  // Helmholtz formula: Map = ρ·Leff/Sp,  Cab = Vb/(ρc²),  fb = 1/(2π·√(Map·Cab)).
  // Ref: https://en.wikipedia.org/wiki/Helmholtz_resonance#Resonant_frequency
  const Vb_m3 = 0.020;
  const Fb_Hz  = 30;
  const Sp_m2  = Math.PI * 0.025 ** 2; // π·r² for a 50 mm diameter port
  const Cab    = Vb_m3 / (RHO * C * C);
  const wb     = 2 * Math.PI * Fb_Hz;
  const Map    = 1 / (wb * wb * Cab); // acoustic mass for Fb
  const Leff   = Map * Sp_m2 / RHO;  // effective duct length (including end correction)
  const d      = deriveDriver(REF_DRIVER);
  const { fs, spl, zmag } = sweep(d, 'vented', {
    Vb: Vb_m3, Ql: 7, Sp: Sp_m2, Leff, eg: 2.83, fmin: 10, fmax: 1000, N: 300,
  });

  it('rolls off at approximately 24 dB/octave below tuning — the 4th-order Butterworth slope', () => {
    // Theory: below Fb, a vented box is a 4th-order high-pass with 24 dB/oct rolloff.
    // We measure the slope between 12 and 15 Hz (well below Fb = 30 Hz).
    // Ref: Thiele, A.N. "Loudspeakers in Vented Boxes, Part I." JAES 19(5) 1971.
    //   https://aes.org/e-lib/browse.cfm?elib=1967
    const f1 = 12, f2 = 15; // Hz — two points well below Fb
    const slope = (spl[idxGe(fs, f2)] - spl[idxGe(fs, f1)]) / Math.log2(f2 / f1);
    assert.ok(Math.abs(slope - 24) < ROLLOFF_SLOPE_TOLERANCE_DB_OCT,
      `rolloff slope ${slope.toFixed(1)} dB/oct — expected 24 ±${ROLLOFF_SLOPE_TOLERANCE_DB_OCT} dB/oct`);
  });

  it('shows exactly two impedance peaks straddling the box tuning frequency Fb', () => {
    // At resonance the vented box splits the single sealed-box peak into two peaks —
    // one below and one above Fb.  This is the acoustic signature of a tuned reflex cabinet.
    // Ref: Small, R.H. "Vented-Box Loudspeaker Systems — Part I." JAES 21(5) 1973.
    //   https://aes.org/e-lib/browse.cfm?elib=2149
    const Re = d.Re; // driver DC resistance — peaks must be well above this
    const peaks = [];
    for (let i = 1; i < zmag.length - 1; i++) {
      if (zmag[i] > zmag[i - 1] && zmag[i] > zmag[i + 1] && zmag[i] > Re * 1.5) {
        peaks.push(+fs[i].toFixed(1));
      }
    }
    assert.equal(peaks.length, 2,
      `expected 2 impedance peaks, found ${peaks.length}: ${JSON.stringify(peaks)}`);
    assert.ok(peaks[0] < Fb_Hz,
      `lower peak ${peaks[0]} Hz should be below Fb (${Fb_Hz} Hz)`);
    assert.ok(peaks[1] > Fb_Hz,
      `upper peak ${peaks[1]} Hz should be above Fb (${Fb_Hz} Hz)`);
  });

});


// ===========================================================================
// Passive radiator box
// ===========================================================================

describe('Passive radiator box simulation', () => {

  const PR_PARAMS = {
    Vb:     0.02,   // m³ — 20 L enclosure
    Ql:     7,      // —  — box leakage Q (same as vented default)
    eg:     2.83,   // V  — IEC 60268-5 reference voltage
    prSd:   0.0133, // m² — PR piston area (same as driver)
    prMmd:  0.010,  // kg — PR moving mass (no added weight)
    prMadd: 0.020,  // kg — 20 g added mass (shifts Fp down)
    prCms:  0.0008, // m/N — PR compliance
    prRms:  1.0,    // kg/s — PR mechanical damping
    prXmax: 0.012,  // m  — PR linear excursion limit (12 mm)
    fmin: 10, fmax: 1000, N: 300,
  };
  const d  = deriveDriver(REF_DRIVER);
  const sw = sweep(d, 'pr', PR_PARAMS);

  it('produces a non-zero excursion curve for the PR cone alongside the main driver curve', () => {
    // The PR is acoustically coupled to the box; at resonance it moves significantly.
    assert.equal(sw.excPR.length, sw.fs.length,
      'PR excursion array length should match frequency array length');
    assert.ok(Math.max(...sw.excPR) > 0,
      'PR peak excursion should be positive (PR is moving)');
  });

  it('the theoretical Fp (from prTuning formula) sits between the two impedance peaks', () => {
    // Like a vented box, the PR system shows two impedance peaks straddling the tuning freq Fp.
    // Ref: Small, R.H. "Passive-Radiator Loudspeaker Systems — Part I." JAES 22(8) 1974.
    //   https://aes.org/e-lib/browse.cfm?elib=2223
    const Re = d.Re;
    const peaks = [];
    for (let i = 1; i < sw.zmag.length - 1; i++) {
      if (sw.zmag[i] > sw.zmag[i - 1] && sw.zmag[i] > sw.zmag[i + 1] && sw.zmag[i] > Re * 1.5) {
        peaks.push(sw.fs[i]);
      }
    }
    const Fp = prTuning(PR_PARAMS);
    assert.equal(peaks.length, 2,
      `expected 2 impedance peaks, found ${peaks.length}`);
    assert.ok(Fp > peaks[0] && Fp < peaks[1],
      `Fp ${Fp.toFixed(1)} Hz should sit between peaks ${peaks[0].toFixed(1)} and ${peaks[1].toFixed(1)} Hz`);
  });

  it('auto-tune computes added mass that achieves the target Fp to within 0.5 Hz', () => {
    // prMassForFp() inverts the Fp formula.  We verify the inversion is accurate.
    const TARGET_FP_HZ = 42; // Hz — a typical low bass tuning
    const totalMass    = prMassForFp(PR_PARAMS, TARGET_FP_HZ);
    const addedMass    = totalMass - PR_PARAMS.prMmd;
    const achievedFp   = prTuning({ ...PR_PARAMS, prMadd: addedMass });
    assert.ok(Math.abs(achievedFp - TARGET_FP_HZ) < TUNING_FREQ_TOLERANCE_HZ,
      `target ${TARGET_FP_HZ} Hz → added ${(addedMass * 1000).toFixed(1)} g → Fp ${achievedFp.toFixed(2)} Hz ` +
      `(limit ±${TUNING_FREQ_TOLERANCE_HZ} Hz)`);
  });

});


// ===========================================================================
// PR parameter conversions: WinISD-style (Fs, Qms, Vas) ↔ T/S (Mms, Cms, Rms)
// ===========================================================================

describe('Passive radiator — WinISD ↔ T/S parameter round-trip', () => {

  // WinISD lets users enter PR parameters as (Fs, Qms, Vas) — the same format
  // as a driver.  Internally these map to (Mms, Cms, Rms) via standard T/S relations.
  // The UI must convert in both directions without drift.
  // Ref: https://en.wikipedia.org/wiki/Thiele/Small_parameters#Small_signal_parameters

  const EXAMPLE_PR = {
    Fs_Hz:  25,     // Hz — free-air resonance of the PR
    Qms:    7,      // —  — mechanical Q
    Vas_L:  18,     // L  — equivalent compliance volume
    Sd_m2:  0.0133, // m² — piston area
  };

  it('WinISD Fs/Qms/Vas converts to Mms/Cms/Rms and back to the exact same Fs/Qms/Vas', () => {
    // Forward: Cms = Vas/(Sd²·ρc²),  Mms = 1/(ωs²·Cms),  Rms = √(Mms/Cms)/Qms
    const Cms   = (EXAMPLE_PR.Vas_L / 1000) / (EXAMPLE_PR.Sd_m2 ** 2 * RHO * C * C);
    const Mms   = 1 / ((2 * Math.PI * EXAMPLE_PR.Fs_Hz) ** 2 * Cms);
    const Rms   = Math.sqrt(Mms / Cms) / EXAMPLE_PR.Qms;
    // Inverse: Fs = 1/(2π·√(Mms·Cms)),  Qms = √(Mms/Cms)/Rms,  Vas = Cms·Sd²·ρc²·1000
    const Fs_rt  = 1 / (2 * Math.PI * Math.sqrt(Mms * Cms));
    const Qms_rt = Math.sqrt(Mms / Cms) / Rms;
    const Vas_rt = Cms * EXAMPLE_PR.Sd_m2 ** 2 * RHO * C * C * 1000;

    assert.ok(Math.abs(Fs_rt  - EXAMPLE_PR.Fs_Hz) < ROUNDTRIP_TOLERANCE,
      `Fs: ${EXAMPLE_PR.Fs_Hz} Hz → Mms/Cms/Rms → ${Fs_rt.toFixed(9)} Hz`);
    assert.ok(Math.abs(Qms_rt - EXAMPLE_PR.Qms)   < ROUNDTRIP_TOLERANCE,
      `Qms: ${EXAMPLE_PR.Qms} → T/S → ${Qms_rt.toFixed(9)}`);
    assert.ok(Math.abs(Vas_rt - EXAMPLE_PR.Vas_L)  < ROUNDTRIP_TOLERANCE,
      `Vas: ${EXAMPLE_PR.Vas_L} L → T/S → ${Vas_rt.toFixed(9)} L`);
  });

});


// ===========================================================================
// .wdr driver file import and export
// ===========================================================================

describe('.wdr driver file import and export', () => {

  // The Tang Band W5-1138SMF .wdr is a committed test fixture — a real driver file
  // from the loudspeakerdatabase repository. Its known parameters are used to
  // verify the parser reads the correct values.
  const TANG_BAND_WDR_PATH = join(here, '..', 'drivers', 'loudspeakerdatabase', 'Tang Band W5-1138SMF.wdr');
  const EXPECTED_MODEL_NAME = 'Tang Band W5-1138SMF';
  const EXPECTED_FS_HZ      = 45;   // Hz  — as written in the .wdr file
  const EXPECTED_SD_M2      = 0.0094; // m² — as written in the .wdr file

  let imported;

  it('reads the model name, Fs, and Sd from a real-world .wdr file', () => {
    imported = parseWdr(readFileSync(TANG_BAND_WDR_PATH, 'utf8'));
    assert.equal(imported.name, EXPECTED_MODEL_NAME,
      `name should be "${EXPECTED_MODEL_NAME}"`);
    assert.equal(imported.Fs, EXPECTED_FS_HZ,
      `Fs should be ${EXPECTED_FS_HZ} Hz`);
    assert.equal(imported.Sd, EXPECTED_SD_M2,
      `Sd should be ${EXPECTED_SD_M2} m²`);
  });

  it('exports to .wdr text and round-trips all T/S parameters to within 0.01%', () => {
    // toWdr uses toPrecision(6) which introduces tiny rounding — relative tolerance
    // of 1e-4 (= 0.01%) captures any real mismatch while allowing formatting drift.
    imported = imported ?? parseWdr(readFileSync(TANG_BAND_WDR_PATH, 'utf8'));
    const roundTripped = parseWdr(toWdr(imported));
    const params = ['Fs', 'Qts', 'Qes', 'Qms', 'Vas', 'Sd', 'Re', 'Le', 'Xmax', 'Pe', 'Z'];
    for (const k of params) {
      if (imported[k] == null) continue;
      const rel = Math.abs(imported[k] - roundTripped[k]) / Math.abs(imported[k]);
      assert.ok(rel < WDR_ROUNDTRIP_RELATIVE_TOLERANCE,
        `${k}: ${imported[k]} → export → import → ${roundTripped[k]} (relative error ${rel.toExponential(2)})`);
    }
  });

  it('the re-imported .wdr is internally self-consistent: deriveDriver gives the same Fs, Qts, Qes', () => {
    // If the export/import round-trip is clean, deriveDriver on the re-imported data
    // should reproduce the same key parameters (within floating-point tolerance).
    imported = imported ?? parseWdr(readFileSync(TANG_BAND_WDR_PATH, 'utf8'));
    const d = deriveDriver(parseWdr(toWdr(imported)));
    assert.ok(Math.abs(d.Fs  - EXPECTED_FS_HZ) < 1e-6,
      `Fs should be ${EXPECTED_FS_HZ} Hz, got ${d.Fs}`);
    assert.ok(Math.abs(d.Qts - 0.49) < 1e-3,
      `Qts should be ~0.49, got ${d.Qts.toFixed(4)}`);
    assert.ok(Math.abs(d.Qes - 0.57) < 1e-3,
      `Qes should be ~0.57, got ${d.Qes.toFixed(4)}`);
  });

});


// ===========================================================================
// Filter chain
// ===========================================================================

describe('Filter chain', () => {

  describe('High-pass filter (2nd order Butterworth, Q = 1/√2)', () => {
    // A 2nd-order Butterworth HP has H(jω) = s²/(s²+(ω₀/Q)s+ω₀²).
    // Key properties at Q = 1/√2 (Butterworth / maximally-flat):
    //   f = fc  → |H| = 1/√2  → -3.0103 dB
    //   f >> fc → |H| → 1     → 0 dB
    //   f = fc/10 → 2nd order → -40 dB (20 dB/dec × 2)
    // Ref: https://en.wikipedia.org/wiki/Butterworth_filter#Transfer_function

    const FC_HZ = 80; // Hz — chosen as a typical subwoofer high-pass point

    it('attenuates by exactly −3 dB at the cutoff frequency', () => {
      const EXPECTED_DB = -3.0103; // = 20·log₁₀(1/√2) — the Butterworth −3 dB point
      const actual = dBmag(highPass(FC_HZ, FC_HZ));
      assert.ok(Math.abs(actual - EXPECTED_DB) < 0.001,
        `HP at fc: ${actual.toFixed(4)} dB (expected ${EXPECTED_DB})`);
    });

    it('passes with < 0.01 dB attenuation one decade above the cutoff', () => {
      const f_above = FC_HZ * 10; // 800 Hz — one decade above fc
      const actual  = dBmag(highPass(f_above, FC_HZ));
      assert.ok(Math.abs(actual) < 0.01,
        `HP 10× above fc: ${actual.toFixed(4)} dB attenuation (limit 0.01 dB)`);
    });

    it('attenuates by approximately −40 dB one decade below the cutoff (2nd-order rolloff)', () => {
      const f_below   = FC_HZ / 10; // 8 Hz — one decade below fc
      const EXPECTED_DB = -40; // 2nd order HP: -20 dB/dec × 2 decades from 8 Hz to 800 Hz
      const actual   = dBmag(highPass(f_below, FC_HZ));
      assert.ok(Math.abs(actual - EXPECTED_DB) < 0.5,
        `HP 10× below fc: ${actual.toFixed(2)} dB (expected ~${EXPECTED_DB} dB)`);
    });
  });

  describe('Low-pass filter (2nd order Butterworth, Q = 1/√2)', () => {
    // LP is the complement of HP — same −3 dB at fc.
    const FC_HZ = 80;

    it('attenuates by exactly −3 dB at the cutoff frequency', () => {
      const EXPECTED_DB = -3.0103;
      const actual = dBmag(lowPass(FC_HZ, FC_HZ));
      assert.ok(Math.abs(actual - EXPECTED_DB) < 0.001,
        `LP at fc: ${actual.toFixed(4)} dB (expected ${EXPECTED_DB})`);
    });
  });

  describe('Peaking (parametric) EQ', () => {
    // H(s) = (s² + (V·ω₀/Q)s + ω₀²) / (s² + (ω₀/Q)s + ω₀²),  V = 10^(gain/20)
    // At f = fc: |H| = V (the requested gain).  At DC and HF: |H| = 1 (unity).
    // Ref: https://en.wikipedia.org/wiki/Audio_equalization#Parametric_equalizer

    const FC_HZ  = 300; // Hz — test centre frequency
    const Q      = 1.0; // — — bandwidth (1 octave at −3 dB points)
    const GAIN_DB = 6;  // dB — boost by 6 dB

    it('boosts by the specified gain (+6 dB) at the centre frequency', () => {
      const actual = dBmag(peakingEQ(FC_HZ, FC_HZ, Q, GAIN_DB));
      assert.ok(Math.abs(actual - GAIN_DB) < 0.01,
        `PEQ at fc: ${actual.toFixed(3)} dB (expected +${GAIN_DB} dB)`);
    });

    it('returns unity gain (0 dB) at DC (very low frequency)', () => {
      const f_dc = 0.001; // 0.001 Hz — effectively DC for audio purposes
      const actual = dBmag(peakingEQ(f_dc, FC_HZ, Q, GAIN_DB));
      assert.ok(Math.abs(actual) < 0.1,
        `PEQ at DC: ${actual.toFixed(3)} dB (expected 0 dB)`);
    });

    it('returns unity gain (0 dB) well above the centre frequency', () => {
      const f_hf = 30_000; // 30 kHz — well above any audio band
      const actual = dBmag(peakingEQ(f_hf, FC_HZ, Q, GAIN_DB));
      assert.ok(Math.abs(actual) < 0.01,
        `PEQ at HF: ${actual.toFixed(3)} dB (expected 0 dB)`);
    });
  });

  describe('Linkwitz transform', () => {
    // Reshapes sealed-box response from (f0, Q0) to (fp, Qp).
    // H(s) = (s²+(ω₀/Q₀)s+ω₀²) / (s²+(ωₚ/Qₚ)s+ωₚ²)
    // At HF both numerator and denominator → 1 (all-pass at high frequency).
    // Ref: https://en.wikipedia.org/wiki/Linkwitz_transform

    it('approaches unity gain well above the transform frequencies', () => {
      const f_hf = 30_000; // Hz — well above f0=50 Hz and fp=20 Hz
      const actual = dBmag(linkwitz(f_hf, /* f0 */ 50, /* Q0 */ 0.7, /* fp */ 20, /* Qp */ 0.5));
      assert.ok(Math.abs(actual) < 0.01,
        `Linkwitz at HF: ${actual.toFixed(3)} dB (expected 0 dB)`);
    });
  });

  describe('Filter cascade and bypass', () => {

    it('an empty filter array leaves the SPL curve completely unchanged', () => {
      // When no filters are applied the engine must produce identical results.
      const d = deriveDriver({ ...REF_DRIVER, Le: 0 });
      const Vb_m3 = 0.020;
      const opts = { Vb: Vb_m3, Ql: 1e6, eg: 2.83, fmin: 10, fmax: 1000, N: 50 };
      const base   = sweep(d, 'sealed', opts);
      const filtered = sweep(d, 'sealed', { ...opts, filters: [] });
      assert.equal(maxAbsDiff(base.spl, filtered.spl), 0,
        'SPL with filters:[] should be bit-for-bit identical to SPL with no filters key');
    });

    it('a disabled filter has no effect on the output', () => {
      // Disabled filters must be silently skipped — not evaluated and multiplied in.
      const GAIN_DB = 12; // dB — large gain; any effect would be obvious
      const H = applyFilters(1000, [{ type: 'peaking', enabled: false, fc: 1000, Q: 1, gain: GAIN_DB }]);
      assert.ok(Math.abs(cAbs(H) - 1) < ROUNDTRIP_TOLERANCE,
        `disabled filter: |H| = ${cAbs(H).toFixed(12)} (expected 1.0)`);
    });

    it('an active high-pass filter visibly reduces SPL below its cutoff', () => {
      // At 10 Hz (7 octaves below 80 Hz), a 2nd-order HP should reduce SPL by
      // approximately 7×12 ≈ 84 dB (2nd order = 12 dB/oct).  We simply assert
      // a large reduction relative to the unfiltered curve to confirm the filter
      // is actually being applied to the sweep.
      const d = deriveDriver({ ...REF_DRIVER, Le: 0 });
      const Vb_m3 = 0.020;
      const opts = { Vb: Vb_m3, Ql: 1e6, eg: 2.83, fmin: 10, fmax: 1000, N: 50 };
      const HP_FC_HZ  = 80;
      const REDUCTION_FLOOR_DB = 20; // 10 Hz is 3 octaves below 80 Hz → ≥36 dB expected; 20 dB is conservative
      const base     = sweep(d, 'sealed', opts);
      const withHP   = sweep(d, 'sealed', {
        ...opts,
        filters: [{ id: 1, type: 'highpass', enabled: true, fc: HP_FC_HZ, Q: Math.SQRT1_2 }],
      });
      const i10 = idxGe(withHP.fs, 10);
      assert.ok(withHP.spl[i10] < base.spl[i10] - REDUCTION_FLOOR_DB,
        `HP-filtered SPL at 10 Hz: ${withHP.spl[i10].toFixed(1)} dB, ` +
        `unfiltered: ${base.spl[i10].toFixed(1)} dB — expected >${REDUCTION_FLOOR_DB} dB reduction`);
    });

    it('an active high-pass filter leaves SPL unchanged well above its cutoff', () => {
      const d = deriveDriver({ ...REF_DRIVER, Le: 0 });
      const Vb_m3 = 0.020;
      const opts = { Vb: Vb_m3, Ql: 1e6, eg: 2.83, fmin: 10, fmax: 1000, N: 50 };
      const HP_FC_HZ = 80;
      const PASSBAND_TOLERANCE_DB = 0.5;
      const base   = sweep(d, 'sealed', opts);
      const withHP = sweep(d, 'sealed', {
        ...opts,
        filters: [{ id: 1, type: 'highpass', enabled: true, fc: HP_FC_HZ, Q: Math.SQRT1_2 }],
      });
      const i800 = idxGe(withHP.fs, 800); // 800 Hz — one decade above fc
      assert.ok(Math.abs(withHP.spl[i800] - base.spl[i800]) < PASSBAND_TOLERANCE_DB,
        `HP-filtered vs unfiltered SPL at 800 Hz: diff ` +
        `${Math.abs(withHP.spl[i800] - base.spl[i800]).toFixed(2)} dB ` +
        `(limit ${PASSBAND_TOLERANCE_DB} dB)`);
    });

  });

});
