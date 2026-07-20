import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'happy-dom',
    root: __dirname,
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
      '@': path.resolve(__dirname, 'src'),
      '~icons/lucide/circle-alert': path.resolve(
        __dirname,
        'tests/stubs/IconStub.vue',
      ),
      '~icons/lucide/clock-3': path.resolve(
        __dirname,
        'tests/stubs/IconStub.vue',
      ),
      '~icons/lucide/image-off': path.resolve(
        __dirname,
        'tests/stubs/IconStub.vue',
      ),
    },
  },
})
