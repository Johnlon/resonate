import { readFileSync, writeFileSync, readdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dir = dirname(fileURLToPath(import.meta.url));
const PE_DIR = join(__dir, '..', 'drivers', 'parts-express');
const TODAY = new Date().toISOString().slice(0, 10);

// ── Label → { field, convert } map ──────────────────────────────────────────
const LABEL_MAP = {
  'Resonant Frequency (Fs)':                  { f: 'Fs',   conv: v => parseNum(v) },
  'DC Resistance (Re)':                        { f: 'Re',   conv: v => parseNum(v) },
  'Voice Coil Inductance (Le)':               { f: 'Le',   conv: v => parseNum(v) / 1000 },  // mH→H
  'Mechanical Q (Qms)':                        { f: 'Qms',  conv: v => parseNum(v) },
  'Electromagnetic Q (Qes)':                   { f: 'Qes',  conv: v => parseNum(v) },
  'Total Q (Qts)':                             { f: 'Qts',  conv: v => parseNum(v) },
  'Compliance Equivalent Volume (Vas)':        { f: 'Vas',  conv: v => convertVas(v) },
  'Mechanical Compliance of Suspension (Cms)': { f: 'Cms',  conv: v => parseNum(v) / 1000 }, // mm/N→m/N
  'BL Product (BL)':                           { f: 'BL',   conv: v => parseNum(v) },
  'Diaphragm Mass Inc. Airload (Mms)':        { f: 'Mms',  conv: v => parseNum(v) / 1000 }, // g→kg
  'Maximum Linear Excursion (Xmax)':           { f: 'Xmax', conv: v => parseNum(v) / 1000 }, // mm→m
  'Surface Area of Cone (Sd)':                 { f: 'Sd',   conv: v => parseNum(v) / 10000 }, // cm²→m²
  'Power Handling (RMS)':                      { f: 'Pe',   conv: v => parseNum(v) },
  'Impedance':                                 { f: 'Znom', conv: v => parseNum(v) },
};

function parseNum(s) {
  if (!s) return NaN;
  return parseFloat(s.replace(/[^\d.eE+-]/g, ''));
}

function convertVas(s) {
  if (!s) return NaN;
  const n = parseFloat(s.replace(/[^\d.eE+-]/g, ''));
  if (isNaN(n)) return NaN;
  if (s.includes('ft')) return n * 0.0283168;   // ft³→m³
  if (s.includes('L') || s.includes('l')) return n / 1000; // L→m³
  return n; // assume m³ already (rare)
}

// ── Parse a WDR file into ordered [ [key, value], ... ] ─────────────────────
function parseWdr(text) {
  return text.split(/\r?\n/).map(line => {
    const eq = line.indexOf('=');
    if (eq < 0) return [null, line]; // section header / blank
    return [line.slice(0, eq).trim(), line.slice(eq + 1)];
  });
}

function serializeWdr(pairs) {
  return pairs.map(([k, v]) => k === null ? v : `${k}=${v}`).join('\n');
}

function getField(pairs, key) {
  const p = pairs.find(([k]) => k === key);
  return p ? p[1].trim() : '';
}

function setField(pairs, key, value) {
  const idx = pairs.findIndex(([k]) => k === key);
  const str = value === null || value === undefined || (typeof value === 'number' && isNaN(value))
    ? '' : String(value);
  if (idx >= 0) pairs[idx][1] = str;
  else pairs.push([key, str]);
}

// ── Scrape a page ────────────────────────────────────────────────────────────
function fetchPage(url) {
  try {
    const html = execSync(`curl -sL --max-time 25 "${url}"`, { encoding: 'utf8', maxBuffer: 4 * 1024 * 1024 });
    return html;
  } catch { return ''; }
}

function parseSpecs(html) {
  const specs = {};
  for (const m of html.matchAll(/<tr><td>([^<]+)<\/td><td>([^<]*)<\/td><\/tr>/g)) {
    const label = m[1].replace(/&nbsp;/g, ' ').trim();
    const value = m[2].replace(/&nbsp;/g, ' ').trim();
    const mapping = LABEL_MAP[label];
    if (!mapping) continue;
    const converted = mapping.conv(value);
    if (!isNaN(converted)) specs[mapping.f] = converted;
  }
  return specs;
}

// ── Main ─────────────────────────────────────────────────────────────────────
const files = readdirSync(PE_DIR).filter(f => f.toLowerCase().endsWith('.wdr')).sort();

let nUpdated = 0, nNoUrl = 0, nFailed = 0, nParseErr = 0;
const failed = [], parseErrors = [];

for (let i = 0; i < files.length; i++) {
  const fname = files[i];
  const fpath = join(PE_DIR, fname);
  const raw = readFileSync(fpath, 'utf8');
  const pairs = parseWdr(raw);

  // Extract URL from Comment
  const comment = getField(pairs, 'Comment');
  const urlMatch = comment.match(/https?:\/\/www\.parts-express\.com\/[^\s|]+/);
  if (!urlMatch) {
    process.stdout.write(`[${i+1}/${files.length}] NO_URL  ${fname}\n`);
    nNoUrl++;
    continue;
  }
  const url = urlMatch[0];

  process.stdout.write(`[${i+1}/${files.length}] fetching ${url.slice(-40)}… `);
  const html = fetchPage(url);

  if (!html || html.length < 500) {
    process.stdout.write(`FAIL (empty/short)\n`);
    failed.push(fname);
    nFailed++;
    await sleep(300);
    continue;
  }

  if (html.includes('Page Not Found') || html.includes('404 Not Found')) {
    process.stdout.write(`FAIL (404)\n`);
    failed.push(fname);
    nFailed++;
    await sleep(300);
    continue;
  }

  const specs = parseSpecs(html);

  if (!specs.Fs || !specs.Qts || !specs.Re) {
    process.stdout.write(`PARSE_ERR (Fs=${specs.Fs} Qts=${specs.Qts} Re=${specs.Re})\n`);
    parseErrors.push(fname);
    nParseErr++;
    await sleep(300);
    continue;
  }

  // Apply fetched specs
  for (const [field, value] of Object.entries(specs)) {
    setField(pairs, field, value);
  }

  // Derive Vd, Dd, Rms if possible
  const Sd   = specs.Sd   !== undefined ? specs.Sd   : (parseFloat(getField(pairs, 'Sd'))   || NaN);
  const Xmax = specs.Xmax !== undefined ? specs.Xmax : (parseFloat(getField(pairs, 'Xmax')) || NaN);
  const Mms  = specs.Mms  !== undefined ? specs.Mms  : (parseFloat(getField(pairs, 'Mms'))  || NaN);
  const Cms  = specs.Cms  !== undefined ? specs.Cms  : (parseFloat(getField(pairs, 'Cms'))  || NaN);
  const Qms  = specs.Qms  !== undefined ? specs.Qms  : (parseFloat(getField(pairs, 'Qms'))  || NaN);
  if (!isNaN(Sd) && !isNaN(Xmax)) setField(pairs, 'Vd', Sd * Xmax);
  if (!isNaN(Sd)) setField(pairs, 'Dd', 2 * Math.sqrt(Sd / Math.PI));
  if (!isNaN(Mms) && !isNaN(Cms) && !isNaN(Qms)) setField(pairs, 'Rms', Math.sqrt(Mms / Cms) / Qms);

  // Update Comment: strip stale notes, record fetch date
  setField(pairs, 'Comment', `Source: Parts Express (fetched ${TODAY}) — ${url}`);

  writeFileSync(fpath, serializeWdr(pairs), 'utf8');
  nUpdated++;
  process.stdout.write(`OK (Fs=${specs.Fs} Qts=${specs.Qts} Qes=${specs.Qes??'—'} Bl=${specs.BL??'—'})\n`);

  await sleep(300);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

console.log('\n════ SUMMARY ════');
console.log(`Total files  : ${files.length}`);
console.log(`Updated      : ${nUpdated}`);
console.log(`No URL       : ${nNoUrl}`);
console.log(`Fetch failed : ${nFailed}`);
console.log(`Parse error  : ${nParseErr}`);
if (failed.length)      console.log('\nFetch failures:\n' + failed.map(f=>'  '+f).join('\n'));
if (parseErrors.length) console.log('\nParse errors:\n' + parseErrors.map(f=>'  '+f).join('\n'));
