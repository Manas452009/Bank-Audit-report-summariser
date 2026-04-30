import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Spring Boot backend (auth, etc.)
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      // Python AI server – direct connection for PDF analysis
      '/ai': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ai/, ''),
      },
    },
  },
})

