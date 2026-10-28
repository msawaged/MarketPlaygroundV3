// Recent beliefs on this device (for quick re-runs). Best-effort: private mode just has none.
const KEY = 'mp_recent_beliefs';

export function recentBeliefs() {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]').slice(0, 6); } catch { return []; }
}

export function rememberBelief(text) {
  try {
    const t = String(text || '').trim();
    if (!t) return;
    const list = [t, ...recentBeliefs().filter((x) => x.toLowerCase() !== t.toLowerCase())].slice(0, 6);
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch { /* ignore */ }
}

export function seen(flag) {
  try { return localStorage.getItem(`mp_seen_${flag}`) === '1'; } catch { return true; }
}

export function markSeen(flag) {
  try { localStorage.setItem(`mp_seen_${flag}`, '1'); } catch { /* ignore */ }
}
