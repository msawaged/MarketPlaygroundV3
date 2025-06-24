// frontend/src/components/BeliefForm.js

import React, { useState } from 'react';

function BeliefForm() {
  const [belief, setBelief] = useState('');
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setResponse(null);

    try {
      const res = await fetch('http://127.0.0.1:8000/process_belief', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ belief })
      });

      if (!res.ok) throw new Error('Server error');
      const data = await res.json();
      setResponse(data);
    } catch (err) {
      setError('Backend not responding or invalid response.');
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <label htmlFor="belief"><strong>🎯 Enter a Market Belief</strong></label>
        <br />
        <input
          type="text"
          id="belief"
          value={belief}
          onChange={(e) => setBelief(e.target.value)}
          placeholder="e.g. oil is going up"
          style={{ padding: '8px', marginTop: '8px', width: '300px' }}
        />
        <button type="submit" style={{ marginLeft: '10px', padding: '8px' }}>
          Submit
        </button>
      </form>

      {response && (
        <div style={{ marginTop: '20px' }}>
          <h3>🧠 AI Response:</h3>
          <pre>{JSON.stringify(response, null, 2)}</pre>
        </div>
      )}

      {error && <div style={{ color: 'red', marginTop: '20px' }}>{error}</div>}
    </div>
  );
}

export default BeliefForm;
