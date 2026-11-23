// Promo step 3/4: renders edit.json frame by frame on stage.html (phone frame on a branded stage, camera moves,
// rings, taps, kinetic captions, end card) and encodes a silent 1080x1920 30fps H.264 video.
//   node scripts/promo/render.js <edit_dir> <out.mp4> [--only=start-end seconds, for quick checks]
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('playwright');

const [editDir, outFile, only] = process.argv.slice(2);
if (!outFile) throw new Error('usage: render.js <edit_dir> <out.mp4>');
const edit = JSON.parse(fs.readFileSync(path.join(editDir, 'edit.json'), 'utf8'));
let frames = edit.frames;
if (only) { const [a, b] = only.replace('--only=', '').split('-').map(Number); frames = frames.filter((f) => f.t >= a && f.t < b); }

(async () => {
  const browser = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage({ viewport: { width: edit.w, height: edit.h }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.join(__dirname, 'stage.html'));
  await page.evaluate(([s, d]) => window.setup(s, d), [edit.scenes, edit.capDir]);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(edit.fps), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', String(edit.fps), outFile], { stdio: ['pipe', 'inherit', 'inherit'] });
  const started = Date.now();
  for (let i = 0; i < frames.length; i++) {
    await page.evaluate((f) => window.show(f), frames[i]);
    const buf = await page.screenshot({ type: 'jpeg', quality: 93 });
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % 150 === 0) console.log(`frame ${i}/${frames.length} (${((Date.now() - started) / 1000).toFixed(0)}s)`);
  }
  ff.stdin.end();
  await new Promise((r, j) => ff.on('close', (c) => (c === 0 ? r() : j(new Error('ffmpeg failed')))));
  await browser.close();
  console.log(outFile);
})().catch((e) => { console.error(e); process.exit(1); });
