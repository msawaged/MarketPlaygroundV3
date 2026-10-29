// How this person likes to trade (shares vs options, and what matters most). Kept on this device.
const KEY = 'mp_prefs';

export function getPrefs() {
  try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch { return null; }
}

export function setPrefs(p) {
  try { localStorage.setItem(KEY, JSON.stringify(p)); } catch { /* private mode */ }
}

export const INSTRUMENTS = [
  { id: 'shares', label: '📈 Shares & funds', hint: 'Simple: own a piece of the company' },
  { id: 'auto', label: '✨ Let the AI pick', hint: 'Shares first, options when they fit better' },
  { id: 'options', label: '🎯 Options', hint: 'More ways to win, more to learn' },
];

export const GOALS = [
  { id: 'upside', label: '🚀 Biggest upside', hint: 'Make the most if I’m right' },
  { id: 'limited', label: '🛡️ Limit my risk', hint: 'Know my worst case up front' },
  { id: 'income', label: '💵 Earn income', hint: 'Get paid while I wait' },
  { id: 'protect', label: '🔒 Protect what I own', hint: 'Insurance for shares I have' },
];

export function prefsLabel(p) {
  if (!p || p.instrument === 'auto' || !p.instrument) return 'Shares first, AI picks';
  if (p.instrument === 'shares') return 'Shares & funds';
  const g = GOALS.find((x) => x.id === p.goal);
  return `Options${g ? ` · ${g.label.replace(/^\S+\s/, '')}` : ''}`;
}
