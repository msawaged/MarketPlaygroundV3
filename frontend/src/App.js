// frontend/src/App.js

import React, { useState } from 'react';

function App() {
  const [belief, setBelief] = useState('');         // Holds user input
  const [response, setResponse] = useState(null);   // Holds backend response

  // Handles submission of belief to backend
  const handleSubmit = async (e) => {
    e.preventDefault(); // Prevent default form refresh

    try {
      // Use relative URL — assumes proxy is set to backend in package.json
      const res = await fetch('/strategy/process_belief', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ belief }), // Send: { "belief": "..." }
      });

      if (!res.ok) {
        const err = await res.text();
        setResponse({ error: `Server Error: ${res.status} - ${err}` });
        return;
      }

      const data = await res.json(); // Extract response data
      setResponse(data);
    } catch (err) {
      setResponse({ error: 'Failed to fetch (backend unreachable)' });
    }
  };

  return (
    <div style={{ padding: '2rem', fontFamily: 'Arial, sans-serif' }}>
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
          <h3>📡 Response from Backend:</h3>
          <pre
            style={{
              background: '#f4f4f4',
              padding: '1rem',
              borderRadius: '5px',
              maxWidth: '600px',
            }}
          >
            {JSON.stringify(response, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default App;
