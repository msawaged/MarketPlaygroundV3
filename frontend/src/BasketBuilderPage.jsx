// frontend/src/BasketBuilderPage.jsx
import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { API_BASE } from "./lib/api";
import BottomNavigation from './components/BottomNavigation';

const BasketBuilderPage = () => {
  const [goalText, setGoalText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [result, error]);

  const handleMicClick = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return alert("Speech recognition not supported");
    
    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    
    if (isListening) {
      recognition.stop();
      setIsListening(false);
    } else {
      recognition.start();
      setIsListening(true);
      recognition.onresult = (event) => {
        setGoalText(event.results[0][0].transcript);
        setIsListening(false);
      };
      recognition.onerror = () => {
        setIsListening(false);
      };
    }
  };

  // KEEPING EXACT API CALL STRUCTURE FROM ORIGINAL
  const handleSubmit = async () => {
    if (!goalText.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      // EXACT SAME API CALL AS ORIGINAL
      const res = await fetch(
        `${API_BASE}/basket/generate_basket`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            input_text: goalText,
            goal: goalText,
            user_id: "test_user"  // KEEPING ORIGINAL user_id
          })
        }
      );

      const data = await res.json();

      if (!res.ok) {
        const errorMessage = typeof data.detail === 'string'
          ? data.detail
          : JSON.stringify(data);
        throw new Error(errorMessage);
      }

      setResult(data);
      setError(null);
    } catch (err) {
      console.error('Backend error:', err);
      const displayError = typeof err.message === 'string' ? err.message : JSON.stringify(err);
      setError(displayError);
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const topAssets = [
    { name: "Vanguard Growth ETF", ticker: "VUG", ytd: "+17.4%", mix: "85% US Stocks / 15% Intl Stocks" },
    { name: "iShares Core Agg Bond", ticker: "AGG", ytd: "+6.2%", mix: "70% US Bonds / 30% Government Bonds" },
    { name: "ARK Innovation ETF", ticker: "ARKK", ytd: "+24.1%", mix: "100% High-Growth Tech" }
  ];

  return (
    <div className="h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white relative overflow-hidden">
      
      {/* Header - Same style as ChatInterface */}
      <motion.div 
        className="fixed top-0 left-0 right-0 z-40 bg-gradient-to-r from-slate-800/95 via-slate-900/95 to-slate-800/95 backdrop-blur-sm border-b border-blue-500/30 p-4"
        initial={{ y: -50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5 }}
      >
        <div className="flex items-center gap-3">
          <motion.div 
            className="w-10 h-10 bg-gradient-to-r from-green-500 via-emerald-600 to-teal-600 rounded-xl flex items-center justify-center shadow-lg"
            whileHover={{ rotate: 360, scale: 1.1 }}
            transition={{ duration: 0.5 }}
          >
            <span className="text-white text-xl">📊</span>
          </motion.div>
          <div>
            <h1 className="font-bold text-lg bg-gradient-to-r from-green-400 to-emerald-400 bg-clip-text text-transparent">
              AI Asset Basket Builder
            </h1>
            <p className="text-sm text-green-400">Portfolio Optimization Engine</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <motion.div 
              className="w-3 h-3 bg-green-400 rounded-full shadow-lg"
              animate={{ scale: [1, 1.3, 1], opacity: [1, 0.5, 1] }}
              transition={{ repeat: Infinity, duration: 2 }}
            />
            <span className="text-xs text-green-400 font-semibold">LIVE</span>
          </div>
        </div>
      </motion.div>

      {/* Main Content Area */}
      <div className="overflow-y-auto p-4 space-y-6" 
           style={{ 
             paddingTop: '100px',
             paddingBottom: '140px',
             height: '100vh',
             WebkitOverflowScrolling: 'touch'
           }}>

        {/* Welcome Message */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-6"
        >
          <p className="text-slate-400 text-sm">
            Describe your investment goals, risk level, or preferences. Example:
          </p>
          <code className="text-green-400 text-xs">
            "I want 70% stocks and 30% bonds for moderate growth"
          </code>
        </motion.div>

        {/* Top Performing Assets Card */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-gradient-to-br from-slate-800/95 to-slate-900/95 rounded-2xl border border-blue-500/30 overflow-hidden backdrop-blur-sm p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-white">🔥 Top Performing Asset Mixes</h2>
            <span className="text-xs text-slate-400">(YTD)</span>
          </div>

          <div className="space-y-3">
            {topAssets.map((asset, index) => (
              <motion.div
                key={index}
                className="bg-slate-700/50 rounded-lg p-4 border border-slate-600"
                whileHover={{ scale: 1.02, borderColor: '#22c55e' }}
                transition={{ duration: 0.2 }}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="font-bold text-white">{asset.name}</div>
                    <div className="text-xs text-blue-400 mt-1">{asset.ticker}</div>
                    <div className="text-xs text-slate-400 mt-1">{asset.mix}</div>
                  </div>
                  <motion.div 
                    className="bg-green-500/20 text-green-400 px-3 py-1 rounded-full text-sm font-bold border border-green-400/30"
                    whileHover={{ scale: 1.1 }}
                  >
                    {asset.ytd}
                  </motion.div>
                </div>
              </motion.div>
            ))}
          </div>

          <p className="text-xs text-slate-500 mt-4 text-center italic">
            Auto-synced from market data — Premium after beta 🚀
          </p>
        </motion.div>

        {/* Error Display */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-red-900/30 border border-red-500/30 rounded-xl p-4"
          >
            <div className="flex items-center gap-2">
              <span className="text-red-400">⚠️</span>
              <span className="text-red-300 text-sm">{error}</span>
            </div>
          </motion.div>
        )}

        {/* Loading Indicator */}
        {isLoading && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex justify-center"
          >
            <div className="bg-gradient-to-r from-slate-700/90 to-slate-800/90 px-6 py-4 rounded-2xl backdrop-blur-sm border border-slate-600/30">
              <div className="flex items-center space-x-3">
                <div className="flex space-x-1">
                  {[0, 1, 2].map((i) => (
                    <motion.div
                      key={i}
                      className="w-3 h-3 bg-green-400 rounded-full"
                      animate={{ y: [0, -10, 0] }}
                      transition={{ repeat: Infinity, duration: 0.8, delay: i * 0.15 }}
                    />
                  ))}
                </div>
                <motion.span 
                  className="text-sm text-slate-300"
                  animate={{ opacity: [0.5, 1, 0.5] }}
                  transition={{ repeat: Infinity, duration: 1.5 }}
                >
                  AI is building your optimal portfolio...
                </motion.span>
              </div>
            </div>
          </motion.div>
        )}

        {/* Result Display - USING EXACT SAME DATA STRUCTURE */}
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.4 }}
            className="bg-gradient-to-br from-slate-800/95 to-slate-900/95 rounded-2xl border border-blue-500/30 overflow-hidden backdrop-blur-sm"
          >
            <div className="bg-gradient-to-r from-green-600 via-emerald-600 to-teal-600 p-4">
              <h2 className="text-2xl font-bold text-white">📊 Suggested Asset Basket</h2>
            </div>

            <div className="p-6 space-y-4">
              {/* USING EXACT RESULT STRUCTURE FROM ORIGINAL */}
              {result.basket?.map((item, index) => (
                <motion.div
                  key={index}
                  className="bg-slate-700/50 rounded-lg p-4 border border-slate-600"
                  whileHover={{ scale: 1.02, borderColor: '#22c55e' }}
                >
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-lg font-bold text-white">{item.ticker}</span>
                    <span className="bg-green-500/20 text-green-400 px-3 py-1 rounded-full font-bold">
                      {item.allocation}
                    </span>
                  </div>
                  <p className="text-slate-400 text-sm italic">{item.rationale}</p>
                </motion.div>
              ))}

              <div className="mt-6 grid grid-cols-3 gap-3">
                <div className="bg-slate-700/30 rounded-lg p-3 text-center">
                  <div className="text-xs text-slate-400">Goal</div>
                  <div className="text-sm font-bold text-white">{result.goal}</div>
                </div>
                <div className="bg-slate-700/30 rounded-lg p-3 text-center">
                  <div className="text-xs text-slate-400">Est. Return</div>
                  <div className="text-sm font-bold text-green-400">{result.estimated_return}</div>
                </div>
                <div className="bg-slate-700/30 rounded-lg p-3 text-center">
                  <div className="text-xs text-slate-400">Risk</div>
                  <div className="text-sm font-bold text-yellow-400">{result.risk_profile}</div>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area - Same style as ChatInterface */}
      <motion.div 
        className="fixed bottom-16 left-0 right-0 z-30 px-3 pb-2"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
        initial={{ y: 100 }}
        animate={{ y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="bg-slate-800/95 backdrop-blur-md rounded-full border border-slate-700/50 shadow-xl">
          <div className="flex items-center px-4 py-3 gap-3">
            
            {/* Voice Input Button */}
            <motion.button
              type="button"
              onClick={handleMicClick}
              className={`w-8 h-8 ${isListening ? 'bg-red-500' : 'bg-purple-500'} hover:opacity-90 text-white rounded-full flex items-center justify-center transition-colors`}
              whileTap={{ scale: 0.95 }}
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
              </svg>
            </motion.button>
            
            {/* Text Input Field */}
            <input
              type="text"
              value={goalText}
              onChange={(e) => setGoalText(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Describe your investment goals..."
              className="flex-1 bg-transparent text-white placeholder-slate-400 focus:outline-none text-base"
              disabled={isLoading}
            />
            
            {/* Send Button */}
            <motion.button
              onClick={handleSubmit}
              disabled={!goalText.trim() || isLoading}
              className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
                goalText.trim() && !isLoading 
                  ? 'bg-green-500 hover:bg-green-600 text-white' 
                  : 'bg-slate-700 text-slate-500'
              }`}
              whileTap={{ scale: 0.95 }}
            >
              {isLoading ? (
                <svg className="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 4V2A10 10 0 0 0 2 12h2a8 8 0 0 1 8-8z"/>
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                </svg>
              )}
            </motion.button>
          </div>
        </div>
      </motion.div>

      {/* Bottom Navigation */}
      <BottomNavigation />
    </div>
  );
};

export default BasketBuilderPage;