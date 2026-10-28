// The original strategy generator ("Classic view"), with the 2D/3D simulated charts.
// Loaded on demand so its 3D and chart libraries don't slow down the rest of the app.
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import SimulatedChart from './SimulatedChart';
import SimulatedChart3D from './SimulatedChart3D';
import { API_BASE as BACKEND_URL } from '../lib/api';
import '../App.css';

export default function GeneratorPage() {
  const navigate = useNavigate(); // ✅ This enables the 🛠️ button to work

  // === 💾 State Hooks ===
  const [belief, setBelief] = useState('');
  const [userId, setUserId] = useState('');
  const [response, setResponse] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loopStatus, setLoopStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [showSimulation, setShowSimulation] = useState(false);
  const [leaderboard, setLeaderboard] = useState([]); // 🆕 Live leaderboard data
  const [show3DChart, setShow3DChart] = useState(false); // 🆕 Toggle for 3D chart

  // === 🔁 On Load: Fetch AI loop + logs + leaderboard
  useEffect(() => {
    fetchLoopStatus();
    fetchRecentLogs();
    fetchLeaderboard(); // 🆕 Load leaderboard from backend
  }, []);

  // === 🧠 GET /debug/ai_loop_status
  const fetchLoopStatus = () => {
    fetch(`${BACKEND_URL}/debug/ai_loop_status`)
      .then((res) => res.json())
      .then((data) => setLoopStatus(data))
      .catch((err) => console.error('Loop status fetch error:', err));
  };

  // === 📜 GET /logs/recent
  const fetchRecentLogs = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/logs/recent`);
      const contentType = res.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        const data = await res.json();
        setLogs(data.logs || []);
      } else {
        console.warn('⚠️ Unexpected content-type from /logs/recent:', contentType);
      }
    } catch (err) {
      console.error('Log fetch error:', err);
    }
  };

  // === 🏆 GET /debug/strategy_leaderboard
  const fetchLeaderboard = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/debug/strategy_leaderboard`);
      const data = await res.json();
      setLeaderboard(Array.isArray(data) ? data : Array.isArray(data?.leaderboard) ? data.leaderboard : []);
    } catch (err) {
      console.error('Leaderboard fetch error:', err);
    }
  };

  // === 🚀 POST /strategy/process_belief
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

  // === 👍👎 POST /feedback/submit_feedback
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
  console.log("🔁 Render block A");

  return (
    <div className="mp-classic" style={{ backgroundColor: '#0f172a', color: '#f8fafc', minHeight: '100vh', padding: '2rem', paddingBottom: '6rem' }}>
  <h1 style={{ fontSize: '2rem', fontWeight: 'bold', marginBottom: '1rem' }}>
    MarketPlayground · Classic view
  </h1>
  <p style={{ marginBottom: '2rem', color: '#94a3b8' }}>
    Enter your belief and watch the strategy unfold
  </p>


      <button
  onClick={() => navigate('/strategy-ops')}
  style={{
    marginBottom: '2rem',
    backgroundColor: '#facc15',
    color: '#000',
    padding: '0.5rem 1rem',
    fontWeight: 'bold',
    borderRadius: '6px',
    border: 'none',
    cursor: 'pointer',
  }}
>
  🛠️ Strategy Ops Page
</button>

{/* === 🔥 Hot Trades Navigation Button === */}
<button
  onClick={() => navigate('/hot-trades')} // Route to /hot-trades
  style={{
    marginBottom: '2rem',
    backgroundColor: '#f97316', // Orange background
    color: '#fff',
    padding: '0.5rem 1rem',
    fontWeight: 'bold',
    borderRadius: '6px',
    border: 'none',
    cursor: 'pointer',
    marginLeft: '1rem', // Creates spacing if buttons align horizontally
  }}
>
  🔥 View Hot Trades
</button>

      {/* === 🧠 AI Loop Status + 🏆 Leaderboard Row === */}
      {loopStatus && (
        <div style={{
          display: 'flex',
          flexDirection: 'row',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          gap: '1rem',
          marginBottom: '2rem'
        }}>
          {/* ✅ AI Loop Box */}
          <div style={{
            flex: '1 1 300px',
            backgroundColor: '#1e293b',
            padding: '1rem',
            borderRadius: '8px',
            boxShadow: '0 0 10px #334155',
            minWidth: '280px'
          }}>
            <h3 style={{ fontWeight: 'bold' }}>🧠 AI Loop Status Dashboard</h3>
            <p><strong>📝 Last Belief:</strong> {loopStatus.last_strategy?.belief}</p>
            <p><strong>📈 Last Strategy:</strong> {loopStatus.last_strategy?.strategy?.type}</p>
            <p><strong>📊 Feedback Entries:</strong> {loopStatus.feedback_count}</p>
            <p><strong>📰 News Beliefs Ingested:</strong> {loopStatus.news_beliefs_ingested}</p>
            <p><strong>🛠️ Last Retrain:</strong> {loopStatus.last_retrain?.timestamp}</p>
          </div>

          {/* ✅ Live Strategy Leaderboard */}
          <div style={{
            flex: '1 1 300px',
            backgroundColor: '#0f172a',
            padding: '1rem',
            borderRadius: '8px',
            boxShadow: '0 0 10px #22d3ee',
            minWidth: '280px',
            color: '#f8fafc'
          }}>
            <h3 style={{ fontWeight: 'bold' }}>📈 Strategy Leaderboard</h3>
            <p>Top trending strategies based on frequency:</p>
            <ul style={{ listStyle: 'none', paddingLeft: 0, marginTop: '1rem' }}>
              {leaderboard.length === 0 ? (
                <li>Loading...</li>
              ) : (
                leaderboard.map((item, index) => (
                  <li key={index}>🥇 {item.strategy} — <strong>{item.count}</strong></li>
                ))
              )}
            </ul>
          </div>
        </div>
      )}

      {/* 📜 Recent Logs Section */}
      {logs.length > 0 && (
        <div style={{ backgroundColor: '#1e1b4b', padding: '1rem', borderRadius: '8px', marginBottom: '2rem', boxShadow: '0 0 10px #4c1d95' }}>
          <h3 style={{ fontWeight: 'bold' }}>📜 Recent Training Logs</h3>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {logs.slice(0, 5).map((log, idx) => (
              <li key={idx} style={{ marginBottom: '0.5rem', fontSize: '0.9rem' }}>
                🕒 <strong>{log.timestamp}</strong><br />
                <code style={{ color: '#a78bfa' }}>{log.message}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 🎯 Belief Input */}
      <form onSubmit={handleSubmit} style={{ marginBottom: '2rem' }}>
        <div style={{ marginBottom: '1rem' }}>
          <label htmlFor="beliefInput" style={{ fontWeight: 'bold' }}>🎯 Market Belief</label><br />
          <input
            id="beliefInput"
            type="text"
            value={belief}
            onChange={(e) => setBelief(e.target.value)}
            placeholder="e.g. TSLA will go up"
            style={{
              padding: '0.5rem',
              width: '100%',
              maxWidth: '400px',
              fontSize: '1rem',
              backgroundColor: '#1e293b',
              color: '#f8fafc',
              border: '1px solid #475569',
              borderRadius: '4px'
            }}
          />
          <button
            type="button"
            onClick={() => {
              const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
              if (!SpeechRecognition) return alert("Speech Recognition not supported.");
              const recognition = new SpeechRecognition();
              recognition.lang = 'en-US';
              recognition.interimResults = false;
              recognition.maxAlternatives = 1;
              recognition.onresult = (event) => setBelief(event.results[0][0].transcript);
              recognition.onerror = (event) => alert('Speech recognition error: ' + event.error);
              recognition.start();
            }}
            style={{
              marginTop: '0.5rem',
              backgroundColor: '#facc15',
              color: '#000',
              padding: '0.4rem 1rem',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 'bold',
              borderRadius: '4px'
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
            style={{
              padding: '0.5rem',
              width: '100%',
              maxWidth: '400px',
              fontSize: '1rem',
              backgroundColor: '#1e293b',
              color: '#f8fafc',
              border: '1px solid #475569',
              borderRadius: '4px'
            }}
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          style={{
            padding: '0.5rem 1rem',
            fontSize: '1rem',
            backgroundColor: '#3b82f6',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: 'bold'
          }}
        >
          {loading ? 'Loading...' : 'Submit'}
        </button>
      </form>

      {/* 📡 Strategy Result Section */}
      {response && (
        <div>
          <h3>📡 Strategy Breakdown:</h3>
          {response.error ? (
            <p style={{ color: 'red' }}>{response.error}</p>
          ) : (
            <div style={{
              backgroundColor: '#1e293b',
              color: '#f8fafc',
              padding: '1.5rem',
              borderRadius: '12px',
              lineHeight: '1.6',
              marginTop: '1rem',
              boxShadow: '0 0 20px rgba(59,130,246,0.5)'
            }}>
              <p>
               <strong>🧠 Strategy:</strong> {response.strategy[currentIndex].type}{' '}
                <span style={{
                  backgroundColor: response.strategy[currentIndex].source === 'ml_model' ? '#f87171' : '#34d399',
                  color: '#000',
                  padding: '0.2rem 0.5rem',
                  marginLeft: '0.5rem',
                  borderRadius: '6px',
                  fontWeight: 'bold',
                  fontSize: '0.8rem'
                }}>
                  {response.strategy[currentIndex].source === 'ml_model'
                    ? '📊 ML Model'
                    : response.strategy[currentIndex].source === 'gpt_soft_parse'
                    ? '🧬 GPT Parsed'
                    : '✅ GPT JSON'}
                </span>
              </p>

              <p><strong>📉 Type:</strong> {response.strategy[currentIndex].trade_legs?.[0]?.instrument || parseOptionType(response.strategy[currentIndex].trade_legs?.[0])}</p>
              <p><strong>💥 Strike:</strong> {response.strategy[currentIndex].trade_legs?.[0]?.strike || parseStrike(response.strategy[currentIndex].trade_legs?.[0])}</p>
              <p><strong>🧾 Quantity:</strong> {response.strategy[currentIndex].trade_legs?.[0]?.quantity || parseQuantity(response.strategy[currentIndex].trade_legs?.[0])}</p>

              <p><strong>📝 Description:</strong> {response.strategy[currentIndex].description}</p>
              <p><strong>📌 Tags:</strong> {response.tags?.join(', ') || 'N/A'}</p>
              <p><strong>🎯 Ticker:</strong> {response.ticker}</p>
              <p>
                <strong>🧠 Asset Class:</strong>{' '}
                <span style={{
                  backgroundColor:
                    response.asset_class === 'options' ? '#0ea5e9' :
                    response.asset_class === 'equity' ? '#10b981' :
                    response.asset_class === 'bonds' ? '#6366f1' :
                    response.asset_class === 'crypto' ? '#ec4899' :
                    '#94a3b8',
                  color: 'white',
                  padding: '0.25rem 0.5rem',
                  borderRadius: '0.5rem',
                  fontSize: '0.85rem',
                  marginLeft: '0.5rem'
                }}>
                  {response.asset_class.toUpperCase()}
                </span>
              </p>


                      {/* ✅ Extra breakdown for option strategies */}
        {response.asset_class === "options" && response.strategy?.trade_legs && (
          <div style={{
            backgroundColor: '#334155',
            padding: '1rem',
            marginTop: '1.5rem',
            borderRadius: '10px',
            boxShadow: '0 0 12px rgba(148,163,184,0.3)'
          }}>
            <h4 style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>🧾 Option Trade Details</h4>
            
            <p><strong>Ticker:</strong> {response.ticker}</p>
            <p><strong>Type:</strong> {response.strategy.trade_legs[0].instrument || parseOptionType(response.strategy.trade_legs[0])}</p>
            <p><strong>Strike:</strong> {response.strategy.trade_legs[0].strike || parseStrike(response.strategy.trade_legs[0])}</p>
            <p><strong>Quantity:</strong> {response.strategy.trade_legs[0].quantity || parseQuantity(response.strategy.trade_legs[0])}</p>
            <p><strong>Expiration:</strong> {response.strategy.expiration}</p>
            <p>
              <strong>🧠 Confidence:</strong>{' '}
              <span style={{
                color: response.confidence > 0.7 ? '#22c55e' : response.confidence > 0.4 ? '#facc15' : '#f87171',
                fontWeight: 'bold'
              }}>
                {(response.confidence * 100).toFixed(1)}%
              </span>
            </p>
            
          </div>
        )}

              <p><strong>📈 Direction:</strong> {response.direction}</p>
              <p><strong>⚡ Confidence:</strong> {response.confidence?.toFixed(4)}</p>
              <p><strong>💸 Latest Price:</strong> ${response.price_info?.latest}</p>
              <p><strong>📅 Expiry:</strong> {response.expiry_date || 'N/A'}</p>
              <p><strong>🎯 Goal:</strong> {response.goal_type} {response.multiplier ? `(${response.multiplier}x)` : ''}</p>
              <p><strong>🧘 Risk Profile:</strong> {response.risk_profile}</p>
              <p><strong>📄 Explanation:</strong> {response.strategy[currentIndex].explanation}</p>

{/* 👇 INSERT THE NEW BLOCK HERE — flush with the rest of the breakdown */}
{response.strategy?.trade_legs?.length > 0 && (
  <>
    <h4 style={{ color: '#fff', fontWeight: 'bold' }}>📈 Trade Legs</h4>
    {response.strategy.trade_legs.map((leg, idx) => {
      const isOption = !!leg.option_type;
      const isEquity = !leg.option_type && !!leg.entry_price;

      return (
        <div
          key={idx}
          style={{
            backgroundColor: '#0f172a',
            padding: '0.75rem',
            marginBottom: '1rem',
            borderRadius: '8px',
            border: '1px solid #333',
          }}
        >
          <p style={{ color: '#fff' }}>
            <strong>🦵 Leg {idx + 1}:</strong> {leg.action || 'N/A'}
          </p>
          <p style={{ color: '#fff' }}>🏷️ Ticker: {leg.ticker || 'N/A'}</p>

          {isOption && (
            <>
              <p style={{ color: '#fff' }}>📝 Option Type: {leg.option_type}</p>
              <p style={{ color: '#fff' }}>💥 Strike Price: {leg.strike_price}</p>
              <p style={{ color: '#fff' }}>📅 Expiry: {leg.expiration || 'N/A'}</p>
            </>
          )}

          {isEquity && (
            <>
              <p style={{ color: '#fff' }}>💲 Entry Price: {leg.entry_price}</p>
              <p style={{ color: '#fff' }}>🔢 Quantity: {leg.quantity}</p>
            </>
          )}
        </div>
      );
    })}
  </>
)}





              {/* ✅ Conditionally show the Execute Trade button if we have a strategy */}
{response && response.strategy && (
  <button
    // ✅ On click, show an alert simulating trade execution
    onClick={() =>
      alert(
        `🚀 Executing trade: ${response.strategy.type || 'UNKNOWN'} on ${
          response.strategy.ticker || 'UNKNOWN'
        }`
      )
    }
    // ✅ Styling: green button, white text, rounded corners, margin from left
    style={{
      marginLeft: '10px',
      backgroundColor: '#10B981',  // Tailwind green-500
      color: '#ffffff',
      border: 'none',
      padding: '8px 12px',
      borderRadius: '8px',
      cursor: 'pointer',
    }}
  >
    🚀 Execute Trade
  </button>
)}

              <div style={{ marginTop: '1rem' }}>
                <button onClick={() => sendFeedback('good')} style={{ marginRight: '1rem', backgroundColor: '#22c55e', color: '#fff', border: 'none', padding: '0.5rem 1rem', borderRadius: '4px' }}>👍 Yes</button>
                <button onClick={() => sendFeedback('bad')} style={{ backgroundColor: '#ef4444', color: '#fff', border: 'none', padding: '0.5rem 1rem', borderRadius: '4px' }}>👎 No</button>
              </div>

              {response.strategy.length > 1 && (
                <div style={{ marginTop: '1rem' }}>
                  <button onClick={handlePrev} disabled={currentIndex === 0} style={{ marginRight: '1rem' }}>⬅️ Previous</button>
                  <button onClick={handleNext} disabled={currentIndex === response.strategy.length - 1}>Next ➡️</button>
                </div>
              )}

              <div style={{ marginTop: '2rem' }}>
                <button
                  onClick={() => setShowSimulation(true)}
                  style={{
                    backgroundColor: '#34d399',
                    color: '#000',
                    padding: '0.5rem 1rem',
                    fontSize: '1rem',
                    border: 'none',
                    borderRadius: '4px',
                    fontWeight: 'bold',
                    cursor: 'pointer'
                  }}
                >
                  🎬 Simulate Belief Outcome
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 🎬 Simulation Modal with 3D toggle 🆕 */}
      {showSimulation && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.9)',
          color: '#fff',
          zIndex: 1000,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '2rem'
        }}>
          <h2>🎬 Belief Simulation: {belief}</h2>
          <p>📈 Simulating: <strong>{response?.strategy[currentIndex].type}</strong></p>

          <button
            onClick={() => setShow3DChart((prev) => !prev)}
            style={{
              marginBottom: '1rem',
              backgroundColor: '#818cf8',
              color: '#fff',
              padding: '0.4rem 0.8rem',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            {show3DChart ? 'Switch to 2D View' : 'Switch to 3D View'}
          </button>

          {show3DChart ? (
            <SimulatedChart3D
              ticker={response.ticker}
              strategyType={response.strategy[currentIndex].type}
              price={response.price_info?.latest}
              confidence={response.confidence}
              assetClass={response.asset_class}
            />
          ) : (
            <SimulatedChart
              ticker={response.ticker}
              strategyType={response.strategy[currentIndex].type}
              price={response.price_info?.latest}
              confidence={response.confidence}
              assetClass={response.asset_class}
            />
          )}

          <button
            onClick={() => setShowSimulation(false)}
            style={{ marginTop: '2rem', backgroundColor: '#f87171', padding: '0.5rem 1rem', borderRadius: '4px' }}
          >
            ❌ Close Simulation
          </button>
        </div>
      )}
    </div>
  );
}
