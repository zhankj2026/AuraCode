import { defineConfig } from '@playwright/test'

// 全栈端到端测试（真实 HTTP 往返）。
// 前置：先启动 Bridge 后端（默认 8765）：
//   cd <引擎根> && python cli.py --bridge
// 然后：npm i -D @playwright/test && npx playwright install && npx playwright test
export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  use: {
    baseURL: process.env.BRIDGE_URL || 'http://127.0.0.1:8765',
  },
})
