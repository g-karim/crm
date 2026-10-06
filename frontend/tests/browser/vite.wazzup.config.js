import { readFileSync } from 'node:fs'
import path from 'node:path'
import { defineConfig } from 'vite'
import crmConfig from '../../vite.config.js'

// Serve the actual application entry and Vue pages. Only the destination of
// the dev HTTP proxy changes; bootstrap, authentication and RPC stay real.
export default defineConfig(async (environment) => {
  const fixtureFile = process.env.WAZZUP_E2E_FIXTURE
  if (!fixtureFile)
    throw new Error('WAZZUP_E2E_FIXTURE is required for the isolated CRM UI.')
  const fixture = JSON.parse(readFileSync(fixtureFile, 'utf8'))
  const frontend = loopbackOrigin(fixture.base_url)
  const backend = loopbackOrigin(fixture.frappe_origin)
  // Select the installed production frappe-ui dependency. Vite still serves in
  // development mode, so src/main.js requests the real Frappe dev bootstrap.
  const config = await crmConfig({ ...environment, mode: 'production' })
  const plugins = config.plugins.flat(Infinity)
  config.plugins = plugins.filter(
    (plugin) =>
      plugin &&
      plugin.name !== 'frappeui-proxy-plugin' &&
      !plugin.name.startsWith('vite-plugin-pwa'),
  )
  config.root = path.resolve(import.meta.dirname, '../..')
  config.cacheDir = path.join(config.root, 'node_modules/.vite-wazzup-local')
  // frappe-ui/editor's TypeScript barrel is optimized, while its Vue files
  // remain source modules. Prebundle their shared editor dependencies too so
  // both paths use one ProseMirror Selection registry (including gapcursor).
  const editorDependencies = [
    '@tiptap/core',
    '@tiptap/vue-3',
    '@tiptap/starter-kit',
    '@tiptap/extensions',
    '@tiptap/extension-paragraph',
    ...Object.keys(
      JSON.parse(
        readFileSync(
          path.join(config.root, 'node_modules/@tiptap/pm/package.json'),
          'utf8',
        ),
      ).dependencies,
    ),
  ]
  config.resolve.dedupe = [...config.resolve.dedupe, ...editorDependencies]
  config.optimizeDeps.include = [
    ...config.optimizeDeps.include,
    'frappe-ui/editor',
    'lottie-web/build/player/lottie_light',
    'mime',
    ...editorDependencies,
  ]
  config.server = {
    ...config.server,
    host: '127.0.0.1',
    port: Number(frontend.port),
    strictPort: true,
    proxy: {
      '^/(api|assets|files|private|login)(/|\\?|$)': {
        target: backend.origin,
        changeOrigin: true,
      },
    },
  }
  return config
})

function loopbackOrigin(value) {
  const url = new URL(value)
  if (
    url.protocol !== 'http:' ||
    url.hostname !== '127.0.0.1' ||
    !url.port ||
    url.username ||
    url.password ||
    url.pathname !== '/' ||
    url.search ||
    url.hash
  ) {
    throw new Error('The isolated UI requires explicit loopback HTTP origins.')
  }
  return url
}
