<script setup>
import { computed } from 'vue';
import { state, driver } from '../store.js';

const drv = driver;
const driveV = computed(() =>
  state.P.voltRef === 'iec' ? 2.83 : Math.sqrt((state.P.Pin ?? 1) * (drv.value.Re || 8)));
</script>

<template>
  <fieldset>
    <legend>Signal &amp; drivers</legend>
    <div class="row" title="WinISD: Le excluded from acoustic circuit — matches WinISD output exactly. Full gyrator: Le included in acoustic drive — physically more complete but diverges slightly from WinISD.">
      <label>Circuit model</label>
      <select v-model="state.P.circuitModel" style="flex:1">
        <option value="winisd">WinISD (Le acoustic-only)</option>
        <option value="gyrator">Full gyrator (Le everywhere)</option>
      </select>
    </div>
    <div class="row" title="Input power used in 1W (WinISD) mode. Drive voltage = √(Pin × Re). Ignored in 2.83V IEC mode.">
      <label>Input power</label>
      <input type="number" step="any" :value="state.P.Pin" @input="e => state.P.Pin = parseFloat(e.target.value)||1">
      <span class="u">W</span>
    </div>
    <div class="row" title="Series resistance (wire, crossover DCR, amplifier output impedance). WinISD default is 0.1 Ω.">
      <label>Series resistance</label>
      <input type="number" step="0.01" min="0" :value="state.P.Rs" @input="e => state.P.Rs = parseFloat(e.target.value)||0">
      <span class="u">Ω</span>
    </div>
    <div class="row" title="SPL reference voltage. '1W (WinISD)' uses √(Pin×Re), matching WinISD output. '2.83V IEC' uses the IEC 60268-5 sensitivity standard — SPL curves will read ~2–4 dB higher for low-impedance drivers and match most datasheets.">
      <label>SPL reference</label>
      <div class="voltref-btns">
        <button :class="{ active: state.P.voltRef !== 'iec' }" @click="state.P.voltRef = 'winisd'">1W (WinISD)</button>
        <button :class="{ active: state.P.voltRef === 'iec' }" @click="state.P.voltRef = 'iec'">2.83V IEC</button>
      </div>
    </div>
    <div class="row" title="Drive voltage applied to the circuit.">
      <label>Drive voltage</label>
      <span style="width:96px;text-align:right;color:var(--acc2)">{{ driveV.toFixed(3) }} V</span>
      <span class="u"></span>
    </div>
    <div class="row">
      <label>No. of drivers</label>
      <input type="number" step="1" :value="state.P.nDrivers" @input="e => state.P.nDrivers = parseInt(e.target.value)||1">
      <span class="u"></span>
    </div>
    <div class="row">
      <label>Wiring</label>
      <select v-model="state.P.wiring" style="flex:1">
        <option value="parallel">Parallel</option>
        <option value="series">Series</option>
      </select>
    </div>
  </fieldset>
</template>

<style scoped>
.voltref-btns {
  display: flex;
  flex: 1;
  gap: 3px;
}
.voltref-btns button {
  flex: 1;
  font-size: 11px;
  padding: 2px 4px;
  background: none;
  border: 1px solid var(--mut);
  border-radius: 3px;
  color: var(--mut);
  cursor: pointer;
}
.voltref-btns button.active {
  border-color: var(--acc);
  color: var(--acc);
  background: color-mix(in srgb, var(--acc) 12%, transparent);
}
.voltref-btns button:hover:not(.active) { color: var(--fg); border-color: var(--fg); }
</style>
