import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/admin': 'http://localhost:8000',
      '/chat':  'http://localhost:8000',
      '/quiz':  'http://localhost:8000',
    },
  },
})
