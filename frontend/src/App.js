// frontend/src/App.js

import React, { useState, useEffect } from 'react';
import './App.css';
import SimulatedChart from './components/SimulatedChart';

/**
 * ✅ Smart backend routing logic:
 * - Uses .env variable if it's clearly set to a Render URL
 * - Falls back to localhost if in dev
 * - Defaults to Render cloud URL if deployed
 */
const BACKEND_URL =
  process.env.REACT_APP_BACKEND_URL?.includes('render.com')
    ? process.env.REACT_APP_BACKEND_URL
    : window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : 'https://marketplayground-backend.onrender.com';

function App() {
  const [belief, setBelief] = useState('');
  const [userId, setUserId] = useState('');
  const [response, setResponse] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loopStatus, setLoopStatus] = useState(null);
  const [showSimulation, setShowSimulation] = useState(false);
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    fetchLoopStatus();
    fetchRecentLogs();
  }, []);

  const fetchLoopStatus = () => {
    fetch(`${BACKEND_URL}/debug/ai_loop_status`)
      .then((res) => res.json())
      .then((data) => setLoopStatus(data))
      .catch((err) => console.error('Loop status fetch error:', err));
  };

  const fetchRecentLogs = () => {
    fetch(`${BACKEND_URL}/logs/recent`)
      .then((res) => res.json())
      .then((data) => setLogs(data.logs || []))
      .catch((err) => console.error('Log fetch error:', err));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResponse(null);

    try {
      const res = await fetch(`${BACKEND_URL}/strategy/process_belief`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          belief,
          user_id: userId.trim() || 'anonymous',
        }),
      });

      const data = await res.json();
      const strategies = Array.isArray(data.strategy) ? data.strategy : [data.strategy];
      setResponse({ ...data, strategy: strategies });
      setCurrentIndex(0);
      fetchLoopStatus();
    } catch {
      setResponse({ error: '❌ Failed to reach backend. Check deployment.' });
    } finally {
      setLoading(false);
    }
  };

  const handleNext = () => {
    setCurrentIndex((prev) => Math.min(prev + 1, response.strategy.length - 1));
  };

  const handlePrev = () => {
    setCurrentIndex((prev) => Math.max(prev - 1, 0));
  };

  const sendFeedback = async (feedbackType) => {
    const currentStrategy = response.strategy[currentIndex];
    const payload = {
      belief,
      strategy: currentStrategy.type,
      feedback: feedbackType,
      tags: response.tags || [],
      ticker: response.ticker,
      asset_class: response.asset_class,
      direction: response.direction,
      confidence: response.confidence,
      user_id: userId.trim() || 'anonymous',
    };

    try {
      const res = await fetch(`${BACKEND_URL}/feedback/submit_feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const result = await res.json();
      alert(result.message || '✅ Feedback submitted');
      fetchLoopStatus();
    } catch {
      alert('❌ Feedback submission failed');
    }
  };

  return (
    <div style={{ padding: '2rem', fontFamily: 'Arial, sans-serif', maxWidth: '800px', margin: 'auto' }}>
      <h1>🚀 MarketPlayground <span role="img" aria-label="brain">🧠</span></h1>
      <p>Enter your belief and watch the strategy unfold</p>

      {loopStatus && (
        <div style={{ backgroundColor: '#eef7ff', padding: '1rem', borderRadius: '8px', marginBottom: '2rem' }}>
          <h3>🧠 AI Loop Status Dashboard</h3>
          <p><strong>📝 Last Belief:</strong> {loopStatus.last_strategy?.belief}</p>
          <p><strong>📈 Last Strategy:</strong> {loopStatus.last_strategy?.strategy?.type}</p>
          <p><strong>📊 Feedback Entries:</strong> {loopStatus.feedback_count}</p>
          <p><strong>📰 News Beliefs Ingested:</strong> {loopStatus.news_beliefs_ingested}</p>
          <p><strong>🛠️ Last Retrain:</strong> {loopStatus.last_retrain?.timestamp}</p>
        </div>
      )}

      {logs.length > 0 && (
        <div style={{ backgroundColor: '#fefbe7', padding: '1rem', borderRadius: '8px', marginBottom: '2rem' }}>
          <h3>📜 Recent Training Logs</h3>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {logs.slice(0, 5).map((log, idx) => (
              <li key={idx} style={{ marginBottom: '0.5rem', fontSize: '0.9rem' }}>
                🕒 <strong>{log.timestamp}</strong><br />
                <code>{log.message}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 🎯 Belief Form */}
      <form onSubmit={handleSubmit} style={{ marginBottom: '2rem' }}>
        <div style={{ marginBottom: '1rem' }}>
          <label htmlFor="beliefInput" style={{ fontWeight: 'bold' }}>🎯 Market Belief</label><br />
          <input
            id="beliefInput"
            type="text"
            value={belief}
            onChange={(e) => setBelief(e.target.value)}
            placeholder="e.g. TSLA will go up"
            style={{ padding: '0.5rem', width: '300px', fontSize: '1rem' }}
          />
          <br />
          {/* 🎤 Voice Input Button */}
          <button
            type="button"
            onClick={() => {
              const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
              if (!SpeechRecognition) {
                alert("Speech Recognition not supported in this browser.");
                return;
              }

              const recognition = new SpeechRecognition();
              recognition.lang = 'en-US';
              recognition.interimResults = false;
              recognition.maxAlternatives = 1;

              recognition.onresult = (event) => {
                const spokenText = event.results[0][0].transcript;
                setBelief(spokenText);
              };

              recognition.onerror = (event) => {
                alert('Speech recognition error: ' + event.error);
              };

              recognition.start();
            }}
            style={{
              marginTop: '0.5rem',
              backgroundColor: '#ffc107',
              color: '#000',
              padding: '0.4rem 1rem',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 'bold'
            }}
          >
            🎤 Speak Belief
          </button>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label htmlFor="userIdInput">👤 Optional User ID</label><br />
          <input
            id="userIdInput"
            type="text"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="e.g. murad123"
            style={{ padding: '0.5rem', width: '300px', fontSize: '1rem' }}
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          style={{
            padding: '0.5rem 1rem',
            fontSize: '1rem',
            backgroundColor: '#007bff',
            color: '#fff',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          {loading ? 'Loading...' : 'Submit'}
        </button>
      </form>

      {/* 📡 Strategy Results */}
      {response && (
        <div>
          <h3>📡 Strategy Breakdown:</h3>
          {response.error ? (
            <p style={{ color: 'red' }}>{response.error}</p>
          ) : (
            <div style={{ background: '#f4f4f4', padding: '1rem', borderRadius: '8px', lineHeight: '1.6' }}>
              <p><strong>🧠 Strategy:</strong> {response.strategy[currentIndex].type}</p>
              <p><strong>📝 Description:</strong> {response.strategy[currentIndex].description}</p>
              <p><strong>📌 Tags:</strong> {response.tags?.join(', ') || 'N/A'}</p>
              <p><strong>🎯 Ticker:</strong> {response.ticker}</p>
              <p><strong>📊 Asset Class:</strong> {response.asset_class}</p>
              <p><strong>📈 Direction:</strong> {response.direction}</p>
              <p><strong>⚡ Confidence:</strong> {response.confidence?.toFixed(4)}</p>
              <p><strong>💸 Latest Price:</strong> ${response.price_info?.latest}</p>
              <p><strong>📅 Expiry:</strong> {response.expiry_date || 'N/A'}</p>
              <p><strong>🎯 Goal:</strong> {response.goal_type} {response.multiplier ? `(${response.multiplier}x)` : ''}</p>
              <p><strong>🧘 Risk Profile:</strong> {response.risk_profile}</p>
              <p><strong>📄 Explanation:</strong> {response.strategy[currentIndex].explanation}</p>

              {/* Feedback */}
              <div style={{ marginTop: '1rem' }}>
                <button onClick={() => sendFeedback('good')} style={{ marginRight: '1rem' }}>👍 Yes</button>
                <button onClick={() => sendFeedback('bad')}>👎 No</button>
              </div>

              {/* Strategy Nav */}
              {response.strategy.length > 1 && (
                <div style={{ marginTop: '1rem' }}>
                  <button onClick={handlePrev} disabled={currentIndex === 0} style={{ marginRight: '1rem' }}>⬅️ Previous</button>
                  <button onClick={handleNext} disabled={currentIndex === response.strategy.length - 1}>Next ➡️</button>
                </div>
              )}

              {/* Simulation */}
              <div style={{ marginTop: '2rem' }}>
                <button
                  onClick={() => setShowSimulation(true)}
                  style={{
                    backgroundColor: '#28a745',
                    color: '#fff',
                    padding: '0.5rem 1rem',
                    fontSize: '1rem',
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  🎬 Simulate Belief Outcome
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {showSimulation && (
        <div
          style={{
            position: 'fixed',
            top: 0, left: 0, right: 0, bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.85)',
            color: '#fff',
            zIndex: 1000,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '2rem'
          }}
        >
          <h2>🎬 Belief Simulation: {belief}</h2>
          <p>📈 Simulating: <strong>{response?.strategy[currentIndex].type}</strong></p>

          <SimulatedChart
            ticker={response.ticker}
            strategyType={response.strategy[currentIndex].type}
            price={response.price_info?.latest}
            confidence={response.confidence}
            assetClass={response.asset_class}
          />

          <button
            onClick={() => setShowSimulation(false)}
            style={{ marginTop: '2rem', padding: '0.5rem 1rem', fontSize: '1rem' }}
          >
            ❌ Close Simulation
          </button>
        </div>
      )}
    </div>
  );
}

export default App;
