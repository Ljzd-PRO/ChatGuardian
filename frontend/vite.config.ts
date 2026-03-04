import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/rules': 'http://localhost:8000',
      '/adapters': 'http://localhost:8000',
      '/llm': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/feedback': 'http://localhost:8000',
      '/suggestions': 'http://localhost:8000',
    },
  },
})
