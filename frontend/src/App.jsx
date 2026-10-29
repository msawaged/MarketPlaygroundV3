import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import ToolSelectorPage from './components/ToolSelectorPage';
import ChatInterface from './components/ChatInterface';
import TrendingPage from './components/TrendingPage';
import MyCallsPage from './components/MyCallsPage';
import LearningPage from './components/LearningPage';
import BasketBuilderPage from './BasketBuilderPage';
import PracticePage from './components/PracticePage';
import AccountPage from './components/AccountPage';
import { VerifyPage, ResetPage } from './components/EmailLinkPage';
import WelcomePage from './components/WelcomePage';
import { useAccount } from './lib/auth';

// Heavier, less-used screens load on demand.

function Loading() {
  return <div className="min-h-screen bg-slate-950 text-slate-400 flex items-center justify-center">Loading…</div>;
}

// Everything except the welcome, account and email-link screens needs a logged-in account.
function Gate({ children }) {
  const account = useAccount();
  const loc = useLocation();
  if (account) return children;
  const here = loc.pathname + loc.search;
  return <Navigate to={here === '/select-tool' ? '/welcome' : `/welcome?next=${encodeURIComponent(here)}`} replace />;
}
const g = (el) => <Gate>{el}</Gate>;

export default function App() {
  return (
    <Router>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<Navigate to="/select-tool" replace />} />
          <Route path="/select-tool" element={g(<ToolSelectorPage />)} />
          <Route path="/chat" element={g(<ChatInterface />)} />
          <Route path="/trending" element={g(<TrendingPage />)} />
          <Route path="/hot-trades" element={<Navigate to="/trending" replace />} />
          <Route path="/my" element={g(<MyCallsPage />)} />
          <Route path="/learning" element={<LearningPage />} />
          <Route path="/welcome" element={<WelcomePage />} />
          <Route path="/account" element={<AccountPage />} />
          <Route path="/verify" element={<VerifyPage />} />
          <Route path="/reset" element={<ResetPage />} />
          <Route path="/basket-builder" element={g(<BasketBuilderPage />)} />
          <Route path="/portfolio" element={g(<PracticePage />)} />
          <Route path="*" element={<Navigate to="/select-tool" replace />} />
        </Routes>
      </Suspense>
    </Router>
  );
}
