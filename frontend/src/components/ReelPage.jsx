// /reel?i=0 : plays one of today's news stories in Story mode, hands-free, for recording a vertical reel.
// Used by scripts/make_reel.js (the daily "Market's open" reel). Public and read-only.
import React, { useEffect, useState } from 'react';
import StoryViewer from './StoryViewer';
import { getMovers } from '../lib/api';

export default function ReelPage() {
  const q = new URLSearchParams(window.location.search);
  const i = Math.max(0, parseInt(q.get('i') || '0', 10) || 0);
  const ms = Math.min(9000, Math.max(2500, parseInt(q.get('ms') || '4200', 10) || 4200));
  const [headline, setHeadline] = useState(q.get('h') || '');
  const [err, setErr] = useState('');
  useEffect(() => {
    if (headline) return;
    getMovers().then((d) => {
      const it = (d.items || [])[i];
      if (it) setHeadline(it.headline); else setErr('No story right now.');
    }).catch(() => setErr('No story right now.'));
  }, [headline, i]);
  if (err) return <div className="min-h-screen bg-slate-950 text-slate-400 flex items-center justify-center">{err}</div>;
  if (!headline) return <div className="min-h-screen bg-slate-950" />;
  return <StoryViewer headline={headline} reel cardMs={ms} onClose={() => {}} />;
}
