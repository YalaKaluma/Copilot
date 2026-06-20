import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  const env = loadEnv(mode, process.cwd(), '');
  
  // Determine proxy target for development server
  // When VITE_BACKEND_URL is empty (local dev), use appropriate proxy target
  const proxyTarget = env.VITE_BACKEND_URL || 'http://backend:8080';
  
  return {
    plugins: [react(), tailwindcss()],
    test: {
      environment: 'happy-dom',
      globals: true,
      setupFiles: ['./vitest.setup.ts'],
    },
    server: {
      host: '0.0.0.0',  // Needed for Docker
      port: 3000,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          ws: true
        }
      }
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
    }
  };
});