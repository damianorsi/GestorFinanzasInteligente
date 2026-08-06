import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
// `defineConfig` viene de vitest/config y no de vite: es el que tipa la clave `test`.
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // En desarrollo, `npm run dev` proxea /api al backend para evitar CORS.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.ts',
    css: false,
    /*
     * Los 5 segundos por defecto quedan justos: cada test monta la aplicación
     * entera y espera a MSW y a React Query, y los archivos corren en paralelo.
     * En una máquina cargada eso da timeouts que no son un bug del código sino
     * de la máquina. Subirlo no esconde fallas: una aserción rota sigue
     * fallando, solo que más tarde.
     */
    testTimeout: 15_000,
    coverage: {
      reporter: ['text', 'lcov'],
      exclude: ['src/main.tsx', '**/*.d.ts'],
    },
  },
})
