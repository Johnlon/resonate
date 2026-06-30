import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { VitePWA } from 'vite-plugin-pwa';
import { fileURLToPath } from 'url';
import { join } from 'path';

const base = process.env.GITHUB_PAGES ? '/resonate/' : '/';
const UI_ROOT = join(fileURLToPath(import.meta.url), '..', 'packages', 'ui');

export default defineConfig({
  root: UI_ROOT,
  base,
  server: {
    watch: {
      ignored: ['**/drivers/**/_html/**', '**/drivers/**/datasheets/**'],
    },
  },
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      base,
      manifest: {
        name: 'Resonate',
        short_name: 'Resonate',
        description: 'Open loudspeaker enclosure simulator — community-owned, runs anywhere',
        theme_color: '#11151c',
        background_color: '#11151c',
        display: 'standalone',
        start_url: '/resonate/',
        icons: [
          { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,ico}'],
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
      },
    }),
  ],
});
