import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Widget là artifact độc lập; đồng thời khóa production branch của React cho browser thuần,
  // nơi global `process` của Node không tồn tại.
  publicDir: false,
  define: {
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
  build: {
    outDir: resolve(import.meta.dirname, 'dist'),
    emptyOutDir: false,
    sourcemap: false,
    license: true,
    lib: {
      entry: resolve(import.meta.dirname, 'src/standalone.ts'),
      name: 'BankDigitalEmbed',
      formats: ['iife'],
      fileName: () => 'bank-digital-widget.iife.js',
    },
  },
})
