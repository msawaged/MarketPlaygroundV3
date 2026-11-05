// Run: node frontend/src/lib/figures.test.mjs
import assert from 'node:assert/strict';
import { amount, change, barWidths } from './figures.js';

const chg = (a, b) => change(amount(a), amount(b))?.text ?? null;

// The Evergy bug: MW vs GW with a range used to read as -99%
assert.equal(chg('350-400 MW', 'About 2.25 GW'), '6.0x');
assert.deepEqual(barWidths(amount('350-400 MW'), amount('About 2.25 GW')).map(Math.round), [17, 100]);
assert.equal(chg('2.25 GW', '3.1 GW'), '+38%');
assert.equal(chg('500 kWh', '1.5 MWh'), '3.0x');

// Money and scale words
assert.equal(chg('$3.5 billion', '$4.2 billion'), '+20%');
assert.equal(chg('$800M', '$1.2B'), '+50%');
assert.equal(chg('$12B', '$10 billion'), '-17%');
assert.equal(chg('1,200', '1,500'), '+25%');
assert.equal(chg('2 million barrels', '1.5 million barrels'), '-25%');

// Percent figures change by points, not percent of percent
assert.equal(chg('4.1%', '3.8%'), '-0.3 pts');
assert.equal(chg('25 percent', '30%'), '+5 pts');

// Mismatched or unreadable units: no badge rather than a wrong one
assert.equal(chg('5 months', '2 years'), null);
assert.equal(chg('$5 billion', '5%'), null);
assert.equal(chg('n/a', '$5'), null);
assert.deepEqual(barWidths(amount('5 months'), amount('2 years')), [100, 100]);

// "m" at the start of a word is not "million"
assert.deepEqual(amount('5 months'), { value: 5, unit: 'months' });

console.log('figures tests passed');
