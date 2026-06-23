import { RHO, C } from './constants.js';
import { cx, cAdd, cSub, cMul, cDiv, cInv, cScale, cPar } from './complex.js';

export function portLoss(w, Map, P) {
  return w * Map / (P.Qp || 100);
}

export function solve(f, drv, box, P) {
  const w      = 2 * Math.PI * f;
  const n      = P.nDrivers || 1;
  const wiring = P.wiring || 'parallel';
  const eg     = P.eg;
  const Sdt    = drv.Sd * n;
  const Zcoil1 = cAdd(cx(drv.Re, 0), cx(0, w * drv.Le));
  let Zcoil, Bl;
  if (wiring === 'series') { Zcoil = cScale(Zcoil1, n);     Bl = drv.Bl * n; }
  else                     { Zcoil = cScale(Zcoil1, 1 / n); Bl = drv.Bl; }
  const pg  = cDiv(cx(eg * Bl, 0), cMul(cx(Sdt, 0), Zcoil));
  const ZaE = cDiv(cx(Bl * Bl, 0), cMul(cx(Sdt * Sdt, 0), Zcoil));
  const Cas = drv.Cms * drv.Sd * drv.Sd * n;
  const Mas = drv.Mms / (drv.Sd * drv.Sd) / n;
  const Ras = drv.Rms / (drv.Sd * drv.Sd) / n;
  const ZaD = cAdd(cAdd(cx(Ras, 0), cx(0, w * Mas)), cInv(cx(0, w * Cas)));
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
    const Map = RHO * P.Leff / P.Sp, Rap = portLoss(w, Map, P);
    const Zport = cAdd(cx(Rap, 0), cx(0, w * Map));
    Zbox = cPar(Zc, Ral, Zport);
    UD = cDiv(pg, cAdd(cAdd(ZaE, ZaD), Zbox));
    UP = cMul(UD, cDiv(Zbox, Zport));
    U0 = cSub(UD, UP);
  } else if (box === 'pr') {
    const Map = P.prMmp / (P.prSd * P.prSd), Cap = P.prCms * P.prSd * P.prSd;
    const Rap = (P.prRms || 0) / (P.prSd * P.prSd);
    const Zpr = cAdd(cAdd(cx(Rap, 0), cx(0, w * Map)), cInv(cx(0, w * Cap)));
    Zbox = cPar(Zc, Ral, Zpr);
    UD = cDiv(pg, cAdd(cAdd(ZaE, ZaD), Zbox));
    UP = cMul(UD, cDiv(Zbox, Zpr));
    U0 = cSub(UD, UP);
  } else if (box === 'bandpass4') {
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

  const Zel = cAdd(Zcoil, cDiv(cx(Bl * Bl, 0), cMul(cx(Sdt * Sdt, 0), cAdd(ZaD, Zbox))));
  return { U0, UD, UP, Zbox, Zel, ZaD };
}
