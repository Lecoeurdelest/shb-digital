/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Backend base — FastAPI/uvicorn default dev port. Override via VITE_API_PROXY_TARGET if
// backend binds elsewhere (architect chưa công bố cổng chính thức ở CLAUDE.md §1 lúc build FE
// — ghi DECISIONS nếu backend chốt khác 8000).
const API_PROXY_TARGET = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: API_PROXY_TARGET,
        changeOrigin: true,
        // SSE endpoint streams — keep the proxy connection open, don't buffer.
        ws: false,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // .archive/ giữ code bỏ đi (CLAUDE.md §2 mv thay rm) — KHÔNG chạy test/không tính coverage.
    exclude: ['**/node_modules/**', '**/dist/**', '**/.archive/**'],
  },
})
