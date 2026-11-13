// node render.js <dir> <out.mp4> [stillsOnly]
// Scene i lasts LEAD + voice_i + GAP; the voice starts LEAD into its scene. Last scene holds HOLD more seconds.
const { chromium } = require('playwright');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs'), path = require('path');
const dir = path.resolve(process.argv[2]), out = path.resolve(process.argv[3]), stills = process.argv[4] === 'stills';
const FPS = 30, LEAD = 0.25, GAP = 0.45, HOLD = 2.2;
const n = JSON.parse(fs.readFileSync(path.join(dir, 'lines.json'))).length;
const lens = [...Array(n).keys()].map((i) => parseFloat(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path.join(dir, `v${i}.wav`)]).toString()));
let t = 0;
const TIMES = lens.map((l, i) => { const s = { start: t, dur: LEAD + l + GAP + (i === n - 1 ? HOLD : 0) }; t += s.dur; return s; });
const TOTAL = t;
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 405, height: 720 }, deviceScaleFactor: 1080 / 405 });
  await pg.goto('file://' + path.join(dir, 'index.html'));
  await pg.evaluate((T) => { window.TIMES = T; }, TIMES);
  await pg.evaluate(() => document.fonts.ready);
  if (stills) {
    for (let i = 0; i < n; i++) {
      await pg.evaluate((x) => window.seek(x), TIMES[i].start + TIMES[i].dur - 0.3 - (i === n - 1 ? 0 : 0));
      await pg.screenshot({ path: path.join(dir, `still${i}.png`) });
    }
    await b.close(); console.log(JSON.stringify(TIMES)); return;
  }
  const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
    ...lens.flatMap((_, i) => ['-i', path.join(dir, `v${i}.wav`)]),
    '-filter_complex', lens.map((_, i) => `[${i + 1}:a]adelay=${Math.round((TIMES[i].start + LEAD) * 1000)}:all=1[a${i}]`).join(';')
      + ';' + lens.map((_, i) => `[a${i}]`).join('') + `amix=inputs=${n}:normalize=0,apad[a]`,
    '-map', '0:v', '-map', '[a]', '-t', TOTAL.toFixed(2), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium',
    '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const frames = Math.ceil(TOTAL * FPS);
  for (let f = 0; f < frames; f++) {
    await pg.evaluate((x) => window.seek(x), f / FPS);
    const buf = await pg.screenshot({ type: 'jpeg', quality: 92 });
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
  await b.close();
  console.log('done', out, TOTAL.toFixed(1) + 's');
})();
