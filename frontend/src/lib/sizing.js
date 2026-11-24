// Trade sizing, the way a desk does it: a dollar amount, or a % of the whole account (net liquidation value:
// cash plus what you own). Selling: any % of the position, or a dollar amount. Pure functions, tested in
// sizing.test.mjs.

const STEP = 10000; // practice shares are fractional to 4 decimals (backend SHARE_STEP)
const floorShares = (x) => Math.floor(x * STEP + 1e-7) / STEP;

/** "12.5" / "$2,500" / "" -> a positive number, or 0. */
export function parseAmount(raw) {
  const n = Number(String(raw ?? '').replace(/[^0-9.]/g, ''));
  return Number.isFinite(n) && n > 0 ? n : 0;
}

/** Dollars a size means: mode 'usd' -> the amount; 'pct' -> that % of the account's total value. */
export function toDollars(mode, raw, accountValue) {
  const n = parseAmount(raw);
  if (mode === 'pct') return n > 0 && accountValue > 0 ? (accountValue * Math.min(n, 100)) / 100 : 0;
  return n;
}

/**
 * A buy of `dollars` of shares, checked against the account: what it buys, its weight in the account
 * and the cash left. `over` when it costs more than the spare cash (the server refuses that).
 */
export function buyPlan(dollars, price, { accountValue = 0, cash = null, held = 0 } = {}) {
  const shares = price > 0 && dollars > 0 ? floorShares(dollars / price) : 0;
  const cost = shares * price;
  const after = (held || 0) * price + cost;
  return {
    shares, cost,
    weight: accountValue > 0 ? (cost / accountValue) * 100 : null,          // this order, % of the account
    weightAfter: accountValue > 0 ? (after / accountValue) * 100 : null,    // the whole position after it
    cashLeft: cash == null ? null : cash - cost,
    over: cash != null && cost > cash + 0.005,
  };
}

/** Whole contracts that fit a budget (0 if not even one). */
export function contractsFor(dollars, perContract, max = 1000) {
  if (!(dollars > 0) || !(perContract > 0)) return 0;
  return Math.min(max, Math.floor(dollars / perContract + 1e-9));
}

/**
 * A sale: mode 'pct' (any % of the position) or 'usd' (about that many dollars of it). Rounds shares down;
 * sells everything when under $1 would be left (the server does the same).
 */
export function sellPlan(position, mode, raw) {
  const held = Number(position?.quantity) || 0;
  const px = Number(position?.current_price) || 0;
  const n = parseAmount(raw);
  let qty = 0;
  if (mode === 'pct') qty = n >= 100 ? held : floorShares(held * (n / 100));
  else qty = n > 0 && px > 0 ? floorShares(n / px) : 0;
  if (qty > 0 && (qty >= held || (held - qty) * px < 1)) qty = held;
  const all = qty > 0 && qty >= held;
  return {
    qty, all, value: qty * px, left: held - qty,
    pctOfPosition: held > 0 ? (qty / held) * 100 : 0,
    tooMuch: (mode === 'usd' && n > held * px + 0.005) || (mode === 'pct' && n > 100),
  };
}
