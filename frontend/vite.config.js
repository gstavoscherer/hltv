import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/hltv/',
  server: {
    proxy: {
      '/hltv/api': {
        target: 'http://localhost:5080',
        rewrite: (path) => path.replace(/^\/hltv\/api/, '/api'),
      }
    }
  }
})
