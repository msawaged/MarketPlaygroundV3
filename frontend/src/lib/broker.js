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

// Options: buy ONE listed call or put with a limit price (the server finds the closest listed contract).
export function previewOptionOrder({ leg, underlying, contracts = 1, limitPrice, beliefId, pickId }) {
  return request('/v4/broker/preview_option', { method: 'POST', body: {
    underlying, option_type: String(leg.option_type || '').toLowerCase(), strike: Number(leg.strike_price),
    expiration: String(leg.expiration || '').slice(0, 10), contracts: Number(contracts),
    limit_price: limitPrice ? Number(limitPrice) : null, belief_id: beliefId, pick_id: pickId,
  } });
}

// Sell something you hold (all of it unless qty is given). Never opens a short.
export function previewClose({ symbol, qty, limitPrice }) {
  return request('/v4/broker/preview_close', { method: 'POST', body: { symbol, qty: qty ? Number(qty) : null, limit_price: limitPrice ? Number(limitPrice) : null } });
}

export async function getPositions() { return (await request('/v4/broker/positions')).positions || []; }
export async function getOrders() { return (await request('/v4/broker/orders')).orders || []; }
export function getJourney() { return request('/v4/journey'); }
