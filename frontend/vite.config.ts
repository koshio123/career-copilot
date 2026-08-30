/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // Same-origin API in dev: forward /api to the FastAPI server. In production
    // CloudFront routes /api/* to API Gateway and everything else to the SPA.
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/setupTests.ts'],
    css: false,
  },
})
