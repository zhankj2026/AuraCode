import { defineConfig } from 'electron-vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // 生产构建统一关闭 sourcemap，避免源码随 app.asar 一起外泄。
  // 仅当显式设置 VITE_SOURCEMAP=1（如排查线上问题时）才重新输出。
  main: {
    build: {
      sourcemap: process.env.VITE_SOURCEMAP === '1',
      rollupOptions: {
        external: ['child_process', 'path', 'fs', 'crypto', 'os', 'util', 'events', 'electron'],
      },
    },
  },
  preload: {
    build: {
      sourcemap: process.env.VITE_SOURCEMAP === '1',
      rollupOptions: { external: ['electron'] },
    },
  },
  renderer: {
    root: 'src/renderer',
    build: {
      sourcemap: process.env.VITE_SOURCEMAP === '1',
      rollupOptions: { input: 'src/renderer/index.html' },
    },
    plugins: [react()],
  },
})
