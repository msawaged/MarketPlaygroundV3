import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import ToolSelectorPage from './components/ToolSelectorPage';
import ChatInterface from './components/ChatInterface';
import TrendingPage from './components/TrendingPage';
import MyCallsPage from './components/MyCallsPage';
import LearningPage from './components/LearningPage';
import BasketBuilderPage from './BasketBuilderPage';
import PracticePage from './components/PracticePage';
import AccountPage from './components/AccountPage';
import { VerifyPage, ResetPage } from './components/EmailLinkPage';

// Heavier, less-used screens load on demand.
const GeneratorPage = lazy(() => import('./components/GeneratorPage'));
const StrategyOpsPage = lazy(() => import('./components/StrategyOpsPage'));

function Loading() {
  return <div className="min-h-screen bg-slate-950 text-slate-400 flex items-center justify-center">Loading…</div>;
}

export default function App() {
  return (
    <Router>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<Navigate to="/select-tool" replace />} />
          <Route path="/select-tool" element={<ToolSelectorPage />} />
          <Route path="/chat" element={<ChatInterface />} />
          <Route path="/trending" element={<TrendingPage />} />
          <Route path="/hot-trades" element={<Navigate to="/trending" replace />} />
          <Route path="/my" element={<MyCallsPage />} />
          <Route path="/learning" element={<LearningPage />} />
          <Route path="/account" element={<AccountPage />} />
          <Route path="/verify" element={<VerifyPage />} />
          <Route path="/reset" element={<ResetPage />} />
          <Route path="/basket-builder" element={<BasketBuilderPage />} />
          <Route path="/portfolio" element={<PracticePage />} />
          <Route path="/generator" element={<GeneratorPage />} />
          <Route path="/strategy-ops" element={<StrategyOpsPage />} />
          <Route path="*" element={<Navigate to="/select-tool" replace />} />
        </Routes>
      </Suspense>
    </Router>
  );
}
