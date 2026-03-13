import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'health',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (req.url?.startsWith('/health')) {
            res.statusCode = 200
            res.setHeader('Content-Type', 'application/json')
            res.end(JSON.stringify({ ok: true }))
            return
          }
          next()
        })
      },
    },
  ],
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
