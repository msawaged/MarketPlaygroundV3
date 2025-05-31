// backend/server.js

// Import required packages
const express = require('express');
const cors = require('cors');

// Import routes
const fusionScanRoute = require('./routes/fusionScan'); // 🧩 NEW

// Create the Express app
const app = express();
const PORT = process.env.PORT || 5000;

// Middleware setup
app.use(cors());              // Allow cross-origin requests
app.use(express.json());      // Parse JSON bodies

// Health check route
app.get('/', (req, res) => {
  res.status(200).send('✅ Market Playground backend is live');
});

// Attach fusion scan API
app.use('/api/fusion-scan', fusionScanRoute); // 🧠 This enables the endpoint

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Server running at http://0.0.0.0:${PORT}`);
});
