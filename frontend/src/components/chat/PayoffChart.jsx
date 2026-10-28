// Interactive profit/loss chart built from the trade's real legs.
// Drag across the chart (or use the sliders) to see what you'd make or lose at any
// price, today or on any date up to expiration.
import React, { useMemo, useRef, useState, useId } from 'react';
import { unitPnl, summarize, money } from '../../lib/payoff';

const W = 340, H = 200, PL = 46, PR = 10, PT = 14, PB = 26;

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'T12:00:00Z');
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function addDays(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export default function PayoffChart({ model, units = 1, ticker, sizeLabel }) {
  const clipId = useId().replace(/:/g, '');
  const svgRef = useRef(null);
  const isOptions = model?.kind === 'options';
  const span = isOptions ? 0.4 : 0.3;
  const lo = model.entry * (1 - span), hi = model.entry * (1 + span);
  const [price, setPrice] = useState(model.entry);
  const [day, setDay] = useState(isOptions ? model.daysToExp : 0);
  const atExpiry = !isOptions || day >= model.daysToExp;

  const summary = useMemo(() => summarize(model), [model]);

  const { curveNow, curveExp, yMin, yMax } = useMemo(() => {
    const n = 90;
    const exp = [], now = [];
    for (let i = 0; i <= n; i++) {
      const S = lo + (hi - lo) * (i / n);
      exp.push([S, unitPnl(model, S, null) * units]);
      if (!atExpiry) now.push([S, unitPnl(model, S, day) * units]);
    }
    const ys = [...exp, ...now].map((p) => p[1]).concat(0);
    let mn = Math.min(...ys), mx = Math.max(...ys);
    const pad = (mx - mn) * 0.12 || Math.abs(mx) * 0.2 || 1;
    return { curveExp: exp, curveNow: now, yMin: mn - pad, yMax: mx + pad };
  }, [model, units, day, atExpiry, lo, hi]);

  const x = (S) => PL + ((S - lo) / (hi - lo)) * (W - PL - PR);
  const y = (v) => PT + ((yMax - v) / (yMax - yMin)) * (H - PT - PB);
  const path = (pts) => pts.map((p, i) => `${i ? 'L' : 'M'}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(' ');
  const active = atExpiry ? curveExp : curveNow;
  const area = `${path(active)} L${x(hi).toFixed(1)},${y(0).toFixed(1)} L${x(lo).toFixed(1)},${y(0).toFixed(1)} Z`;
  const zeroY = y(0);

  const pnlHere = unitPnl(model, price, atExpiry ? null : day) * units;
  const pctMove = (price / model.entry - 1) * 100;

  const onPointer = (e) => {
    const svg = svgRef.current;
    if (!svg) return;
    const r = svg.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    const S = lo + ((Math.min(Math.max(px, PL), W - PR) - PL) / (W - PL - PR)) * (hi - lo);
    setPrice(S);
  };

  const ticks = [lo, model.entry, hi];
  const yTicks = [yMax - (yMax - yMin) * 0.06, 0, yMin + (yMax - yMin) * 0.06];
  const when = atExpiry ? (isOptions ? `on ${fmtDate(model.expiration)}` : 'when you sell') : `on ${addDays(day)}`;

  return (
    <div className="bg-slate-900/70 rounded-xl border border-slate-700 p-3">
      <div className="flex items-baseline justify-between gap-2 mb-1">
        <div className="text-xs text-slate-400">Profit / loss {sizeLabel ? `· ${sizeLabel}` : ''}</div>
        <div className="text-[11px] text-slate-500">Drag the chart</div>
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto touch-none select-none cursor-crosshair"
        role="img"
        aria-label={`Profit and loss chart for ${ticker}`}
        onPointerDown={(e) => { e.currentTarget.setPointerCapture?.(e.pointerId); onPointer(e); }}
        onPointerMove={(e) => { if (e.buttons || e.pointerType !== 'mouse') onPointer(e); }}
      >
        <defs>
          <clipPath id={`${clipId}-up`}><rect x="0" y="0" width={W} height={Math.max(0, zeroY)} /></clipPath>
          <clipPath id={`${clipId}-dn`}><rect x="0" y={zeroY} width={W} height={Math.max(0, H - zeroY)} /></clipPath>
        </defs>

        {yTicks.map((v, i) => (
          <g key={i}>
            <line x1={PL} x2={W - PR} y1={y(v)} y2={y(v)} stroke="#334155" strokeWidth={i === 1 ? 1 : 0.5} strokeDasharray={i === 1 ? '' : '2 3'} />
            <text x={PL - 6} y={y(v) + 3.5} textAnchor="end" fontSize="9.5" fill="#94a3b8">{money(v, { sign: true })}</text>
          </g>
        ))}

        <path d={area} fill="#22c55e" fillOpacity="0.18" clipPath={`url(#${clipId}-up)`} />
        <path d={area} fill="#ef4444" fillOpacity="0.18" clipPath={`url(#${clipId}-dn)`} />
        {!atExpiry && <path d={path(curveExp)} fill="none" stroke="#64748b" strokeWidth="1.2" strokeDasharray="4 3" />}
        <path d={path(active)} fill="none" stroke="#60a5fa" strokeWidth="2.4" strokeLinejoin="round" />

        <line x1={x(model.entry)} x2={x(model.entry)} y1={PT} y2={H - PB} stroke="#94a3b8" strokeWidth="1" strokeDasharray="2 3" />

        {summary?.breakevens?.filter((b) => b > lo && b < hi).map((b, i) => (
          <circle key={i} cx={x(b)} cy={zeroY} r="3.5" fill="#fbbf24" stroke="#0f172a" strokeWidth="1" />
        ))}

        <line x1={x(price)} x2={x(price)} y1={PT} y2={H - PB} stroke="#e2e8f0" strokeWidth="1.2" />
        <circle cx={x(price)} cy={y(pnlHere)} r="5" fill={pnlHere >= 0 ? '#22c55e' : '#ef4444'} stroke="#0f172a" strokeWidth="1.5" />

        {ticks.map((S, i) => (
          <text key={i} x={x(S)} y={H - 8} textAnchor={i === 0 ? 'start' : i === 2 ? 'end' : 'middle'} fontSize="9.5" fill="#94a3b8">
            {i === 1 ? `now $${S.toFixed(2)}` : `$${S.toFixed(0)}`}
          </text>
        ))}
      </svg>

      <div className="mt-2 rounded-lg bg-slate-800/80 px-3 py-2 text-sm" aria-live="polite">
        If <span className="font-semibold text-white">{ticker}</span> is{' '}
        <span className="font-semibold text-white">${price.toFixed(2)}</span>{' '}
        <span className="text-slate-400">({pctMove >= 0 ? '+' : ''}{pctMove.toFixed(0)}%)</span> {when}:{' '}
        <span className={`font-bold ${pnlHere >= 0 ? 'text-green-400' : 'text-red-400'}`}>{money(pnlHere, { sign: true })}</span>
      </div>

      <div className="mt-3 space-y-3">
        <label className="block text-xs text-slate-400">
          <span className="flex justify-between"><span>Price</span><span className="text-slate-300">${price.toFixed(2)}</span></span>
          <input
            type="range" min={lo} max={hi} step={(hi - lo) / 200} value={price}
            onChange={(e) => setPrice(parseFloat(e.target.value))}
            className="w-full accent-blue-500"
            aria-label="Price of the stock"
          />
        </label>
        {isOptions && model.daysToExp > 1 && (
          <label className="block text-xs text-slate-400">
            <span className="flex justify-between">
              <span>Date</span>
              <span className="text-slate-300">{atExpiry ? `Expiration (${fmtDate(model.expiration)})` : `${addDays(day)} · ${model.daysToExp - day} days left`}</span>
            </span>
            <input
              type="range" min={0} max={model.daysToExp} step={1} value={day}
              onChange={(e) => setDay(parseInt(e.target.value, 10))}
              className="w-full accent-blue-500"
              aria-label="Date between today and expiration"
            />
          </label>
        )}
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-400">
        <span className="inline-flex items-center gap-1"><span className="w-3 h-0.5 bg-blue-400 inline-block" />{atExpiry ? 'At expiration' : 'On chosen date'}</span>
        {!atExpiry && <span className="inline-flex items-center gap-1"><span className="w-3 h-0 border-t border-dashed border-slate-500 inline-block" />At expiration</span>}
        {summary?.breakevens?.length > 0 && <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />Breakeven</span>}
        {isOptions && <span>Option prices are estimates</span>}
      </div>
    </div>
  );
}
