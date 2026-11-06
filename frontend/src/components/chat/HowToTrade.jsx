// Asked before every belief (unless the person chose "remember"): how do you want to trade this?
import React, { useState } from 'react';
import { TrendingUp, Target, Shuffle } from 'lucide-react';
import { GOALS } from '../../lib/prefs';

const CHOICES = [
  { id: 'shares', icon: TrendingUp, title: 'Shares', line: 'Own a piece of the company. You gain if it rises, lose if it falls.',
    bits: ['Any amount, even $10', 'No expiration', 'Best when you think something will grow'] },
  { id: 'options', icon: Target, title: 'Options', line: 'Bigger payoff for less money, but they expire and can go to zero.',
    bits: ['Win on a rise or a fall', 'Has an end date', 'One contract often costs $100+'] },
  { id: 'auto', icon: Shuffle, title: 'Let the AI decide', line: 'A mix: shares where they’re simplest, options where they fit better.',
    bits: ['Good if you’re not sure', 'You can switch on each idea'] },
];

const BUDGETS = [100, 500, 1000, 5000];
const MAX_BUDGET = 100000; // the practice account starts with $100,000
const TIMES = [{ d: 0, l: 'AI decides' }, { d: 30, l: '1 month' }, { d: 90, l: '3 months' }, { d: 180, l: '6 months' }, { d: 365, l: '1 year' }];

function Chips({ label, items, value, onChange }) {
  return (
    <div className="mt-2.5">
      <div className="text-xs text-slate-300">{label}</div>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {items.map((it) => (
          <button key={it.v} onClick={() => onChange(it.v)} aria-pressed={value === it.v}
            className={`text-xs font-semibold rounded-full px-3 py-1.5 border ${value === it.v ? 'bg-blue-600 border-blue-400 text-white' : 'bg-slate-900/80 border-slate-700 text-slate-200 hover:border-slate-500'}`}>
            {it.l}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function HowToTrade({ belief, onPick }) {
  const [remember, setRemember] = useState(false);
  const [goalStep, setGoalStep] = useState(false);
  const [budget, setBudget] = useState(0);
  const [typed, setTyped] = useState('');
  const [days, setDays] = useState(0);
  const pick = (instrument, goal = '') => onPick({ instrument, goal, remember, budget_usd: budget, horizon_days: days });
  return (
    <div className="rounded-2xl border border-blue-400/40 bg-blue-500/[0.08] p-3.5">
      <div className="text-sm font-bold">How do you want to trade “{belief.length > 60 ? belief.slice(0, 57) + '…' : belief}”?</div>
      <Chips label="How much do you want to put on this idea?" value={typed ? -1 : budget} onChange={(v) => { setTyped(''); setBudget(v); }}
        items={[...BUDGETS.map((b) => ({ v: b, l: `$${b.toLocaleString()}` })), { v: 0, l: 'Not sure' }]} />
      <label className={`mt-2 flex items-center gap-2 rounded-xl border px-3 py-2 ${typed ? 'border-blue-400 bg-blue-600/10' : 'border-slate-700 bg-slate-900/80'}`}>
        <span className="text-xs text-slate-400 shrink-0">Or type your own amount</span>
        <span className="ml-auto text-slate-400 font-bold">$</span>
        <input type="text" inputMode="decimal" placeholder="e.g. 750" value={typed} aria-label="Your own amount in dollars"
          onChange={(e) => {
            const raw = e.target.value.replace(/[^0-9.]/g, '').slice(0, 9);
            setTyped(raw);
            const n = Math.round(Number(raw));
            setBudget(n >= 10 ? Math.min(n, MAX_BUDGET) : 0);
          }}
          className="w-28 bg-transparent text-right font-bold text-white placeholder:text-slate-500 focus:outline-none" />
      </label>
      {typed && Math.round(Number(typed)) < 10 && <p className="text-[11px] text-amber-200 mt-1">The smallest amount is $10.</p>}
      {Number(typed) > MAX_BUDGET && <p className="text-[11px] text-amber-200 mt-1">The practice account holds ${MAX_BUDGET.toLocaleString()}, so this uses ${MAX_BUDGET.toLocaleString()}.</p>}
      <Chips label="For how long?" value={days} onChange={setDays} items={TIMES.map((t) => ({ v: t.d, l: t.l }))} />
      {!goalStep ? (
        <div className="mt-3 grid gap-2">
          {CHOICES.map((c) => (
            <button key={c.id} onClick={() => (c.id === 'options' ? setGoalStep(true) : pick(c.id))}
              className="text-left rounded-xl bg-slate-900/80 border border-slate-700 hover:border-blue-400 px-3 py-2.5">
              <div className="text-sm font-bold flex items-center gap-1.5"><c.icon className="w-4 h-4 text-blue-300" aria-hidden />{c.title}</div>
              <div className="text-xs text-slate-300 mt-0.5">{c.line}</div>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {c.bits.map((b) => <span key={b} className="text-[10px] rounded-full bg-slate-800 border border-slate-700 px-2 py-0.5 text-slate-300">{b}</span>)}
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="mt-2.5">
          <div className="text-xs text-slate-300">With options, what matters most?</div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {GOALS.map((g) => (
              <button key={g.id} onClick={() => pick('options', g.id)}
                className="text-left rounded-xl bg-slate-900/80 border border-slate-700 hover:border-blue-400 px-3 py-2">
                <div className="text-sm font-semibold">{g.label}</div>
                <div className="text-[11px] text-slate-400 leading-snug">{g.hint}</div>
              </button>
            ))}
          </div>
          <div className="mt-2 flex gap-4">
            <button onClick={() => pick('options')} className="text-xs font-semibold text-blue-300">Any options strategy</button>
            <button onClick={() => setGoalStep(false)} className="text-xs text-slate-400">Back</button>
          </div>
        </div>
      )}
      <label className="mt-3 flex items-center gap-2 text-xs text-slate-400">
        <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="accent-blue-500" />
        Remember my choice (change it anytime on an idea card)
      </label>
    </div>
  );
}
