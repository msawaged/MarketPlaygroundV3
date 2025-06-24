// frontend/src/App.js

import React, { useState } from 'react';

function App() {
  const [belief, setBelief] = useState('');
  const [response, setResponse] = useState(null);

  // Function to handle belief submission
  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      const res = await fetch('http://127.0.0.1:8000/strategy/process_belief', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ belief }), // Send { "belief": "..." }
      });

      if (!res.ok) {
        const err = await res.text();
        setResponse({ error: `Server Error: ${res.status} - ${err}` });
        return;
      }

      const data = await res.json();
      setResponse(data);
    } catch (err) {
      setResponse({ error: 'Failed to fetch' });
    }
  };

  return (
    <div style={{ padding: '2rem', fontFamily: 'monospace' }}>
      <h1>MarketPlayground 🧠</h1>

      <form onSubmit={handleSubmit}>
        <label>
          Enter Your Belief:
          <input
            type="text"
            value={belief}
            onChange={(e) => setBelief(e.target.value)}
            style={{ marginLeft: '0.5rem', width: '300px' }}
          />
        </label>
        <button type="submit" style={{ marginLeft: '0.5rem' }}>Submit</button>
      </form>

      <h3 style={{ marginTop: '2rem' }}>Test Response from Backend:</h3>
      <pre>{response ? JSON.stringify(response, null, 2) : 'No response yet'}</pre>
    </div>
  );
}

export default App;
