// "How sure are you?": one tap to say how likely you think your own call is to play out. Scored later against what
// happened (My beliefs shows how well-calibrated you are once enough calls are graded). Not advice; nothing trades.
import React, { useState } from 'react';
import { saveUserProb } from '../../lib/api';

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

export default function HowSure({ beliefId, direction, horizonDays, checkpointDays = null, initial = null, canSet = true, inChat = false, onSaved }) {
  const [prob, setProb] = useState(initial);
  const [state, setState] = useState({ saving: null, error: null });
  if (!beliefId || !['bullish', 'bearish', 'volatile'].includes(direction)) return null;
  const cp = checkpointDays || checkpointFor(horizonDays);

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
      </div>
    );
  }

  return (
    <div className={`mt-3 rounded-2xl border px-3 py-2.5 ${prob != null ? 'border-blue-400/30 bg-blue-500/10' : 'border-slate-700 bg-slate-900/60'}`}>
      <div className="text-sm font-semibold text-slate-100">How sure are you?</div>
      <div className="text-xs text-slate-400">That your idea {sureGoal(direction)} at the {cp}-day check. Optional, one tap.</div>
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
