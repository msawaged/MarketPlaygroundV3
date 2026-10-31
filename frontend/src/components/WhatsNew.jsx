// "What's new" on the welcome and login screens. Newest first; keep each line short and plain.
// To update: add a line at the top of UPDATES and bump the date.
import React from 'react';

export const UPDATED = 'Oct 30';
export const UPDATES = [
  'Watch any news story in 30 seconds with Story mode',
  'AI strategists compete daily: only the strong survive',
  'An honest scorecard on the brain page, real numbers only',
  'The brain now learns from 90-day results, not 30',
  'Log in with Face ID',
  'Practice options trades, priced live',
];

export default function WhatsNew({ max = 4, className = '' }) {
  return (
    <div className={`rounded-2xl border border-slate-700/70 bg-slate-900/70 px-4 py-3 text-left ${className}`}>
      <div className="flex items-center justify-between">
        <div className="text-[11px] font-bold uppercase tracking-wider text-blue-300">What's new</div>
        <div className="text-[11px] text-slate-500">Updated {UPDATED}</div>
      </div>
      <ul className="mt-2 space-y-1.5">
        {UPDATES.slice(0, max).map((u) => (
          <li key={u} className="flex gap-2 text-sm text-slate-200">
            <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
            <span>{u}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
