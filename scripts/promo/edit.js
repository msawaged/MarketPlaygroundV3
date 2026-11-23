// Promo step 2/4: turns the captured footage (capture.js) and the voice lengths into a frame-by-frame edit:
// which footage frame each output frame shows, the camera (zoom + focus), highlight rings, tap ripples, captions,
// plus the sound-effect cues for mix.py.
//   node scripts/promo/edit.js <config.json> <capture_dir> <voice_dir> <out_dir>
// Out: <out_dir>/edit.json {fps, w, h, duration, scenes, frames: [...]}, <out_dir>/cues.json
// Shots are tied to the capture's marks (not fixed times), so a fresh capture lines up by itself.
const fs = require('fs');
const path = require('path');

const [cfgPath, capDir, voDir, outDir] = process.argv.slice(2);
if (!outDir) throw new Error('usage: edit.js <config.json> <capture_dir> <voice_dir> <out_dir>');
const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
const marks = JSON.parse(fs.readFileSync(path.join(capDir, 'marks.json'), 'utf8'));
const frames = JSON.parse(fs.readFileSync(path.join(capDir, 'frames.json'), 'utf8'));
const lens = JSON.parse(fs.readFileSync(path.join(voDir, 'lens.json'), 'utf8'));
const FPS = 30;
const LEAD = 0.25; // voice starts this long after its scene's cut
const TAIL = 0.4; // breathing room after each line

const ev = (n) => { const e = marks.events.find((x) => x.name === n); if (!e) throw new Error(`no mark ${n}`); return e.t; };
const tapT = (n) => marks.taps.find((x) => x.name === n).t;
const card = (i) => marks.cards[i].t;
const scrollAt = (t) => { let y = marks.scrolls[0][1]; for (const [st, sy] of marks.scrolls) if (st <= t) y = sy; return y; };

// shots per scene: [from, to] in capture seconds; cam keys: [sceneFraction, zoom, fx, fy, pageCoords?] in phone CSS px
const plan = {
  hook: { shots: [[ev('news'), tapT('search') + 0.1]], cam: [[0, 1.22, 195, 380], [1, 1.38, 195, 400]] },
  // the search bar's page position is fixed; following the page keeps the sign-up box above it out of shot
  search: {
    shots: [[tapT('search') + 0.05, card(0) + 1.4]],
    cam: (dur, shot) => {
      const story = (card(0) - 0.3 - shot[0]) / (shot[1] - shot[0]);
      return [[0, 1.5, 195, 470, true], [0.12, 1.72, 195, 470, true], [story - 0.02, 1.72, 195, 470, true], [story + 0.06, 1.0, 195, 422], [1, 1.04, 195, 400]];
    },
  },
  learn: {
    shots: [[card(1) + 0.2, card(1) + 1.6], [card(2) + 0.15, card(2) + 1.45], [card(3) + 0.9, card(3) + 2.2]],
    cam: [[0, 1.22, 195, 400], [1, 1.3, 195, 400]],
  },
  who: { shots: [[card(4) + 0.1, card(4) + 3.5]], rings: /^story_indirect/, cam: [[0, 1.0, 195, 422], [0.3, 1.0, 195, 422], [0.55, 1.3, 195, 560], [1, 1.36, 195, 570]] },
  practice: { shots: [[ev('plays') - 2.0, ev('plays') + 3.4]], rings: /^plays$/, cam: [[0, 1.0, 195, 422], [0.4, 1.0, 195, 422], [0.62, 1.3, 195, 290], [1, 1.36, 195, 290]] },
  score: {
    shots: [[ev('brain') + 0.1, ev('brain') + 1.7], [ev('graded') - 0.45, ev('graded') + 1.75], [ev('scorecard') - 0.45, ev('scorecard') + 2.6]],
    rings: /^(graded|scorecard)$/,
    cam: (dur, shots, bounds) => [[0, 1.0, 195, 300], [bounds[1] - 0.001, 1.08, 195, 280], [bounds[1], 1.4, 103, 360], [bounds[2] - 0.001, 1.48, 103, 360], [bounds[2], 1.55, 110, 195], [1, 1.62, 110, 195]],
  },
  end: { shots: [] },
};

// v7 (cfg.plan = "typo"): types a misspelling ("lithum"), the search fixes it, then the same story flow.
// Story cards there: 0 cover, 1 what happened, 2 the numbers, 3 why, 4 twist, 5 who it moves, 6 sources.
const plans = {
  typo: {
    hook: marks.events.some((x) => x.name === 'm0')
      ? { // montage: each search from its last letters to a beat after its results land
        shots: marks.events.filter((x) => /^m\d+$/.test(x.name)).map((x, i) => [x.t - (i ? 0.55 : 0.05), x.t + 1.1]), // first: results already in (cover)
        cam: [[0, 1.5, 195, 545, true], [1, 1.54, 195, 545, true]],
      }
      : { shots: [[ev('news'), tapT('search') + 0.1]], cam: [[0, 1.3, 195, 330], [1, 1.45, 195, 300]] },
    typo: {
      shots: [[(marks.events.find((x) => x.name === 'm0') ? ev('type') - 0.2 : tapT('search') + 0.05), (marks.events.find((x) => x.name === 'fixed') || { t: ev('results') }).t + 2.4]],
      rings: /^fixed$/,
      cam: [[0, 1.6, 195, 455, true], [0.45, 1.64, 195, 458, true], [1, 1.68, 195, 470, true]],
    },
    make: {
      shots: [[tapT('make') - 0.7, card(0) + 1.6]],
      cam: (dur, shot) => {
        const story = (card(0) - 0.3 - shot[0]) / (shot[1] - shot[0]);
        return [[0, 1.5, 195, 478, true], [story - 0.04, 1.55, 195, 478, true], [story + 0.06, 1.0, 195, 422], [1, 1.05, 195, 400]];
      },
    },
    learn: {
      shots: [[card(1) + 0.2, card(1) + 1.6], [card(2) + 0.15, card(2) + 1.6], [card(4) + 0.4, card(4) + 2.0]],
      cam: [[0, 1.2, 195, 400], [1, 1.3, 195, 400]],
    },
    who: { shots: [[card(5) + 0.1, card(5) + 0.9 + (marks.events.find((x) => x.name === 'movers_done') || { t: card(5) + 2.5 }).t - card(5)], [card(6) + 0.1, card(6) + 1.3]],
      rings: /^story_(mover|indirect)/, cam: [[0, 1.0, 195, 422], [0.5, 1.12, 195, 420], [0.5001, 1.0, 195, 422], [1, 1.12, 195, 470]] },
    practice: plan.practice,
    trade: { shots: [] },
    score: plan.score,
    end: { shots: [] },
  },
};
const PLAN = cfg.plan ? plans[cfg.plan] : plan;

const ease = (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);
function camAt(keys, f, srcT) {
  let a = keys[0]; let b = keys[keys.length - 1];
  for (let i = 0; i < keys.length - 1; i++) if (f >= keys[i][0] && f <= keys[i + 1][0]) { a = keys[i]; b = keys[i + 1]; break; }
  const k = b[0] === a[0] ? 1 : ease(Math.min(1, Math.max(0, (f - a[0]) / (b[0] - a[0]))));
  const fix = (key) => (key[4] ? key[3] - scrollAt(srcT) : key[3]);
  return { z: a[1] + (b[1] - a[1]) * k, fx: a[2] + (b[2] - a[2]) * k, fy: fix(a) + (fix(b) - fix(a)) * k };
}
const frameAt = (t) => { let lo = 0; let hi = frames.length - 1; while (lo < hi) { const m = (lo + hi + 1) >> 1; if (frames[m].t <= t) lo = m; else hi = m - 1; } return frames[lo].f; };

const scenes = []; const out = []; const cues = { voice: [], sfx: [] };
let t = 0;
cfg.scenes.forEach((sc, i) => {
  const p = PLAN[sc.id];
  const dur = sc.end ? lens[i] + 1.6 : lens[i] + LEAD + TAIL;
  scenes.push({ ...sc, start: +t.toFixed(3), dur: +dur.toFixed(3) });
  cues.voice.push({ i, t: +(t + LEAD + (sc.end ? 0.5 : 0)).toFixed(3) });
  if (i > 0) cues.sfx.push({ kind: sc.end ? 'impact' : 'whoosh', t: +t.toFixed(3) });
  if (sc.end) cues.sfx.push({ kind: 'riser', t: +(t - 1.2).toFixed(3) });
  // split the scene across its shots in proportion to their length
  const total = p.shots.reduce((s, [a, b]) => s + (b - a), 0);
  const bounds = []; let acc = 0;
  for (const [a, b] of p.shots) { bounds.push(acc / total); acc += b - a; }
  const keys = typeof p.cam === 'function' ? p.cam(dur, p.shots[0], bounds) : p.cam;
  const seenRing = {};
  const n = Math.round(dur * FPS);
  for (let k = 0; k < n; k++) {
    const ot = t + k / FPS; const f = k / n;
    const fr = { t: +ot.toFixed(3), scene: i, local: +(k / FPS).toFixed(3) };
    if (p.shots.length) {
      let si = bounds.length - 1; while (si > 0 && f < bounds[si]) si--;
      const [a, b] = p.shots[si];
      const shotF = (f - bounds[si]) / ((si + 1 < bounds.length ? bounds[si + 1] : 1) - bounds[si]);
      const src = a + (b - a) * shotF;
      fr.src = frameAt(src); fr.shot = si;
      fr.shotAge = +(shotF * (b - a) / total * dur).toFixed(3);
      fr.cam = camAt(keys, f, src);
      fr.rings = [];
      if (p.rings) for (const r of marks.rings) {
        if (!p.rings.test(r.name) || r.t > src || r.t < a - 0.05) continue;
        if (seenRing[r.name] === undefined) { seenRing[r.name] = ot; cues.sfx.push({ kind: 'ding', t: +ot.toFixed(3) }); }
        fr.rings.push({ x: r.x, y: r.y, w: r.w, h: r.h, age: +(ot - seenRing[r.name]).toFixed(3) });
      }
      fr.taps = marks.taps.filter((tp) => src >= tp.t && src - tp.t < 0.55 && tp.t >= a).map((tp) => ({ x: tp.x, y: tp.y, age: +(src - tp.t).toFixed(3) }));
    }
    if (cfg.fullPhone && fr.cam) fr.cam = { z: 1, fx: 195, fy: 0, full: true };
    out.push(fr);
  }
  for (const tp of marks.taps) for (const [si, [a, b]] of p.shots.entries()) {
    if (tp.t >= a && tp.t < b) cues.sfx.push({ kind: 'tap', t: +(t + (bounds[si] + (tp.t - a) / total) * dur).toFixed(3) });
  }
  t += dur;
});

fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, 'edit.json'), JSON.stringify({ fps: FPS, w: 1080, h: 1920, duration: +t.toFixed(3), capDir: path.resolve(capDir), scenes, frames: out }));
fs.writeFileSync(path.join(outDir, 'cues.json'), JSON.stringify({ duration: +t.toFixed(3), ...cues }, null, 1));
console.log(`${out.length} frames, ${t.toFixed(2)}s`);
