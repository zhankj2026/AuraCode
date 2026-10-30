import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// 仅用于运行 renderer 端的组件 / 端到端测试，不干扰 electron-vite 生产构建。
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/renderer/src/__tests__/setup.ts'],
    include: ['src/renderer/src/__tests__/**/*.test.{ts,tsx}'],
    css: false,
  },
})
