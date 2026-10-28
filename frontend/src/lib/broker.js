// Real-money (Stage 2) client: the server keeps this switched off until a lawyer signs off.
import { useEffect, useState } from 'react';
import { request } from './api';

let cached = null;
const listeners = new Set();

export async function refreshBroker() {
  try { cached = await request('/v4/broker/status'); } catch { cached = { enabled: false, connected: false }; }
  listeners.forEach((f) => f(cached));
  return cached;
}

export function useBroker() {
  const [s, setS] = useState(cached);
  useEffect(() => {
    listeners.add(setS);
    if (!cached) refreshBroker();
    return () => listeners.delete(setS);
  }, []);
  return s;
}

export async function connectBroker() {
  const { url } = await request('/v4/broker/connect');
  window.location.href = url;
}

export async function disconnectBroker() {
  await request('/v4/broker/disconnect', { method: 'POST' });
  return refreshBroker();
}

export function previewOrder({ ticker, side = 'buy', amount, beliefId, pickId }) {
  return request('/v4/broker/preview', { method: 'POST', body: { ticker, side, amount_usd: amount, belief_id: beliefId, pick_id: pickId } });
}

export function placeOrder(previewId) {
  return request('/v4/broker/order', { method: 'POST', body: { preview_id: previewId, confirm: true } });
}
