import { useState } from 'react'
import { actions, useStore } from '../state/store'

export function McpModal() {
  const open = useStore((s) => s.mcpOpen)
  const root = useStore((s) => s.config?.root)
  const [name, setName] = useState('')
  const [transport, setTransport] = useState('stdio')
  const [command, setCommand] = useState('')
  const [args, setArgs] = useState('')
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)

  if (!open) return null

  async function connect() {
    if (!root || !name.trim()) {
      actions.setToast('请填写名称，并确保工作区已就绪', 'error')
      return
    }
    setBusy(true)
    try {
      const res = await window.auracode.addMcp({
        root,
        name: name.trim(),
        transport,
        command: command.trim() || undefined,
        args: args.trim() || undefined,
        url: url.trim() || undefined,
      })
      if (res.ok) {
        actions.setToast(`已添加 MCP 服务器「${name.trim()}」`, 'ok')
        actions.loadExtensions()
        actions.closeMcp()
        // 重置表单
        setName('')
        setCommand('')
        setArgs('')
        setUrl('')
        setTransport('stdio')
      } else {
        actions.setToast('添加失败：' + res.message, 'error')
      }
    } catch (e) {
      actions.setToast('添加失败：' + (e instanceof Error ? e.message : String(e)), 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mask show" onClick={(e) => e.target === e.currentTarget && actions.closeMcp()}>
      <div className="modal">
        <div className="mh" style={{ background: 'var(--bg3)' }}>
          <div className="ic" style={{ background: 'var(--accent)' }}>🔌</div>
          <div className="ti">连接 MCP 服务器</div>
        </div>
        <div className="mb">
          <div className="field">
            <label>名称</label>
            <input value={name} placeholder="例如 postgres" onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="field">
            <label>传输方式</label>
            <select value={transport} onChange={(e) => setTransport(e.target.value)}>
              <option value="stdio">stdio</option>
              <option value="sse">sse</option>
              <option value="http">http</option>
              <option value="websocket">websocket</option>
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
          <div className="note">
            配置将写入工程根目录 <b>.mcp.json</b> 的 mcpServers，左侧「扩展 → MCP」会即时刷新。
          </div>
        </div>
        <div className="mf">
          <div className="spacer" style={{ flex: 1 }} />
          <button className="btn" onClick={() => actions.closeMcp()} disabled={busy}>取消</button>
          <button className="btn ok" onClick={connect} disabled={busy}>
            {busy ? '连接中…' : '连接'}
          </button>
        </div>
      </div>
    </div>
  )
}
