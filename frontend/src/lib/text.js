const ACRONYMS = new Set(['ai', 'ev', 'evs', 'us', 'uk', 'eu', 'etf', 'etfs', 'reit', 'reits', 'gpu', 'gpus', 'fed', 'glp-1']);

/** "ai chips" -> "AI chips" */
export function themeLabel(t) {
  const words = String(t || '').split(' ').map((w) => (ACRONYMS.has(w.toLowerCase()) ? w.toUpperCase() : w));
  const s = words.join(' ');
  return s.charAt(0).toUpperCase() + s.slice(1);
}
