import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

// The console ships as static files served by FastAPI at '/'. Assets stay relative-rooted so
// the bundle never assumes a host, and nothing is fetched from a CDN at runtime (INV-4).
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    {
      name: 'offline-content-policy',
      apply: 'build',
      // Restrict the shipped console to local resources. Development keeps Vite's
      // inline refresh preamble; production needs only the bundled scripts.
      transformIndexHtml: () => [
        {
          tag: 'meta',
          attrs: {
            'http-equiv': 'Content-Security-Policy',
            content:
              "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'",
          },
          injectTo: 'head-prepend',
        },
      ],
    },
  ],
  base: '/',
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    // Split the heavy, route-local libraries out of the entry chunk so the entry screen and
    // workspace do not pay for charts or motion they have not rendered yet.
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (!id.includes('node_modules')) return undefined
          if (/[\\/]recharts[\\/]|[\\/]d3-/.test(id)) return 'charts'
          if (/[\\/]framer-motion[\\/]|[\\/]motion-dom[\\/]/.test(id))
            return 'motion'
          if (/[\\/]react(-dom|-router|-router-dom)?[\\/]/.test(id))
            return 'react'
          return undefined
        },
      },
    },
  },
  server: {
    // Dev only. The demo machine serves the built dist/ from FastAPI on one port.
    proxy: {
      '/transforms': 'http://127.0.0.1:8000',
      '/jobs': 'http://127.0.0.1:8000',
      '/models': 'http://127.0.0.1:8000',
      '/templates': 'http://127.0.0.1:8000',
      '/conversions': 'http://127.0.0.1:8000',
      '/convert': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/sources': 'http://127.0.0.1:8000',
      '/selfcheck': 'http://127.0.0.1:8000',
      '/qa': 'http://127.0.0.1:8000',
    },
  },
})
