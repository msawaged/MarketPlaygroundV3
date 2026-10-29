// The MarketPlayground mark: an M whose middle is a swing seat caught mid-swing (white tile, blue M).
import React from 'react';

export function LogoMark({ size = 36, className = '', title }) {
  const small = size < 28; // tiny sizes drop the path + ghost so the M stays crisp
  return (
    <svg viewBox="0 0 120 120" width={size} height={size} className={className}
      role={title ? 'img' : undefined} aria-label={title} aria-hidden={title ? undefined : true}>
      <rect width="120" height="120" rx="30" fill="#ffffff" />
      {!small && <path d="M23.2 56.9 A48 48 0 0 0 96.8 56.9" fill="none" stroke="#bfdbfe" strokeWidth="5" strokeLinecap="round" />}
      {!small && <path d="M26 30 L60 74 L94 30" fill="none" stroke="#2563eb" strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" opacity="0.25" />}
      <path d="M26 92 V30 L72 72.5 L94 30 V92" fill="none" stroke="#2563eb" strokeWidth={small ? 14 : 10} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="72" cy="72.5" r={small ? 15 : 12} fill="#2563eb" />
    </svg>
  );
}

export function Wordmark({ className = '' }) {
  return <span className={`font-extrabold tracking-tight ${className}`}>market<span className="text-blue-400">playground</span></span>;
}
