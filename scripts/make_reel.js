// Records one of today's news stories (Story mode) as a 1080x1920 vertical reel, ready for Instagram / TikTok.
//
//   node scripts/make_reel.js [out.mp4] [storyIndex=0]
//   SITE=https://marketplayground-web.onrender.com (default)  CARD_MS=4200
//
// Needs Playwright + Chromium and ffmpeg. The page /reel?i=N plays the story hands-free and sets
// window.__reelStart when the first card appears and window.__reelDone after the last one.
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const SITE = (process.env.SITE || 'https://marketplayground-web.onrender.com').replace(/\/$/, '');
const OUT = path.resolve(process.argv[2] || 'market_open_reel.mp4');
const IDX = parseInt(process.argv[3] || '0', 10) || 0;
const CARD_MS = parseInt(process.env.CARD_MS || '4200', 10);
const W = 1080, H = 1920, ZOOM = W / 405; // lay the page out like a 405px-wide phone, render at full HD

(async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'reel-'));
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, recordVideo: { dir, size: { width: W, height: H } } });
  await ctx.addInitScript((z) => {
    document.addEventListener('DOMContentLoaded', () => { document.documentElement.style.zoom = String(z); });
  }, ZOOM);
  const page = await ctx.newPage();
  const t0 = Date.now();
  await page.goto(`${SITE}/reel?i=${IDX}&ms=${CARD_MS}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForFunction(() => window.__reelStart, null, { timeout: 90000 });
  const start = (Date.now() - t0) / 1000;
  await page.waitForFunction(() => window.__reelDone, null, { timeout: 120000, polling: 100 });
  await page.waitForTimeout(400);
  const video = page.video();
  await ctx.close();
  await browser.close();
  const raw = await video.path();
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-ss', String(Math.max(0, start - 0.15)), '-i', raw,
    '-vf', `scale=${W}:${H},fps=30,format=yuv420p`, '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
    '-movflags', '+faststart', '-an', OUT]);
  fs.rmSync(dir, { recursive: true, force: true });
  console.log(OUT);
})().catch((e) => { console.error(e); process.exit(1); });
