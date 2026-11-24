// Run: node frontend/src/lib/sizing.test.mjs
import assert from 'node:assert/strict';
import { parseAmount, toDollars, buyPlan, contractsFor, sellPlan } from './sizing.js';

assert.equal(parseAmount('$2,500'), 2500);
assert.equal(parseAmount('12.5'), 12.5);
assert.equal(parseAmount(''), 0);
assert.equal(parseAmount('-3'), 3); // the minus sign is stripped: amounts are sizes, never negative
// a decimal comma (iPhone keypad outside the US) is a decimal point, never a 10x size; thousands commas still work
assert.equal(parseAmount('2,5'), 2.5);
assert.equal(parseAmount('12,75'), 12.75);
assert.equal(parseAmount('0,5'), 0.5);
assert.equal(parseAmount('1,000,000'), 1000000);
assert.equal(parseAmount('2,500.50'), 2500.5);
assert.equal(toDollars('pct', '2,5', 100000), 2500);

// 2.5% of a $102,000 account is $2,550; percent above 100 is capped
assert.equal(toDollars('pct', '2.5', 102000), 2550);
assert.equal(toDollars('pct', '150', 1000), 1000);
assert.equal(toDollars('usd', '750', 102000), 750);
assert.equal(toDollars('pct', '5', 0), 0);

// $2,550 of a $182.40 stock: 13.9802 shares, ~2.5% of the account, cash left, adding to 10 shares held
const b = buyPlan(2550, 182.4, { accountValue: 102000, cash: 40000, held: 10 });
assert.equal(b.shares, 13.9802);
assert.ok(Math.abs(b.weight - 2.5) < 0.01);
assert.ok(Math.abs(b.weightAfter - ((23.9802 * 182.4) / 102000) * 100) < 1e-9);
assert.ok(Math.abs(b.cashLeft - (40000 - 13.9802 * 182.4)) < 1e-6);
assert.equal(b.over, false);
assert.equal(buyPlan(50000, 100, { accountValue: 100000, cash: 40000 }).over, true);

// contracts that fit: $1,000 at $230 a contract is 4; $100 buys none; capped at the server's 1,000
assert.equal(contractsFor(1000, 230), 4);
assert.equal(contractsFor(100, 230), 0);
assert.equal(contractsFor(1e9, 1), 1000);
assert.equal(contractsFor(460, 230), 2); // exact fit counts

// selling: any %, any dollars; nearly everything sells everything
const pos = { quantity: 13.7061, current_price: 182.4 };
const s33 = sellPlan(pos, 'pct', '33');
assert.equal(s33.qty, 4.523);
assert.equal(s33.all, false);
assert.ok(Math.abs(s33.left - 9.1831) < 1e-9);
assert.equal(sellPlan(pos, 'pct', '100').all, true);
assert.equal(sellPlan(pos, 'pct', '120').tooMuch, true);
const s1k = sellPlan(pos, 'usd', '1000');
assert.equal(s1k.qty, 5.4824);
assert.equal(sellPlan(pos, 'usd', '2499.50').all, true);   // would leave 49 cents
assert.equal(sellPlan(pos, 'usd', '9999').tooMuch, true);
assert.equal(sellPlan(pos, 'usd', '').qty, 0);

console.log('sizing tests passed');
