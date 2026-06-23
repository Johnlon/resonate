import { RHO, P0 } from './constants.js';
import { cx, cScale, cMul, cAbs, cArg } from './complex.js';
import { solve } from './circuit.js';

export function unwrap(p) {
  const o = [p[0]];
  for (let i = 1; i < p.length; i++) {
    let d = p[i] - p[i - 1];
    while (d >  Math.PI) d -= 2 * Math.PI;
    while (d < -Math.PI) d += 2 * Math.PI;
    o.push(o[i - 1] + d);
  }
  return o;
}

export function sweep(drv, box, P) {
  const f0 = P.fmin || 10, f1 = P.fmax || 1000, N = P.N || 400, r = 1;
  const fs = [], H = [], spl = [], exc = [], excPR = [], pv = [], zmag = [], zph = [], gd = [], phase = [];
  for (let i = 0; i <= N; i++) {
    const f   = f0 * Math.pow(f1 / f0, i / N);
    const s   = solve(f, drv, box, P);
    const w   = 2 * Math.PI * f;
    const Hc  = cScale(cMul(cx(0, w), s.U0), RHO / (2 * Math.PI * r));
    const pm  = cAbs(Hc);
    const Sdt = drv.Sd * (P.nDrivers || 1);
    const area = box === 'pr' ? P.prSd : P.Sp;
    fs.push(f); H.push(Hc);
    spl.push(pm > 0 ? 20 * Math.log10(pm / P0) : -200);
    phase.push(cArg(Hc));
    exc.push(Math.SQRT2 * cAbs(s.UD) / (w * Sdt) * 1000);
    pv.push(area ? Math.SQRT2 * cAbs(s.UP) / area : 0);
    excPR.push(box === 'pr' ? Math.SQRT2 * cAbs(s.UP) / (w * P.prSd) * 1000 : 0);
    zmag.push(cAbs(s.Zel));
    zph.push(cArg(s.Zel) * 180 / Math.PI);
  }
  const ph = unwrap(phase);
  for (let i = 0; i < fs.length; i++) {
    const a = Math.max(0, i - 1), b = Math.min(fs.length - 1, i + 1);
    const dw = 2 * Math.PI * (fs[b] - fs[a]);
    gd.push(dw !== 0 ? -(ph[b] - ph[a]) / dw * 1000 : 0);
  }
  return { fs, H, spl, phase: ph, exc, excPR, pv, zmag, zph, gd };
}

export function maxCurves(drv, box, P) {
  const base = sweep(drv, box, Object.assign({}, P, { eg: 2.83 }));
  const Pe   = (drv.Pe || 50) * (P.nDrivers || 1);
  const Znom = drv.Z || drv.Re;
  const maxspl = [], maxpwr = [], xlim = [];
  for (let i = 0; i < base.fs.length; i++) {
    const excAt283 = base.exc[i] / 1000;
    const vXmax = excAt283 > 0 ? 2.83 * (drv.Xmax / excAt283) : 1e9;
    const vPe   = Math.sqrt(Pe * Znom);
    const vUse  = Math.min(vXmax, vPe);
    maxspl.push(base.spl[i] + 20 * Math.log10(vUse / 2.83));
    maxpwr.push(vUse * vUse / Znom);
    xlim.push(vXmax < vPe);
  }
  return { fs: base.fs, maxspl, maxpwr, xlim };
}
