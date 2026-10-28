import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import ToolSelectorPage from './components/ToolSelectorPage';
import ChatInterface from './components/ChatInterface';
import TrendingPage from './components/TrendingPage';
import BasketBuilderPage from './BasketBuilderPage';
import { PortfolioModal } from './components/PortfolioComponents';
import BottomNavigation from './components/BottomNavigation';
import { API_BASE } from './lib/api';

// Heavier, less-used screens load on demand.
const GeneratorPage = lazy(() => import('./components/GeneratorPage'));
const StrategyOpsPage = lazy(() => import('./components/StrategyOpsPage'));

function PortfolioPage() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-slate-950">
      <PortfolioModal isOpen onClose={() => navigate('/chat')} BACKEND_URL={API_BASE} />
      <BottomNavigation />
    </div>
  );
}

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
          <Route path="/basket-builder" element={<BasketBuilderPage />} />
          <Route path="/portfolio" element={<PortfolioPage />} />
          <Route path="/generator" element={<GeneratorPage />} />
          <Route path="/strategy-ops" element={<StrategyOpsPage />} />
          <Route path="*" element={<Navigate to="/select-tool" replace />} />
        </Routes>
      </Suspense>
    </Router>
  );
}
