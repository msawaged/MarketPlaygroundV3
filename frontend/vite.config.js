// vite.config.js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// ✅ Fixed: Added .jsx to extensions for proper module resolution
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    extensions: ['.js', '.jsx', '.json'], // ✅ Added .jsx
  },
  server: {
    port: 3000,
    open: true,
  },
});
