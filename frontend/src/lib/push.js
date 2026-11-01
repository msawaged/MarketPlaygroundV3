// Turn "Market's open" alerts on or off for this device (Web Push).
import { request, userId } from './api';

const b64ToBytes = (s) => {
  const pad = '='.repeat((4 - (s.length % 4)) % 4);
  const raw = atob((s + pad).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
};
export const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent || '');
export const isStandalone = () => window.matchMedia?.('(display-mode: standalone)').matches || navigator.standalone === true;
export const pushSupported = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
// iPhone only allows web alerts once the app is on the home screen
export const needsHomeScreen = () => isIOS() && !isStandalone();

async function registration() {
  return (await navigator.serviceWorker.getRegistration('/')) || navigator.serviceWorker.register('/sw.js', { scope: '/' });
}

export async function currentSubscription() {
  if (!pushSupported()) return null;
  const reg = await navigator.serviceWorker.getRegistration('/');
  return reg ? reg.pushManager.getSubscription() : null;
}

export async function enableAlerts() {
  if (!pushSupported()) throw new Error("This browser can't show alerts.");
  const perm = await Notification.requestPermission();
  if (perm !== 'granted') throw new Error('Alerts are blocked. Allow notifications for MarketPlayground in your settings.');
  const reg = await registration();
  await navigator.serviceWorker.ready;
  const { key } = await request('/v4/push/key');
  let sub;
  try {
    sub = (await reg.pushManager.getSubscription()) || await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(key) });
  } catch {
    throw new Error("Couldn't turn on alerts in this browser. Check that notifications are allowed for MarketPlayground, or try Chrome or Safari.");
  }
  await request('/v4/push/subscribe', { method: 'POST', body: { subscription: sub.toJSON(), device_id: userId() } });
  return sub;
}

export async function disableAlerts() {
  const sub = await currentSubscription();
  if (sub) {
    await request('/v4/push/unsubscribe', { method: 'POST', body: { endpoint: sub.endpoint } }).catch(() => {});
    await sub.unsubscribe().catch(() => {});
  }
}

export async function testAlert() {
  const sub = await currentSubscription();
  if (!sub) throw new Error('Turn on alerts first.');
  return request('/v4/push/test', { method: 'POST', body: { endpoint: sub.endpoint } });
}
