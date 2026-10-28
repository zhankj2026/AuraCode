import { useEffect, useState } from 'react'
import { actions, useStore } from '../state/store'

/**
 * MCP 服务器连接/编辑弹窗。
 * - 新增：scope 选择项目（<工作区>/.mcp.json）或用户（~/.auracode/mcp.json）
 * - 编辑：从列表 ✎ 进入，预填原配置，保存时整体替换
 * 支持 stdio / http / sse / ws 四种传输方式与可选 env（KEY=VALUE 行）。
 */
export function McpModal() {
  const open = useStore((s) => s.mcpOpen)
  const edit = useStore((s) => s.mcpEdit)
  const ext = useStore((s) => s.extensions)
  const workDir = useStore(
    (s) => s.sessions.find((x) => x.session_id === s.activeSessionId)?.work_dir || '',
  )
  const [scope, setScope] = useState<'project' | 'user'>('project')
  const [name, setName] = useState('')
  const [transport, setTransport] = useState('stdio')
  const [command, setCommand] = useState('')
  const [args, setArgs] = useState('')
  const [url, setUrl] = useState('')
  const [env, setEnv] = useState('')
  const [busy, setBusy] = useState(false)

  // 打开时初始化表单：编辑模式预填原配置
  useEffect(() => {
    if (!open) return
    if (edit) {
      const server = ext?.mcp.find((m) => m.name === edit.name && m.scope === edit.scope)
      if (server) {
        setScope(edit.scope)
        setName(server.name)
        // 从展示用 command（"cmd arg1 arg2"）里拆出启动命令与参数
        if (server.type === 'stdio' && server.command) {
          setTransport('stdio')
          const parts = server.command.split(/\s+/)
          setCommand(parts[0] || '')
          setArgs(parts.slice(1).join(' '))
        } else {
          setTransport(server.type === 'ws' ? 'ws' : server.type === 'sse' ? 'sse' : 'http')
          setUrl(server.url || '')
        }
        setEnv('')
      }
    } else {
      setScope('project')
      setName('')
      setCommand('')
      setArgs('')
      setUrl('')
      setEnv('')
      setTransport('stdio')
    }
  }, [open, edit])
  // eslint-disable-next-line react-hooks/exhaustive-deps

  if (!open) return null

  const editing = !!edit

  async function save() {
    if (!name.trim()) {
      actions.setToast('请填写服务器名称', 'error')
      return
    }
    if (!workDir && scope === 'project') {
      actions.setToast('当前无工作区，请选择「用户」作用域或先打开工作区', 'error')
      return
    }
    setBusy(true)
    try {
      const res = editing
        ? await window.auracode.updateMcp({
            workDir,
            scope,
            oldName: edit!.name,
            newName: name.trim(),
            newCfg: {
              transport,
              command: command.trim() || undefined,
              args: args.trim() || undefined,
              url: url.trim() || undefined,
              env: env.trim() || undefined,
            },
          })
        : await window.auracode.upsertMcp({
            workDir,
            scope,
            name: name.trim(),
            transport,
            command: command.trim() || undefined,
            args: args.trim() || undefined,
            url: url.trim() || undefined,
            env: env.trim() || undefined,
          })
      if (res.ok) {
        actions.setToast(
          `${editing ? '已更新' : '已添加'} MCP 服务器「${name.trim()}」（新会话生效）`,
          'ok',
        )
        actions.loadExtensions()
        actions.closeMcp()
      } else {
        actions.setToast((editing ? '更新失败：' : '添加失败：') + res.message, 'error')
      }
    } catch (e) {
      actions.setToast('保存失败：' + (e instanceof Error ? e.message : String(e)), 'error')
    } finally {
      setBusy(false)
    }
  }

  const targetFile =
    scope === 'user' ? '~/.auracode/mcp.json' : `${workDir || '(当前工作区)'}/.mcp.json`

  return (
    <div className="mask show" onClick={(e) => e.target === e.currentTarget && actions.closeMcp()}>
      <div className="modal">
        <div className="mh" style={{ background: 'var(--bg3)' }}>
          <div className="ic" style={{ background: 'var(--accent)' }}>🔌</div>
          <div className="ti">{editing ? `编辑 MCP 服务器 · ${edit!.name}` : '连接 MCP 服务器'}</div>
        </div>
        <div className="mb">
          <div className="field">
            <label>作用域</label>
            <select value={scope} onChange={(e) => setScope(e.target.value as 'project' | 'user')} disabled={editing}>
              <option value="project">项目级 —— {targetFile}</option>
              <option value="user">用户级 —— ~/.auracode/mcp.json（所有项目可用）</option>
            </select>
          </div>
          <div className="field">
            <label>名称</label>
            <input value={name} placeholder="例如 postgres" onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="field">
            <label>传输方式</label>
            <select value={transport} onChange={(e) => setTransport(e.target.value)}>
              <option value="stdio">stdio（本地命令）</option>
              <option value="http">http</option>
              <option value="sse">sse</option>
              <option value="ws">websocket</option>
            </select>
          </div>
          {transport === 'stdio' ? (
            <>
              <div className="field">
                <label>启动命令</label>
                <input value={command} placeholder="例如 npx" onChange={(e) => setCommand(e.target.value)} />
              </div>
              <div className="field">
                <label>参数（空格分隔）</label>
                <input value={args} placeholder="-y @my/postgres-mcp" onChange={(e) => setArgs(e.target.value)} />
              </div>
            </>
          ) : (
            <div className="field">
              <label>URL</label>
              <input value={url} placeholder="https://..." onChange={(e) => setUrl(e.target.value)} />
            </div>
          )}
          <div className="field">
            <label>环境变量（可选，每行一个 KEY=VALUE）</label>
            <textarea
              value={env}
              placeholder={'API_KEY=xxx\nBASE_URL=https://...'}
              onChange={(e) => setEnv(e.target.value)}
              style={{ minHeight: 56, fontFamily: 'var(--mono, monospace)', resize: 'vertical' }}
            />
          </div>
          <div className="note">
            配置写入 <b>{targetFile}</b> 的 mcpServers；新建会话时自动连接并把工具注册为 mcp__名称__工具。
          </div>
        </div>
        <div className="mf">
          <div className="spacer" style={{ flex: 1 }} />
          <button className="btn" onClick={() => actions.closeMcp()} disabled={busy}>取消</button>
          <button className="btn ok" onClick={save} disabled={busy}>
            {busy ? '保存中…' : editing ? '保存' : '连接'}
          </button>
        </div>
      </div>
    </div>
  )
}
