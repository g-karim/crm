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
    entries: [
      'tests/browser/messenger-bubbles.html',
      'tests/browser/messenger-voice.html',
    ],
    // The real frappe-ui Button imports reka-ui's barrel. Prebundle it so a
    // cold layout test does not request hundreds of individual modules.
    include: [
      ...config.optimizeDeps.include,
      'reka-ui',
      'vue-router',
      'dayjs',
      'lottie-web/build/player/lottie_light',
      'linkifyjs',
    ],
  },
  server: { host: '127.0.0.1', port: 4187, strictPort: true },
}
