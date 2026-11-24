// "Put it on your home screen": offer the installable app at the right moment, never on first visit, and count it.
// Chrome/Edge/Android fire `beforeinstallprompt`; we keep it and show our own button. iPhone never fires it, so there
// we show Safari's Share -> Add to Home Screen steps. Counts go to /v4/install/event (no personal data).
import { request, userId } from './api';
import { isIOS, isStandalone } from './push';

const SNOOZE_KEY = 'mp_install_snooze_until';
const OPENED_KEY = 'mp_install_opened_day';
const SNOOZE_DAYS = 30;
let deferred = null;
const listeners = new Set();
const notify = () => listeners.forEach((f) => { try { f(); } catch { /* ignore */ } });

export function track(kind) {
  request('/v4/install/event', { method: 'POST', body: { kind, device_id: userId() } }).catch(() => {});
}

// Called once at startup (index.jsx), before React renders, so an early event isn't missed.
export function initInstall() {
  if (typeof window === 'undefined') return;
  window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferred = e; notify(); });
  window.addEventListener('appinstalled', () => { deferred = null; track('installed'); notify(); });
  if (isStandalone()) {   // opened from the home screen: counted once a day per device
    const day = new Date().toISOString().slice(0, 10);
    try { if (localStorage.getItem(OPENED_KEY) !== day) { localStorage.setItem(OPENED_KEY, day); track('opened_standalone'); } } catch { /* private mode */ }
  }
}

export function onInstallChange(f) { listeners.add(f); return () => listeners.delete(f); }

export const isInstalled = () => isStandalone();

// Safari is the browser that reliably shows Add to Home Screen on iPhone; other iPhone browsers may hide it.
export const isIOSSafari = () => isIOS() && !/crios|fxios|edgios|opios|gsa\//i.test(navigator.userAgent || '');

export function snoozed() {
  try { return Date.now() < Number(localStorage.getItem(SNOOZE_KEY) || 0); } catch { return false; }
}

export function snooze() {
  try { localStorage.setItem(SNOOZE_KEY, String(Date.now() + SNOOZE_DAYS * 86400000)); } catch { /* private mode */ }
  track('dismissed');
}

// What this device can be offered: 'prompt' (one-tap install), 'ios' (Share steps), or null (nothing to offer).
export function installOffer() {
  if (isInstalled()) return null;
  if (deferred) return 'prompt';
  if (isIOS()) return 'ios';
  return null;
}

export async function promptInstall() {
  if (!deferred) return 'unavailable';
  const e = deferred;
  deferred = null;   // the browser allows prompt() once per event
  try {
    await e.prompt();
    const { outcome } = await e.userChoice;
    track(outcome === 'accepted' ? 'accepted' : 'dismissed');
    notify();
    return outcome;
  } catch {
    notify();
    return 'unavailable';
  }
}
