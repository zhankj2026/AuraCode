import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { CronCreateModal } from '../components/CronCreateModal'

function makeClient() {
  return {
    createSession: vi.fn(async () => ({ session_id: 'sess_new' })),
    createCron: vi.fn(async (body: any) => ({
      job_id: 'abc123456789',
      next_fire: '2026-01-02 09:00:00',
      ...body,
    })),
  }
}

function setup(client: any) {
  const onClose = vi.fn()
  const onToast = vi.fn()
  const onCreated = vi.fn()
  render(
    <CronCreateModal
      activeSessionId={null}
      sessions={[]}
      client={client}
      onClose={onClose}
      onToast={onToast}
      onCreated={onCreated}
    />,
  )
  return { onClose, onToast, onCreated }
}

const typePrompt = (value: string) =>
  fireEvent.change(screen.getByPlaceholderText(/汇总今天/), {
    target: { value },
  })

describe('CronCreateModal 端到端流程', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('默认（每天 09:00）填写提示词并提交 → 调用 createCron', async () => {
    const client = makeClient()
    const { onClose, onToast, onCreated } = setup(client)
    typePrompt('生成日报')
    fireEvent.click(screen.getByRole('button', { name: '创建' }))

    await waitFor(() => expect(client.createCron).toHaveBeenCalled())
    expect(client.createCron).toHaveBeenCalledWith(
      expect.objectContaining({
        cron: '0 9 * * *',
        prompt: '生成日报',
        recurring: true,
        durable: true,
        session_id: '',
        work_dir: '.',
      }),
    )
    expect(onToast).toHaveBeenCalledWith(expect.stringContaining('已创建定时任务'), 'ok')
    expect(onCreated).toHaveBeenCalled()
    expect(onClose).toHaveBeenCalled()
  })

  it('选择预设「每周一 09:00」→ 提交带对应 cron', async () => {
    const client = makeClient()
    setup(client)
    fireEvent.click(screen.getByRole('button', { name: '每周一 09:00' }))
    typePrompt('周报')
    fireEvent.click(screen.getByRole('button', { name: '创建' }))

    await waitFor(() => expect(client.createCron).toHaveBeenCalled())
    expect(client.createCron).toHaveBeenCalledWith(
      expect.objectContaining({ cron: '0 9 * * 1', prompt: '周报' }),
    )
  })

  it('关联会话选「新建专用会话并绑定」→ 先 createSession 再 createCron', async () => {
    const client = makeClient()
    setup(client)
    fireEvent.change(screen.getByLabelText('关联会话'), { target: { value: 'new' } })
    typePrompt('专属任务')
    fireEvent.click(screen.getByRole('button', { name: '创建' }))

    await waitFor(() => expect(client.createSession).toHaveBeenCalled())
    expect(client.createSession).toHaveBeenCalledWith({
      work_dir: '.',
      permission_mode: 'auto',
      restore_history: false,
    })
    await waitFor(() => expect(client.createCron).toHaveBeenCalled())
    expect(client.createCron).toHaveBeenCalledWith(
      expect.objectContaining({ session_id: 'sess_new' }),
    )
  })

  it('高级模式填入非法 cron → 阻止提交并报错', async () => {
    const client = makeClient()
    const { onToast } = setup(client)
    fireEvent.click(screen.getByRole('button', { name: '高级' }))
    fireEvent.change(screen.getByLabelText('cron 表达式（高级）'), {
      target: { value: 'bad expr' },
    })
    typePrompt('非法任务')
    fireEvent.click(screen.getByRole('button', { name: '创建' }))

    await waitFor(() => expect(onToast).toHaveBeenCalled())
    expect(client.createCron).not.toHaveBeenCalled()
    expect(onToast).toHaveBeenCalledWith(expect.stringContaining('不合法'), 'error')
  })

  it('提示词为空时创建按钮禁用', () => {
    makeClient()
    setup(makeClient())
    const btn = screen.getByRole('button', { name: '创建' }) as HTMLButtonElement
    expect(btn.disabled).toBe(true)
  })
})
