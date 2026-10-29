// Draws a shareable image (1080x1350, made for Instagram/TikTok) and shares or downloads it.
const W = 1080, H = 1350;
const FONT = '"Plus Jakarta Sans", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif';

function wrap(ctx, text, maxWidth) {
  const words = String(text).split(/\s+/);
  const lines = [];
  let line = '';
  for (const w of words) {
    const t = line ? `${line} ${w}` : w;
    if (ctx.measureText(t).width > maxWidth && line) { lines.push(line); line = w; } else line = t;
  }
  if (line) lines.push(line);
  return lines;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

/**
 * card = { kicker, belief, headline, picks: [{ticker, label, value, good}], footnote }
 * Returns a PNG Blob.
 */
export async function drawCard(card) {
  try { await document.fonts?.ready; } catch { /* ignore */ }
  const c = document.createElement('canvas');
  c.width = W; c.height = H;
  const ctx = c.getContext('2d');

  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, '#0b1a3a'); bg.addColorStop(0.55, '#020617'); bg.addColorStop(1, '#0b1224');
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  const glow = ctx.createRadialGradient(W * 0.85, 80, 10, W * 0.85, 80, 700);
  glow.addColorStop(0, 'rgba(77,163,255,0.35)'); glow.addColorStop(1, 'rgba(77,163,255,0)');
  ctx.fillStyle = glow; ctx.fillRect(0, 0, W, H);

  // brand
  // the swing-M mark (white tile, blue M whose middle is a swing seat)
  ctx.fillStyle = '#fff'; roundRect(ctx, 80, 80, 88, 88, 22); ctx.fill();
  ctx.save(); ctx.translate(80, 80); ctx.scale(88 / 120, 88 / 120);
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.strokeStyle = '#bfdbfe'; ctx.lineWidth = 5;
  ctx.beginPath(); ctx.arc(60, 26, 48, Math.PI * 0.778, Math.PI * 0.222, true); ctx.stroke();
  ctx.strokeStyle = 'rgba(37,99,235,0.25)'; ctx.lineWidth = 10;
  ctx.beginPath(); ctx.moveTo(26, 30); ctx.lineTo(60, 74); ctx.lineTo(94, 30); ctx.stroke();
  ctx.strokeStyle = '#2563eb';
  ctx.beginPath(); ctx.moveTo(26, 92); ctx.lineTo(26, 30); ctx.lineTo(72, 72.5); ctx.lineTo(94, 30); ctx.lineTo(94, 92); ctx.stroke();
  ctx.fillStyle = '#2563eb'; ctx.beginPath(); ctx.arc(72, 72.5, 12, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
  ctx.fillStyle = '#fff';
  ctx.textAlign = 'left'; ctx.font = `700 38px ${FONT}`; ctx.fillText('MarketPlayground', 190, 136);

  // kicker + belief
  let yy = 290;
  ctx.fillStyle = '#93c5fd'; ctx.font = `700 34px ${FONT}`; ctx.fillText((card.kicker || 'MY BELIEF').toUpperCase(), 80, yy);
  yy += 30;
  ctx.fillStyle = '#fff'; ctx.font = `800 72px ${FONT}`;
  const lines = wrap(ctx, `“${card.belief}”`, W - 160).slice(0, 4);
  for (const l of lines) { yy += 88; ctx.fillText(l, 80, yy); }

  // headline result
  yy += 90;
  if (card.headline) {
    ctx.font = `700 46px ${FONT}`; ctx.fillStyle = card.good === false ? '#fca5a5' : '#86efac';
    for (const l of wrap(ctx, card.headline, W - 160).slice(0, 2)) { ctx.fillText(l, 80, yy); yy += 60; }
    yy += 10;
  }

  // picks
  const picks = (card.picks || []).slice(0, 3);
  const gap = 28, bw = (W - 160 - gap * (picks.length - 1)) / Math.max(1, picks.length), bh = 230;
  picks.forEach((p, i) => {
    const x = 80 + i * (bw + gap);
    ctx.fillStyle = p.good == null ? 'rgba(30,41,59,0.85)' : p.good ? 'rgba(34,197,94,0.14)' : 'rgba(239,68,68,0.14)';
    roundRect(ctx, x, yy, bw, bh, 32); ctx.fill();
    ctx.strokeStyle = p.good == null ? '#334155' : p.good ? 'rgba(34,197,94,0.5)' : 'rgba(239,68,68,0.5)';
    ctx.lineWidth = 3; ctx.stroke();
    ctx.fillStyle = '#fff'; ctx.font = `800 56px ${FONT}`; ctx.fillText(p.ticker, x + 32, yy + 82);
    ctx.fillStyle = '#94a3b8'; ctx.font = `500 28px ${FONT}`; ctx.fillText(String(p.label || '').slice(0, 18), x + 32, yy + 126);
    ctx.fillStyle = p.good == null ? '#e2e8f0' : p.good ? '#86efac' : '#fca5a5';
    ctx.font = `800 54px ${FONT}`; ctx.fillText(p.value || '', x + 32, yy + 196);
  });

  // footer
  ctx.fillStyle = '#4DA3FF'; ctx.font = `800 40px ${FONT}`; ctx.fillText('Your hunch. Real stocks.', 80, H - 150);
  ctx.fillStyle = '#94a3b8'; ctx.font = `500 30px ${FONT}`;
  ctx.fillText(`What do you believe? Try yours free: ${card.url || window.location.host}`, 80, H - 100);
  ctx.fillStyle = '#64748b'; ctx.font = `500 24px ${FONT}`;
  ctx.fillText(card.footnote || 'For education, not investment advice. Past results don’t predict future ones.', 80, H - 56);

  return new Promise((res) => c.toBlob(res, 'image/png'));
}

/** Share the image where the phone supports it; otherwise download it. Returns 'shared' | 'downloaded'. */
export async function shareCard(card, text) {
  const blob = await drawCard(card);
  const file = new File([blob], 'marketplayground.png', { type: 'image/png' });
  if (navigator.canShare?.({ files: [file] })) {
    try { await navigator.share({ files: [file], text }); return 'shared'; } catch { return 'cancelled'; }
  }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'marketplayground.png';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  return 'downloaded';
}
