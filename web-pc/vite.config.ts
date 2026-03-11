import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    host: '0.0.0.0',
    port: 10601,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://python-service:10600',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/ws': {
        target: 'ws://python-service:10600',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
