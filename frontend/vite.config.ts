import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/app/',
  server: {
    proxy: {
      // Note: browser API calls in dev typically go directly to http://localhost:8000 via API_BASE in client.ts.
      // These proxies remain for tools/tests that hit the Vite dev server origin.
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/rules': 'http://localhost:8000',
      '/adapters': 'http://localhost:8000',
      '/llm': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/feedback': 'http://localhost:8000',
      '/suggestions': 'http://localhost:8000',
    },
  },
})
