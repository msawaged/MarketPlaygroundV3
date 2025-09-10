// frontend/src/components/HotTrades.jsx

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Flame, RefreshCw, Eye, MessageSquare,
  TrendingUp, TrendingDown, Minus, Clock,
  Target, DollarSign, AlertCircle
} from 'lucide-react';
import { API_BASE, processBelief } from '../lib/api';
import BottomNavigation from './BottomNavigation';  // ADD THIS LINE


const HotTrades = () => {
  const navigate = useNavigate();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [expandedCards, setExpandedCards] = useState(new Set());

  // Normalize inconsistent API responses
  const normalizeItem = (raw) => {
    return {
      id: raw.id || Math.random().toString(36).substr(2, 9),
      ticker: raw.ticker || raw.symbol || 'N/A',
      headline: raw.headline || raw.title || raw.news_title || '',
      source: raw.source || raw.news_source || 'Unknown',
      belief: raw.belief || raw.thesis || raw.headline || '',
      sentiment: raw.sentiment || raw.sentiment_score || raw.score || 'neutral',
      confidence: raw.confidence || raw.confidence_score || 0,
      strategy: raw.strategy || null,
      createdAt: raw.created_at || raw.createdAt || raw.timestamp || new Date().toISOString()
    };
  };

  // Fetch hot trades from backend
  const fetchHotTrades = useCallback(async (showRefreshState = false) => {
    if (showRefreshState) setRefreshing(true);
    
    try {
      const response = await fetch(`${API_BASE}/hot_trades?limit=8`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch hot trades: ${response.statusText}`);
      }

      const data = await response.json();
      const normalizedTrades = (data.trades || data.items || data || []).map(normalizeItem);
      
      setTrades(normalizedTrades);
      setError(null);
    } catch (err) {
      console.error('Error fetching hot trades:', err);
      setError(err.message);
    } finally {
      setLoading(false);
      if (showRefreshState) setRefreshing(false);
    }
  }, []);

  /**
   * Setup initial data fetch and auto-refresh interval
   * Cleans up interval on unmount or when auto-refresh is disabled
   */
  useEffect(() => {
    fetchHotTrades();

    // Auto-refresh every 60 seconds if enabled
    let interval;
    if (autoRefresh) {
      interval = setInterval(() => {
        fetchHotTrades(false); // Don't show spinner for auto-refresh
      }, 60000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [fetchHotTrades, autoRefresh]);

  /**
   * Toggle expansion state for a trade card
   * If strategy is not available, it will use the embedded strategy from API
   * @param {string} tradeId - ID of trade to toggle
   * @param {Object} trade - Trade object with belief for fallback fetch
   */
  const toggleExpanded = async (tradeId, trade) => {
    const newExpanded = new Set(expandedCards);
    
    if (newExpanded.has(tradeId)) {
      newExpanded.delete(tradeId);
    } else {
      // If no strategy exists, try to fetch it from backend
      if (!trade.strategy && trade.belief) {
        try {
          // Call backend endpoint to generate strategy for this belief
          const response = await fetch(`${API_BASE}/process_belief`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              model: 'murad',
              belief: trade.belief,
              ticker: trade.ticker
            })
          });
          
          if (response.ok) {
            const strategy = await response.json();
            // Update the trade with the fetched strategy
            setTrades(prev => prev.map(t => 
              t.id === tradeId ? { ...t, strategy } : t
            ));
          }
        } catch (err) {
          console.error('Failed to fetch strategy:', err);
          // Continue anyway - just show expanded card without strategy details
        }
      }
      newExpanded.add(tradeId);
    }
    
    setExpandedCards(newExpanded);
  };

  /**
   * Navigate to ChatInterface with pre-filled belief
   * @param {string} belief - Belief text to pass as URL param
   */
  const openInChat = (belief) => {
    navigate(`/chat?belief=${encodeURIComponent(belief)}`);
  };

  /**
   * Format timestamp into human-readable relative time
   * @param {string} timestamp - ISO timestamp
   * @returns {string} Formatted time (e.g., "5m ago", "2h ago")
   */
  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return date.toLocaleDateString();
  };

  /**
   * Get sentiment display properties (icon, color, label)
   * Handles various sentiment formats (string, number, keywords)
   * @param {string|number} sentiment - Sentiment value from API
   * @returns {Object} Display properties for sentiment badge
   */
  const getSentimentDisplay = (sentiment) => {
    const normalized = String(sentiment).toLowerCase();
    
    if (normalized.includes('pos') || normalized === 'bullish' || Number(sentiment) > 0) {
      return { icon: TrendingUp, color: 'text-green-400', bg: 'bg-green-900/30', label: 'Bullish' };
    }
    if (normalized.includes('neg') || normalized === 'bearish' || Number(sentiment) < 0) {
      return { icon: TrendingDown, color: 'text-red-400', bg: 'bg-red-900/30', label: 'Bearish' };
    }
    return { icon: Minus, color: 'text-gray-400', bg: 'bg-gray-900/30', label: 'Neutral' };
  };

  // Render loading skeleton
  const renderSkeleton = () => (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {[1, 2, 3, 4, 5, 6].map(i => (
        <div key={i} className="bg-gray-900 rounded-lg p-4 animate-pulse">
          <div className="h-4 bg-gray-800 rounded w-3/4 mb-2"></div>
          <div className="h-3 bg-gray-800 rounded w-1/2 mb-4"></div>
          <div className="h-16 bg-gray-800 rounded mb-4"></div>
          <div className="flex gap-2">
            <div className="h-8 bg-gray-800 rounded w-20"></div>
            <div className="h-8 bg-gray-800 rounded w-20"></div>
          </div>
        </div>
      ))}
    </div>
  );

  // Render strategy details
  const renderStrategyDetails = (strategy) => {
    if (!strategy) return null;

    return (
      <div className="mt-4 p-4 bg-gray-800/50 rounded-lg border border-gray-700">
        <h4 className="text-sm font-semibold text-gray-300 mb-3">Strategy Details</h4>
        
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-blue-400" />
            <span className="text-gray-400">Type:</span>
            <span className="text-white font-medium">{strategy.type || 'Options Strategy'}</span>
          </div>
          
          {strategy.expiration && (
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-yellow-400" />
              <span className="text-gray-400">Expiration:</span>
              <span className="text-white">{strategy.expiration}</span>
            </div>
          )}
          
          {strategy.target_return && (
            <div className="flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-green-400" />
              <span className="text-gray-400">Target Return:</span>
              <span className="text-green-400 font-medium">{strategy.target_return}%</span>
            </div>
          )}
          
          {strategy.legs && strategy.legs.length > 0 && (
            <div className="mt-3">
              <p className="text-gray-400 mb-2">Trade Legs:</p>
              <div className="space-y-1">
                {strategy.legs.map((leg, idx) => (
                  <div key={idx} className="flex items-center gap-2 text-xs bg-gray-900/50 p-2 rounded">
                    <span className={leg.action === 'buy' ? 'text-green-400' : 'text-red-400'}>
                      {leg.action?.toUpperCase()}
                    </span>
                    <span className="text-white">{leg.quantity || 1}x</span>
                    <span className="text-gray-300">{leg.type || 'OPTION'}</span>
                    {leg.strike && <span className="text-gray-400">${leg.strike}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {strategy.max_profit && (
            <div className="flex justify-between pt-2 border-t border-gray-700">
              <span className="text-gray-400">Max Profit:</span>
              <span className="text-green-400">${strategy.max_profit}</span>
            </div>
          )}
          
          {strategy.max_loss && (
            <div className="flex justify-between">
              <span className="text-gray-400">Max Loss:</span>
              <span className="text-red-400">${strategy.max_loss}</span>
            </div>
          )}
        </div>
      </div>
    );
  };

  // Render trade card
  const renderTradeCard = (trade) => {
    const sentimentDisplay = getSentimentDisplay(trade.sentiment);
    const SentimentIcon = sentimentDisplay.icon;
    const isExpanded = expandedCards.has(trade.id);

    return (
      <div key={trade.id} className="bg-gray-900 rounded-lg p-4 border border-gray-800 hover:border-gray-700 transition-all">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold text-blue-400">{trade.ticker}</span>
            <span className="text-xs text-gray-500">{trade.source}</span>
          </div>
          <span className="text-xs text-gray-500 flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formatTime(trade.createdAt)}
          </span>
        </div>

        {/* Headline/Belief */}
        <p className="text-sm text-gray-300 mb-3 line-clamp-3">
          {trade.belief || trade.headline}
        </p>

        {/* Metrics */}
        <div className="flex items-center gap-3 mb-4">
          <div className={`flex items-center gap-1 px-2 py-1 rounded-full ${sentimentDisplay.bg}`}>
            <SentimentIcon className={`w-3 h-3 ${sentimentDisplay.color}`} />
            <span className={`text-xs font-medium ${sentimentDisplay.color}`}>
              {sentimentDisplay.label}
            </span>
          </div>
          
          {trade.confidence > 0 && (
            <div className="flex items-center gap-1">
              <div className="w-16 h-2 bg-gray-800 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-blue-500 transition-all"
                  style={{ width: `${Math.min(100, trade.confidence)}%` }}
                />
              </div>
              <span className="text-xs text-gray-400">{trade.confidence}%</span>
            </div>
          )}
        </div>

        {/* Strategy Preview (if expanded) */}
        {isExpanded && renderStrategyDetails(trade.strategy)}

        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={() => toggleExpanded(trade.id, trade)}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors text-sm font-medium text-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label={isExpanded ? "Hide strategy details" : "Preview strategy details"}
          >
            <Eye className="w-4 h-4" />
            {isExpanded ? 'Hide' : 'Preview'} Strategy
          </button>
          
          <button
            onClick={() => openInChat(trade.belief)}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg transition-colors text-sm font-medium text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label="Open trade in chat interface"
          >
            <MessageSquare className="w-4 h-4" />
            Open in Chat
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-black text-white p-4 pb-24">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Flame className="w-8 h-8 text-orange-500" />
              Hot Trades
            </h1>
            
            <div className="flex items-center gap-3">
              {/* Auto-refresh toggle */}
              <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="w-4 h-4 text-blue-600 bg-gray-800 border-gray-600 rounded focus:ring-blue-500"
                />
                Auto-refresh
              </label>
              
              {/* Manual refresh button */}
              <button
                onClick={() => fetchHotTrades(true)}
                disabled={refreshing}
                className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                aria-label="Refresh hot trades"
              >
                <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>
          </div>
          
          <p className="text-gray-400">News-driven strategies from Alpaca + our AI engine</p>
        </div>

        {/* Error state */}
        {error && (
          <div className="mb-6 p-4 bg-red-900/20 border border-red-800 rounded-lg flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400" />
            <span className="text-red-400">{error}</span>
            <button
              onClick={() => fetchHotTrades()}
              className="ml-auto px-3 py-1 bg-red-800 hover:bg-red-700 rounded text-sm font-medium transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Content */}
        {loading ? (
          renderSkeleton()
        ) : trades.length === 0 ? (
          <div className="text-center py-12">
            <Flame className="w-16 h-16 text-gray-600 mx-auto mb-4" />
            <p className="text-gray-400 text-lg">No hot trades available</p>
            <p className="text-gray-500 text-sm mt-2">Check back soon for new opportunities</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {trades.map(trade => renderTradeCard(trade))}
          </div>
        )}
      </div>
      <BottomNavigation />
    </div>
  );
};

export default HotTrades;

