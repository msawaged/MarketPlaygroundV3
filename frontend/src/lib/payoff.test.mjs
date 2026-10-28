// Run: node frontend/src/lib/payoff.test.mjs
import assert from 'node:assert/strict';
import { bsPrice, buildModel, unitPnl, summarize, sizePosition, scenarios, money } from './payoff.js';

const today = new Date('2026-10-27T15:00:00Z');
const near = (a, b, tol) => assert.ok(Math.abs(a - b) <= tol, `${a} !~ ${b} (±${tol})`);

// Black-Scholes sanity: put-call parity
const S = 100, K = 100, T = 0.5, v = 0.3;
near(bsPrice(S, K, T, v, 'call') - bsPrice(S, K, T, v, 'put'), S - K * Math.exp(-0.04 * T), 1e-3);
assert.equal(bsPrice(120, 100, 0, v, 'call'), 20);

// Bull call spread 205/230, debit 14.2 - 5.1 = 9.1
const bcs = buildModel({ type: 'Bull Call Spread', vol: 0.3, trade_legs: [
  { action: 'Buy', option_type: 'Call', strike_price: 205, est_premium: 14.2, quantity: 1, expiration: '2027-02-19', instrument: 'option' },
  { action: 'Sell', option_type: 'Call', strike_price: 230, est_premium: 5.1, quantity: 1, expiration: '2027-02-19', instrument: 'option' },
] }, 204.6, today);
assert.equal(bcs.kind, 'options');
near(bcs.capitalPerUnit, 910, 0.01);
near(unitPnl(bcs, 150), -910, 0.01);          // below both strikes at expiry: lose the debit
near(unitPnl(bcs, 300), 2500 - 910, 0.01);    // above both: width - debit
const sb = summarize(bcs);
near(sb.maxProfit, 1590, 1); near(sb.maxLoss, -910, 1);
assert.equal(sb.breakevens.length, 1); near(sb.breakevens[0], 214.1, 0.3);
assert.equal(sb.unlimitedUp, false);
// before expiry the curve is smoother: value at the money is between the extremes
const mid = unitPnl(bcs, 214.1, 30);
assert.ok(mid > -910 && mid < 1590);

// Sizing: $500 < one contract -> 1 contract with a note; $5000 -> 5 contracts
assert.equal(sizePosition(bcs, 500).units, 1);
assert.match(sizePosition(bcs, 500).note, /One contract/);
assert.equal(sizePosition(bcs, 5000).units, 5);
const sc = scenarios(bcs, 5000);
assert.equal(sc.length, 3);
near(sc[0].pnl, -4550, 1);                     // falls 20% -> lose 5 x 910

// Long call: unlimited upside
const lc = buildModel({ type: 'Long Call', vol: 0.3, trade_legs: [
  { action: 'Buy', option_type: 'Call', strike_price: 100, est_premium: 8, quantity: 1, expiration: '2027-01-15', instrument: 'option' }] }, 100, today);
assert.equal(summarize(lc).unlimitedUp, true);
assert.equal(money(summarize(lc).maxProfit), 'Unlimited');

// Iron condor: credit trade, capital = wing - credit
const ic = buildModel({ type: 'Iron Condor', vol: 0.25, trade_legs: [
  { action: 'Buy', option_type: 'Put', strike_price: 80, est_premium: 0.5, instrument: 'option', expiration: '2027-01-15' },
  { action: 'Sell', option_type: 'Put', strike_price: 90, est_premium: 1.5, instrument: 'option', expiration: '2027-01-15' },
  { action: 'Sell', option_type: 'Call', strike_price: 110, est_premium: 1.5, instrument: 'option', expiration: '2027-01-15' },
  { action: 'Buy', option_type: 'Call', strike_price: 120, est_premium: 0.5, instrument: 'option', expiration: '2027-01-15' }] }, 100, today);
near(ic.netPremium, -2, 1e-9);
near(ic.capitalPerUnit, 800, 0.01);
near(unitPnl(ic, 100), 200, 0.01);
near(unitPnl(ic, 50), -800, 0.01);
assert.equal(summarize(ic).breakevens.length, 2);

// Stock
const st = buildModel({ type: 'Buy Stock', trade_legs: [{ action: 'Buy', instrument: 'stock' }] }, 50, today);
assert.equal(st.kind, 'stock');
near(unitPnl(st, 60), 10, 1e-9);
near(scenarios(st, 1000)[2].pnl, 200, 1e-6);   // +20% on $1000

assert.equal(buildModel({ type: 'Sell / Avoid', trade_legs: [] }, 10).kind, 'avoid');
assert.equal(money(-1234.4), '-$1,234');
assert.equal(money(50, { sign: true }), '+$50');
console.log('payoff tests passed');

// plain English
{
  const { buildModel, summarize, plainEnglish } = await import('./payoff.js');
  const trade = { type: 'Bull Call Spread', vol: 0.3, trade_legs: [
    { instrument: 'option', action: 'Buy', option_type: 'call', strike_price: 230, est_premium: 19.19, expiration: '2027-05-21' },
    { instrument: 'option', action: 'Sell', option_type: 'call', strike_price: 262.5, est_premium: 7.56, expiration: '2027-05-21' },
  ] };
  const m = buildModel(trade, 229.36, new Date('2026-10-27T12:00:00Z'));
  const lines = plainEnglish(m, summarize(m), 1, 'FERG', 1000);
  const txt = lines.map((l) => l.text).join(' | ');
  if (!/\$1,163 today/.test(txt)) throw new Error('cost line: ' + txt);
  if (!/\+\$2,087 if FERG is at or above \$262\.5 on May 21, 2027/.test(txt)) throw new Error('best line: ' + txt);
  if (!/−\$1,163 if it's at or below \$230/.test(txt)) throw new Error('worst line: ' + txt);
  if (!/break even if FERG is at \$241\.6/.test(txt)) throw new Error('breakeven: ' + txt);
  const s = buildModel({ type: 'Buy Stock', trade_legs: [] }, 100);
  const sl = plainEnglish(s, summarize(s), 10, 'XYZ', 1000).map((l) => l.text).join(' | ');
  if (!/10 shares/.test(sl) || !/make about \$100/.test(sl)) throw new Error('stock: ' + sl);
  console.log('plain English ok');
}

// straddle
{
  const { buildModel, summarize, plainEnglish } = await import('./payoff.js');
  const trade = { type: 'Long Straddle', vol: 0.4, trade_legs: [
    { instrument: 'option', action: 'Buy', option_type: 'Call', strike_price: 100, est_premium: 6, expiration: '2027-01-15' },
    { instrument: 'option', action: 'Buy', option_type: 'Put', strike_price: 100, est_premium: 5, expiration: '2027-01-15' },
  ] };
  const m = buildModel(trade, 100, new Date('2026-10-27T12:00:00Z'));
  const s = summarize(m);
  if (s.breakevens.length !== 2 || Math.abs(s.breakevens[0] - 89) > 0.5 || Math.abs(s.breakevens[1] - 111) > 0.5) throw new Error('straddle breakevens ' + s.breakevens);
  if (Math.abs(s.maxLoss + 1100) > 15) throw new Error('straddle max loss ' + s.maxLoss);
  const txt = plainEnglish(m, s, 1, 'XYZ', 1000).map((l) => l.text).join(' | ');
  if (!/up or down/.test(txt) || !/exactly \$100/.test(txt)) throw new Error('straddle text: ' + txt);
  console.log('straddle ok');
}

// shares + options, income strategies
{
  const { buildModel, summarize, plainEnglish, sizePosition } = await import('./payoff.js');
  const exp = '2027-01-15', T = new Date('2026-10-27T12:00:00Z');
  const cc = buildModel({ type: 'Covered Call', vol: 0.3, trade_legs: [
    { instrument: 'stock', action: 'Buy', quantity: 100, ticker: 'X' },
    { instrument: 'option', action: 'Sell', option_type: 'Call', strike_price: 110, est_premium: 3, expiration: exp }] }, 100, T);
  const s1 = summarize(cc);
  if (Math.abs(cc.capitalPerUnit - 9700) > 1) throw new Error('covered call capital ' + cc.capitalPerUnit);
  if (s1.unlimitedUp || Math.abs(s1.maxProfit - 1300) > 5) throw new Error('covered call max profit ' + s1.maxProfit);
  if (Math.abs(s1.breakevens[0] - 97) > 0.5) throw new Error('covered call breakeven ' + s1.breakevens);
  const csp = buildModel({ type: 'Cash-Secured Put', vol: 0.3, trade_legs: [
    { instrument: 'option', action: 'Sell', option_type: 'Put', strike_price: 90, est_premium: 2, expiration: exp }] }, 100, T);
  if (Math.abs(csp.capitalPerUnit - 8800) > 20) throw new Error('csp capital ' + csp.capitalPerUnit);
  if (sizePosition(csp, 1000).note.indexOf('needs about') < 0) throw new Error('csp sizing note');
  const t1 = plainEnglish(csp, summarize(csp), 1, 'X', 1000).map((l) => l.text).join(' | ');
  if (!/set aside/.test(t1) || !/buy the shares at that price/.test(t1)) throw new Error('csp text ' + t1);
  const pp = buildModel({ type: 'Protective Put', vol: 0.3, trade_legs: [
    { instrument: 'stock', action: 'Buy', quantity: 100, ticker: 'X' },
    { instrument: 'option', action: 'Buy', option_type: 'Put', strike_price: 90, est_premium: 2, expiration: exp }] }, 100, T);
  const s3 = summarize(pp);
  if (!s3.unlimitedUp || Math.abs(s3.maxLoss + 1200) > 5) throw new Error('protective put ' + s3.maxLoss);
  console.log('income + protection ok');
}
