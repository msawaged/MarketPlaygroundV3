// frontend/src/lib/payoff.js
// Real profit/loss math for a v4 trade (stock, single options, spreads, iron condor).
// Option values before expiration use Black-Scholes with the trade's volatility
// estimate, matching how the backend grades strategies. Results are estimates.

const RISK_FREE = 0.04;
const CONTRACT = 100;

function ncdf(x) {
  // Abramowitz & Stegun 7.1.26
  const t = 1 / (1 + 0.3275911 * Math.abs(x) / Math.SQRT2);
  const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-(x * x) / 2);
  return x >= 0 ? 0.5 * (1 + y) : 0.5 * (1 - y);
}

export function bsPrice(spot, strike, years, vol, kind) {
  if (years <= 0 || vol <= 0 || spot <= 0) {
    return kind === 'call' ? Math.max(0, spot - strike) : Math.max(0, strike - spot);
  }
  const sq = vol * Math.sqrt(years);
  const d1 = (Math.log(spot / strike) + (RISK_FREE + 0.5 * vol * vol) * years) / sq;
  const d2 = d1 - sq;
  const disc = Math.exp(-RISK_FREE * years);
  return kind === 'call'
    ? spot * ncdf(d1) - strike * disc * ncdf(d2)
    : strike * disc * ncdf(-d2) - spot * ncdf(-d1);
}

const DAY_MS = 86400000;

function daysBetween(a, b) {
  return Math.max(0, Math.round((b - a) / DAY_MS));
}

/**
 * Turn a trade (as returned by the v4 engine) into a model we can price.
 * trade: { type, trade_legs, expiration, net_cost, vol? }
 */
export function buildModel(trade, entryPrice, today = new Date()) {
  const type = trade?.type || '';
  const legs = (trade?.trade_legs || []).filter((l) => l && l.instrument === 'option' && l.strike_price);
  const vol = Number(trade?.vol) > 0 ? Number(trade.vol) : 0.35;
  if (type === 'Sell / Avoid') return { kind: 'avoid', type };
  if (!legs.length) {
    return { kind: 'stock', type, entry: Number(entryPrice), direction: type === 'Buy Stock' ? 1 : -1 };
  }
  const exp = legs[0].expiration ? new Date(legs[0].expiration + 'T21:00:00Z') : null;
  const daysToExp = exp ? daysBetween(today, exp) : 90;
  const parsed = legs.map((l) => ({
    sign: l.action === 'Sell' ? -1 : 1,
    kind: String(l.option_type || '').toLowerCase() === 'put' ? 'put' : 'call',
    strike: Number(l.strike_price),
    premium: Number(l.est_premium) || 0,
    qty: Number(l.quantity) || 1,
  }));
  const netPremium = parsed.reduce((s, l) => s + l.sign * l.premium * l.qty, 0); // >0 debit, <0 credit
  let capitalPerUnit = Math.abs(netPremium) * CONTRACT;
  if (netPremium < 0) {
    // credit structure (iron condor): capital at risk = widest wing - credit
    const strikes = parsed.map((l) => l.strike).sort((a, b) => a - b);
    const width = strikes.length >= 4 ? Math.max(strikes[1] - strikes[0], strikes[3] - strikes[2]) : 0;
    capitalPerUnit = Math.max(1, (width + netPremium) * CONTRACT);
  }
  return {
    kind: 'options', type, legs: parsed, vol, entry: Number(entryPrice),
    expiration: legs[0].expiration, daysToExp, netPremium, capitalPerUnit,
  };
}

/** P&L of one unit (1 contract set, or 1 share) at underlying price S with `daysFromNow` elapsed. */
export function unitPnl(model, S, daysFromNow = null) {
  if (!model || model.kind === 'avoid') return 0;
  if (model.kind === 'stock') return model.direction * (S - model.entry);
  const left = daysFromNow == null ? 0 : Math.max(0, model.daysToExp - daysFromNow);
  const years = left / 365;
  let value = 0;
  for (const l of model.legs) value += l.sign * l.qty * bsPrice(S, l.strike, years, model.vol, l.kind);
  return (value - model.netPremium) * CONTRACT;
}

/** How many units an investment buys, and what it actually costs. */
export function sizePosition(model, amount) {
  amount = Number(amount) || 0;
  if (!model || model.kind === 'avoid' || amount <= 0) return { units: 0, cost: 0, note: null };
  if (model.kind === 'stock') {
    const units = amount / model.entry;
    return { units, cost: amount, note: `${units.toFixed(units < 10 ? 2 : 0)} shares` };
  }
  const per = model.capitalPerUnit;
  const units = Math.max(1, Math.floor(amount / per));
  const note = amount < per
    ? `One contract needs about $${Math.round(per).toLocaleString()}, so this shows 1 contract`
    : `${units} contract${units > 1 ? 's' : ''} at about $${Math.round(per).toLocaleString()} each`;
  return { units, cost: units * per, note };
}

/** Summary at expiration over a wide price range: breakevens, max profit, max loss (per unit). */
export function summarize(model) {
  if (!model || model.kind === 'avoid') return null;
  const lo = model.entry * 0.01, hi = model.entry * 3;
  const n = 1200;
  let maxP = -Infinity, maxL = Infinity, prev = null;
  const breakevens = [];
  for (let i = 0; i <= n; i++) {
    const S = lo + (hi - lo) * (i / n);
    const v = unitPnl(model, S);
    maxP = Math.max(maxP, v);
    maxL = Math.min(maxL, v);
    if (prev && Math.sign(prev.v) !== Math.sign(v) && v !== 0) {
      const t = prev.v / (prev.v - v);
      breakevens.push(prev.S + t * (S - prev.S));
    }
    prev = { S, v };
  }
  const rising = unitPnl(model, hi) > unitPnl(model, hi * 0.95) + 1e-6;
  const falling = unitPnl(model, lo) > unitPnl(model, lo * 1.05) + 1e-6;
  const unlimitedUp = model.kind === 'stock' ? model.direction > 0 : rising && model.legs.some((l) => l.kind === 'call' && l.sign > 0) && !model.legs.some((l) => l.kind === 'call' && l.sign < 0);
  return {
    breakevens,
    maxProfit: unlimitedUp ? Infinity : maxP,
    maxLoss: model.kind === 'stock' && model.direction < 0 ? -Infinity : maxL,
    unlimitedUp,
    falling,
  };
}

/** Bear / flat / bull outcomes for an investment, at expiration (options) or after the horizon (stock). */
export function scenarios(model, amount, movePct = 0.2) {
  if (!model || model.kind === 'avoid') return [];
  const { units, cost } = sizePosition(model, amount);
  const at = (mult) => unitPnl(model, model.entry * mult) * units;
  return [
    { label: `Falls ${Math.round(movePct * 100)}%`, pnl: at(1 - movePct), cost },
    { label: 'Stays flat', pnl: at(1), cost },
    { label: `Rises ${Math.round(movePct * 100)}%`, pnl: at(1 + movePct), cost },
  ];
}

export function money(v, { sign = false } = {}) {
  if (v === Infinity) return 'Unlimited';
  if (v === -Infinity) return 'Unlimited';
  if (v == null || Number.isNaN(v)) return '—';
  const r = Math.round(v);
  const s = `$${Math.abs(r).toLocaleString()}`;
  if (r < 0) return `-${s}`;
  return sign && r > 0 ? `+${s}` : s;
}

// ---------------- plain English ----------------

export function niceDate(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'T12:00:00Z');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
}

const $ = (v) => `$${Number(v).toLocaleString('en-US', { maximumFractionDigits: 2 })}`;

/**
 * The trade in three or four plain sentences: what you pay, best case, worst case, breakeven.
 * Returns [{ tone: 'neutral'|'good'|'bad'|'warn', text }].
 */
export function plainEnglish(model, sum, units, ticker, amount) {
  if (!model || model.kind === 'avoid' || !sum) return [];
  if (model.kind === 'stock') {
    const ten = Math.round(amount * 0.1);
    const up = model.direction > 0;
    return [
      { tone: 'neutral', text: `You ${up ? 'buy' : 'short'} about ${$(amount)} of ${ticker} (${(amount / model.entry).toFixed(amount / model.entry < 10 ? 2 : 0)} shares).` },
      { tone: 'good', text: `Every 10% ${ticker} ${up ? 'rises' : 'falls'}, you make about ${$(ten)}.` },
      { tone: 'bad', text: `Every 10% it ${up ? 'falls' : 'rises'}, you lose about ${$(ten)}. You can sell any time.` },
    ];
  }
  const n = Math.max(1, units || 1);
  const strikes = model.legs.map((l) => l.strike).sort((a, b) => a - b);
  const date = niceDate(model.expiration);
  const lo = strikes[0], hi = strikes[strikes.length - 1];
  const cost = model.capitalPerUnit * n;
  const best = Number.isFinite(sum.maxProfit) ? sum.maxProfit * n : null;
  const worst = Math.abs(sum.maxLoss) * n;
  const be = sum.breakevens.map((b) => $(b.toFixed(2))).join(' or ');
  const credit = model.netPremium < 0;
  const lines = [];
  lines.push(credit
    ? { tone: 'neutral', text: `You collect about ${$(Math.round(-model.netPremium * 100 * n))} today and set aside ${$(Math.round(cost))} as the most you could lose.` }
    : { tone: 'neutral', text: `You pay about ${$(Math.round(cost))} today${n > 1 ? ` for ${n} contracts` : ''}. That's the most you can lose.` });
  switch (model.type) {
    case 'Bull Call Spread':
      lines.push({ tone: 'good', text: `Best case: +${$(Math.round(best))} if ${ticker} is at or above ${$(hi)} on ${date}.` });
      lines.push({ tone: 'bad', text: `Worst case: −${$(Math.round(worst))} if it's at or below ${$(lo)} on ${date}.` });
      break;
    case 'Bear Put Spread':
      lines.push({ tone: 'good', text: `Best case: +${$(Math.round(best))} if ${ticker} is at or below ${$(lo)} on ${date}.` });
      lines.push({ tone: 'bad', text: `Worst case: −${$(Math.round(worst))} if it's at or above ${$(hi)} on ${date}.` });
      break;
    case 'Long Call':
      lines.push({ tone: 'good', text: `Best case: no cap. The higher ${ticker} goes above ${be} by ${date}, the more you make.` });
      lines.push({ tone: 'bad', text: `Worst case: −${$(Math.round(worst))} if it's at or below ${$(lo)} on ${date}.` });
      break;
    case 'Long Put':
      lines.push({ tone: 'good', text: `Best case: +${$(Math.round(best))} if ${ticker} drops toward zero; you profit below ${be} by ${date}.` });
      lines.push({ tone: 'bad', text: `Worst case: −${$(Math.round(worst))} if it's at or above ${$(hi)} on ${date}.` });
      break;
    case 'Iron Condor': {
      const inner = strikes.length >= 4 ? [strikes[1], strikes[2]] : [lo, hi];
      lines.push({ tone: 'good', text: `Best case: keep +${$(Math.round(best))} if ${ticker} stays between ${$(inner[0])} and ${$(inner[1])} until ${date}.` });
      lines.push({ tone: 'bad', text: `Worst case: −${$(Math.round(worst))} if it ends below ${$(lo)} or above ${$(hi)}.` });
      break;
    }
    default:
      if (best != null) lines.push({ tone: 'good', text: `Best case: +${$(Math.round(best))} by ${date}.` });
      lines.push({ tone: 'bad', text: `Worst case: −${$(Math.round(worst))}.` });
  }
  if (be) lines.push({ tone: 'warn', text: `You break even if ${ticker} is at ${be} on ${date}.` });
  return lines;
}
