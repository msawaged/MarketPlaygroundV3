// frontend/src/lib/api.js
// Centralized API base + helper functions

// Use .env.local → VITE_API_BASE, fallback to creative server :8001
export const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8001";

// === Belief → Strategy ===
export async function processBelief(user_id, belief) {
  const r = await fetch(`${API_BASE}/strategy/process_belief`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id, belief }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// === Ticker Prices ===
export async function getTickerPrices(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const r = await fetch(`${API_BASE}/ticker/prices${qs ? `?${qs}` : ""}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
