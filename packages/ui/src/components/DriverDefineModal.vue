<script setup>
import { ref, computed, reactive, watch, nextTick } from 'vue';

const props = defineProps({ open: Boolean });
const emit  = defineEmits(['close', 'apply']);

const RHO = 1.2;   // kg/m³
const C   = 343;   // m/s

// ── Parameter definitions ─────────────────────────────────────────────────
// readOnly = always derived by engine, can't be overridden — show as read-only display
const PARAMS = [
  // Electrical
  { key: 'Re',   unit: 'Ω',       sect: 'Electrical',  label: 'Re',   desc: 'DC voice coil resistance' },
  { key: 'Le',   unit: 'mH',      sect: 'Electrical',  label: 'Le',   desc: 'Voice coil inductance at 1 kHz' },
  { key: 'Znom', unit: 'Ω',       sect: 'Electrical',  label: 'Znom', desc: 'Nominal impedance (typically 4, 8, or 16 Ω)' },
  // T/S
  { key: 'Fs',   unit: 'Hz',      sect: 'T/S',         label: 'Fs',   desc: 'Free-air resonance frequency' },
  { key: 'Qms',  unit: '',        sect: 'T/S',         label: 'Qms',  desc: 'Mechanical Q factor — losses due to spider/surround' },
  { key: 'Qes',  unit: '',        sect: 'T/S',         label: 'Qes',  desc: 'Electrical Q factor — losses due to voice coil resistance' },
  { key: 'Qts',  unit: '',        sect: 'T/S',         label: 'Qts',  desc: 'Total Q = Qms·Qes / (Qms+Qes). Enter any 2 of the 3 Q values.' },
  { key: 'Bl',   unit: 'T·m',     sect: 'T/S',         label: 'Bl',   desc: 'Force factor — derived from Fs, Mms, Re, Qes. Always recalculated by the engine.',  readOnly: true },
  { key: 'Mms',  unit: 'g',       sect: 'T/S',         label: 'Mms',  desc: 'Moving mass incl. air load — derived from Fs, Vas, Sd. Always recalculated.',       readOnly: true },
  { key: 'Cms',  unit: 'mm/N',    sect: 'T/S',         label: 'Cms',  desc: 'Suspension compliance — derived from Vas, Sd. Always recalculated.',                 readOnly: true },
  { key: 'Rms',  unit: 'N·s/m',   sect: 'T/S',         label: 'Rms',  desc: 'Mechanical resistance — derived from Fs, Mms, Qms. Always recalculated.',           readOnly: true },
  // Physical / acoustic
  { key: 'Sd',   unit: 'cm²',     sect: 'Physical',    label: 'Sd',   desc: 'Effective piston area. Sd = π·(Dia/2)².' },
  { key: 'Dia',  unit: 'mm',      sect: 'Physical',    label: 'Dia',  desc: 'Cone diameter → Sd. Enter Sd or Dia, the other is calculated.' },
  { key: 'Vas',  unit: 'L',       sect: 'Physical',    label: 'Vas',  desc: 'Equivalent compliance volume (volume of air with same compliance as the cone)' },
  { key: 'Xmax', unit: 'mm',      sect: 'Physical',    label: 'Xmax', desc: 'Peak linear excursion (one-way, mm). Typically from manufacturer.' },
  { key: 'Vd',   unit: 'cm³',     sect: 'Physical',    label: 'Vd',   desc: 'Volume displacement = Sd × Xmax. Always recalculated.',  readOnly: true },
  // Performance
  { key: 'Pe',   unit: 'W',       sect: 'Performance', label: 'Pe',   desc: 'Power handling — long-term continuous power rating' },
  { key: 'SPL',  unit: 'dB',      sect: 'Performance', label: 'SPL',  desc: '1W/1m sensitivity — derived from efficiency. Always recalculated.',  readOnly: true },
  { key: 'no',   unit: '%',       sect: 'Performance', label: 'η₀',   desc: 'Reference efficiency = (4π²/c³)·Fs³·Vas/Qes. Always recalculated.',  readOnly: true },
];

const SECTIONS = [
  { id: 'Electrical',  label: 'Electrical' },
  { id: 'T/S',         label: 'Thiele–Small' },
  { id: 'Physical',    label: 'Physical / Acoustic' },
  { id: 'Performance', label: 'Performance' },
];

// ── Reactive state ────────────────────────────────────────────────────────
const drvName    = ref('');
const drvBrand   = ref('');
const drvModel   = ref('');
const drvComment = ref('');

// entered: key → display-unit string (only E state params, empty key = deleted = N/C)
const entered = reactive({});

// ── Unit conversions ──────────────────────────────────────────────────────
function toSI(key, displayStr) {
  const v = parseFloat(displayStr);
  if (!isFinite(v) || v < 0) return null;
  switch (key) {
    case 'Le':   return v / 1000;
    case 'Mms':  return v / 1000;
    case 'Cms':  return v / 1000;
    case 'Sd':   return v / 1e4;
    case 'Dia':  return v / 1000;
    case 'Vas':  return v / 1000;
    case 'Xmax': return v / 1000;
    case 'Vd':   return v / 1e6;
    case 'no':   return v / 100;
    default:     return v;
  }
}

function fmtSI(key, si) {
  if (si == null || !isFinite(si) || si <= 0) return '';
  let v;
  switch (key) {
    case 'Le':   v = si * 1000;  break;
    case 'Mms':  v = si * 1000;  break;
    case 'Cms':  v = si * 1000;  break;
    case 'Sd':   v = si * 1e4;   break;
    case 'Dia':  v = si * 1000;  break;
    case 'Vas':  v = si * 1000;  break;
    case 'Xmax': v = si * 1000;  break;
    case 'Vd':   v = si * 1e6;   break;
    case 'no':   v = si * 100;   break;
    default:     v = si;
  }
  if (['Qts', 'Qms', 'Qes'].includes(key)) return v.toFixed(3);
  if (key === 'SPL')  return v.toFixed(1);
  if (key === 'no')   return v.toFixed(4);
  if (key === 'Sd')   return v.toFixed(1);
  if (key === 'Vd')   return v.toFixed(1);
  if (key === 'Dia')  return v.toFixed(0);
  if (key === 'Fs')   return v.toFixed(1);
  if (key === 'Rms')  return v.toFixed(3);
  if (key === 'Cms')  return v.toFixed(4);
  if (key === 'Bl')   return v.toFixed(2);
  if (key === 'Vas')  return v.toFixed(3);
  if (key === 'Mms')  return v.toFixed(2);
  return parseFloat(v.toPrecision(4)).toString();
}

// ── Calculation (same equations as engine's deriveDriver) ─────────────────
const resolvedSI = computed(() => {
  const r = {};

  // Seed with entered values
  for (const [key, str] of Object.entries(entered)) {
    if (!str) continue;
    const si = toSI(key, str);
    if (si != null && si > 0) r[key] = si;
  }

  // Two passes to handle cascaded deps
  for (let pass = 0; pass < 2; pass++) {
    // Sd ↔ Dia
    if (!r.Sd && r.Dia)  r.Sd  = Math.PI * (r.Dia / 2) ** 2;
    if (!r.Dia && r.Sd)  r.Dia = 2 * Math.sqrt(r.Sd / Math.PI);

    // Q interdependencies (match engine's deriveDriver logic)
    if (!r.Qts && r.Qes && r.Qms) r.Qts = r.Qes * r.Qms / (r.Qes + r.Qms);
    if (!r.Qes && r.Qts && r.Qms) r.Qes = r.Qts * r.Qms / (r.Qms - r.Qts);
    if (!r.Qms && r.Qts && r.Qes) r.Qms = r.Qts * r.Qes / (r.Qes - r.Qts);

    // T/S derivations — engine always recalculates these
    if (r.Fs && r.Vas && r.Sd) {
      const Cas = r.Vas / (RHO * C * C);
      r.Cms = Cas / (r.Sd * r.Sd);
      r.Mms = 1 / ((2 * Math.PI * r.Fs) ** 2 * r.Cms);
      if (r.Qms) r.Rms = 2 * Math.PI * r.Fs * r.Mms / r.Qms;
      if (r.Re && r.Qes) r.Bl = Math.sqrt(2 * Math.PI * r.Fs * r.Mms * r.Re / r.Qes);
    }

    // Vd and efficiency/SPL
    if (r.Sd && r.Xmax) r.Vd = r.Sd * r.Xmax;
    if (r.Fs && r.Vas && r.Qes)
      r.no = 4 * Math.PI ** 2 / C ** 3 * r.Fs ** 3 * r.Vas / r.Qes;
    if (r.no && r.no > 0) r.SPL = 112.1 + 10 * Math.log10(r.no);
  }

  return r;
});

function stateOf(key) {
  const p = PARAMS.find(x => x.key === key);
  if (p?.readOnly) return resolvedSI.value[key] != null ? 'C' : 'N';
  if (key in entered && entered[key] !== '') return 'E';
  if (resolvedSI.value[key] != null) return 'C';
  return 'N';
}

function displayVal(key) {
  if ((key in entered) && entered[key] !== '') return entered[key];
  const si = resolvedSI.value[key];
  return si != null ? fmtSI(key, si) : '';
}

function onInput(key, e) {
  const val = e.target.value;
  if (val === '') delete entered[key];
  else entered[key] = val;
}

// ── Validation ────────────────────────────────────────────────────────────
const canApply = computed(() => {
  const si = resolvedSI.value;
  const qCount = [si.Qts, si.Qes, si.Qms].filter(v => v != null).length;
  return !!(si.Fs && si.Sd && si.Re && si.Vas && qCount >= 2);
});

const missing = computed(() => {
  const si = resolvedSI.value;
  const m = [];
  if (!si.Fs)  m.push('Fs');
  if (!si.Re)  m.push('Re');
  if (!si.Sd)  m.push('Sd or Dia');
  if (!si.Vas) m.push('Vas');
  const qCount = [si.Qts, si.Qes, si.Qms].filter(v => v != null).length;
  if (qCount < 2) m.push('at least 2 of Qts/Qes/Qms');
  return m;
});

// ── Actions ───────────────────────────────────────────────────────────────
function resetAll() {
  drvName.value = ''; drvBrand.value = ''; drvModel.value = ''; drvComment.value = '';
  Object.keys(entered).forEach(k => delete entered[k]);
}

function applyDriver() {
  if (!canApply.value) return;
  const si = resolvedSI.value;
  const name = drvName.value.trim() ||
    [drvBrand.value, drvModel.value].filter(Boolean).join(' ') || 'Custom Driver';

  const raw = { name };
  if (drvBrand.value.trim())   raw.brand   = drvBrand.value.trim();
  if (drvModel.value.trim())   raw.model   = drvModel.value.trim();
  if (drvComment.value.trim()) raw.comment = drvComment.value.trim();

  // Primary T/S parameters (engine reads these directly)
  if (si.Fs)   raw.Fs   = si.Fs;
  if (si.Qts)  raw.Qts  = si.Qts;
  if (si.Qes)  raw.Qes  = si.Qes;
  if (si.Qms)  raw.Qms  = si.Qms;
  if (si.Re)   raw.Re   = si.Re;
  if (si.Le)   raw.Le   = si.Le;
  if (si.Znom) raw.Z    = si.Znom;   // engine uses .Z for Znom
  if (si.Vas)  raw.Vas  = si.Vas;
  if (si.Sd)   raw.Sd   = si.Sd;
  if (si.Xmax) raw.Xmax = si.Xmax;
  if (si.Pe)   raw.Pe   = si.Pe;
  // Note: Bl/Mms/Cms/Rms are NOT stored — engine always recalculates from above

  emit('apply', raw);
}

watch(() => props.open, v => { if (v) { resetAll(); nextTick(() => document.querySelector('.dd-name')?.focus()); } });
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="dd-overlay" @click.self="$emit('close')">
      <div class="dd-modal">
        <!-- Header -->
        <div class="dd-header">
          <span>Define Driver Model</span>
          <button class="dd-x" @click="$emit('close')" title="Close">×</button>
        </div>

        <div class="dd-body">
          <!-- Identity -->
          <div class="dd-id-grid">
            <label>Name</label>
            <input class="dd-text dd-name" v-model="drvName"
                   placeholder="Display name (auto-built from Brand + Model if blank)">
            <label>Brand</label>
            <input class="dd-text" v-model="drvBrand" placeholder="e.g. Dayton Audio">
            <label>Model</label>
            <input class="dd-text" v-model="drvModel" placeholder="e.g. RS180-8">
          </div>

          <!-- Parameter table -->
          <div class="dd-table">
            <template v-for="sect in SECTIONS" :key="sect.id">
              <div class="dd-sect-hdr">{{ sect.label }}</div>
              <div v-for="p in PARAMS.filter(x => x.sect === sect.id)" :key="p.key"
                   class="dd-row" :class="'row-' + stateOf(p.key)" :title="p.desc">
                <span class="dd-lbl">{{ p.label }}</span>
                <input v-if="!p.readOnly"
                       class="dd-val" type="number" step="any"
                       :class="'input-' + stateOf(p.key)"
                       :value="displayVal(p.key)"
                       @input="onInput(p.key, $event)"
                       @focus="e => { if (stateOf(p.key) !== 'E') e.target.select(); }"
                       :title="p.desc">
                <span v-else class="dd-ro-val" :class="'ro-' + stateOf(p.key)">
                  {{ displayVal(p.key) || '–' }}
                </span>
                <span class="dd-unit">{{ p.unit }}</span>
                <span class="dd-badge" :class="'badge-' + stateOf(p.key)">{{ stateOf(p.key) }}</span>
              </div>
            </template>
          </div>

          <!-- Notes -->
          <div class="dd-notes-wrap">
            <label class="dd-notes-lbl">Notes</label>
            <textarea class="dd-notes" v-model="drvComment" rows="2"
                      placeholder="Optional notes about this driver…"></textarea>
          </div>

          <!-- Missing params hint -->
          <div v-if="!canApply" class="dd-missing">
            Required: {{ missing.join(' · ') }}
          </div>

          <!-- Reference links -->
          <div class="dd-refs">
            <a href="https://en.wikipedia.org/wiki/Thiele/Small_parameters"
               target="_blank" rel="noopener" title="Wikipedia: Thiele/Small parameters — definitions, equations, and units">
              Wikipedia: T/S Parameters
            </a>
            <span class="dd-ref-sep">·</span>
            <a href="https://www.youtube.com/watch?v=JdQ3mLU5zBE"
               target="_blank" rel="noopener" title="T/S Parameters Explained — YouTube video guide">
              T/S Parameters Explained ▶
            </a>
          </div>
        </div>

        <!-- Footer -->
        <div class="dd-footer">
          <button @click="resetAll" title="Clear all entered values">Reset</button>
          <span class="dd-sp"></span>
          <button @click="$emit('close')">Cancel</button>
          <button class="pri" :disabled="!canApply" @click="applyDriver"
                  :title="canApply ? 'Load this driver into the current design' : 'Fill in required parameters first'">
            Apply
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dd-overlay {
  position: fixed; inset: 0; background: rgba(4,8,14,.75);
  display: flex; align-items: center; justify-content: center; z-index: 300;
}
.dd-modal {
  width: min(460px, 96vw); max-height: 90vh;
  display: flex; flex-direction: column;
  background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden;
  box-shadow: 0 8px 32px #0009;
}
.dd-header {
  display: flex; align-items: center; padding: 10px 14px;
  border-bottom: 1px solid var(--line); font-weight: 600; font-size: 13px; flex-shrink: 0;
}
.dd-x {
  margin-left: auto; background: none; border: none; color: var(--mut);
  font-size: 20px; cursor: pointer; padding: 0 2px; min-height: unset; line-height: 1;
}
.dd-x:hover { color: var(--fg); }

.dd-body { overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 8px; }

.dd-id-grid { display: grid; grid-template-columns: 52px 1fr; gap: 3px 8px; align-items: center; }
.dd-id-grid label { font-size: 11px; color: var(--mut); text-align: right; }
.dd-text { padding: 3px 6px; background: var(--panel2); border: 1px solid var(--line); border-radius: 4px; color: var(--fg); font: inherit; font-size: 12px; width: 100%; }
.dd-name { border-color: var(--acc); }

.dd-table { border: 1px solid var(--line); border-radius: 5px; overflow: hidden; }
.dd-sect-hdr {
  padding: 3px 8px;
  background: var(--panel2); border-bottom: 1px solid var(--line);
  font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; color: var(--acc);
}
.dd-row {
  display: grid; grid-template-columns: 52px 1fr 52px 22px;
  align-items: center; border-bottom: 1px solid var(--line);
}
.dd-row:last-child { border-bottom: none; }
.dd-lbl {
  font-size: 11px; color: var(--mut); padding: 0 6px;
  text-align: right; white-space: nowrap; user-select: none;
}
.dd-val {
  width: 100%; padding: 3px 5px; border: none;
  border-left: 1px solid var(--line); border-right: 1px solid var(--line);
  font: inherit; font-size: 11px; font-variant-numeric: tabular-nums;
  text-align: right; outline: none; min-height: 24px;
}
.dd-val:focus { border-color: var(--acc); position: relative; z-index: 1; }

/* State-specific input colours */
.input-E { background: color-mix(in srgb, #3a3 8%, var(--bg)); color: var(--fg); }
.input-C { background: color-mix(in srgb, var(--acc) 10%, var(--bg)); color: var(--acc); }
.input-N { background: var(--bg); color: var(--mut); }

/* Read-only derived cells */
.dd-ro-val {
  padding: 3px 5px; font-size: 11px; font-variant-numeric: tabular-nums;
  text-align: right; border-left: 1px solid var(--line); border-right: 1px solid var(--line);
  line-height: 1.45; min-height: 24px; display: flex; align-items: center; justify-content: flex-end;
}
.ro-C { background: color-mix(in srgb, var(--acc) 10%, var(--bg)); color: var(--acc); font-style: italic; }
.ro-N { background: var(--bg); color: var(--line); }

.dd-unit { font-size: 10px; color: var(--mut); padding: 0 4px; white-space: nowrap; text-align: left; }
.dd-badge { font-size: 9px; font-weight: 700; text-align: center; padding: 0 2px; }
.badge-E { color: #5ad17a; }
.badge-C { color: var(--acc); }
.badge-N { color: var(--line); }

.dd-notes-wrap { display: flex; flex-direction: column; gap: 3px; }
.dd-notes-lbl { font-size: 10.5px; color: var(--mut); }
.dd-notes {
  background: var(--panel2); border: 1px solid var(--line); border-radius: 4px;
  color: var(--fg); font: inherit; font-size: 11px; padding: 4px 6px; resize: vertical; width: 100%;
}

.dd-missing {
  font-size: 10.5px; color: var(--acc2);
  background: rgba(255,180,84,.07); border: 1px solid rgba(255,180,84,.25);
  border-radius: 4px; padding: 5px 8px;
}
.dd-refs { font-size: 10.5px; color: var(--mut); display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.dd-refs a { color: var(--acc); text-decoration: none; }
.dd-refs a:hover { text-decoration: underline; }
.dd-ref-sep { color: var(--line); }

.dd-footer {
  display: flex; gap: 8px; padding: 10px 14px;
  border-top: 1px solid var(--line); align-items: center; flex-shrink: 0;
}
.dd-sp { flex: 1; }
.dd-footer button:disabled { opacity: .4; cursor: not-allowed; }
</style>
