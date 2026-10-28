// Shared page shell: soft gradient background, safe-area padding, title, bottom nav.
import React from 'react';
import BottomNavigation from '../BottomNavigation';

export default function Page({ title, subtitle, right, children }) {
  return (
    <div className="min-h-screen mp-bg text-white pb-28">
      <div className="max-w-lg mx-auto px-4" style={{ paddingTop: 'max(2rem, env(safe-area-inset-top))' }}>
        {(title || right) && (
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              {title && <h1 className="text-3xl font-extrabold tracking-tight">{title}</h1>}
              {subtitle && <p className="mt-1 text-slate-300">{subtitle}</p>}
            </div>
            {right}
          </div>
        )}
        {children}
      </div>
      <BottomNavigation />
    </div>
  );
}

export function Card({ className = '', children, ...rest }) {
  return (
    <div className={`rounded-3xl border border-slate-700/70 bg-slate-900/70 backdrop-blur p-4 ${className}`} {...rest}>
      {children}
    </div>
  );
}

export function pct(v, digits = 1) {
  if (v == null || Number.isNaN(v)) return '—';
  return `${v >= 0 ? '+' : ''}${(v * 100).toFixed(digits)}%`;
}
