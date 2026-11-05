// What to post: picks a content type at random ("scramble"), renders it to a 1080x1920 MP4 and writes the caption.
// Every number in a caption comes from the live API at post time. Nothing is invented.
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const SITE = (process.env.SITE || 'https://marketplayground-web.onrender.com').replace(/\/$/, '');
const API = (process.env.API || 'https://marketplayground-backend-18mm.onrender.com').replace(/\/$/, '');
const W = 1080, H = 1920;
const DISCLAIMER = 'Practice money. Not investment advice.';
const TAGS = ['#stocks', '#investing', '#stockmarket', '#finance', '#markets', '#learninvesting', '#personalfinance',
  '#wallstreet', '#trading', '#news', '#ai', '#fintech'];

const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
const shuffle = (arr) => arr.map((v) => [Math.random(), v]).sort((a, b) => a[0] - b[0]).map((p) => p[1]);
const hashtags = (extra = []) => shuffle([...new Set([...extra, ...shuffle(TAGS).slice(0, 5)])]).join(' ');
const pct = (x) => `${Math.round(x * 100)}%`;
const decode = (s) => String(s || '').replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&').trim();

async function getJSON(p) {
  const r = await fetch(`${API}${p}`, { headers: { 'User-Agent': 'MarketPlayground-social/1.0' } });
  if (!r.ok) throw new Error(`${p}: HTTP ${r.status}`);
  return r.json();
}

// A still page -> a short video with a slow push-in, so it posts as a Reel / TikTok video.
function stillToVideo(png, out, seconds = 8) {
  const frames = seconds * 30;
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-loop', '1', '-i', png,
    '-vf', `scale=${W * 2}:${H * 2},zoompan=z='min(zoom+0.0006,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${frames}:s=${W}x${H}:fps=30,format=yuv420p`,
    '-t', String(seconds), '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-movflags', '+faststart', '-an', out]);
}

async function screenshot(url, png, { scrollTo, wait = 4000 } = {}) {
  const browser = await chromium.launch();
  try {
    // Lay out like a 405px-wide phone and render at full HD (same trick as make_reel.js).
    const ctx = await browser.newContext({ viewport: { width: 405, height: 720 }, deviceScaleFactor: W / 405 });
    await ctx.addInitScript(() => { try { localStorage.setItem('mp_whats_new_seen', '999'); } catch { /* ignore */ } });
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: 'networkidle', timeout: 90000 });
    await page.waitForTimeout(wait);
    if (scrollTo) {
      const el = page.getByText(scrollTo, { exact: false }).first();
      await el.evaluate((n) => n.scrollIntoView({ block: 'start' }));
      await page.evaluate(() => window.scrollBy(0, -40));
      await page.waitForTimeout(800);
    }
    await page.screenshot({ path: png });
  } finally {
    await browser.close();
  }
}

// ---- content types ----

async function storyReel(dir, state) {
  const movers = await getJSON('/v4/movers');
  const items = (movers.items || []).filter((it) => it.hunch && (it.companies || []).length);
  if (!items.length) throw new Error('no stories with companies today');
  const seen = new Set((state.posted || []).map((p) => p.headline));
  const fresh = items.map((it, i) => [it, i]).filter(([it]) => !seen.has(decode(it.headline)));
  if (!fresh.length) throw new Error('every story today was already posted');
  const [it, idx] = pick(fresh.slice(0, 5));
  const out = path.join(dir, 'story.mp4');
  execFileSync('node', [path.join(__dirname, '..', 'make_reel.js'), out, String(idx)],
    { stdio: 'inherit', env: { ...process.env, SITE } });
  const cos = it.companies.slice(0, 4).map((c) => `$${c.ticker} ${c.direction === 'down' ? '↓' : '↑'}`).join(' · ');
  const headline = decode(it.headline);
  const opener = pick([
    'The story behind today\'s move, in 30 seconds.',
    'What this headline could mean for stocks:',
    'Today\'s market story, explained.',
    'One headline, the companies it touches.',
  ]);
  const cta = pick([
    'Got a hunch about the news? Turn it into a practice trade. Link in bio.',
    'Type your own hunch and see which stocks it points to. Link in bio.',
    'Think it\'s overblown? Try the other side with practice money. Link in bio.',
  ]);
  const caption = `${opener}\n\n"${headline}"\n\nWhat it could mean: ${decode(it.hunch).replace(/\.+$/, '')}.\nCompanies it touches: ${cos}\n\n${cta}\n${DISCLAIMER}\n\n${hashtags(it.companies.slice(0, 2).map((c) => `#${c.ticker}`))}`;
  return { type: 'story', video: out, caption, headline };
}

async function scorecard(dir) {
  const brain = await getJSON('/v4/brain');
  const top = brain?.skill?.top;
  if (!top?.n) throw new Error('scorecard not ready');
  const png = path.join(dir, 'scorecard.png');
  await screenshot(`${SITE}/live`, png, { scrollTo: 'scorecard' });
  const out = path.join(dir, 'scorecard.mp4');
  stillToVideo(png, out);
  const opener = pick([
    'Our AI grades itself in public.',
    'We show our AI\'s real track record, good or bad.',
    'No cherry-picking: here is the real scorecard.',
  ]);
  const caption = `${opener}\n\nOf ${top.n.toLocaleString('en-US')} #1 picks (mostly practice calls) graded 90 days later, ${pct(top.beat_rate)} beat the S&P 500. `
    + `Most professional funds trail the S&P over 10 years, so we publish the real number.\n\n`
    + `Watch the brain learn, live: link in bio.\n${DISCLAIMER} Past results don't predict future ones.\n\n${hashtags(['#ai', '#machinelearning'])}`;
  return { type: 'scorecard', video: out, caption, headline: `scorecard ${new Date().toISOString().slice(0, 10)}` };
}

async function pitch(dir) {
  const png = path.join(dir, 'pitch.png');
  await screenshot(`${SITE}/welcome`, png);
  const out = path.join(dir, 'pitch.mp4');
  stillToVideo(png, out, 7);
  const hunch = 'People will travel more next summer'; // the example shown on the welcome screen in the video
  const opener = pick(['Got a hunch? Turn it into a stock trade.', 'What if your gut feeling could pick stocks?', 'Type a hunch. Get the stocks behind it.']);
  const caption = `${opener}\n\nType something like "${hunch}" and get real companies that fit it, with the reasons.\n\n`
    + `Free, with $100,000 of practice money. Link in bio.\n${DISCLAIMER}\n\n${hashtags(['#investingforbeginners'])}`;
  return { type: 'pitch', video: out, caption, headline: `pitch ${new Date().toISOString().slice(0, 10)}` };
}

const TYPES = { story: storyReel, scorecard, pitch };
const WEIGHTS = { story: 3, scorecard: 1, pitch: 1 };

// Scramble: weighted random, never the same type twice in a row; falls back to another type if one can't render.
async function make(dir, state, forced) {
  const order = forced ? [forced] : (() => {
    const pool = Object.keys(TYPES).filter((t) => t !== state.last_type);
    const bag = pool.flatMap((t) => Array(WEIGHTS[t]).fill(t));
    const first = pick(bag);
    return [first, ...shuffle(pool.filter((t) => t !== first))];
  })();
  let lastErr;
  for (const t of order) {
    try { return await TYPES[t](dir, state); } catch (e) { lastErr = e; console.warn(`[content] ${t} skipped: ${e.message}`); }
  }
  throw lastErr || new Error('nothing to post');
}

module.exports = { make, TYPES };
