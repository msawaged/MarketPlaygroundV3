// /story?h=<headline> opens one news story full screen (shareable link). Without h it opens today's top story.
// ?reel=1 is the clean, hands-free version used to record the daily "Market's open" reel.
import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import StoryViewer from './StoryViewer';
import { getMovers } from '../lib/api';

export default function StoryPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const reel = params.get('reel') === '1';
  const [headline, setHeadline] = useState(params.get('h') || '');
  const [err, setErr] = useState('');

  useEffect(() => {
    if (headline) return;
    const pick = Math.max(0, parseInt(params.get('i') || '0', 10) || 0);
    getMovers()
      .then((d) => {
        const it = (d.items || [])[pick] || (d.items || [])[0];
        if (it) setHeadline(it.headline); else setErr('No stories right now. Check back soon.');
      })
      .catch(() => setErr("Couldn't load today's news."));
  }, [headline, params]);

  if (err) return <div className="min-h-screen bg-slate-950 text-slate-300 flex items-center justify-center p-6 text-center">{err}</div>;
  if (!headline) return <div className="min-h-screen bg-slate-950" />;
  return <StoryViewer headline={headline} reel={reel} onClose={() => navigate('/trending')} />;
}
