// frontend/src/components/DebugDashboard.jsx
// 🔧 REAL-TIME BACKEND DEBUG DASHBOARD COMPONENT
// PURPOSE: Provides live monitoring of API performance, error tracking, and strategy quality metrics
// USAGE: Displays as floating button that expands to full debug panel on click
// DATA SOURCE: Fetches from /debug/logs/latest endpoint every 3 seconds when visible
// QA NOTES: All metrics are real-time, component handles connection failures gracefully

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

const DebugDashboard = ({ BACKEND_URL }) => {
  // 📊 STATE MANAGEMENT: Store logs and performance metrics from backend
  const [logs, setLogs] = useState([]);
  const [metrics, setMetrics] = useState({
    avgResponseTime: 0,     // Average API response time in seconds
    errorCount: 0,          // Total number of errors detected
    successRate: 0,         // Percentage of successful API calls
    strategies: { good: [], bad: [] }  // Strategy quality tracking
  });
  // 🎛️ UI STATE: Controls visibility of debug panel (starts hidden)
  const [isVisible, setIsVisible] = useState(false);

  // 🔄 DATA FETCHING: Auto-refresh metrics every 3 seconds when panel is visible
  useEffect(() => {
    const fetchLogs = async () => {
      try {
        // 📡 API CALL: Fetch latest performance data from backend debug endpoint
        const response = await fetch(`${BACKEND_URL}/debug/logs/latest`);
        const data = await response.json();
        
        // 💾 STATE UPDATE: Store fetched data in component state
        setLogs(data.logs || []);
        setMetrics(data.metrics || metrics);
      } catch (error) {
        // 🚨 ERROR HANDLING: Log fetch failures without breaking UI
        console.error('Failed to fetch debug metrics:', error);
      }
    };

    // 🔄 POLLING LOGIC: Only fetch data when debug panel is visible to save resources
    if (isVisible) {
      fetchLogs(); // Initial fetch
      const interval = setInterval(fetchLogs, 3000); // Auto-refresh every 3 seconds
      return () => clearInterval(interval); // Cleanup on unmount
    }
  }, [isVisible, BACKEND_URL]);

  // 🎛️ COLLAPSED STATE: Show floating debug button when panel is hidden
  if (!isVisible) {
    return (
      <motion.button
        onClick={() => setIsVisible(true)}
        className="fixed bottom-20 right-4 bg-purple-600 text-white p-3 rounded-full shadow-lg z-50"
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
      >
        🔧 Debug
      </motion.button>
    );
  }

  // 🎛️ EXPANDED STATE: Full debug dashboard panel
  return (
    <motion.div
      initial={{ x: '100%' }}           // Animation: slide in from right
      animate={{ x: 0 }}
      className="fixed top-0 right-0 w-96 h-full bg-slate-900 border-l border-slate-600 p-4 overflow-y-auto z-50"
    >
      {/* 🎯 HEADER: Title and close button */}
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold text-white">🔧 Backend Debug</h2>
        <button
          onClick={() => setIsVisible(false)}
          className="text-slate-400 hover:text-white"
        >
          ✕
        </button>
      </div>

      {/* 📊 PERFORMANCE METRICS SECTION: Key performance indicators */}
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-blue-400 mb-3">📊 Performance</h3>
        <div className="grid grid-cols-2 gap-3">
          {/* ⏱️ AVERAGE RESPONSE TIME: Color-coded by performance thresholds */}
          <div className="bg-slate-800 p-3 rounded">
            <div className="text-xs text-slate-400">Avg Response</div>
            <div className={`text-lg font-bold ${
              metrics.avgResponseTime > 5 ? 'text-red-400' :     // Red if > 5 seconds (slow)
              metrics.avgResponseTime > 3 ? 'text-yellow-400' :  // Yellow if > 3 seconds (moderate)
              'text-green-400'                                   // Green if < 3 seconds (fast)
            }`}>
              {metrics.avgResponseTime.toFixed(2)}s
            </div>
          </div>
          
          {/* ✅ SUCCESS RATE: Color-coded by reliability thresholds */}
          <div className="bg-slate-800 p-3 rounded">
            <div className="text-xs text-slate-400">Success Rate</div>
            <div className={`text-lg font-bold ${
              metrics.successRate > 90 ? 'text-green-400' :     // Green if > 90% (excellent)
              metrics.successRate > 70 ? 'text-yellow-400' :    // Yellow if > 70% (acceptable)
              'text-red-400'                                     // Red if < 70% (poor)
            }`}>
              {metrics.successRate.toFixed(1)}%
            </div>
          </div>
        </div>
      </div>

      {/* 🚨 ERROR TRACKING SECTION: Shows breakdown of error types */}
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-red-400 mb-3">🚨 Error Summary</h3>
        <div className="space-y-2">
          {/* 🔄 DYNAMIC ERROR LIST: Maps through all error types and their counts */}
          {Object.entries(metrics.errorTypes || {}).map(([type, count]) => (
            <div key={type} className="flex justify-between bg-slate-800 p-2 rounded">
              <span className="text-slate-300">{type}</span>
              <span className="text-red-400 font-bold">{count}</span>
            </div>
          ))}
          {/* 🎉 NO ERRORS STATE: Show success message when no errors detected */}
          {Object.keys(metrics.errorTypes || {}).length === 0 && (
            <div className="text-slate-400 text-sm">No errors detected ✅</div>
          )}
        </div>
      </div>

      {/* 📈 STRATEGY QUALITY SECTION: Track good vs bad AI-generated strategies */}
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-green-400 mb-3">📈 Strategy Quality</h3>
        
        {/* ✅ GOOD STRATEGIES SUBSECTION */}
        <div className="mb-4">
          <h4 className="text-sm font-semibold text-green-300 mb-2">
            ✅ Good ({metrics.strategies.good.length})
          </h4>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {/* 🔄 DYNAMIC GOOD STRATEGIES LIST: Show up to 5 recent good strategies */}
            {metrics.strategies.good.slice(0, 5).map((strategy, idx) => (
              <div key={idx} className="bg-green-900/30 p-2 rounded text-xs">
                <div className="text-green-300 font-bold">{strategy.type}</div>
                <div className="text-slate-400">{strategy.ticker} • {strategy.confidence}%</div>
              </div>
            ))}
            {/* 🔄 EMPTY STATE: Message when no good strategies exist yet */}
            {metrics.strategies.good.length === 0 && (
              <div className="text-slate-400 text-xs">No good strategies yet</div>
            )}
          </div>
        </div>

        {/* ❌ BAD STRATEGIES SUBSECTION */}
        <div>
          <h4 className="text-sm font-semibold text-red-300 mb-2">
            ❌ Bad ({metrics.strategies.bad.length})
          </h4>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {/* 🔄 DYNAMIC BAD STRATEGIES LIST: Show up to 5 recent bad strategies */}
            {metrics.strategies.bad.slice(0, 5).map((strategy, idx) => (
              <div key={idx} className="bg-red-900/30 p-2 rounded text-xs">
                <div className="text-red-300 font-bold">{strategy.type}</div>
                <div className="text-slate-400">{strategy.ticker} • {strategy.issue}</div>
              </div>
            ))}
            {/* 🔄 EMPTY STATE: Message when no bad strategies detected */}
            {metrics.strategies.bad.length === 0 && (
              <div className="text-slate-400 text-xs">No bad strategies detected</div>
            )}
          </div>
        </div>
      </div>

      {/* 📋 LIVE LOGS SECTION: Real-time API call logs with timestamps */}
      <div>
        <h3 className="text-lg font-semibold text-slate-300 mb-3">📋 Live Logs</h3>
        <div className="space-y-1 max-h-96 overflow-y-auto">
          {/* 🔄 DYNAMIC LOGS LIST: Show last 20 log entries with color coding */}
          {logs.slice(-20).map((log, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, x: 20 }}    // Animation: fade in from right
              animate={{ opacity: 1, x: 0 }}
              className={`p-2 rounded text-xs font-mono ${
                log.level === 'ERROR' ? 'bg-red-900/30 text-red-300' :        // Red for errors
                log.level === 'WARNING' ? 'bg-yellow-900/30 text-yellow-300' : // Yellow for warnings
                log.level === 'SUCCESS' ? 'bg-green-900/30 text-green-300' :   // Green for success
                'bg-slate-800 text-slate-300'                                  // Default gray
              }`}
            >
              {/* 🔄 LOG ENTRY HEADER: Level and timestamp */}
              <div className="flex justify-between">
                <span className="font-bold">{log.level}</span>
                <span className="text-slate-500">{log.timestamp}</span>
              </div>
              {/* 📝 LOG MESSAGE: Main log content */}
              <div>{log.message}</div>
              {/* ⏱️ DURATION INFO: Show timing data if available */}
              {log.duration && (
                <div className="text-slate-500">⏱️ {log.duration}</div>
              )}
            </motion.div>
          ))}
          {/* 🔄 EMPTY STATE: Message when no logs available */}
          {logs.length === 0 && (
            <div className="text-slate-400 text-sm">No logs yet. Make an API call to see data.</div>
          )}
        </div>
      </div>

      {/* 🔄 REFRESH BUTTON: Manual refresh option for debug data */}
      <motion.button
        onClick={() => window.location.reload()}
        className="w-full mt-4 bg-blue-600 text-white p-3 rounded font-bold"
        whileTap={{ scale: 0.95 }}
      >
        🔄 Refresh Debug Data
      </motion.button>
    </motion.div>
  );
};

export default DebugDashboard;