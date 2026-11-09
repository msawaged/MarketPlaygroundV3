// Records one of today's news stories (Story mode) as a 1080x1920 vertical reel with a voiceover, ready for Instagram / TikTok.
//
//   node scripts/make_reel.js [out.mp4] [storyIndex=0]
//   SITE=https://marketplayground-web.onrender.com (default)  API=https://marketplayground-backend-18mm.onrender.com (default)
//   VOICE=1 (default; 0 = silent reel, every card CARD_MS long)  VOICE_NAME=am_michael  CARD_MS=4200  LEAD_IN=0.3
//   LIVE=1 once the app is public (last card says "Make your call free"; before that it says "coming soon")
//   STORY_JSON=path.json  one-off: record a story you wrote yourself ({story, item} like /v4/movers/story returns)
//
// Needs Playwright + Chromium and ffmpeg; the voice needs python with kokoro-onnx + soundfile (scripts/reel_voice.py).
// The page /reel?h=...&d=... plays the story hands-free, each card as long as its voice line, and sets
// window.__reelStart / __reelMarks[i] (when each card appeared) / __reelDone (or __reelError), which this
// uses to trim the start and drop each voice line in at its card.
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const SITE = (process.env.SITE || 'https://marketplayground-web.onrender.com').replace(/\/$/, '');
const API = (process.env.API || 'https://marketplayground-backend-18mm.onrender.com').replace(/\/$/, '');
const OUT = path.resolve(process.argv[2] || 'market_open_reel.mp4');
const IDX = parseInt(process.argv[3] || '0', 10) || 0;
const CARD_MS = parseInt(process.env.CARD_MS || '4200', 10);
const LEAD_IN = parseFloat(process.env.LEAD_IN || '0.3'); // seconds past the first card's appearance
const VOICE = process.env.VOICE !== '0';
const LIVE = process.env.LIVE === '1';
const VOICE_LEAD = 0.25, VOICE_TAIL = 0.35, LAST_HOLD = 1.2; // seconds around each line
const W = 1080, H = 1920, ZOOM = W / 405; // lay the page out like a 405px-wide phone, render at full HD

async function getJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} -> ${r.status} ${(await r.text()).slice(0, 200)}`);
  return r.json();
}

// "NVDA" -> "N V D A" so the voice reads tickers letter by letter
const spell = (t) => String(t).replace(/[^A-Z]/g, '').split('').join(' ');
const decode = (t) => String(t || '').replace(/&#39;|&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&');

// One line per card, in StoryViewer's order: hook, what happened, why, twist, [who it moves], your call.
function voiceLines({ story: s, item }) {
  const lines = [
    `${s.hook_big}. ${s.hook_line}`,
    s.happened,
    `Why it matters: ${s.why}`,
    `But here's the twist. ${s.twist}`,
  ];
  const cos = item.companies || [];
  if (cos.length === 1 && cos[0].change != null) {
    const c = cos[0], pct = Math.abs(c.change * 100);
    lines.push(`${spell(c.ticker)} is ${c.change >= 0 ? 'up' : 'down'} ${pct < 1 ? pct.toFixed(1) : Math.round(pct)} percent today.`);
  } else if (cos.length) {
    const t = cos.slice(0, 4).map((c) => spell(c.ticker));
    lines.push(`Stocks it moves: ${t.length > 1 ? `${t.slice(0, -1).join(', ')} and ${t[t.length - 1]}` : t[0]}.`);
  }
  const hunch = decode(item.hunch).replace(/\.+$/, '');
  lines.push(`${hunch}. Believe it or doubt it? ${LIVE ? 'Make your call free, link in bio.' : 'MarketPlayground is coming soon. Follow for launch day.'}`);
  return lines.map(decode);
}

(async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'reel-'));
  // 1. the story, fetched here so the voice and the cards say exactly the same thing
  let data;
  if (process.env.STORY_JSON) data = JSON.parse(fs.readFileSync(process.env.STORY_JSON, 'utf8'));
  else {
    const it = ((await getJson(`${API}/v4/movers`)).items || [])[IDX];
    if (!it) throw new Error(`Story ${IDX} didn't load: no story at that index`);
    data = await getJson(`${API}/v4/movers/story?h=${encodeURIComponent(it.headline)}`);
  }
  const headline = data.item.headline;

  // 2. the voiceover, one clip per card; each card stays up as long as its line
  let lens = null, durs = null;
  if (VOICE) {
    const lines = voiceLines(data);
    fs.writeFileSync(path.join(dir, 'lines.json'), JSON.stringify(lines));
    const py = process.env.PYTHON || 'python3';
    lens = JSON.parse(execFileSync(py, [path.join(__dirname, 'reel_voice.py'), path.join(dir, 'lines.json'), dir,
      process.env.VOICE_NAME || 'am_michael'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'inherit'] }).trim().split('\n').pop());
    durs = lens.map((v, i) => Math.round((v + VOICE_LEAD + VOICE_TAIL + (i === lens.length - 1 ? LAST_HOLD : 0)) * 1000));
  }

  // 3. record the page playing the story
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, recordVideo: { dir, size: { width: W, height: H } } });
  await ctx.addInitScript((z) => {
    document.addEventListener('DOMContentLoaded', () => { document.documentElement.style.zoom = String(z); });
  }, ZOOM);
  const body = JSON.stringify(data);
  await ctx.route('**/v4/movers/story**', (r) => r.fulfill({ status: 200, contentType: 'application/json', body }));
  const t0 = Date.now(); // the video starts when the page is created, so measure from just before that
  const page = await ctx.newPage();
  const q = new URLSearchParams({ h: headline, ms: String(CARD_MS) });
  if (durs) q.set('d', durs.join(','));
  if (LIVE) q.set('live', '1');
  await page.goto(`${SITE}/reel?${q}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForFunction(() => window.__reelStart || window.__reelError, null, { timeout: 90000 });
  const err = await page.evaluate(() => window.__reelError || '');
  if (err) throw new Error(`Story ${IDX} didn't load: ${err}`);
  await page.waitForFunction(() => window.__reelDone, null, { timeout: 180000, polling: 100 });
  await page.waitForTimeout(300);
  // When each card appeared, on the page's own clock. An older deployed page has no __reelMarks:
  // then the voice can't be lined up, so fail rather than ship a reel that's out of sync.
  const marks = await page.evaluate(() => (window.__reelMarks || []).map((m) => performance.timeOrigin + m));
  const end = await page.evaluate(() => performance.timeOrigin + performance.now());
  const video = page.video();
  await ctx.close();
  await browser.close();
  const raw = await video.path();
  if (!marks.length) throw new Error('The page gave no card timings (is the site deployed with per-card durations?)');
  if (VOICE && marks.length !== lens.length) throw new Error(`The page showed ${marks.length} cards but there are ${lens.length} voice lines`);

  // 4. trim (skip the first card's fade-in, so frame one is the hook, not "Writing the story..."), mix the voice in
  const sec = (t) => (t - t0) / 1000;
  const start = Math.max(0, sec(marks[0]) + LEAD_IN);
  const len = sec(end) - start - 0.2;
  const args = ['-v', 'error', '-y', '-ss', start.toFixed(3), '-i', raw];
  const enc = ['-t', len.toFixed(3), '-vf', `scale=${W}:${H},fps=30,format=yuv420p`, '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-movflags', '+faststart'];
  if (VOICE) {
    lens.forEach((_, i) => args.push('-i', path.join(dir, `v${i}.wav`)));
    const f = lens.map((_, i) => {
      const ms = Math.max(0, Math.round((sec(marks[i]) - start + VOICE_LEAD) * 1000));
      return `[${i + 1}:a]adelay=${ms}|${ms}[a${i}]`;
    });
    f.push(`${lens.map((_, i) => `[a${i}]`).join('')}amix=inputs=${lens.length}:normalize=0,loudnorm=I=-14:TP=-1.5,aresample=48000[a]`);
    args.push('-filter_complex', f.join(';'), '-map', '0:v', '-map', '[a]', ...enc, '-c:a', 'aac', '-b:a', '192k', OUT);
  } else {
    args.push(...enc, '-an', OUT);
  }
  execFileSync('ffmpeg', args);
  fs.rmSync(dir, { recursive: true, force: true });
  console.log(OUT);
})().catch((e) => { console.error(e); process.exit(1); });
