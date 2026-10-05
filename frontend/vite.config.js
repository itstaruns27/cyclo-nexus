import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Dev proxy target: VITE_DEV_API_TARGET in .env.development.local (default http://localhost:3001)
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Long-lived vendor chunks cache across deploys; app code stays small
        manualChunks: {
          maplibre: ['maplibre-gl'],
          react: ['react', 'react-dom', 'react-router-dom'],
        },
      },
    },
    chunkSizeWarningLimit: 900,
  },
  server: {
    proxy: {
      '/api': {
        target: loadEnv(mode, process.cwd(), '').VITE_DEV_API_TARGET || 'http://localhost:3001',
        changeOrigin: true,
      }
    }
  }
}))
