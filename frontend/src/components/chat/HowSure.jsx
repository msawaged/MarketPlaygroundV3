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
      <div className="text-xs text-slate-400">That your idea {sureGoal(direction)} at the {cp}-day check. Optional, one tap.</div>
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
