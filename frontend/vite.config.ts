import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// Дев-сервер: /api проксируется на FastAPI (uvicorn app.main:app)
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
