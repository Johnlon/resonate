import { RHO, C } from './constants.js';

export function ebp(drv) { return drv.Fs / drv.Qes; }

export function sealedFromQtc(drv, Qtc) {
  const ratio = (Qtc / drv.Qts) ** 2 - 1;
  return ratio <= 0 ? null : drv.Vas / ratio;
}

export function ventedAlignment(drv) {
  const Vb = 15 * drv.Vas * Math.pow(drv.Qts, 2.87);
  return { Vb, Fb: drv.Fs * Math.pow(drv.Vas / Vb, 0.5) };
}

export function ventLength(Vb, fb, Sp) {
  const Cab = Vb / (RHO * C * C);
  const wb  = 2 * Math.PI * fb;
  const Map = 1 / (wb * wb * Cab);
  const d   = 2 * Math.sqrt(Sp / Math.PI);
  return Math.max(Map * Sp / RHO - 0.85 * d, 0.005);
}

export function tuningFromLength(Vb, L, Sp) {
  const d    = 2 * Math.sqrt(Sp / Math.PI);
  const Leff = L + 0.85 * d;
  const Cab  = Vb / (RHO * C * C);
  const Map  = RHO * Leff / Sp;
  return 1 / (2 * Math.PI * Math.sqrt(Map * Cab));
}

export function prTuning(P) {
  const Cab  = P.Vb / (RHO * C * C);
  const Map  = P.prMmp / (P.prSd * P.prSd);
  const Cap  = P.prCms * P.prSd * P.prSd;
  const Cpar = (Cab * Cap) / (Cab + Cap);
  return 1 / (2 * Math.PI * Math.sqrt(Map * Cpar));
}

export function prMassForFp(P, fp) {
  const Cab  = P.Vb / (RHO * C * C);
  const Cap  = P.prCms * P.prSd * P.prSd;
  const Cpar = (Cab * Cap) / (Cab + Cap);
  const Map  = 1 / ((2 * Math.PI * fp) ** 2 * Cpar);
  return Map * P.prSd * P.prSd;
}
