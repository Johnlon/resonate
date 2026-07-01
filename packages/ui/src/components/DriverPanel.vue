<script setup>
import { computed, ref, watch, nextTick } from 'vue';
import { state, driver, driverWarnings, driverShort } from '../store.js';
import DriverDefineModal from './DriverDefineModal.vue';

const MY_DRIVERS_KEY = 'resonate_my_drivers';

function loadMyDrivers() {
  try { return JSON.parse(localStorage.getItem(MY_DRIVERS_KEY) || '[]'); } catch { return []; }
}
function saveMyDrivers(list) {
  try { localStorage.setItem(MY_DRIVERS_KEY, JSON.stringify(list)); } catch {}
}

const savingMode = ref(false);
const saveName   = ref('');

function startSave() {
  saveName.value = state.driverRaw.name || 'Custom Driver';
  savingMode.value = true;
  nextTick(() => document.querySelector('.save-name-input')?.select());
}

function confirmSave() {
  const name = saveName.value.trim() || state.driverRaw.name || 'Custom Driver';
  const list = loadMyDrivers();
  const entry = { ...state.driverRaw, name, _savedAt: Date.now() };
  const idx = list.findIndex(d => d.name === name);
  if (idx >= 0) list[idx] = entry; else list.push(entry);
  saveMyDrivers(list);
  state.driverRaw.name = name;
  state.driverSource = { ...state.driverRaw };
  state.editDriver = false;
  savingMode.value = false;
}

let _skipNextRename = false;

function resetToSource() {
  _skipNextRename = true;
  state.driverRaw = { ...state.driverSource };
  nextTick(() => { _skipNextRename = false; });
}

const TS_KEYS = ['Fs', 'Qts', 'Qes', 'Qms', 'Vas', 'Sd', 'Re', 'Le', 'Xmax', 'Pe'];
watch(
  () => TS_KEYS.map(k => state.driverRaw[k]),
  () => {
    if (_skipNextRename || !state.editDriver || !state.driverSource) return;
    if (!state.driverRaw.name?.startsWith('Custom - ')) {
      state.driverRaw.name = 'Custom - ' + (state.driverSource.name || 'Driver');
    }
  }
);
import { ebp } from '@resonate/engine';

const d = computed(() => state.driverRaw);
const drv = driver;

const ebpVal = computed(() => ebp(drv.value));
const sug = computed(() => {
  const e = ebpVal.value;
  return e < 50 ? 'sealed' : e > 100 ? 'vented' : 'sealed or vented';
});

const dismissed = ref(false);
watch(driver, () => { dismissed.value = false; });

function startEdit() {
  if (!state.driverSource) state.driverSource = { ...state.driverRaw };
  state.editDriver = true;
}

const drvLinks = computed(() => {
  const r = state.driverRaw;
  const links = [];
  if (r.datasheetUrl)  links.push({ href: r.datasheetUrl,  label: 'Datasheet ↗',   title: 'Open manufacturer datasheet PDF' });
  if (r.manuPageUrl)   links.push({ href: r.manuPageUrl,   label: 'Manufacturer ↗', title: 'Open manufacturer product page' });
  if (r.vendorpageUrl && r.vendorpageUrl !== r.manuPageUrl)
    links.push({ href: r.vendorpageUrl, label: 'Vendor ↗', title: 'Open vendor/retailer product listing' });
  if (r.sourceUrl && r.sourceUrl !== r.vendorpageUrl && r.sourceUrl !== r.manuPageUrl)
    links.push({ href: r.sourceUrl, label: 'Source ↗', title: 'Source where T/S data was obtained' });
  if (r.frdUrl)        links.push({ href: r.frdUrl,        label: 'FRD/ZMA ↗',     title: 'Download frequency response & impedance measurement data' });
  if (r.impedanceUrl && r.impedanceUrl !== r.frdUrl)
    links.push({ href: r.impedanceUrl, label: 'Impedance ↗', title: 'Download impedance curve data' });
  return links;
});

// Reasonable physical ranges for edit inputs (in display units)
const RANGES = {
  Fs:   { min: 1,      max: 5000 },
  Qts:  { min: 0.01,   max: 20   },
  Qes:  { min: 0.01,   max: 20   },
  Qms:  { min: 0.05,   max: 200  },
  Vas:  { min: 0.001,  max: 10000 },  // litres
  Sd:   { min: 0.5,    max: 6000  },  // cm²
  Re:   { min: 0.1,    max: 300   },  // Ω
  Le:   { min: 0,      max: 100   },  // mH (0 = resistive, allowed)
  Xmax: { min: 0.1,    max: 500   },  // mm
  Pe:   { min: 0.1,    max: 50000 },  // W
};

function isValid(key, displayVal) {
  const r = RANGES[key];
  if (!r) return true;
  const v = parseFloat(displayVal);
  return isFinite(v) && v >= r.min && v <= r.max;
}

function numInput(key, scale, val) {
  if (isValid(key, val)) state.driverRaw[key] = parseFloat(val) / scale;
}

function applyDefine(raw) {
  state.driverRaw = raw;
  state.driverSource = { ...raw };
  state.defineOpen = false;
}
</script>

<template>
  <fieldset>
    <legend>Driver</legend>
    <div v-if="driverWarnings.length && !dismissed" class="drv-warn">
      <span>⚠ {{ driverWarnings.join(' · ') }}</span>
      <button class="drv-warn-x" @click="dismissed = true" title="Dismiss this warning">✕</button>
    </div>
    <div class="row" style="margin-bottom:6px">
      <button style="flex:1" @click="state.browseOpen = true" title="Browse the driver library — click any driver to see its specs, then load it into the current design">Browse / Select…</button>
      <button style="flex:1" @click="state.defineOpen = true" title="Enter T/S parameters from a datasheet to create a new custom driver model">Define new…</button>
    </div>
    <DriverDefineModal :open="state.defineOpen" @close="state.defineOpen = false" @apply="applyDefine" />
    <template v-if="!state.editDriver">
      <div class="drvsum" @click="startEdit" title="Click to edit driver Thiele/Small parameters — opens the full T/S parameter editor">
        <span class="nm">{{ driverShort(d) }}</span>
        <span class="drvlinks">
          <a v-if="d.datasheetUrl" :href="d.datasheetUrl" target="_blank" rel="noopener"
             :title="d.datasheetUrl.match(/\.pdf(\?|$)/i) ? 'Open datasheet PDF' : 'Open product page'"
             @click.stop>{{ d.datasheetUrl.match(/\.pdf(\?|$)/i) ? 'PDF' : '↗' }}</a>
        </span>
        <span class="ed">Edit ✎</span>
      </div>
      <div class="drvspecs">
        Fs <b>{{ (+d.Fs||0).toFixed(0) }} Hz</b> ·
        Qts <b>{{ (drv.Qts||0).toFixed(2) }}</b> ·
        Vas <b>{{ (d.Vas*1000).toFixed(1) }} L</b> ·
        Sd <b>{{ (d.Sd*1e4).toFixed(0) }} cm²</b> ·
        Re <b>{{ (+d.Re||0).toFixed(1) }} Ω</b> ·
        Xmax <b>{{ (d.Xmax*1000).toFixed(1) }} mm</b><br>
        EBP <b>{{ ebpVal.toFixed(0) }}</b> → {{ sug }} ·
        Bl {{ drv.Bl.toFixed(1) }} Tm ·
        Mms {{ (drv.Mms*1000).toFixed(1) }} g
      </div>
      <div v-if="d.providedBy || d.comment || drvLinks.length" class="drvsource">
        <span v-if="d.providedBy || d.comment">{{ [d.providedBy, d.comment].filter(Boolean).join(' · ') }}</span>
        <template v-for="(lnk, i) in drvLinks" :key="lnk.href">
          <span v-if="i === 0 && (d.providedBy || d.comment)"> · </span>
          <span v-else-if="i > 0"> · </span>
          <a :href="lnk.href" target="_blank" rel="noopener" :title="lnk.title">{{ lnk.label }}</a>
        </template>
      </div>
    </template>
    <template v-else>
      <div class="whatif-hint">
        Tweak specs for what-if analysis. Hit <b>Save to My Drivers</b> to keep this as a custom model, or <b>Done</b> to close without saving.
      </div>
      <div class="row"><label>Fs</label>
        <input type="number" step="any" min="1" max="5000" data-bind="Fs" :value="(+d.Fs).toFixed(1)"
               :class="{ 'inp-bad': !isValid('Fs',(+d.Fs).toFixed(1)) }"
               @input="e => numInput('Fs',1,e.target.value)"
               title="Resonance frequency — must be 1–5000 Hz">
        <span class="u">Hz</span></div>
      <div class="row"><label>Qts</label>
        <input type="number" step="any" min="0.01" max="20" :value="(+d.Qts).toPrecision(3)"
               :class="{ 'inp-bad': !isValid('Qts',(+d.Qts).toPrecision(3)) }"
               @input="e => numInput('Qts',1,e.target.value)"
               title="Total Q factor — must be 0.01–20">
        <span class="u"></span></div>
      <div class="row"><label>Qes</label>
        <input type="number" step="any" min="0.01" max="20" :value="(+d.Qes).toPrecision(3)"
               :class="{ 'inp-bad': !isValid('Qes',(+d.Qes).toPrecision(3)) }"
               @input="e => numInput('Qes',1,e.target.value)"
               title="Electrical Q factor — must be 0.01–20">
        <span class="u"></span></div>
      <div class="row"><label>Qms</label>
        <input type="number" step="any" min="0.05" max="200" :value="(+d.Qms).toPrecision(3)"
               :class="{ 'inp-bad': !isValid('Qms',(+d.Qms).toPrecision(3)) }"
               @input="e => numInput('Qms',1,e.target.value)"
               title="Mechanical Q factor — must be 0.05–200">
        <span class="u"></span></div>
      <div class="row"><label>Vas</label>
        <input type="number" step="any" min="0.001" max="10000" :value="(d.Vas*1000).toPrecision(4)"
               :class="{ 'inp-bad': !isValid('Vas',(d.Vas*1000).toPrecision(4)) }"
               @input="e => numInput('Vas',1000,e.target.value)"
               title="Equivalent volume — must be 0.001–10000 L">
        <span class="u">L</span></div>
      <div class="row"><label>Sd</label>
        <input type="number" step="any" min="0.5" max="6000" :value="(d.Sd*1e4).toPrecision(4)"
               :class="{ 'inp-bad': !isValid('Sd',(d.Sd*1e4).toPrecision(4)) }"
               @input="e => numInput('Sd',1e4,e.target.value)"
               title="Piston area — must be 0.5–6000 cm²">
        <span class="u">cm²</span></div>
      <div class="row"><label>Re</label>
        <input type="number" step="any" min="0.1" max="300" :value="(+d.Re).toPrecision(3)"
               :class="{ 'inp-bad': !isValid('Re',(+d.Re).toPrecision(3)) }"
               @input="e => numInput('Re',1,e.target.value)"
               title="DC resistance — must be 0.1–300 Ω">
        <span class="u">Ω</span></div>
      <div class="row"><label>Le</label>
        <input type="number" step="any" min="0" max="100" :value="(d.Le*1000).toPrecision(3)"
               :class="{ 'inp-bad': !isValid('Le',(d.Le*1000).toPrecision(3)) }"
               @input="e => numInput('Le',1000,e.target.value)"
               title="Inductance — 0–100 mH (0 is allowed for resistive voice coil)">
        <span class="u">mH</span></div>
      <div class="row"><label>Xmax</label>
        <input type="number" step="any" min="0.1" max="500" :value="(d.Xmax*1000).toPrecision(3)"
               :class="{ 'inp-bad': !isValid('Xmax',(d.Xmax*1000).toPrecision(3)) }"
               @input="e => numInput('Xmax',1000,e.target.value)"
               title="Peak excursion — must be 0.1–500 mm">
        <span class="u">mm</span></div>
      <div class="row"><label>Pe</label>
        <input type="number" step="any" min="0.1" max="50000" :value="(+d.Pe||0)"
               :class="{ 'inp-bad': !isValid('Pe',(+d.Pe||0)) }"
               @input="e => numInput('Pe',1,e.target.value)"
               title="Power handling — must be 0.1–50000 W">
        <span class="u">W</span></div>
      <div class="ebp">
        EBP = Fs/Qes = <b>{{ ebpVal.toFixed(0) }}</b> → suggests <b>{{ sug }}</b>.<br>
        Derived: Bl={{ drv.Bl.toFixed(2) }} Tm, Mms={{ (drv.Mms*1000).toFixed(1) }} g,
        Cms={{ (drv.Cms*1000).toFixed(3) }} mm/N
      </div>
      <div class="ts-refs">
        <a href="https://en.wikipedia.org/wiki/Thiele/Small_parameters"
           target="_blank" rel="noopener" title="Wikipedia: Thiele/Small parameters — definitions, equations, and units">
          Wikipedia: T/S Parameters
        </a>
        ·
        <a href="https://www.youtube.com/watch?v=JdQ3mLU5zBE"
           target="_blank" rel="noopener" title="T/S Parameters Explained — YouTube video guide">
          T/S Parameters Explained ▶
        </a>
      </div>
      <div v-if="drvLinks.length" class="drvsource" style="margin-top:4px">
        <template v-for="(lnk, i) in drvLinks" :key="lnk.href">
          <span v-if="i > 0"> · </span>
          <a :href="lnk.href" target="_blank" rel="noopener" :title="lnk.title">{{ lnk.label }}</a>
        </template>
      </div>
      <div v-if="savingMode" class="save-dlg">
        <label class="save-lbl">Save as</label>
        <input class="save-name-input" v-model="saveName"
               @keydown.enter="confirmSave" @keydown.escape="savingMode = false">
        <div class="save-btns">
          <button class="pri" @click="confirmSave" title="Save with this name to My Drivers">Save</button>
          <button @click="savingMode = false" title="Cancel">Cancel</button>
        </div>
      </div>
      <div v-else class="btns">
        <button :disabled="!state.driverSource"
                @click="resetToSource"
                :title="state.driverSource ? 'Reset all parameters back to ' + state.driverSource.name : 'No original to reset to — load a driver from the library first'">Reset</button>
        <button @click="startSave"
                title="Save this driver (with tweaked specs) to My Drivers in the browser library">Save to My Drivers</button>
        <button @click="state.editDriver = false; savingMode = false"
                title="Collapse the driver parameter editor and return to the summary view">Done</button>
      </div>
    </template>
  </fieldset>
</template>
