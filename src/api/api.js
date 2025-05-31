// src/api/api.js

// 👉 Replace this IP with your Mac’s IP if different
const BACKEND_URL = 'http://10.0.0.61:5000';

/**
 * Fetches the top 5 fused trades (options + futures).
 */
export async function fusionScan() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/fusion-scan`);
    return await res.json(); // { fusion: [...] }
  } catch (err) {
    console.error('Error calling /api/fusion-scan:', err);
    return { fusion: [], error: true };
  }
}

/**
 * Plays one round of the Futures Fusion game.
 */
export async function playFusion() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/play-fusion`, { method: 'POST' });
    return await res.json(); // { message, result, ... }
  } catch (err) {
    console.error('Error calling /api/play-fusion:', err);
    return { error: true };
  }
}
