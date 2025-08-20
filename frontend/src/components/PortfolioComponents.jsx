// FILE: frontend/src/components/PortfolioComponents.jsx
// Portfolio Integration Components

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// Portfolio Summary Card Component
const PortfolioSummary = ({ BACKEND_URL }) => {
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  // Fetch portfolio data
  const fetchPortfolio = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/paper-trading/portfolio/demo_user`);
      const data = await response.json();
      setPortfolio(data);
      setLastUpdate(new Date());
    } catch (error) {
      console.error('Portfolio fetch error:', error);
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh portfolio every 30 seconds
  useEffect(() => {
    fetchPortfolio();
    const interval = setInterval(fetchPortfolio, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="bg-slate-800/50 rounded-lg p-4 animate-pulse">
        <div className="h-4 bg-slate-700 rounded w-1/3 mb-2"></div>
        <div className="h-8 bg-slate-700 rounded w-1/2"></div>
      </div>
    );
  }

  if (!portfolio) return null;

  const { account, summary } = portfolio;
  const totalReturn = account.total_return_pct * 100;
  const isProfit = totalReturn >= 0;

  return (
    <motion.div 
      className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-xl p-4 border border-blue-500/30"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
    >
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-bold text-white">Portfolio Summary</h3>
        <div className="text-xs text-slate-400">
          Updated: {lastUpdate.toLocaleTimeString()}
        </div>
      </div>

      {/* Main metrics grid */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* Total Value */}
        <motion.div 
          className="bg-slate-700/50 rounded-lg p-3 border border-slate-600"
          whileHover={{ scale: 1.02, borderColor: '#3b82f6' }}
        >
          <div className="text-xs text-slate-400 font-semibold">Total Value</div>
          <div className="text-xl font-bold text-white">
            ${account.total_value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
        </motion.div>

        {/* P&L */}
        <motion.div 
          className="bg-slate-700/50 rounded-lg p-3 border border-slate-600"
          whileHover={{ scale: 1.02, borderColor: isProfit ? '#22c55e' : '#ef4444' }}
        >
          <div className="text-xs text-slate-400 font-semibold">Total P&L</div>
          <div className={`text-xl font-bold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
            {isProfit ? '+' : ''}${account.total_pnl.toFixed(2)}
          </div>
          <div className={`text-sm ${isProfit ? 'text-green-300' : 'text-red-300'}`}>
            ({isProfit ? '+' : ''}{totalReturn.toFixed(2)}%)
          </div>
        </motion.div>

        {/* Cash Balance */}
        <motion.div 
          className="bg-slate-700/50 rounded-lg p-3 border border-slate-600"
          whileHover={{ scale: 1.02, borderColor: '#22c55e' }}
        >
          <div className="text-xs text-slate-400 font-semibold">Cash Balance</div>
          <div className="text-lg font-bold text-green-400">
            ${account.cash_balance.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
        </motion.div>

        {/* Active Positions */}
        <motion.div 
          className="bg-slate-700/50 rounded-lg p-3 border border-slate-600"
          whileHover={{ scale: 1.02, borderColor: '#8b5cf6' }}
        >
          <div className="text-xs text-slate-400 font-semibold">Positions</div>
          <div className="text-lg font-bold text-purple-400">
            {summary.total_positions}
          </div>
          <div className="text-sm text-slate-300">
            Grade: {summary.performance_grade}
          </div>
        </motion.div>
      </div>

      {/* Refresh button */}
      <motion.button
        onClick={fetchPortfolio}
        className="w-full bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/50 rounded-lg py-2 text-blue-400 text-sm font-semibold transition-colors"
        whileTap={{ scale: 0.98 }}
      >
        Refresh Portfolio
      </motion.button>
    </motion.div>
  );
};

// Active Positions Component
const ActivePositions = ({ BACKEND_URL }) => {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchPositions = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/paper-trading/portfolio/demo_user`);
      const data = await response.json();
      setPositions(data.positions || []);
    } catch (error) {
      console.error('Positions fetch error:', error);
    } finally {
      setLoading(false);
    }
  };

  const closePosition = async (positionId) => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/paper-trading/close_position`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'demo_user',
          position_id: positionId
        })
      });
      
      if (response.ok) {
        // Refresh positions after closing
        fetchPositions();
        
        // Show success notification
        const toast = document.createElement('div');
        toast.className = 'fixed top-20 right-4 bg-green-500 text-white px-4 py-2 rounded-lg z-50';
        toast.textContent = 'Position closed successfully!';
        document.body.appendChild(toast);
        setTimeout(() => document.body.removeChild(toast), 3000);
      }
    } catch (error) {
      console.error('Close position error:', error);
    }
  };

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map(i => (
          <div key={i} className="bg-slate-800/50 rounded-lg p-4 animate-pulse">
            <div className="h-4 bg-slate-700 rounded w-1/4 mb-2"></div>
            <div className="h-6 bg-slate-700 rounded w-1/2"></div>
          </div>
        ))}
      </div>
    );
  }

  if (positions.length === 0) {
    return (
      <div className="bg-slate-800/50 rounded-lg p-6 text-center">
        <div className="text-slate-400 text-lg mb-2">No active positions</div>
        <div className="text-sm text-slate-500">Execute a strategy to see positions here</div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-bold text-white mb-4">Active Positions</h3>
      <AnimatePresence>
        {positions.map((position, index) => {
          const pnlIsProfit = position.unrealized_pnl >= 0;
          
          return (
            <motion.div
              key={position.strategy_id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ delay: index * 0.1 }}
              className="bg-gradient-to-r from-slate-800 to-slate-900 rounded-lg p-4 border border-slate-700"
            >
              {/* Position header */}
              <div className="flex justify-between items-start mb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-bold text-white">{position.ticker}</span>
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${
                      position.position_type === 'long' 
                        ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                        : 'bg-red-500/20 text-red-400 border border-red-500/30'
                    }`}>
                      {position.position_type.toUpperCase()}
                    </span>
                  </div>
                  <div className="text-sm text-slate-400">
                    Qty: {position.quantity} @ ${position.avg_price}
                  </div>
                </div>
                
                {/* Close button */}
                <motion.button
                  onClick={() => closePosition(position.strategy_id)}
                  className="bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 rounded-lg px-3 py-1 text-red-400 text-sm font-semibold"
                  whileTap={{ scale: 0.95 }}
                >
                  Close
                </motion.button>
              </div>

              {/* Position metrics */}
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center">
                  <div className="text-xs text-slate-400">Current Price</div>
                  <div className="text-sm font-bold text-white">
                    ${position.current_price}
                  </div>
                </div>
                
                <div className="text-center">
                  <div className="text-xs text-slate-400">Market Value</div>
                  <div className="text-sm font-bold text-blue-400">
                    ${position.market_value.toFixed(2)}
                  </div>
                </div>
                
                <div className="text-center">
                  <div className="text-xs text-slate-400">P&L</div>
                  <div className={`text-sm font-bold ${pnlIsProfit ? 'text-green-400' : 'text-red-400'}`}>
                    {pnlIsProfit ? '+' : ''}${position.unrealized_pnl.toFixed(2)}
                  </div>
                  <div className={`text-xs ${pnlIsProfit ? 'text-green-300' : 'text-red-300'}`}>
                    ({pnlIsProfit ? '+' : ''}{(position.unrealized_pnl_pct * 100).toFixed(2)}%)
                  </div>
                </div>
              </div>

              {/* Position details */}
              <div className="mt-3 pt-3 border-t border-slate-700">
                <div className="text-xs text-slate-400">
                  Opened: {new Date(position.opened_at).toLocaleString()}
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  Belief: "{position.belief}"
                </div>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
};

// Portfolio Modal Component
const PortfolioModal = ({ isOpen, onClose, BACKEND_URL }) => {
  if (!isOpen) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl p-6 max-w-md w-full max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal header */}
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-white">Portfolio</h2>
          <motion.button
            onClick={onClose}
            className="w-8 h-8 bg-slate-700 hover:bg-slate-600 rounded-full flex items-center justify-center text-slate-400"
            whileTap={{ scale: 0.95 }}
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </motion.button>
        </div>

        {/* Portfolio content */}
        <div className="space-y-6">
          <PortfolioSummary BACKEND_URL={BACKEND_URL} />
          <ActivePositions BACKEND_URL={BACKEND_URL} />
        </div>
      </motion.div>
    </motion.div>
  );
};

// Portfolio Button for ChatInterface
const PortfolioButton = ({ BACKEND_URL }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [portfolioSummary, setPortfolioSummary] = useState(null);

  // Fetch basic portfolio data for button display
  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/api/paper-trading/portfolio/demo_user`);
        const data = await response.json();
        setPortfolioSummary(data);
      } catch (error) {
        console.error('Portfolio summary fetch error:', error);
      }
    };

    fetchSummary();
    const interval = setInterval(fetchSummary, 60000); // Update every minute
    return () => clearInterval(interval);
  }, []);

  const totalValue = portfolioSummary?.account?.total_value || 0;
  const totalPnl = portfolioSummary?.account?.total_pnl || 0;
  const isProfit = totalPnl >= 0;

  return (
    <>
      <motion.button
        onClick={() => setIsModalOpen(true)}
        className="fixed top-20 left-4 z-40 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white rounded-xl p-3 shadow-lg border border-blue-500/30"
        whileHover={{ scale: 1.05, y: -2 }}
        whileTap={{ scale: 0.95 }}
      >
        <div className="text-left">
          <div className="text-xs font-semibold">Portfolio</div>
          <div className="text-sm font-bold">
            ${totalValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className={`text-xs ${isProfit ? 'text-green-300' : 'text-red-300'}`}>
            {isProfit ? '+' : ''}${totalPnl.toFixed(0)}
          </div>
        </div>
      </motion.button>

      <AnimatePresence>
        {isModalOpen && (
          <PortfolioModal
            isOpen={isModalOpen}
            onClose={() => setIsModalOpen(false)}
            BACKEND_URL={BACKEND_URL}
          />
        )}
      </AnimatePresence>
    </>
  );
};

export { PortfolioSummary, ActivePositions, PortfolioModal, PortfolioButton };