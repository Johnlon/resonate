/**
 * refresh-si-catalog.mjs
 *
 * Scrapes SoundImports (soundimports.eu) driver catalog and writes WDR files
 * to drivers/soundimports/.
 *
 * Source: https://www.soundimports.eu/en/audio-components/
 * No public API — uses HTML scraping via curl with 350ms politeness delay.
 * Specs are in a plain <table><tr><td>Label</td><td>Value</td></tr></table>.
 *
 * Usage:
 *   node scripts/refresh-si-catalog.mjs           # add new files, skip existing
 *   node scripts/refresh-si-catalog.mjs --force   # overwrite all existing files
 *   node scripts/refresh-si-catalog.mjs --dry-run # print what would happen, write nothing
 *
 * Requirements: Node.js 18+, curl in PATH. No npm dependencies.
 *
 * Categories scraped:
 *   /en/audio-components/woofers/   — woofers, subwoofers, midwoofers, full-range, PRs
 *   /en/audio-components/tweeters/  — all tweeter types (dome, AMT, planar, compression etc.)
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __dir  = path.dirname(fileURLToPath(import.meta.url));
const SI_DIR = path.join(__dir, '..', 'drivers', 'soundimports');
const BASE   = 'https://www.soundimports.eu';
const TODAY  = new Date().toISOString().slice(0, 10);
const DELAY  = 350; // ms — be polite to a small retailer

const FORCE   = process.argv.includes('--force');
const DRY_RUN = process.argv.includes('--dry-run');

if (!fs.existsSync(SI_DIR)) fs.mkdirSync(SI_DIR, { recursive: true });

const sleep = ms => new Promise(r => setTimeout(r, ms));

// ── HTTP fetch via curl ───────────────────────────────────────────────────────
function fetchHtml(url) {
  try {
    return execSync(
      `curl -sL --max-time 30 -A "Mozilla/5.0" "${url}"`,
      { encoding: 'utf8', maxBuffer: 4 * 1024 * 1024 }
    );
  } catch { return ''; }
}

// ── HTML helpers ──────────────────────────────────────────────────────────────
function extractText(html, tag) {
  const m = html.match(new RegExp(`<${tag}[^>]*>([^<]+)</${tag}>`, 'i'));
  return m ? m[1].replace(/&quot;/g, '"').replace(/&#039;/g, "'").replace(/&amp;/g, '&').trim() : '';
}

/** Extract spec key/value pairs from <dt>Label</dt><dd>Value</dd> markup. */
function extractTableRows(html) {
  const rows = {};
  for (const m of html.matchAll(/<dt>([\s\S]*?)<\/dt>\s*<dd>([\s\S]*?)<\/dd>/gi)) {
    const label = m[1].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
    const value = m[2].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
    if (label && value) rows[label] = value;
  }
  return rows;
}

/** Extract all product page URLs from a category listing page. */
function extractProductUrls(html) {
  const seen = new Set();
  const urls = [];
  // Links are absolute: href="https://www.soundimports.eu/en/brand-model.html"
  for (const m of html.matchAll(/href="(https:\/\/www\.soundimports\.eu\/en\/[a-z0-9][a-z0-9._-]+\.html)"/gi)) {
    const url = m[1];
    if (url.includes('/page') || url.includes('/audio-components') ||
        url.includes('/brands') || url.includes('/blogs') ||
        url.includes('/service') || url.includes('/collections') ||
        seen.has(url)) continue;
    seen.add(url);
    urls.push(url);
  }
  return urls;
}

/** Extract last page number from pagination HTML. */
function extractLastPage(html) {
  const nums = [...html.matchAll(/soundimports\.eu\/en\/[^"]*\/page(\d+)\.html/g)].map(m => +m[1]);
  return nums.length ? Math.max(...nums) : 1;
}

// ── Unit conversions ──────────────────────────────────────────────────────────
function parseNum(s) {
  if (!s) return NaN;
  return parseFloat(s.replace(/[^\d.eE+-]/g, ''));
}

// SI uses: Vas in litres, Xmax in mm, Le in mH, Mms in g, Cms in mm/N, Sd in cm²
const LABEL_MAP = {
  'Resonant Frequency (Fs)':                  { f: 'Fs',   conv: v => parseNum(v) },
  'Total Q (Qts)':                            { f: 'Qts',  conv: v => parseNum(v) },
  'Electromagnetic Q (Qes)':                  { f: 'Qes',  conv: v => parseNum(v) },
  'Mechanical Q (Qms)':                       { f: 'Qms',  conv: v => parseNum(v) },
  'DC Resistance (Re)':                       { f: 'Re',   conv: v => parseNum(v) },
  'Voice Coil Inductance (Le)':               { f: 'Le',   conv: v => parseNum(v) / 1000 },  // mH→H
  'BL Product (BL)':                          { f: 'BL',   conv: v => parseNum(v) },
  'Diaphragm Mass Inc. Airload (Mms)':        { f: 'Mms',  conv: v => parseNum(v) / 1000 },  // g→kg
  'Mechanical Compliance of Suspension (Cms)':{ f: 'Cms',  conv: v => parseNum(v) / 1000 },  // mm/N→m/N
  'Surface Area of Cone (Sd)':               { f: 'Sd',   conv: v => parseNum(v) / 10000 }, // cm²→m²
  'Compliance Equivalent Volume (Vas)':       { f: 'Vas',  conv: v => parseNum(v) / 1000 },  // L→m³
  'Maximum Linear Excursion (Xmax)':          { f: 'Xmax', conv: v => parseNum(v) / 1000 },  // mm→m
  'Driver\'s Mechanical Losses (Rms)':        { f: 'Rms',  conv: v => parseNum(v) },         // kg/s (already SI)
  'Impedance (Z)':                            { f: 'Znom', conv: v => parseNum(v) },
  'Impedance':                                { f: 'Znom', conv: v => parseNum(v) },
  'Power Handling (RMS)':                     { f: 'Pe',   conv: v => parseNum(v) },
};

const fmt = (v, p = 6) => v == null || !isFinite(v) ? '' : String(+v.toPrecision(p));

// ── WDR builder ───────────────────────────────────────────────────────────────
function buildWdr(brand, model, specs, url) {
  const Fs   = specs.Fs   ?? null;
  const Qts  = specs.Qts  ?? null;
  const Qes  = specs.Qes  ?? null;
  const Qms  = specs.Qms  ?? null;
  const Re   = specs.Re   ?? null;
  const Le   = specs.Le   ?? null;
  const BL   = specs.BL   ?? null;
  const Mms  = specs.Mms  ?? null;
  const Cms  = specs.Cms  ?? null;
  const Sd   = specs.Sd   ?? null;
  const Vas  = specs.Vas  ?? null;
  const Xmax = specs.Xmax ?? null;
  const Znom = specs.Znom ?? null;
  const Pe   = specs.Pe   ?? null;

  // Derive what we can
  const Rms = specs.Rms ?? ((Qms && Mms && Fs) ? (2 * Math.PI * Fs * Mms / Qms) : null);
  const Dd  = Sd  ? 2 * Math.sqrt(Sd / Math.PI) : null;
  const Vd  = (Sd && Xmax) ? Sd * Xmax : null;

  return [
    '[Driver]',
    `Brand=${brand}`,
    `Model=${model}`,
    'Manufacturer=',
    `ProvidedBy=SoundImports (fetched ${TODAY})`,
    `Comment=Source: SoundImports (fetched ${TODAY}) — ${url}`,
    'DateAdded=',
    `DateModified=${TODAY}`,
    `Qts=${fmt(Qts)}`,
    `Znom=${fmt(Znom)}`,
    `Fs=${fmt(Fs)}`,
    `Pe=${fmt(Pe)}`,
    `Re=${fmt(Re)}`,
    `Le=${fmt(Le)}`,
    `BL=${fmt(BL)}`,
    `Xmax=${fmt(Xmax)}`,
    `Cms=${fmt(Cms)}`,
    `Qms=${fmt(Qms)}`,
    `Qes=${fmt(Qes)}`,
    `Rms=${fmt(Rms)}`,
    `Mms=${fmt(Mms)}`,
    `Sd=${fmt(Sd)}`,
    `Vas=${fmt(Vas)}`,
    `Vd=${fmt(Vd)}`,
    `Dd=${fmt(Dd)}`,
    'numVC=1',
    'VCCon=2',
    'ParState=EEECEENNEENEEEEEEEEEEECENNCCCNNNCCCCECNNNNNNNNECC',
    '',
  ].join('\n');
}

function safeFilename(brand, model) {
  return `${brand} ${model}.wdr`.replace(/[\\/:*?"<>|]/g, '_');
}

// ── Category crawler ──────────────────────────────────────────────────────────
const CATEGORIES = [
  '/en/audio-components/woofers/',
  '/en/audio-components/tweeters/',
];

async function collectProductUrls() {
  const all = new Set();
  for (const cat of CATEGORIES) {
    process.stdout.write(`Scanning ${cat}… `);
    const page1 = fetchHtml(BASE + cat);
    await sleep(DELAY);
    const lastPage = extractLastPage(page1);
    extractProductUrls(page1).forEach(u => all.add(u));

    for (let p = 2; p <= lastPage; p++) {
      const html = fetchHtml(`${BASE}${cat}page${p}.html`);
      await sleep(DELAY);
      extractProductUrls(html).forEach(u => all.add(u));
      if (p % 10 === 0) process.stdout.write(`${p}/${lastPage}… `);
    }
    console.log(`done (${lastPage} pages)`);
  }
  return [...all];
}

// ── Main ──────────────────────────────────────────────────────────────────────
console.log('Phase 1: collecting product URLs from category pages…');
const productUrls = await collectProductUrls();
console.log(`\nFound ${productUrls.length} product URLs\n`);

console.log('Phase 2: fetching product specs…');
let written = 0, skipped = 0, noTs = 0, errors = 0;

for (let i = 0; i < productUrls.length; i++) {
  const url = productUrls[i];

  const html = fetchHtml(url);
  await sleep(DELAY);

  if (!html || html.length < 500) { errors++; continue; }

  // Extract article number (= model code)
  const rows = extractTableRows(html);
  const articleNumber = rows['Article number'] || rows['Article Number'] || rows['Artikelnummer'] || '';
  if (!articleNumber) { noTs++; continue; }

  // Extract T/S params
  const specs = {};
  for (const [label, mapping] of Object.entries(LABEL_MAP)) {
    if (rows[label] !== undefined) {
      const converted = mapping.conv(rows[label]);
      if (!isNaN(converted)) specs[mapping.f] = converted;
    }
  }
  if (!specs.Fs) { noTs++; continue; } // skip if no Fs at all

  // Extract brand: H1 is "[Brand...] [ArticleNumber] [description]"
  const h1 = extractText(html, 'h1');
  const modelIdx = h1.indexOf(articleNumber);
  const brand = (modelIdx > 0 ? h1.slice(0, modelIdx) : h1).trim();
  const model = articleNumber;

  if (!brand || !model) { errors++; continue; }

  const fname = safeFilename(brand, model);
  const fpath = path.join(SI_DIR, fname);

  if (fs.existsSync(fpath) && !FORCE) {
    skipped++;
    continue;
  }

  if (!DRY_RUN) {
    fs.writeFileSync(fpath, buildWdr(brand, model, specs, url), 'utf8');
  }
  written++;

  if ((written + skipped) % 50 === 0 || i === productUrls.length - 1) {
    process.stdout.write(`[${i+1}/${productUrls.length}] ${written} written, ${skipped} skipped, ${noTs} no T/S\r`);
  }
}

console.log(`\n\n════ SUMMARY ════`);
console.log(`Product pages fetched : ${productUrls.length}`);
console.log(`Written               : ${written}${DRY_RUN ? ' (dry-run)' : ''}`);
console.log(`Skipped (exists)      : ${skipped}`);
console.log(`No T/S data           : ${noTs}`);
console.log(`Errors                : ${errors}`);
console.log(`Total in SI dir       : ${fs.readdirSync(SI_DIR).filter(f => f.endsWith('.wdr')).length}`);
