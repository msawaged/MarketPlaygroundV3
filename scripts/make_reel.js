// Records one of today's news stories (Story mode) as a 1080x1920 vertical reel, ready for Instagram / TikTok.
//
//   node scripts/make_reel.js [out.mp4] [storyIndex=0]
//   SITE=https://marketplayground-web.onrender.com (default)  CARD_MS=4200  LEAD_IN=0.3
//
// Needs Playwright + Chromium and ffmpeg. The page /reel?i=N plays the story hands-free and sets
// window.__reelStart when the first card appears and window.__reelDone after the last one
// (or window.__reelError when there's no story to play, so this fails fast instead of timing out).
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const SITE = (process.env.SITE || 'https://marketplayground-web.onrender.com').replace(/\/$/, '');
const OUT = path.resolve(process.argv[2] || 'market_open_reel.mp4');
const IDX = parseInt(process.argv[3] || '0', 10) || 0;
const CARD_MS = parseInt(process.env.CARD_MS || '4200', 10);
const LEAD_IN = parseFloat(process.env.LEAD_IN || '0.3'); // seconds past the first card's appearance
const W = 1080, H = 1920, ZOOM = W / 405; // lay the page out like a 405px-wide phone, render at full HD

(async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'reel-'));
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, recordVideo: { dir, size: { width: W, height: H } } });
  await ctx.addInitScript((z) => {
    document.addEventListener('DOMContentLoaded', () => { document.documentElement.style.zoom = String(z); });
  }, ZOOM);
  const t0 = Date.now(); // the video starts when the page is created, so measure from just before that
  const page = await ctx.newPage();
  await page.goto(`${SITE}/reel?i=${IDX}&ms=${CARD_MS}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForFunction(() => window.__reelStart || window.__reelError, null, { timeout: 90000 });
  const err = await page.evaluate(() => window.__reelError || '');
  if (err) throw new Error(`Story ${IDX} didn't load: ${err}`);
  // When the first card appeared, on the page's own clock, converted to seconds into the video.
  // A little extra skips the card's fade-in, so frame one is the hook, not "Writing the story..." or a blank.
  const shownAt = await page.evaluate(() => performance.timeOrigin + window.__reelStart);
  const start = Math.max(0, (shownAt - t0) / 1000 + LEAD_IN);
  await page.waitForFunction(() => window.__reelDone, null, { timeout: 120000, polling: 100 });
  await page.waitForTimeout(400);
  const video = page.video();
  await ctx.close();
  await browser.close();
  const raw = await video.path();
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-ss', start.toFixed(3), '-i', raw,
    '-vf', `scale=${W}:${H},fps=30,format=yuv420p`, '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
    '-movflags', '+faststart', '-an', OUT]);
  fs.rmSync(dir, { recursive: true, force: true });
  console.log(OUT);
})().catch((e) => { console.error(e); process.exit(1); });
