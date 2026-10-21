import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

import { texts } from './src/texts.ts';

// Куда dev-сервер проксирует /api — в том же формате host:port, что у Caddy на Railway.
// По умолчанию локальный api на порту 8000.
const apiUpstream = process.env.API_UPSTREAM ?? 'localhost:8000';
const background = '#12131a'; // как --bg в src/index.css

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // Свой service worker (src/sw.ts): кеш приложения и web push. Регистрирует его сам код
      // (main.tsx) и только в режиме PWA.
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      injectRegister: false,
      registerType: 'autoUpdate',
      manifest: {
        name: texts.appName,
        short_name: texts.appShortName,
        lang: 'ru',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        background_color: background,
        theme_color: background,
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
      },
    }),
  ],
  build: {
    // Сборка — в /static/: имена с хешем, Caddy кеширует их навсегда.
    // /assets/ остаётся графике игры из public/ — её имена не меняются при замене заглушек.
    assetsDir: 'static',
  },
  server: {
    host: true,
    proxy: {
      '/api': `http://${apiUpstream}`,
    },
  },
});
