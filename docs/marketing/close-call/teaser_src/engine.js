// Deterministic scene player: window.seek(t) draws the frame at t seconds. Scene timings come from window.TIMES
// ([{start, dur}] per .scene). Elements animate from data attributes, relative to their scene's start.
const ease = (x) => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3);
const fmt = (v, f) => f === 'usd' ? '$' + Math.round(v).toLocaleString('en-US')
  : f === 'pct' ? Math.round(v) + '%' : Math.round(v).toLocaleString('en-US');
window.seek = (t) => {
  const scenes = [...document.querySelectorAll('.scene')];
  scenes.forEach((s, i) => {
    const { start, dur } = window.TIMES[i];
    const lt = t - start;
    const last = i === scenes.length - 1;
    let o = lt < 0 || lt > dur ? 0 : Math.min(1, lt / 0.25) * (last ? 1 : Math.min(1, (dur - lt) / 0.2));
    s.style.opacity = o;
    s.style.transform = `scale(${1 + 0.015 * Math.min(1, Math.max(0, lt) / dur)})`; // slow push-in
    if (o === 0) return;
    s.querySelectorAll('[data-in]').forEach((e) => {
      const p = ease((lt - parseFloat(e.dataset.in)) / 0.45);
      e.style.opacity = p;
      e.style.transform = `translateY(${(1 - p) * 18}px)` + (e.dataset.pop ? ` scale(${0.85 + 0.15 * p})` : '');
    });
    s.querySelectorAll('[data-count]').forEach((e) => {
      const p = ease((lt - parseFloat(e.dataset.at || 0)) / parseFloat(e.dataset.dur || 1.2));
      const a = parseFloat(e.dataset.from || 0), b = parseFloat(e.dataset.count);
      e.textContent = fmt(a + (b - a) * p, e.dataset.fmt);
    });
    s.querySelectorAll('[data-bar]').forEach((e) => {
      const p = ease((lt - parseFloat(e.dataset.at || 0)) / parseFloat(e.dataset.dur || 1.2));
      e.style.width = `${parseFloat(e.dataset.bar) * 100 * p}%`;
    });
    s.querySelectorAll('[data-draw]').forEach((e) => {
      const L = e.getTotalLength();
      const p = ease((lt - parseFloat(e.dataset.at || 0)) / parseFloat(e.dataset.dur || 1.5));
      e.style.strokeDasharray = L; e.style.strokeDashoffset = L * (1 - p);
    });
    s.querySelectorAll('[data-type]').forEach((e) => { // typewriter
      const full = e.dataset.type, p = Math.max(0, Math.min(1, (lt - parseFloat(e.dataset.at || 0)) / parseFloat(e.dataset.dur || 1.5)));
      e.textContent = full.slice(0, Math.round(full.length * p));
    });
  });
};
