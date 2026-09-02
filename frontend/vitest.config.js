import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import path from 'path'

export default defineConfig({
  plugins: [vue(), vueJsx()],
  test: {
    globals: true,
    environment: 'happy-dom',
    root: import.meta.dirname,
    setupFiles: ['./tests/setup.js'],
    include: ['tests/**/*.test.js', 'src/**/*.test.js'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'json-summary'],
      reportsDirectory: './coverage',
      include: [
        'src/utils/fieldTransforms.js',
        'src/utils/scriptHelpers.js',
        'src/utils/expressions.js',
        'src/utils/renderFieldLayoutDialog.js',
      ],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
      '~icons/lucide/circle-alert': path.resolve(
        import.meta.dirname,
        'tests/stubs/IconStub.vue',
      ),
      '~icons/lucide/audio-lines': path.resolve(
        import.meta.dirname,
        'tests/stubs/IconStub.vue',
      ),
      '~icons/lucide/clock-3': path.resolve(
        import.meta.dirname,
        'tests/stubs/IconStub.vue',
      ),
      '~icons/lucide/image-off': path.resolve(
        import.meta.dirname,
        'tests/stubs/IconStub.vue',
      ),
      '~icons/lucide/play': path.resolve(
        import.meta.dirname,
        'tests/stubs/IconStub.vue',
      ),
      '~icons/lucide/chevron-left': path.resolve(
        import.meta.dirname,
        'tests/stubs/IconStub.vue',
      ),
      '~icons/lucide/chevron-right': path.resolve(
        import.meta.dirname,
        'tests/stubs/IconStub.vue',
      ),
      '~icons/lucide/download': path.resolve(
        import.meta.dirname,
        'tests/stubs/IconStub.vue',
      ),
      '~icons/lucide/minus': path.resolve(
        import.meta.dirname,
        'tests/stubs/IconStub.vue',
      ),
      '~icons/lucide/plus': path.resolve(
        import.meta.dirname,
        'tests/stubs/IconStub.vue',
      ),
      '~icons/lucide/x': path.resolve(
        import.meta.dirname,
        'tests/stubs/IconStub.vue',
      ),
    },
  },
})
