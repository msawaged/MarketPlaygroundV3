// "How sure are you?": one tap to say how likely you think your own call is to play out. Scored later against what
// happened (My beliefs shows how well-calibrated you are once enough calls are graded). Not advice; nothing trades.
import React, { useEffect, useState } from 'react';
import { getBaseRates, saveUserProb } from '../../lib/api';
import Term from '../ui/Term';

export const SURE_CHOICES = [0.55, 0.65, 0.75, 0.9];
const CHECKPOINTS = [7, 30, 90, 180, 365];

// Same rule as backend calibration.checkpoint_for: the first graded checkpoint at or after the call's horizon.
export function checkpointFor(horizonDays) {
  const h = Number(horizonDays) || 0;
  return CHECKPOINTS.find((c) => c >= h) || 365;
}

// When the call's window falls between checks ("~4 months" is graded at 180 days), say why the check is later.
export function checkNote(horizonDays, cp) {
  const h = Number(horizonDays) || 0;
  if (!h || cp <= h) return '';
  const w = h >= 60 ? `~${Math.round(h / 30)}-month` : `${h}-day`;
  return `, the first one after your ${w} window`;
}

export function sureGoal(direction) {
  if (direction === 'bearish') return 'does worse than the S&P 500';
  if (direction === 'volatile') return 'moves more than the S&P 500';
  return 'beats the S&P 500';
}

function monthYear(iso) {
  const d = new Date(`${String(iso).slice(0, 10)}T12:00:00Z`);
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' });
}

// "The outside view": how often graded calls of the same direction came true at the same check (backend baserate.py).
// The past record, shown before the user picks; no default, no nudge.
export function useBaseRate(direction, cp) {
  const [cell, setCell] = useState(null);
  useEffect(() => {
    let live = true;
    getBaseRates().then((t) => { if (live) setCell(t?.cells?.[direction]?.[String(cp)] || null); }).catch(() => {});
    return () => { live = false; };
  }, [direction, cp]);
  return cell;
}

function pastGoal(direction) {
  if (direction === 'bearish') return 'did worse than the S&P 500';
  if (direction === 'volatile') return 'moved more than the S&P 500';
  return 'beat the S&P 500';
}

// "How wide it can go": the spread of how far those same calls finished from the S&P, in the direction called
// (backend baserate p10 / p50 / p90). The hit rate alone reads as a coin flip with small stakes.
const pts = (x) => Math.round(Math.abs(x) * 100);

function ptsWay(x) {
  if (pts(x) === 0) return 'about even with the S&P';
  return `${pts(x)} pts ${x > 0 ? 'the right way' : 'the wrong way'}`;
}

// The tail of the spread, said so it stays true when the whole range sits on one side of the S&P.
function worstTail(x) {
  if (pts(x) === 0) return 'about even with the S&P or worse';
  return x < 0 ? `${pts(x)} pts or more the wrong way` : `still ${pts(x)} pts the right way`;
}

function bestTail(x) {
  if (pts(x) === 0) return 'about even with the S&P or better';
  return x > 0 ? `${pts(x)} pts or more the right way` : `still ${pts(x)} pts the wrong way`;
}

const hasSpread = (cell) => !!cell && cell.p10 != null && cell.p90 != null && cell.p50 != null;

// The bar: blue band = the middle 8 in 10, dot = the middle call, line = even with the S&P. `you` (optional) marks
// the user's own graded result on the same scale.
export function SpreadBar({ cell, you = null }) {
  if (!hasSpread(cell)) return null;
  // symmetric scale, so the S&P mark sits mid-bar; widened to keep the user's mark on the bar
  const w = Math.max(Math.abs(cell.p10), Math.abs(cell.p90), you == null ? 0 : Math.abs(you) * 1.08, 0.01);
  const at = (x) => `${((x + w) / (2 * w)) * 100}%`;
  return (
    <>
      <div className={`relative h-2.5 rounded-full bg-slate-700/70 ${you != null ? 'mt-5' : ''}`} aria-hidden="true">
        <div className="absolute inset-y-0 rounded-full bg-blue-400/40" style={{ left: at(cell.p10), right: `calc(100% - ${at(cell.p90)})` }} />
        <div className="absolute -inset-y-0.5 w-px bg-slate-300" style={{ left: '50%' }} />
        <div className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-slate-900 bg-blue-300" style={{ left: at(cell.p50) }} />
        {you != null && (
          <div className="absolute -top-5 flex -translate-x-1/2 flex-col items-center" style={{ left: at(you) }}>
            <span className="rounded bg-amber-300 px-1 text-[9px] font-bold leading-[14px] text-slate-900">You</span>
            <span className="h-[18px] w-0.5 bg-amber-300" />
          </div>
        )}
      </div>
      <div className="mt-0.5 flex justify-between text-[10px] text-slate-500" aria-hidden="true">
        <span>{pts(w)} pts wrong way</span><span>S&amp;P</span><span>{pts(w)} pts right way</span>
      </div>
    </>
  );
}

// Where one graded result sits among calls like it (only the 10th / 50th / 90th percentiles are stored).
export function spotWord(x, cell) {
  if (!hasSpread(cell) || x == null) return null;
  if (x < cell.p10) return 'in the worst 1 in 10';
  if (x > cell.p90) return 'in the best 1 in 10';
  return x >= cell.p50 ? 'above the middle call (the dot), inside the blue band where 8 in 10 land' : 'below the middle call (the dot), inside the blue band where 8 in 10 land';
}

export function SpreadLine({ cell, cp }) {
  if (!hasSpread(cell)) return null;
  return (
    <div className="mt-1.5" aria-label="How wide it can go">
      <SpreadBar cell={cell} />
      <div className="mt-0.5">
        <span className="font-semibold text-slate-100">How wide it can go</span> (one call vs the S&amp;P, {cp}-day check):
        the worst 1 in 10 ended {worstTail(cell.p10)}; the best 1 in 10 ended {bestTail(cell.p90)}.
        The middle call ended {ptsWay(cell.p50)}.
      </div>
    </div>
  );
}

export function BaseRateLine({ cell, direction, cp, prob = null }) {
  if (!cell || cell.beat == null) return null;
  const pct = Math.round(cell.beat * 100);
  const since = monthYear(cell.since);
  const upto = monthYear(cell.upto);
  const span = since && upto ? (since === upto ? ` (made ${since})` : ` (made ${since} to ${upto})`) : '';
  const gap = prob != null ? Math.round(prob * 100) - pct : null;
  return (
    <div className="mt-1.5 rounded-xl bg-slate-800/70 px-2.5 py-1.5 text-xs text-slate-300">
      <span className="font-semibold text-slate-100"><Term k="base rate">Base rate</Term>:</span>{' '}
      of {cell.n.toLocaleString()} graded {direction} calls{span},{' '}
      <span className="font-semibold text-slate-100">{pct}%</span> {pastGoal(direction)} at the {cp}-day check.
      {gap != null && Math.abs(gap) >= 10 && (
        <span className="text-slate-400"> You said {Math.round(prob * 100)}%, {Math.abs(gap)} points {gap > 0 ? 'above' : 'below'} it.</span>
      )}
      <SpreadLine cell={cell} cp={cp} />
      <span className="text-slate-500"> Mostly the app's practice calls; past record, not a forecast.</span>
    </div>
  );
}

export default function HowSure({ beliefId, direction, horizonDays, checkpointDays = null, initial = null, canSet = true, inChat = false, onSaved }) {
  const [prob, setProb] = useState(initial);
  const [state, setState] = useState({ saving: null, error: null });
  const cp = checkpointDays || checkpointFor(horizonDays);
  const base = useBaseRate(direction, cp);
  if (!beliefId || !['bullish', 'bearish', 'volatile'].includes(direction)) return null;

  async function pick(p) {
    if (!canSet || state.saving) return;
    setState({ saving: p, error: null });
    try {
      const r = await saveUserProb(beliefId, p);
      setProb(r.sure.prob);
      setState({ saving: null, error: null });
      onSaved?.(r.sure);
    } catch (e) {
      setState({ saving: null, error: e.message });
    }
  }

  if (!canSet) {
    if (prob == null) return null;
    return (
      <div className="mt-3 text-xs text-slate-400">
        You said <span className="font-semibold text-slate-200">{Math.round(prob * 100)}% sure</span> it {sureGoal(direction)} at the {cp}-day check.
        <BaseRateLine cell={base} direction={direction} cp={cp} prob={prob} />
      </div>
    );
  }

  return (
    <div className={`mt-3 rounded-2xl border px-3 py-2.5 ${prob != null ? 'border-blue-400/30 bg-blue-500/10' : 'border-slate-700 bg-slate-900/60'}`}>
      <div className="text-sm font-semibold text-slate-100">How sure are you?</div>
      <div className="text-xs text-slate-400">That your idea {sureGoal(direction)} at the {cp}-day check{checkNote(horizonDays, cp)}. Optional, one tap.</div>
      <BaseRateLine cell={base} direction={direction} cp={cp} prob={prob} />
      <div className="mt-2 grid grid-cols-4 gap-1.5" role="group" aria-label="How sure are you">
        {SURE_CHOICES.map((p) => {
          const on = prob != null && Math.abs(prob - p) < 1e-6;
          return (
            <button key={p} type="button" onClick={() => pick(p)} aria-pressed={on} disabled={!!state.saving}
              className={`rounded-xl py-2 text-sm font-bold border transition ${on ? 'bg-blue-500 border-blue-400 text-white' : 'bg-slate-800 border-slate-700 text-slate-200 hover:border-blue-300'} ${state.saving === p ? 'opacity-60' : ''}`}>
              {Math.round(p * 100)}%
            </button>
          );
        })}
      </div>
      {state.error && <div className="mt-2 text-xs text-red-300">{state.error}</div>}
      <div className="mt-1.5 text-[11px] text-slate-500">
        {prob != null
          ? (inChat ? 'Saved. You can change it until tomorrow; then it\'s locked and scored when the call is graded.' : 'You can change it until the day after the call; then it\'s locked.')
          : '50% would be a coin flip. Your answers are scored against what happens, so you learn how sure you should be.'}
      </div>
    </div>
  );
}


// My beliefs: the user's own graded result marked on the spread of calls like it at the same check. The lesson is
// the professor's one: a single call inside the usual range says little about skill either way.
export function YourSpot({ graded, direction, ownCp }) {
  const cell = useBaseRate(direction, graded?.checkpoint_days);
  if (!graded || !['bullish', 'bearish', 'volatile'].includes(direction)) return null;
  const cp = graded.checkpoint_days;
  const x = graded.vs_spy;
  const where = spotWord(x, cell);
  const on = graded.on ? new Date(`${graded.on}T12:00:00Z`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' }) : null;
  return (
    <div className="mt-3 rounded-2xl border border-slate-700 bg-slate-800/50 px-3 py-2.5 text-xs text-slate-300" aria-label="Your graded result">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Graded at the {cp}-day check{on ? ` (${on})` : ''}</div>
      <div className="mt-0.5 text-sm text-slate-100">
        Your idea finished <b className={x > 0 ? 'text-green-300' : x < 0 ? 'text-red-300' : 'text-white'}>{ptsWay(x)}</b>{pts(x) === 0 ? '' : ' vs the S&P'}.
      </div>
      {where ? (
        <>
          <SpreadBar cell={cell} you={x} />
          <div className="mt-1">
            Among {cell.n.toLocaleString()} graded {direction} calls at this check, that's {where}.{' '}
            {/blue band/.test(where)
              ? 'Most calls land here, so one result says little about skill either way.'
              : `About 1 in 10 calls ${x > 0 ? 'do this well' : 'do this badly'}, so one call still says little about skill on its own.`}
          </div>
        </>
      ) : null}
      {ownCp && cp < ownCp && (
        <div className="mt-1 text-[11px] text-slate-500">An early read: your call is judged at the {ownCp}-day check.</div>
      )}
      <div className="mt-1 text-[11px] text-slate-500">Measured like the base rate: your idea's theme vs the S&amp;P, in the direction you called. Calls like it: mostly the app's practice calls.</div>
    </div>
  );
}
