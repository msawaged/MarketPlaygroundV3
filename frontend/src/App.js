// frontend/src/App.js

import React, { useState } from 'react';

function App() {
  const [belief, setBelief] = useState('');
  const [response, setResponse] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(false);

  // 🔄 Submit belief to backend
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResponse(null);

    try {
      const res = await fetch('/strategy/process_belief', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ belief }),
      });

      const data = await res.json();
      const strategies = Array.isArray(data.strategy) ? data.strategy : [data.strategy];
      setResponse({ ...data, strategy: strategies });
      setCurrentIndex(0);
    } catch {
      setResponse({ error: '❌ Backend unreachable. Is FastAPI running?' });
    } finally {
      setLoading(false);
    }
  };

  // ⏮️⏭️ Navigation
  const handleNext = () => setCurrentIndex((prev) => Math.min(prev + 1, response.strategy.length - 1));
  const handlePrev = () => setCurrentIndex((prev) => Math.max(prev - 1, 0));

  // 🧠 Send feedback to backend
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
      user_id: 'anonymous',
    };

    try {
      const res = await fetch('/feedback/submit_feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const result = await res.json();
      alert(result.message || '✅ Feedback submitted');
    } catch {
      alert('❌ Failed to submit feedback');
    }
  };

  return (
    <div style={{ padding: '2rem', fontFamily: 'Arial, sans-serif', maxWidth: '800px', margin: 'auto' }}>
      <h1>🚀 MarketPlayground <span role="img" aria-label="brain">🧠</span></h1>
      <p>Enter your belief and watch the strategy unfold</p>

      {/* 🎯 Input form */}
      <form onSubmit={handleSubmit} style={{ marginBottom: '2rem' }}>
        <label htmlFor="beliefInput" style={{ fontWeight: 'bold', fontSize: '1.1rem' }}>
          🎯 Enter a Market Belief
        </label>
        <br />
        <input
          id="beliefInput"
          type="text"
          value={belief}
          onChange={(e) => setBelief(e.target.value)}
          placeholder="e.g. TSLA will go up"
          style={{ padding: '0.5rem', width: '300px', marginTop: '0.5rem', marginRight: '0.5rem', fontSize: '1rem' }}
        />
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

      {/* 📡 AI Output */}
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
              <p><strong>⚡ Confidence:</strong> {response.confidence.toFixed(4)}</p>
              <p><strong>💸 Latest Price:</strong> ${response.price_info?.latest}</p>
              <p><strong>📅 Expiry:</strong> {response.expiry_date || 'N/A'}</p>
              <p><strong>🎯 Goal:</strong> {response.goal_type} {response.multiplier ? `(${response.multiplier}x)` : ''}</p>
              <p><strong>🧘 Risk Profile:</strong> {response.risk_profile}</p>
              <p><strong>📄 Explanation:</strong> {response.strategy[currentIndex].explanation}</p>

              {/* 👍 👎 Feedback */}
              <div style={{ marginTop: '1rem' }}>
                <button onClick={() => sendFeedback('good')} style={{ marginRight: '1rem' }}>👍 Yes</button>
                <button onClick={() => sendFeedback('bad')}>👎 No</button>
              </div>

              {/* 🔄 Navigation */}
              {response.strategy.length > 1 && (
                <div style={{ marginTop: '1rem' }}>
                  <button onClick={handlePrev} disabled={currentIndex === 0} style={{ marginRight: '1rem' }}>⬅️ Previous</button>
                  <button onClick={handleNext} disabled={currentIndex === response.strategy.length - 1}>Next ➡️</button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
