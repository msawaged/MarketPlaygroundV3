// Run: node frontend/src/lib/text.test.mjs
import assert from 'node:assert/strict';
import { oppositeOf, lowerFirst } from './text.js';

assert.equal(oppositeOf('Bitcoin may slide toward $38,000 as technical weakness deepens.'),
  "I don't think bitcoin will slide toward $38,000 as technical weakness deepens");
assert.equal(oppositeOf("Missile production demand will keep rising, lifting defense contractors' orders."),
  "I don't think missile production demand will keep rising, lifting defense contractors' orders");
assert.equal(oppositeOf('AI firms will pay publishers for medical content licensing deals'),
  "I don't think AI firms will pay publishers for medical content licensing deals");
assert.equal(oppositeOf("Europe's race to build AI data centers will pull in more chip and power spending"),
  "I don't think Europe's race to build AI data centers will pull in more chip and power spending");
assert.equal(oppositeOf('Social Security overhaul debates will reshape retirement benefits'),
  "I don't think Social Security overhaul debates will reshape retirement benefits");
assert.equal(oppositeOf('Nvidia will face tighter China scrutiny'), "I don't think Nvidia will face tighter China scrutiny");
assert.equal(oppositeOf('German small home solar systems will keep earning'), "I don't think German small home solar systems will keep earning");
assert.equal(oppositeOf('The Fed won\'t cut rates soon'), "I doubt that the Fed won't cut rates soon");
assert.equal(oppositeOf('Rate cuts could lift homebuilders'), "I don't think rate cuts will lift homebuilders");
assert.equal(lowerFirst('Chip stocks will keep rallying'), 'chip stocks will keep rallying');
assert.equal(lowerFirst('5G rollouts speed up'), '5G rollouts speed up');
console.log('text tests passed');
