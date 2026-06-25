/**
 * fix-dq-zeros.mjs — batch fix two classes of mechanical DQ errors:
 *
 *  1. Fs_low  — Fs < 5 Hz (dot-thousands scraper bug: "1.600 Hz" → 1.6)
 *               Fix: multiply Fs by 1000.  Zero ambiguity — no real driver
 *               has Fs below 5 Hz, so every hit is the kHz bug.
 *
 *  2. Zero T/S fields — Sd=0, Re=0, Pe=0, Xmax=0, BL=0, Mms=0, Qts=0,
 *               Qms=0, Vas=0, and near-zero Sd (< 0.5 cm²).
 *               Fix: delete the field.  Real datasheets never publish 0 for
 *               these params; a zero is always a blank cell → 0 scraper bug.
 *               Deleting is more honest than leaving a lying 0.
 *
 * Run:  node scripts/fix-dq-zeros.mjs [--dry-run] [--collection <name>]
 *   --dry-run    print what would change without writing files
 *   --collection filter to one collection directory
 */
import fs   from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const DRIVERS_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'drivers');
const dryRun     = process.argv.includes('--dry-run');
const _ci        = process.argv.indexOf('--collection');
const filterColl = _ci >= 0 ? process.argv[_ci + 1] : null;

// T/S fields where exactly 0 is a scraper artifact and the field should be deleted.
const ZERO_DELETE = new Set(['Sd','Re','Pe','Xmax','BL','Mms','Qts','Qms','Vas']);

// Sd threshold: below this (in m²) = near-zero scraper artifact (Beyma pattern).
const SD_TINY_M2 = 0.5e-4;  // 0.5 cm²

let fixed = 0, filesChanged = 0;

for (const coll of fs.readdirSync(DRIVERS_DIR).sort()) {
  if (filterColl && coll !== filterColl) continue;
  const collPath = path.join(DRIVERS_DIR, coll);
  if (!fs.statSync(collPath).isDirectory()) continue;

  for (const fname of fs.readdirSync(collPath).sort()) {
    if (!fname.endsWith('.wdr')) continue;
    const fpath = path.join(collPath, fname);
    const original = fs.readFileSync(fpath, 'utf8');
    const lines = original.split(/\r?\n/);

    const changes = [];   // { line_idx, old, new, reason }

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const eq = line.indexOf('=');
      if (eq < 0 || line[0] === '[') continue;
      const key = line.slice(0, eq).trim();
      const raw = line.slice(eq + 1).trim();
      const val = parseFloat(raw);

      // ── Fix 1: Fs_low ──────────────────────────────────────────────────
      if (key === 'Fs' && isFinite(val) && val > 0 && val < 5) {
        const newFs = +(val * 1000).toFixed(6).replace(/\.?0+$/, '');
        changes.push({ i, old: line, new: `Fs=${newFs}`, reason: `Fs ${val}→${newFs} Hz (×1000 dot-thousands bug)` });
        lines[i] = `Fs=${newFs}`;
      }

      // ── Fix 2a: exact-zero T/S fields ──────────────────────────────────
      if (ZERO_DELETE.has(key) && isFinite(val) && val === 0) {
        changes.push({ i, old: line, new: null, reason: `${key}=0 deleted (scraper artifact)` });
        lines[i] = null;  // mark for removal
      }

      // ── Fix 2b: near-zero Sd (Sd_tiny) ─────────────────────────────────
      if (key === 'Sd' && isFinite(val) && val > 0 && val < SD_TINY_M2) {
        changes.push({ i, old: line, new: null, reason: `Sd=${(val*1e4).toFixed(3)} cm² deleted (near-zero scraper artifact)` });
        lines[i] = null;
      }
    }

    if (changes.length === 0) continue;

    // Add correction note to boxbench_corrections
    const notes = changes.map(c => c.reason).join('; ');
    let corrIdx = lines.findIndex(l => l && l.startsWith('boxbench_corrections='));
    if (corrIdx >= 0) {
      lines[corrIdx] = lines[corrIdx] + '; ' + notes;
    } else {
      // Insert after ParState= so boxbench fields don't pollute the WinISD-native block
      let insertAt = lines.findIndex(l => l && l.startsWith('ParState='));
      if (insertAt < 0) insertAt = lines.length - 1;
      lines.splice(insertAt + 1, 0, `boxbench_corrections=${notes}`);
    }

    const result = lines.filter(l => l !== null).join('\n');

    console.log(`\n${coll}/${fname}`);
    for (const c of changes) console.log(`  ${c.reason}`);

    if (!dryRun) {
      fs.writeFileSync(fpath, result, 'utf8');
    }

    fixed += changes.length;
    filesChanged++;
  }
}

console.log(`\n${ dryRun ? '[DRY RUN] ' : ''}Fixed ${fixed} values across ${filesChanged} files.`);
