import path from 'node:path'
import config from './vite.config.js'

export default {
  ...config,
  cacheDir: path.join(
    config.root,
    'node_modules/.vite-messenger-bubbles-browser',
  ),
  resolve: {
    ...config.resolve,
    alias: [
      {
        find: /^@\/utils$/,
        replacement: path.join(config.root, 'tests/browser/bubble-utils.js'),
      },
      { find: '@', replacement: path.join(config.root, 'src') },
    ],
  },
  optimizeDeps: {
    ...config.optimizeDeps,
    entries: ['tests/browser/messenger-bubbles.html'],
  },
  server: { host: '127.0.0.1', port: 4187, strictPort: true },
}
