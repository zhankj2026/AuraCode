import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { HooksModal } from '../components/HooksModal'
import { setState, getState } from '../state/store'

type AuraApi = {
  saveHooks: ReturnType<typeof vi.fn>
  [k: string]: any
}

function mockAura(): AuraApi {
  const api = {
    saveHooks: vi.fn(async () => ({ ok: true, message: '' })),
  }
  ;(window as any).auracode = { ...(window as any).auracode, ...api }
  return api as AuraApi
}

const emptyExt = { skills: [], mcp: [], hooks: [], plugins: [], tasks: [] }

function openHooks() {
  act(() => {
    setState({
      hooksOpen: true,
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

describe('HooksModal 端到端流程', () => {
  it('新增一条钩子并保存 → 调用 saveHooks（写回 workDir/scope）', async () => {
    openHooks()
    render(<HooksModal />)
    fireEvent.click(screen.getByLabelText('添加钩子'))
    fireEvent.change(screen.getByLabelText('执行命令'), { target: { value: 'echo hi' } })
    fireEvent.click(screen.getByRole('button', { name: '保存全部' }))

    await waitFor(() => expect((window as any).auracode.saveHooks).toHaveBeenCalled())
    const [wd, scope, list] = (window as any).auracode.saveHooks.mock.calls[0]
    expect(wd).toBe('/proj')
    expect(scope).toBe('project')
    expect(list).toHaveLength(1)
    expect(list[0].command).toBe('echo hi')
    expect(list[0].event).toBe('PreToolUse')
  })

  it('命令为空 → 拦截、不调用 IPC、弹错误提示', async () => {
    openHooks()
    render(<HooksModal />)
    fireEvent.click(screen.getByLabelText('添加钩子'))
    fireEvent.click(screen.getByRole('button', { name: '保存全部' }))

    await waitFor(() => expect(getState().toast?.kind).toBe('error'))
    expect((window as any).auracode.saveHooks).not.toHaveBeenCalled()
  })

  it('项目级但无工作区 → 拦截并报错', async () => {
    act(() => {
      setState({
        hooksOpen: true,
        extensions: emptyExt as any,
        sessions: [],
        activeSessionId: null,
        config: null,
      })
    })
    render(<HooksModal />)
    fireEvent.click(screen.getByLabelText('添加钩子'))
    fireEvent.change(screen.getByLabelText('执行命令'), { target: { value: 'echo x' } })
    fireEvent.click(screen.getByRole('button', { name: '保存全部' }))

    await waitFor(() => expect(getState().toast?.kind).toBe('error'))
    expect((window as any).auracode.saveHooks).not.toHaveBeenCalled()
  })

  it('从扩展配置预填已有钩子 → 改命令后整表写回', async () => {
    act(() => {
      setState({
        hooksOpen: true,
        extensions: {
          ...emptyExt,
          hooks: [
            {
              event: 'PostToolUse',
              matcher: '',
              command: 'old-cmd',
              enabled: true,
              description: '',
              priority: 0,
              timeout: 10,
              onFail: 'ignore',
              scope: 'project',
            },
          ],
        } as any,
        sessions: [{ session_id: 's1', work_dir: '/proj' }] as any,
        activeSessionId: 's1',
        config: null,
      })
    })
    render(<HooksModal />)
    fireEvent.change(screen.getByLabelText('执行命令'), { target: { value: 'new-cmd' } })
    fireEvent.click(screen.getByRole('button', { name: '保存全部' }))

    await waitFor(() => expect((window as any).auracode.saveHooks).toHaveBeenCalled())
    const [, , list] = (window as any).auracode.saveHooks.mock.calls[0]
    expect(list).toHaveLength(1)
    expect(list[0].command).toBe('new-cmd')
    expect(list[0].event).toBe('PostToolUse')
  })

  it('切换到用户级作用域 → saveHooks 收到 user', async () => {
    openHooks()
    render(<HooksModal />)
    fireEvent.change(screen.getByLabelText('作用域'), { target: { value: 'user' } })
    fireEvent.click(screen.getByLabelText('添加钩子'))
    fireEvent.change(screen.getByLabelText('执行命令'), { target: { value: 'echo u' } })
    fireEvent.click(screen.getByRole('button', { name: '保存全部' }))

    await waitFor(() => expect((window as any).auracode.saveHooks).toHaveBeenCalled())
    const [, scope] = (window as any).auracode.saveHooks.mock.calls[0]
    expect(scope).toBe('user')
  })
})
