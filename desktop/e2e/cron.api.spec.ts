import { test, expect } from '@playwright/test'

// 全栈 E2E：通过真实 HTTP 调用 /api/cron 验证「创建 → 列表」闭环。
// 与 Vitest 的组件级端到端测试互补：这里验证的是后端持久化与 API 契约。
const JOB = {
  cron: '0 9 * * *',
  prompt: 'e2e-probe: 汇总今日 git 提交',
  recurring: true,
  durable: true,
}

test('创建定时任务后可在列表中查到', async ({ request }) => {
  const created = await request.post('/api/cron', { data: JOB })
  expect(created.ok()).toBeTruthy()
  const body = await created.json()
  expect(body.job_id).toBeTruthy()
  expect(body.next_fire).toBeTruthy()

  const list = await request.get('/api/cron')
  expect(list.ok()).toBeTruthy()
  const listBody = await list.json()
  const jobs = Array.isArray(listBody) ? listBody : listBody.jobs ?? []
  expect(jobs.some((j: any) => j.job_id === body.job_id)).toBeTruthy()
})
