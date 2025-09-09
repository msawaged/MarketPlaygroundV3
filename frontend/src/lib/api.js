// frontend/src/lib/api.js
// Centralized API base + helper functions

// Use .env.local → VITE_API_BASE, fallback to correct server :8000 (not 8001)
export const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

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

// === Hot Trades ===
export async function getHotTrades(limit = 20, sort = "createdAt") {
  const qs = new URLSearchParams({ limit, sort }).toString();
  const r = await fetch(`${API_BASE}/hot_trades?${qs}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// === Strategy History ===
export async function getStrategyHistory(user_id) {
  const r = await fetch(`${API_BASE}/strategy/history/${user_id}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// === Submit Feedback ===
export async function submitFeedback(belief, strategy, feedback) {
  const r = await fetch(`${API_BASE}/submit_feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ belief, strategy, feedback }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// === Analytics ===
export async function getStrategyDistribution(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const r = await fetch(`${API_BASE}/analytics/strategy_distribution${qs ? `?${qs}` : ""}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function getTrendingStrategies(limit = 5) {
  const r = await fetch(`${API_BASE}/analytics/trending_strategies?limit=${limit}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// === Debug/Logs ===
export async function getRecentLogs(limit = 10) {
  const r = await fetch(`${API_BASE}/logs/recent?limit=${limit}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function getDebugStatus() {
  const r = await fetch(`${API_BASE}/debug/status`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}