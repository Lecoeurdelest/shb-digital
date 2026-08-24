import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const source = (file: string) => resolve(import.meta.dirname, 'src', file)

export default defineConfig({
  plugins: [react()],
  // SDK artifact không được kế thừa favicon/font/assets của reference SPA.
  publicDir: false,
  build: {
    outDir: resolve(import.meta.dirname, 'dist'),
    emptyOutDir: true,
    sourcemap: false,
    lib: {
      entry: {
        index: source('index.ts'),
        react: source('react.ts'),
        element: source('element.ts'),
      },
      formats: ['es', 'cjs'],
      fileName: (format, entryName) => `${entryName}.${format === 'es' ? 'js' : 'cjs'}`,
    },
    rolldownOptions: {
      external: ['react', 'react-dom', 'react-dom/client', 'react/jsx-runtime'],
    },
  },
})
