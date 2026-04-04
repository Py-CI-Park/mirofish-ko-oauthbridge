import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const frontendPort = Number(process.env.FRONTEND_PORT || '3000')
const backendPort = Number(process.env.BACKEND_PORT || '5001')

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: frontendPort,
    strictPort: true,
    open: true,
    proxy: {
      '/api': {
        target: `http://localhost:${backendPort}`,
        changeOrigin: true,
        secure: false
      }
    }
  }
})
