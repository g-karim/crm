import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import { barrelImports, lucideIcons } from 'frappe-ui/vite'
import path from 'node:path'

// Serve only an isolated test entry; this does not add a production CRM route.
const root = path.resolve(import.meta.dirname, '../..')
export default defineConfig({
  root,
  cacheDir: path.join(root, 'node_modules/.vite-messenger-settings-browser'),
  // frappe-ui publishes Vue source through a broad barrel. Load the actual
  // components this fixture uses without crawling its editor/socket modules.
  plugins: [
    barrelImports({ linkedOnly: false }),
    vue(),
    vueJsx(),
    lucideIcons(),
  ],
  resolve: {
    alias: { '@': path.join(root, 'src') },
    dedupe: ['vue', 'vue-router', 'frappe-ui', 'dompurify'],
  },
  optimizeDeps: {
    entries: ['tests/browser/messenger-settings.html'],
    force: true,
    include: [
      'feather-icons',
      'tailwind.config.js',
      'prosemirror-state',
      'prosemirror-view',
      'lowlight',
      'interactjs',
    ],
  },
  server: { host: '127.0.0.1', port: 4186, strictPort: true },
})
