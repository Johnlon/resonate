/**
 * Lumped-element acoustical circuit solver.
 *
 * Circuit element equations:
 *
 *   Driver acoustic elements (Cas, Mas, Ras from T/S parameters):
 *   https://en.wikipedia.org/wiki/Thiele/Small_parameters#Small_signal_parameters
 *
 *   Port tuning (Helmholtz resonator, Map = ρ·Leff/Sp):
 *   https://en.wikipedia.org/wiki/Helmholtz_resonance#Resonant_frequency
 *
 *   Loudspeaker electrical characteristics (Ze, gyrator, Zel):
 *   https://en.wikipedia.org/wiki/Electrical_characteristics_of_a_dynamic_loudspeaker
 *
 * Authoritative sources (paywalled):
 *   Small, R.H. "Direct-Radiator Loudspeaker System Analysis." JAES 20(5) 1972.
 *   https://aes.org/e-lib/browse.cfm?elib=2008
 *
 *   Small, R.H. "Closed-Box Loudspeaker Systems — Part I." JAES 20(10) 1972.
 *   https://aes.org/e-lib/browse.cfm?elib=2062
 *
 *   Small, R.H. "Vented-Box Loudspeaker Systems — Part I." JAES 21(5) 1973.
 *   https://aes.org/e-lib/browse.cfm?elib=2149
 *
 *   Small, R.H. "Passive-Radiator Loudspeaker Systems — Part I." JAES 22(8) 1974.
 *   https://aes.org/e-lib/browse.cfm?elib=2223
 */

import { RHO, C } from './constants.js';
import { cx, cAdd, cSub, cMul, cDiv, cInv, cScale, cPar } from './complex.js';

export function portLoss(w, Map, P) {
  return w * Map / (P.Qp || 100);
}

/**
 * Solve the acoustic circuit at frequency f (Hz).
 *
 * Models the motor + enclosure as an impedance network using the acoustical
 * mobility analogy (pressure → voltage, volume velocity → current).
 * https://en.wikipedia.org/wiki/Electrical_characteristics_of_a_dynamic_loudspeaker
 *
 * Returns U0 (net output volume velocity), UD (driver), UP (port/PR),
 * and Zel (electrical input impedance).
 */
export function solve(f, drv, box, P) {
  const w      = 2 * Math.PI * f;
  const n      = P.nDrivers || 1;
  const wiring = P.wiring || 'parallel';
  const eg     = P.eg;
  const Sdt    = drv.Sd * n;

  // Voice coil impedance Ze = Re + jωLe
  // https://en.wikipedia.org/wiki/Electrical_characteristics_of_a_dynamic_loudspeaker
  const Zcoil1 = cAdd(cx(drv.Re, 0), cx(0, w * drv.Le));
  let Zcoil, Bl;
  if (wiring === 'series') { Zcoil = cScale(Zcoil1, n);     Bl = drv.Bl * n; }
  else                     { Zcoil = cScale(Zcoil1, 1 / n); Bl = drv.Bl; }

  // Gyrator transforms electrical domain to acoustical pressure source pg = Bl·eg/(Sd·Ze)
  // https://en.wikipedia.org/wiki/Electrical_characteristics_of_a_dynamic_loudspeaker
  const pg  = cDiv(cx(eg * Bl, 0), cMul(cx(Sdt, 0), Zcoil));
  const ZaE = cDiv(cx(Bl * Bl, 0), cMul(cx(Sdt * Sdt, 0), Zcoil));

  // Driver acoustic elements derived from T/S parameters:
  // Cas = Cms·Sd²,  Mas = Mms/Sd²,  Ras = Rms/Sd²
  // https://en.wikipedia.org/wiki/Thiele/Small_parameters#Small_signal_parameters
  const Cas = drv.Cms * drv.Sd * drv.Sd * n;
  const Mas = drv.Mms / (drv.Sd * drv.Sd) / n;
  const Ras = drv.Rms / (drv.Sd * drv.Sd) / n;
  const ZaD = cAdd(cAdd(cx(Ras, 0), cx(0, w * Mas)), cInv(cx(0, w * Cas)));

  // Box acoustic compliance Cab = Vb/(ρc²), leakage resistance Ral = Ql/(ω·Cab)
  // https://en.wikipedia.org/wiki/Helmholtz_resonance#Resonant_frequency
  const Cab = P.Vb / (RHO * C * C);
  const Zc  = cInv(cx(0, w * Cab));
  const Ql  = P.Ql || 7;
  const Ral = cx(Ql / (w * Cab), 0);

  let Zbox, UP = cx(0, 0), U0, UD;

  if (box === 'sealed') {
    Zbox = cPar(Zc, Ral);
    UD = cDiv(pg, cAdd(cAdd(ZaE, ZaD), Zbox));
    U0 = UD;

  } else if (box === 'vented') {
    // Port acoustic mass Map = ρ·Leff/Sp, Leff = L + 0.85·d (end correction)
    // https://en.wikipedia.org/wiki/Helmholtz_resonance#Resonant_frequency
    const Map = RHO * P.Leff / P.Sp, Rap = portLoss(w, Map, P);
    const Zport = cAdd(cx(Rap, 0), cx(0, w * Map));
    Zbox = cPar(Zc, Ral, Zport);
    UD = cDiv(pg, cAdd(cAdd(ZaE, ZaD), Zbox));
    UP = cMul(UD, cDiv(Zbox, Zport));
    U0 = cSub(UD, UP);

  } else if (box === 'pr') {
    // Passive radiator: mechanical elements referred to acoustical domain
    // https://en.wikipedia.org/wiki/Thiele/Small_parameters#Small_signal_parameters
    const Map = P.prMmp / (P.prSd * P.prSd);
    const Cap = P.prCms * P.prSd * P.prSd;
    const Rap = (P.prRms || 0) / (P.prSd * P.prSd);
    const Zpr = cAdd(cAdd(cx(Rap, 0), cx(0, w * Map)), cInv(cx(0, w * Cap)));
    Zbox = cPar(Zc, Ral, Zpr);
    UD = cDiv(pg, cAdd(cAdd(ZaE, ZaD), Zbox));
    UP = cMul(UD, cDiv(Zbox, Zpr));
    U0 = cSub(UD, UP);

  } else if (box === 'bandpass4') {
    // 4th-order bandpass: rear sealed chamber + front vented chamber
    const Cabr   = P.Vb / (RHO * C * C);
    const Zr     = cPar(cInv(cx(0, w * Cabr)), cx(Ql / (w * Cabr), 0));
    const Cabf   = P.Vf / (RHO * C * C);
    const Map    = RHO * P.Leff / P.Sp, Rap = portLoss(w, Map, P);
    const Zportf = cAdd(cx(Rap, 0), cx(0, w * Map));
    const Zf     = cPar(cInv(cx(0, w * Cabf)), cx(Ql / (w * Cabf), 0), Zportf);
    Zbox = cAdd(Zr, Zf);
    UD = cDiv(pg, cAdd(cAdd(ZaE, ZaD), Zbox));
    UP = cMul(UD, cDiv(Zf, Zportf));
    U0 = UP;
  }

  // Electrical input impedance Zel = Ze + Bl²/(Sd²·(ZaD+Zbox))
  // https://en.wikipedia.org/wiki/Electrical_characteristics_of_a_dynamic_loudspeaker
  const Zel = cAdd(Zcoil, cDiv(cx(Bl * Bl, 0), cMul(cx(Sdt * Sdt, 0), cAdd(ZaD, Zbox))));
  return { U0, UD, UP, Zbox, Zel, ZaD };
}
