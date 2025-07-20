// vite.config.js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// ✅ Final Vite config for MarketPlaygroundBeta
// - Enables mobile testing via 10.0.0.61:3000
// - Supports .jsx file resolution
// - Aliases @/ to /src for clean imports

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    extensions: ['.js', '.jsx', '.json'],
  },
  server: {
    host: '10.0.0.61',   // ✅ YOUR exact IP — NOT 0.0.0.0
    port: 3000,
    open: true,
  },
});
