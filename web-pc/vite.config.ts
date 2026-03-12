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
        target: 'http://127.0.0.1:10600',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/ws': {
        target: 'ws://127.0.0.1:10600',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
