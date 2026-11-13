#!/usr/bin/env node
// MarketPlayground social bot: makes one post (scrambled content type) and publishes it to Instagram and TikTok.
//
//   node scripts/social/post.js              # dry run unless config.live is true: renders + prints, posts nothing
//   node scripts/social/post.js --type story # force a type: story | scorecard | pitch
//   node scripts/social/post.js --dry-run    # never posts, even if live
//
// Queue (2026-11-13): a folder in scripts/social/queue/<id>/ with video.mp4 + caption.txt is posted before any
// auto-made post, oldest id first, once each (state.queue_done). The bot pulls the repo first so new queue items
// arrive without anyone touching the Mac. Murad approves what goes in the queue; the CTO session adds it.
//
// Config and state live in ~/.mp_social/ (never in the repo): config.json holds the tokens, state.json what was posted.
const fs = require('fs');
const os = require('os');
const path = require('path');
const { make } = require('./content');
const { igRefresh, igPostReel, ttRefresh, ttPostVideo } = require('./platforms');

const HOME = process.env.MP_SOCIAL_HOME || path.join(os.homedir(), '.mp_social');
const CONFIG = path.join(HOME, 'config.json');
const STATE = path.join(HOME, 'state.json');
const args = process.argv.slice(2);
const flag = (n) => args.includes(n);
const opt = (n) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : null; };

const read = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return d; } };
const write = (f, v) => { fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, JSON.stringify(v, null, 2), { mode: 0o600 }); };

(async () => {
  const cfg = read(CONFIG, { live: false, instagram: { enabled: false }, tiktok: { enabled: false } });
  const state = read(STATE, { posted: [] });
  const live = cfg.live === true && !flag('--dry-run');

  const day = new Date().toISOString().slice(0, 10);
  const today = (state.posted || []).filter((p) => p.at.startsWith(day)).length;
  if (live && today >= (cfg.max_per_day || 2)) { console.log(`Already posted ${today} today; skipping.`); return; }

  try {  // pick up newly approved queue items
    require('child_process').execSync('git pull --ff-only -q', { cwd: path.join(__dirname, '..', '..'), stdio: 'ignore', timeout: 60000 });
  } catch { /* offline or local changes: use what's here */ }
  const outDir = path.join(HOME, 'out', new Date().toISOString().replace(/[:.]/g, '-'));
  fs.mkdirSync(outDir, { recursive: true });
  const qdir = path.join(__dirname, 'queue');
  const done = new Set(state.queue_done || []);
  const qid = opt('--type') ? null : (fs.existsSync(qdir) ? fs.readdirSync(qdir).sort() : [])
    .find((d) => !done.has(d) && fs.existsSync(path.join(qdir, d, 'video.mp4')) && fs.existsSync(path.join(qdir, d, 'caption.txt')));
  const post = qid
    ? { type: 'queued', video: path.join(qdir, qid, 'video.mp4'), caption: fs.readFileSync(path.join(qdir, qid, 'caption.txt'), 'utf8').trim(), headline: qid }
    : await make(outDir, state, opt('--type'));
  fs.writeFileSync(path.join(outDir, 'caption.txt'), post.caption);
  console.log(`\n[${post.type}] ${post.video}\n---\n${post.caption}\n---`);

  if (!live) { console.log('Dry run: nothing posted. Set "live": true in ~/.mp_social/config.json to publish.'); return; }

  const rec = { at: new Date().toISOString(), type: post.type, headline: post.headline };
  if (cfg.instagram?.enabled) {
    try {
      if (await igRefresh(cfg.instagram)) write(CONFIG, cfg);
      rec.instagram = await igPostReel(cfg.instagram, post.video, post.caption);
      console.log(`Instagram: posted ${rec.instagram}`);
    } catch (e) { rec.instagram_error = e.message; console.error(`Instagram failed: ${e.message}`); }
  }
  if (cfg.tiktok?.enabled) {
    try {
      await ttRefresh(cfg.tiktok); write(CONFIG, cfg);
      rec.tiktok = await ttPostVideo(cfg.tiktok, post.video, post.caption);
      console.log(`TikTok: posted ${rec.tiktok}`);
    } catch (e) { rec.tiktok_error = e.message; console.error(`TikTok failed: ${e.message}`); }
  }
  if (qid && (rec.instagram || rec.tiktok)) state.queue_done = [...done, qid];
  if (!qid) state.last_type = post.type;
  state.posted = [...(state.posted || []), rec].slice(-200);
  write(STATE, state);
  if (rec.instagram_error && rec.tiktok_error) process.exit(1);
})().catch((e) => { console.error(e); process.exit(1); });
