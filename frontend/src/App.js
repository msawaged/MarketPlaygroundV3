import React, { useState } from 'react';

function App() {
  const [belief, setBelief] = useState('');
  const [response, setResponse] = useState(null); // Full response from backend
  const [currentIndex, setCurrentIndex] = useState(0); // Tracks current strategy index

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      const res = await fetch('/strategy/process_belief', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ belief }),
      });

      if (!res.ok) {
        const err = await res.text();
        setResponse({ error: `Server Error: ${res.status} - ${err}` });
        return;
      }

      const data = await res.json();

      // Normalize to list of strategies, even if only one
      const strategies = Array.isArray(data.strategy) ? data.strategy : [data.strategy];

      setResponse({ ...data, strategy: strategies });
      setCurrentIndex(0);
    } catch (err) {
      setResponse({ error: 'Failed to fetch (backend unreachable)' });
    }
  };

  const handleNext = () => {
    setCurrentIndex((prev) => Math.min(prev + 1, response.strategy.length - 1));
  };

  const handlePrev = () => {
    setCurrentIndex((prev) => Math.max(prev - 1, 0));
  };

  return (
    <div style={{ padding: '2rem', fontFamily: 'Arial, sans-serif', maxWidth: '800px', margin: 'auto' }}>
      <h1>🚀 MarketPlayground <span role="img" aria-label="brain">🧠</span></h1>
      <p>Enter your belief and watch the strategy unfold</p>

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
          style={{
            padding: '0.5rem',
            width: '300px',
            marginTop: '0.5rem',
            marginRight: '0.5rem',
            fontSize: '1rem',
          }}
        />
        <button
          type="submit"
          style={{
            padding: '0.5rem 1rem',
            fontSize: '1rem',
            backgroundColor: '#007bff',
            color: '#fff',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          Submit
        </button>
      </form>

      {response && (
        <div>
          <h3>📡 Strategy Breakdown:</h3>
          {response.error ? (
            <p style={{ color: 'red' }}>{response.error}</p>
          ) : (
            <div style={{ background: '#f4f4f4', padding: '1rem', borderRadius: '8px', lineHeight: '1.6' }}>
              <p><strong>🧠 Strategy:</strong> {response.strategy[currentIndex].type}</p>
              <p><strong>📝 Description:</strong> {response.strategy[currentIndex].description}</p>
              <p><strong>📌 Tags:</strong> {response.tags?.join(', ')}</p>
              <p><strong>🎯 Ticker:</strong> {response.ticker}</p>
              <p><strong>📊 Asset Class:</strong> {response.asset_class}</p>
              <p><strong>📈 Direction:</strong> {response.direction}</p>
              <p><strong>📈 Confidence:</strong> {response.confidence}</p>
              <p><strong>💸 Latest Price:</strong> ${response.price_info?.latest}</p>
              <p><strong>📅 Expiry:</strong> {response.expiry_date || 'N/A'}</p>
              <p><strong>🧾 Goal:</strong> {response.goal_type} {response.multiplier ? `(${response.multiplier}x)` : ''}</p>
              <p><strong>🧘 Risk Profile:</strong> {response.risk_profile}</p>
              <p><strong>📄 Explanation:</strong> {response.strategy[currentIndex].explanation}</p>

              {/* Navigation Buttons */}
              {response.strategy.length > 1 && (
                <div style={{ marginTop: '1rem' }}>
                  <button
                    onClick={handlePrev}
                    disabled={currentIndex === 0}
                    style={{ marginRight: '1rem' }}
                  >
                    ⬅️ Previous
                  </button>
                  <button
                    onClick={handleNext}
                    disabled={currentIndex === response.strategy.length - 1}
                  >
                    Next ➡️
                  </button>
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
