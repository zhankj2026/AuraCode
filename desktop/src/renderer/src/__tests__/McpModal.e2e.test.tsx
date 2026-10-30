import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { McpModal } from '../components/McpModal'
import { setState, getState } from '../state/store'

type AuraApi = {
  upsertMcp: ReturnType<typeof vi.fn>
  updateMcp: ReturnType<typeof vi.fn>
  saveHooks: ReturnType<typeof vi.fn>
  [k: string]: any
}

function mockAura(): AuraApi {
  const api = {
    upsertMcp: vi.fn(async () => ({ ok: true, message: '' })),
    updateMcp: vi.fn(async () => ({ ok: true, message: '' })),
    saveHooks: vi.fn(async () => ({ ok: true, message: '' })),
  }
  ;(window as any).auracode = api
  return api as AuraApi
}

const emptyExt = { skills: [], mcp: [], hooks: [], plugins: [], tasks: [] }

function openNew() {
  act(() => {
    setState({
      mcpOpen: true,
      mcpEdit: null,
      extensions: emptyExt as any,
      sessions: [{ session_id: 's1', work_dir: '/proj' }] as any,
      activeSessionId: 's1',
      config: null,
    })
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  act(() => {
    setState({
      mcpOpen: false,
      mcpEdit: null,
      hooksOpen: false,
      extensions: emptyExt as any,
      sessions: [],
      activeSessionId: null,
      config: null,
    })
  })
  mockAura()
})

describe('McpModal 端到端流程', () => {
  it('新建 stdio 服务器 → 调用 upsertMcp（含命令/参数）', async () => {
    openNew()
    render(<McpModal />)
    fireEvent.change(screen.getByLabelText('服务器名称'), { target: { value: 'pg' } })
    fireEvent.change(screen.getByLabelText('启动命令'), { target: { value: 'npx' } })
    fireEvent.change(screen.getByLabelText('参数'), { target: { value: '-y @x' } })
    fireEvent.click(screen.getByRole('button', { name: '连接' }))

    await waitFor(() => expect((window as any).auracode.upsertMcp).toHaveBeenCalled())
    const arg = (window as any).auracode.upsertMcp.mock.calls[0][0]
    expect(arg).toMatchObject({
      name: 'pg',
      transport: 'stdio',
      command: 'npx',
      args: '-y @x',
      scope: 'project',
      workDir: '/proj',
    })
    expect(getState().toast?.kind).toBe('ok')
  })

  it('名称为空 → 拦截、不调用 IPC、弹错误提示', async () => {
    openNew()
    render(<McpModal />)
    fireEvent.click(screen.getByRole('button', { name: '连接' }))

    await waitFor(() => expect(getState().toast?.kind).toBe('error'))
    expect((window as any).auracode.upsertMcp).not.toHaveBeenCalled()
  })

  it('项目级但无工作区 → 拦截并报错', async () => {
    act(() => {
      setState({
        mcpOpen: true,
        mcpEdit: null,
        extensions: emptyExt as any,
        sessions: [],
        activeSessionId: null,
        config: null,
      })
    })
    render(<McpModal />)
    fireEvent.change(screen.getByLabelText('服务器名称'), { target: { value: 'pg' } })
    fireEvent.click(screen.getByRole('button', { name: '连接' }))

    await waitFor(() => expect(getState().toast?.kind).toBe('error'))
    expect((window as any).auracode.upsertMcp).not.toHaveBeenCalled()
  })

  it('编辑已有服务器 → 调用 updateMcp（保留 oldName）', async () => {
    act(() => {
      setState({
        mcpOpen: true,
        mcpEdit: { name: 'pg', scope: 'project' },
        extensions: {
          ...emptyExt,
          mcp: [
            {
              name: 'pg',
              type: 'stdio',
              command: 'npx -y old',
              enabled: true,
              scope: 'project',
            },
          ],
        } as any,
        sessions: [{ session_id: 's1', work_dir: '/proj' }] as any,
        activeSessionId: 's1',
        config: null,
      })
    })
    render(<McpModal />)
    // 编辑态预填了名称 pg，改个命令
    fireEvent.change(screen.getByLabelText('启动命令'), { target: { value: 'bun' } })
    fireEvent.click(screen.getByRole('button', { name: '保存' }))

    await waitFor(() => expect((window as any).auracode.updateMcp).toHaveBeenCalled())
    const arg = (window as any).auracode.updateMcp.mock.calls[0][0]
    expect(arg.oldName).toBe('pg')
    expect(arg.newName).toBe('pg')
    expect(arg.newCfg.command).toBe('bun')
  })

  it('切换为 http 传输 → 仅 URL 字段参与保存', async () => {
    openNew()
    render(<McpModal />)
    fireEvent.change(screen.getByLabelText('服务器名称'), { target: { value: 'svc' } })
    fireEvent.change(screen.getByLabelText('传输方式'), { target: { value: 'http' } })
    fireEvent.change(screen.getByLabelText('URL'), { target: { value: 'https://h/' } })
    expect(screen.queryByLabelText('启动命令')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: '连接' }))
    await waitFor(() => expect((window as any).auracode.upsertMcp).toHaveBeenCalled())
    const arg = (window as any).auracode.upsertMcp.mock.calls[0][0]
    expect(arg.transport).toBe('http')
    expect(arg.url).toBe('https://h/')
    expect(arg.command).toBeUndefined()
  })
})
