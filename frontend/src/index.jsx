// frontend/src/index.js

// ✅ Main React entry point using React 18 and Vite
import React from 'react';
import ReactDOM from 'react-dom/client';

// ✅ Global styles including Tailwind utilities
import './index.css';

// ✅ Main App component 
import App from './App.jsx';


// ✅ Mount React app to #root element in index.html
const rootElement = document.getElementById('root');

// ✅ Use React 18 root rendering API (required by Vite setup)
const root = ReactDOM.createRoot(rootElement);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
