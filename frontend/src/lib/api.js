// frontend/src/lib/api.js
// One place for the backend address and every call the app makes.
//
// Backend address, in order:
//   1. VITE_API_BASE (set it in Render / .env.local), e.g. https://marketplayground-backend-18mm.onrender.com
//   2. http://localhost:8000 when the app itself runs on localhost
//   3. the default Render backend URL

const PROD_DEFAULT = "https://marketplayground-backend-18mm.onrender.com";
const isLocal = typeof window !== "undefined" && ["localhost", "127.0.0.1"].includes(window.location.hostname);

export const API_BASE = (import.meta.env.VITE_API_BASE || (isLocal ? "http://localhost:8000" : PROD_DEFAULT)).replace(/\/$/, "");

/** Anonymous per-device id so the shared learning can tell users apart (no sign-in needed for the beta). */
export function userId() {
  const KEY = "mp_user_id";
  try {
    let id = localStorage.getItem(KEY);
    if (!id) {
      id = "u-" + (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2)) ;
      localStorage.setItem(KEY, id);
    }
    return id;
  } catch {
    return "anonymous";
  }
}

async function request(path, { method = "GET", body, signal } = {}) {
  const r = await fetch(`${API_BASE}${path}`, {
    method,
    signal,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await r.json(); } catch { /* empty body */ }
  if (!r.ok) {
    const msg = (data && (data.detail || data.message)) || `The server returned ${r.status}`;
    const err = new Error(typeof msg === "string" ? msg : `The server returned ${r.status}`);
    err.status = r.status;
    throw err;
  }
  return data;
}

/** Belief -> strategy (v4 engine behind the existing endpoint). */
export function processBelief(belief, { riskProfile = "moderate", signal } = {}) {
  return request("/strategy/process_belief", {
    method: "POST",
    body: { belief, user_id: userId(), risk_profile: riskProfile },
    signal,
  });
}

/** Thumbs up/down or "placed a paper trade" — feeds the shared learning. */
export function sendFeedback(beliefId, kind, pickId) {
  if (!beliefId) return Promise.resolve();
  return request("/v4/feedback", { method: "POST", body: { belief_id: beliefId, pick_id: pickId, kind, user_id: userId() } })
    .catch(() => {}); // feedback must never break the UI
}

export function getTrending(days = 14) {
  return request(`/v4/trending?days=${days}`);
}

export function getTickerPrices(symbols) {
  return request(`/ticker/prices?tickers=${encodeURIComponent(symbols.join(","))}`);
}

export function searchTickers(query, signal) {
  return request(`/ticker/search?query=${encodeURIComponent(query)}&limit=10`, { signal });
}

export function paperTrade(strategyData, belief) {
  return request("/api/paper-trading/execute", {
    method: "POST",
    body: { user_id: userId(), strategy_data: strategyData, belief },
  });
}

export function generateBasket(inputText) {
  return request("/basket/generate_basket", { method: "POST", body: { input_text: inputText, user_id: userId() } });
}
