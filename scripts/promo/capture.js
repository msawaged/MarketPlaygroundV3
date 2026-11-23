// Promo step 1/4: records real footage of the live site (no login, no account, no new idea) as a phone-sized
// CDP screencast, plus a marks file saying when each moment happened, where each tap landed and where to draw
// highlight rings.  node scripts/promo/capture.js <out_dir> [search=black friday]
// Out: <out_dir>/frames/*.jpg, <out_dir>/frames.json [{f, t}], <out_dir>/marks.json
// The search should be a story already made today (cached = free, and it doesn't count as a new idea).
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const SITE = process.env.MP_SITE || 'https://marketplayground-web.onrender.com';
const out = process.argv[2];
const query = process.argv[3] || 'black friday';
if (!out) throw new Error('usage: capture.js <out_dir> [search]');
fs.mkdirSync(path.join(out, 'frames'), { recursive: true });

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  const frames = [];
  const marks = { query, viewport: [390, 844], events: [], taps: [], rings: [], cards: [] };
  let t0 = null;
  const now = () => (Date.now() / 1000) - t0;
  const mark = (name) => { marks.events.push({ name, t: +now().toFixed(3) }); console.log(name, now().toFixed(2)); };
  const hold = (ms) => page.waitForTimeout(ms);

  cdp.on('Page.screencastFrame', async ({ data, metadata, sessionId }) => {
    const f = `${String(frames.length).padStart(5, '0')}.jpg`;
    fs.writeFileSync(path.join(out, 'frames', f), Buffer.from(data, 'base64'));
    frames.push({ f, t: +(metadata.timestamp - t0).toFixed(4) });
    try { await cdp.send('Page.screencastFrameAck', { sessionId }); } catch (e) { /* page gone */ }
  });

  // smooth eased scroll so the footage glides instead of jumping
  const glide = (y, ms = 1200) => page.evaluate(([y, ms]) => new Promise((done) => {
    const from = window.scrollY; const to = Math.max(0, Math.min(y, document.documentElement.scrollHeight - innerHeight));
    const s = performance.now();
    const step = (n) => {
      const k = Math.min(1, (n - s) / ms); const e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
      window.scrollTo(0, from + (to - from) * e); if (k < 1) requestAnimationFrame(step); else done();
    };
    requestAnimationFrame(step);
  }), [y, ms]);
  const glideTo = async (loc, top, ms) => {
    const y = await loc.evaluate((el) => el.getBoundingClientRect().top + window.scrollY);
    await glide(y - top, ms);
  };
  const tap = async (x, y, name) => { marks.taps.push({ name, t: +now().toFixed(3), x, y }); await page.mouse.click(x, y); };
  const tapEl = async (loc, name) => { const b = await loc.boundingBox(); await tap(b.x + b.width / 2, b.y + b.height / 2, name); };
  const ring = async (loc, name, pad = 6) => {
    const b = await loc.boundingBox();
    if (!b) throw new Error(`ring target missing: ${name}`);
    marks.rings.push({ name, t: +now().toFixed(3), x: b.x - pad, y: b.y - pad, w: b.width + 2 * pad, h: b.height + 2 * pad });
  };

  // 1. News tab, search bar near the top (the sign-up box above it stays out of shot: the app isn't launched)
  await page.goto(`${SITE}/trending`, { waitUntil: 'networkidle', timeout: 120000 });
  await hold(2500);
  const input = page.getByLabel('Search the news');
  await glideTo(input, 110, 10);
  await hold(600);
  t0 = Date.now() / 1000;
  // scroll positions over time, so the edit can keep the camera on the same spot of the page when it jumps
  await page.evaluate((t0) => {
    window.__sy = [[Date.now() / 1000 - t0, scrollY]];
    addEventListener('scroll', () => window.__sy.push([Date.now() / 1000 - t0, scrollY]), { passive: true });
  }, t0);
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 88, maxWidth: 1170, maxHeight: 2532, everyNthFrame: 1 });
  mark('news');
  await hold(1400);
  await tapEl(input, 'search');
  await hold(300);
  mark('type');
  await input.type(query, { delay: 105 });
  const make = page.getByText(/Make a story about/).first();
  await make.waitFor({ timeout: 60000 });
  mark('results');
  await hold(1300);
  await tapEl(make, 'make');
  mark('make');
  marks.scrolls = (await page.evaluate(() => window.__sy)).map(([t, y]) => [+t.toFixed(3), y]);

  // 2. Story mode: tap through the cards (taps pace them; each card would auto-advance at 7s)
  const dialog = page.getByRole('dialog', { name: 'Story' });
  await dialog.waitFor({ timeout: 120000 });
  await hold(400);
  mark('story');
  for (let i = 0; i < 12; i++) {
    const txt = (await dialog.innerText().catch(() => '')).replace(/\s+/g, ' ').slice(0, 90);
    marks.cards.push({ i, t: +now().toFixed(3), text: txt });
    console.log('card', i, txt);
    if (/WHO IT MOVES/i.test(txt)) {
      await hold(500);
      const ind = dialog.getByText(/^indirect$/i);
      for (let k = 0; k < await ind.count(); k++) {
        await ring(ind.nth(k).locator('xpath=ancestor::li[1]'), `story_indirect${k}`, 4);
      }
    }
    await hold(i === 0 ? 2600 : 3000);
    if (!(await dialog.count())) break;
    if (/Where this comes from/i.test(txt) || i >= 8) break;
    await tap(330, 560, `card${i}`);
    await hold(350);
  }
  if (await dialog.count()) await tapEl(page.getByLabel('Close story'), 'close');
  await hold(500);
  mark('closed');

  // 3. The story's card on the page: who it moves (indirect plays ringed), then the ways to play it
  const mine = page.locator('div.mt-4', { has: page.getByText('Made for your search') }).last();
  const touches = mine.getByText('Companies it touches').first();
  await glideTo(touches, 90, 1300);
  await hold(500);
  mark('companies');
  const ind = mine.locator('li', { hasText: /indirect/i });
  for (let i = 0; i < await ind.count(); i++) await ring(ind.nth(i), `indirect${i}`, 4);
  await hold(3200);
  const plays = mine.getByText(/Ways to play it/i).first();
  await page.waitForFunction(() => /bets it|Buy the shares|Sell|bets on/i.test(document.body.innerText), null, { timeout: 240000 });
  await glideTo(plays, 90, 1300);
  await hold(500);
  mark('plays');
  await ring(plays.locator('xpath=..'), 'plays', 6);
  await hold(3800);

  // 4. Brain page: the market keeps score, in the open
  await page.goto(`${SITE}/brain`, { waitUntil: 'networkidle', timeout: 120000 });
  await hold(1200);
  mark('brain');
  await hold(2200);
  const graded = page.getByText('Graded by the market', { exact: false }).first();
  await glideTo(graded, 300, 1600);
  await hold(400);
  mark('graded');
  await ring(graded.locator('xpath=..'), 'graded', 8);
  await hold(2600);
  const score = page.getByText(/The honest scorecard/i).first();
  await glideTo(score, 120, 1400);
  await hold(400);
  mark('scorecard');
  await ring(page.getByText(/of our #1 picks beat/i).first().locator('xpath=..'), 'scorecard', 10);
  await hold(3500);
  mark('end');
  await cdp.send('Page.stopScreencast');
  await hold(300);
  fs.writeFileSync(path.join(out, 'frames.json'), JSON.stringify(frames));
  fs.writeFileSync(path.join(out, 'marks.json'), JSON.stringify(marks, null, 1));
  console.log(`${frames.length} frames, ${now().toFixed(1)}s`);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
