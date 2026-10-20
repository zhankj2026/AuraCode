import { defineConfig } from 'electron-vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  main: {
    build: {
      rollupOptions: {
        external: ['child_process', 'path', 'fs', 'crypto', 'os', 'util', 'events', 'electron'],
      },
    },
  },
  preload: {
    build: {
      rollupOptions: { external: ['electron'] },
    },
  },
  renderer: {
    root: 'src/renderer',
    build: {
      rollupOptions: { input: 'src/renderer/index.html' },
    },
    plugins: [react()],
  },
})
