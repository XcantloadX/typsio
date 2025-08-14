import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    allowedHosts: true,
    proxy: {
      '/socket.io': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  base: './',
})