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

function authHeader() {
  try { const t = localStorage.getItem("mp_token"); return t ? { Authorization: `Bearer ${t}` } : {}; } catch { return {}; }
}

// The server is briefly unreachable while a new version deploys (about a minute). Requests wait it out:
// 502/503/504 come from the hosting proxy before the app sees anything, so any request is safe to resend;
// a dropped connection is only resent for reads and logins, never for trades.
const SAFE_TO_RESEND = /^\/v4\/auth\/(login|passkey\/login\/options|me)|^\/v4\/(movers|brain|trending|headlines|learning|my_beliefs|stats)/;
const WAITS = [1500, 3000, 5000, 8000];
const OFFLINE = "Can't reach MarketPlayground right now. Check your connection, or try again in a minute.";
const sleep = (ms) => new Promise((res) => setTimeout(res, ms));

export async function request(path, { method = "GET", body, signal, headers = {} } = {}) {
  const resendOnDrop = method === "GET" || SAFE_TO_RESEND.test(path);
  for (let attempt = 0; ; attempt++) {
    let r;
    try {
      r = await fetch(`${API_BASE}${path}`, {
        method,
        signal,
        headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...authHeader(), ...headers },
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (e) {
      if (e?.name === "AbortError") throw e;
      if (resendOnDrop && attempt < WAITS.length) { await sleep(WAITS[attempt]); continue; }
      const err = new Error(OFFLINE); err.status = 0; err.offline = true; throw err;
    }
    if ([502, 503, 504].includes(r.status) && attempt < WAITS.length) { await sleep(WAITS[attempt]); continue; }
    let data = null;
    try { data = await r.json(); } catch { /* empty body */ }
    if (!r.ok) {
      const msg = [502, 503, 504].includes(r.status) ? OFFLINE : (data && (data.detail || data.message)) || `The server returned ${r.status}`;
      const err = new Error(typeof msg === "string" ? msg : `The server returned ${r.status}`);
      err.status = r.status;
      throw err;
    }
    return data;
  }
}

/** Belief -> strategy (v4 engine behind the existing endpoint). */
export function processBelief(belief, { riskProfile = "moderate", prefs = null, signal } = {}) {
  return request("/strategy/process_belief", {
    method: "POST",
    body: { belief, user_id: userId(), risk_profile: riskProfile, prefs },
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

/** How the shared learning is going (aggregate, plain English). */
/** Owner-only: the learning page shows the practice feed and network internals. */
export function ownerKey() {
  try { return localStorage.getItem("mp_owner_key") || ""; } catch { return ""; }
}

export function getLearning() {
  return request("/v4/learning", { headers: { "X-Admin-Token": ownerKey() } });
}

/** This device's beliefs and how the picks it was shown are doing so far. */
export function getMyBeliefs() {
  return request(`/v4/my_beliefs?user_id=${encodeURIComponent(userId())}`);
}

export function getPortfolio() {
  return request(`/api/paper-trading/portfolio/${encodeURIComponent(userId())}?ts=${Date.now()}`);
}

export function closePosition(positionId) {
  return request("/api/paper-trading/close_position", { method: "POST", body: { user_id: userId(), position_id: positionId } });
}

export function cancelQueued(orderId) {
  return request("/api/paper-trading/cancel_queued", { method: "POST", body: { user_id: userId(), order_id: orderId } });
}

export function getHeadlines(limit = 4) {
  return request(`/v4/headlines?limit=${limit}`);
}

export function getReplay(picks, days = 365) {
  const t = picks.map((p) => p.ticker).join(",");
  const d = picks.map((p) => p.direction || "bullish").join(",");
  return request(`/v4/replay?tickers=${encodeURIComponent(t)}&directions=${encodeURIComponent(d)}&days=${days}`);
}

/** Today's headlines as hunches, with the companies each one moves (shared feed, refreshed ~30 min). */
export function getMovers() {
  return request("/v4/movers");
}

/** Story mode: one of today's news stories as full-screen cards. */
export function getStory(headline) {
  return request(`/v4/movers/story?h=${encodeURIComponent(headline)}`);
}

/** Practice options: the server re-prices every leg; we only send which contracts. */
export function paperTradeOptions({ ticker, structure, trade_legs, contracts, belief }) {
  return request("/api/paper-trading/execute_options", {
    method: "POST", body: { user_id: userId(), ticker, structure, trade_legs, contracts, belief },
  });
}

export function closeOption(positionId) {
  return request("/api/paper-trading/close_option", { method: "POST", body: { user_id: userId(), position_id: positionId } });
}
