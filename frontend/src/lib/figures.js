// Before/after figures on story cards ("350-400 MW" -> "About 2.25 GW").
// Parses a figure into { value, unit } so two figures are only compared when they're in the same unit.
// A bad comparison is worse than none: when units differ or can't be read, change() returns null.

const SCALE = { thousand: 1e3, million: 1e6, billion: 1e9, trillion: 1e12, k: 1e3, m: 1e6, mm: 1e6, mn: 1e6, b: 1e9, bn: 1e9, t: 1e12 };
const SI = { k: 1e3, M: 1e6, G: 1e9, T: 1e12 };
const SI_UNITS = ['Wh', 'W']; // MW vs GW must compare correctly; a bare B is billions, not bytes

export function amount(s) {
  const str = String(s || '').replace(/,/g, '').replace(/[–—]/g, '-');
  const m = str.match(/(-?\d+(?:\.\d+)?)(?:\s*(?:-|to)\s*(\d+(?:\.\d+)?))?\s*(.*)$/i);
  if (!m) return null;
  let value = m[2] != null ? (parseFloat(m[1]) + parseFloat(m[2])) / 2 : parseFloat(m[1]); // ranges -> midpoint
  const rest = m[3].trim();
  const word = (rest.match(/^[A-Za-z%$€£]+/) || [''])[0];
  let unit = word.toLowerCase();

  const si = /[$€£]/.test(str) ? null : word.match(/^([kMGT])(Wh|W|B)$/); // $5MB isn't a thing; $5M is
  if (si) return { value: value * SI[si[1]], unit: si[2].toLowerCase() };
  if (SI_UNITS.includes(word)) return { value, unit: word.toLowerCase() };

  const scale = SCALE[unit];
  if (scale) {
    value *= scale;
    unit = (rest.slice(word.length).trim().match(/^[A-Za-z%]+/) || [''])[0].toLowerCase(); // "2 million barrels" -> barrels
  }
  if (/%|percent/.test(rest) && !unit) unit = '%';
  if (unit === 'percent') unit = '%';
  const cur = str.match(/[$€£]/);
  if (cur && !unit) unit = cur[0];
  return { value, unit };
}

export function change(a, b) {
  if (!a || !b || a.unit !== b.unit || !a.value) return null;
  if (a.unit === '%') {
    const d = b.value - a.value;
    return { text: `${d >= 0 ? '+' : ''}${+d.toFixed(Math.abs(d) < 10 ? 1 : 0)} pts`, up: d >= 0 };
  }
  const r = b.value / a.value;
  if (r <= 0) return null;
  if (r >= 1.95) return { text: `${r.toFixed(r >= 10 ? 0 : 1)}x`, up: true };
  const p = (r - 1) * 100;
  return { text: `${p >= 0 ? '+' : ''}${p.toFixed(Math.abs(p) < 10 ? 1 : 0)}%`, up: p >= 0 };
}

// Bar widths only make sense when both sides share a unit; otherwise draw them equal.
export function barWidths(a, b) {
  if (!a || !b || a.unit !== b.unit) return [100, 100];
  const max = Math.max(Math.abs(a.value), Math.abs(b.value)) || 1;
  return [a, b].map((x) => Math.max(6, (Math.abs(x.value) / max) * 100));
}
