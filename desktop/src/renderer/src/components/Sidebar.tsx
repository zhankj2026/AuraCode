import { ReactNode, useEffect, useState } from 'react'
import { actions, useStore } from '../state/store'
import { readTextFull } from '../api/fsread'
import type { FileEntry, McpServerInfo, SkillInfo, PluginInfo, HookInfo } from '../api/types'

const EXT_TABS = ['MCP', '技能', '插件', '钩子']

export function Sidebar() {
  const activity = useStore((s) => s.activity)
  if (activity === 'chat') return <ChatSidebar />
  if (activity === 'files') return <FilesSidebar />
  if (activity === 'ext') return <ExtSidebar />
  if (activity === 'audit') return <AuditSidebar />
  if (activity === 'models') return null
  if (activity === 'archives') return <ArchivesSidebar />
  return <TasksSidebar />
}

function ChatSidebar() {
  const sessions = useStore((s) => s.sessions)
  const activeId = useStore((s) => s.activeSessionId)
  const runningSessions = useStore((s) => s.runningSessions)

  return (
    <>
      <button className="btn-primary" onClick={() => actions.newSession()}>
        ＋ 新会话
      </button>
      <div className="scroll">
        {sessions.map((s) => (
          <div
            key={s.session_id}
            className={`item ${activeId === s.session_id ? 'active' : ''}`}
            onClick={() => actions.selectSession(s.session_id)}
            title={s.work_dir}
          >
            <span
              className="dot-s"
              style={{ background: runningSessions[s.session_id] ? 'var(--ok)' : activeId === s.session_id ? 'var(--accentLite)' : '#3a4a66', width: 7, height: 7, borderRadius: '50%' }}
            />
            <div className="t">
              <div className="n">{s.title || '(未命名会话)'}</div>
              <div className="s">{s.round_count} 轮 · {s.model || '—'} · {s.state}</div>
            </div>
            <button
              className="item-del"
              title="归档此会话（停止并保存到历史归档，可在归档页恢复）"
              onClick={(e) => {
                e.stopPropagation()
                const label = s.title ? `「${s.title.slice(0, 24)}」` : '该会话'
                if (window.confirm(`确定归档 ${label}？会话将停止并保存为历史归档。`))
                  actions.archiveSession(s.session_id)
              }}
            >
              📦
            </button>
            <button
              className="item-del"
              title="删除此会话"
              onClick={(e) => {
                e.stopPropagation()
                const label = s.title ? `「${s.title.slice(0, 24)}」` : '该会话'
                if (window.confirm(`确定删除 ${label}？（归档文件将一并删除，不可恢复）`))
                  actions.deleteSession(s.session_id)
              }}
            >
              ✕
            </button>
          </div>
        ))}
        {sessions.length === 0 && <div className="search">暂无会话，点击上方新建</div>}
      </div>
      <button className="btn" style={{ marginTop: 'auto' }} onClick={() => actions.setActivity('archives')}>
        📦 历史归档
      </button>
    </>
  )
}

function ArchivesSidebar() {
  const archives = useStore((s) => s.archives)
  const [q, setQ] = useState('')
  useEffect(() => {
    actions.loadArchives()
  }, [])
  const filtered = q
    ? archives.filter(
        (a) =>
          (a.title || '').toLowerCase().includes(q.toLowerCase()) ||
          (a.work_dir || '').toLowerCase().includes(q.toLowerCase()),
      )
    : archives
  const fmt = (ts: number) =>
    ts ? new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false }) : '—'

  return (
    <>
      <h3>📦 历史归档（{archives.length}）</h3>
      <div className="search">
        <input
          style={{ width: '100%', background: 'transparent', border: 'none', color: 'inherit', outline: 'none' }}
          placeholder="搜索标题 / 工作区…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      <div className="scroll">
        {filtered.length === 0 && <div className="search">无归档会话</div>}
        {filtered.map((a) => (
          <div className="item" key={a.session_id} title={a.work_dir}>
            <span className="dot-s" style={{ background: 'var(--muted2)', width: 7, height: 7, borderRadius: '50%' }} />
            <div className="t">
              <div className="n">{a.title || '(未命名会话)'}</div>
              <div className="s">
                {a.round_count} 轮 · {a.model || '—'}
                <br />
                {fmt(a.last_activity)}
              </div>
            </div>
            <button className="item-del" title="查看归档内容" onClick={(e) => { e.stopPropagation(); actions.openArchiveViewer(a.session_id) }}>
              👁
            </button>
            <button className="item-del" title="恢复为可用会话" onClick={(e) => { e.stopPropagation(); actions.resumeSession(a.session_id) }}>
              ↩
            </button>
            <button
              className="item-del"
              title="删除此归档（不可恢复）"
              onClick={(e) => {
                e.stopPropagation()
                const label = a.title ? `「${a.title.slice(0, 24)}」` : '该归档'
                if (window.confirm(`确定删除归档 ${label}？文件将删除，不可恢复。`)) {
                  actions.deleteSession(a.session_id)
                  actions.loadArchives()
                }
              }}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </>
  )
}

function FilesSidebar() {
  const client = useStore((s) => s.client)
  const activeId = useStore((s) => s.activeSessionId)
  const workspace = useStore((s) => s.workspace)
  const workDir = useStore(
    (s) => (s.sessions.find((x) => x.session_id === s.activeSessionId)?.work_dir || '').trim(),
  )
  const [cwd, setCwd] = useState('')
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      if (!client || !activeId) return
      setLoading(true)
      setErr('')
      try {
        const listing = await client.listFiles(activeId, cwd)
        if (!cancelled) setEntries(listing.entries || [])
      } catch (e: any) {
        if (!cancelled) setErr(String(e?.message || e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [client, activeId, cwd])

  async function openFile(name: string) {
    if (!client || !activeId) return
    const path = cwd ? `${cwd}/${name}` : name
    // 走整文件读取：后端 REST 默认只返回 200 行，超长文件会被腰斩，保存时还会写坏原文
    const r = await readTextFull(client, activeId, workDir, path)
    if (r.error) actions.setToast(`读取失败：${r.error}`, 'error')
    if (r.truncated) actions.setToast('文件超过后端 2000 行上限，内容可能不完整', 'error')
    actions.openFile(path, r.content)
  }
  function enterDir(name: string) {
    setCwd(cwd ? `${cwd}/${name}` : name)
  }
  const segments = cwd ? cwd.split('/') : []

  return (
    <>
      <h3>资源管理器 · {workspace}</h3>
      <div className="search" style={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ color: 'var(--accentLite)', cursor: 'pointer' }} onClick={() => setCwd('')}>📁</span>
        {segments.map((seg, i) => (
          <span
            key={i}
            style={{ cursor: 'pointer' }}
            onClick={() => setCwd(segments.slice(0, i + 1).join('/'))}
          >
            {i > 0 && ' / '}
            {seg}
          </span>
        ))}
      </div>
      <div className="scroll tree">
        {loading && <div className="n d">加载中…</div>}
        {!loading && err && <div className="n d" style={{ color: 'var(--danger)' }}>读取失败：{err}</div>}
        {!loading && !err && entries.length === 0 && <div className="n d">空目录</div>}
        {entries.map((n) => (
          <div
            key={n.name}
            className={`n ${n.type === 'dir' ? 'd' : 'f'}`}
            onClick={() => (n.type === 'dir' ? enterDir(n.name) : openFile(n.name))}
          >
            {n.type === 'dir' ? '📁 ' : '📄 '}
            {n.name}
          </div>
        ))}
      </div>
    </>
  )
}

function ExtSidebar() {
  const extTab = useStore((s) => s.extTab)
  const ext = useStore((s) => s.extensions)
  const data = ext || { skills: [], mcp: [], hooks: [], plugins: [], tasks: [] }
  const workDir = useStore(
    (s) => s.sessions.find((x) => x.session_id === s.activeSessionId)?.work_dir || '',
  )

  /** MCP 启停/删除（enterprise/managed 为只读管理作用域，不提供操作） */
  async function mcpToggle(m: McpServerInfo, enabled: boolean) {
    if (m.scope !== 'project' && m.scope !== 'user') return
    const r = await window.auracode.updateMcp({ workDir, scope: m.scope, oldName: m.name, enabled })
    if (r.ok) {
      actions.setToast(`${enabled ? '已启用' : '已禁用'}「${m.name}」（新会话生效）`, 'ok')
      actions.loadExtensions()
    } else {
      actions.setToast(r.message, 'error')
    }
  }
  async function mcpDelete(m: McpServerInfo) {
    if (m.scope !== 'project' && m.scope !== 'user') return
    if (!window.confirm(`确定删除 MCP 服务器「${m.name}」？配置将从文件中移除。`)) return
    const r = await window.auracode.deleteMcp(workDir, m.scope, m.name)
    if (r.ok) {
      actions.setToast(r.message, 'ok')
      actions.loadExtensions()
    } else {
      actions.setToast(r.message, 'error')
    }
  }

  /** 插件启停（写 ~/.auracode/plugins_settings.json） */
  async function pluginToggle(p: PluginInfo, enabled: boolean) {
    const r = await window.auracode.setPluginEnabled(p.name, p.source, enabled)
    if (r.ok) {
      actions.setToast(r.message, 'ok')
      actions.loadExtensions()
    } else {
      actions.setToast(r.message, 'error')
    }
  }

  return (
    <>
      <div className="tabs">
        {EXT_TABS.map((t) => (
          <button key={t} className={extTab === t ? 'on' : ''} onClick={() => actions.setExtTab(t)}>
            {t}
          </button>
        ))}
      </div>
      <div className="scroll">
        {extTab === 'MCP' && <McpList data={data.mcp} onToggle={mcpToggle} onDelete={mcpDelete} />}
        {extTab === '技能' && <SkillList data={data.skills} />}
        {extTab === '插件' && <PluginList data={data.plugins} onToggle={pluginToggle} />}
        {extTab === '钩子' && <HookList data={data.hooks} />}
      </div>
    </>
  )
}

/** 可操作列表项的小按钮（启停/编辑/删除） */
function RowBtn({
  title,
  children,
  onClick,
}: {
  title: string
  children: ReactNode
  onClick: () => void
}) {
  return (
    <button
      className="item-del"
      title={title}
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
    >
      {children}
    </button>
  )
}

function McpList({
  data,
  onToggle,
  onDelete,
}: {
  data: McpServerInfo[]
  onToggle: (m: McpServerInfo, enabled: boolean) => void
  onDelete: (m: McpServerInfo) => void
}) {
  if (data.length === 0)
    return (
      <>
        <button className="btn-primary" onClick={() => actions.openMcp()}>
          🔌 连接 MCP 服务器
        </button>
        <div className="search">
          暂无 MCP 服务器配置
          <br />
          （项目 .mcp.json 或 ~/.auracode/mcp.json）
        </div>
      </>
    )
  return (
    <>
      <button className="btn-primary" onClick={() => actions.openMcp()}>
        🔌 连接 MCP 服务器
      </button>
      {data.map((m) => {
        const manageable = m.scope === 'project' || m.scope === 'user'
        return (
          <div className="item" key={`${m.scope}:${m.name}`} title={`${m.scope} 作用域`}>
            <span className="t">
              <div className="n">{m.name}</div>
              <div className="s">
                {m.scope === 'project' ? '项目' : m.scope === 'user' ? '用户' : m.scope}
                {' · '}
                {m.type}
                {m.command ? ' · ' + m.command : ''}
                {m.url ? ' · ' + m.url : ''}
              </div>
            </span>
            {manageable ? (
              <>
                <span
                  className={`tag ${m.enabled ? 'green' : 'red'}`}
                  style={{ cursor: 'pointer' }}
                  title={m.enabled ? '点击禁用（新会话生效）' : '点击启用'}
                  onClick={() => onToggle(m, !m.enabled)}
                >
                  {m.enabled ? '已启用' : '已禁用'}
                </span>
                <RowBtn
                  title="编辑配置"
                  onClick={() => {
                    if (m.scope === 'project' || m.scope === 'user') actions.openMcpEdit(m.name, m.scope)
                  }}
                >
                  ✎
                </RowBtn>
                <RowBtn title="删除此服务器" onClick={() => onDelete(m)}>✕</RowBtn>
              </>
            ) : (
              <span className={`tag ${m.enabled ? 'green' : 'red'}`} title="企业管理配置，只读">
                {m.enabled ? '已启用' : '已禁用'}
              </span>
            )}
          </div>
        )
      })}
    </>
  )
}

function SkillList({ data }: { data: SkillInfo[] }) {
  return (
    <>
      <button
        className="btn"
        style={{ marginBottom: 8, width: '100%' }}
        onClick={() => actions.openSkillhub()}
      >
        🛒 SkillHub 技能商店
      </button>
      {data.length === 0 && <div className="search">未扫描到技能（skills/*/SKILL.md）</div>}
      {data.map((s) => (
        <div className="item" key={s.name}>
          <span className="t">
            <div className="n">{s.name}</div>
            <div className="s">{s.description}</div>
          </span>
        </div>
      ))}
    </>
  )
}

function PluginList({
  data,
  onToggle,
}: {
  data: PluginInfo[]
  onToggle: (p: PluginInfo, enabled: boolean) => void
}) {
  if (data.length === 0) return <div className="search">未扫描到插件模块（plugins/*.py 中的 ToolPlugin）</div>
  return data.map((p) => {
    const enabled = p.enabled !== false
    return (
      <div className="item" key={`${p.source}:${p.name}`}>
        <span className="t">
          <div className="n">
            {p.name}
            {p.version ? ` v${p.version}` : ''}
          </div>
          <div className="s">{p.description}</div>
        </span>
        <span className="meta">{p.source === 'builtin' ? '内置' : p.source === 'project' ? '项目' : '用户'}</span>
        <span
          className={`tag ${enabled ? 'green' : 'red'}`}
          style={{ cursor: 'pointer' }}
          title="点击切换启停（新会话生效）"
          onClick={() => onToggle(p, !enabled)}
        >
          {enabled ? '启用' : '禁用'}
        </span>
      </div>
    )
  })
}

function HookList({ data }: { data: HookInfo[] }) {
  if (data.length === 0)
    return (
      <>
        <button className="btn-primary" onClick={() => actions.openHooks()}>
          🪝 管理钩子
        </button>
        <div className="search">
          暂无钩子配置
          <br />
          （.auracode/hooks.json 或 ~/.auracode/hooks.json）
        </div>
      </>
    )
  const scopeLabel = (s: string) => (s === 'project' ? '项目' : '用户')
  return (
    <>
      <button className="btn-primary" onClick={() => actions.openHooks()}>
        🪝 管理钩子
      </button>
      {data.map((h, i) => (
        <div className="item" key={`${h.scope}:${i}`} title={`${scopeLabel(h.scope)}级 · ${h.command}`}>
          <span className="t">
            <div className="n">
              {h.event}
              {h.matcher ? ` · ${h.matcher}` : ''}
            </div>
            <div className="s">{h.command}</div>
          </span>
          <span className="meta">{scopeLabel(h.scope)}</span>
          <span className={`tag ${h.enabled ? 'green' : 'red'}`}>{h.enabled ? '启用' : '禁用'}</span>
        </div>
      ))}
    </>
  )
}

function AuditSidebar() {
  const events = useStore((s) => s.events)
  const activeId = useStore((s) => s.activeSessionId)
  const rows = events
    .filter((e) => e.session_id === activeId || !activeId)
    .filter((e) =>
      [
        'permission_request',
        'permission_response',
        'tool_execute',
        'tool_complete',
        'session_created',
        'session_started',
        'session_stopped',
        'session_error',
        'turn_start',
        'turn_complete',
      ].includes(e.type),
    )
    .slice(-80)
    .reverse()

  const time = (t: number) => new Date(t * 1000).toLocaleTimeString('zh-CN', { hour12: false })
  const dotColor: Record<string, string> = {
    permission_request: 'var(--warn)',
    permission_response: 'var(--ok)',
    tool_execute: 'var(--primaryLite)',
    tool_complete: 'var(--accentLite)',
    session_error: 'var(--danger)',
  }

  function describe(e: any): { title: string; sub: string } {
    switch (e.type) {
      case 'permission_request':
        return { title: '权限请求', sub: `${e.data?.tool_name} · ${e.data?.description || ''}` }
      case 'permission_response':
        return {
          title: e.data?.behavior === 'allow' ? '权限允许' : '权限拒绝',
          sub: e.data?.request_id || '',
        }
      case 'tool_execute': {
        const a = typeof e.data?.arguments === 'string' ? safeParse(e.data.arguments) : e.data?.arguments
        const p = a?.path ? ` · ${a.path}` : ''
        return { title: `工具调用 · ${e.data?.tool_name}`, sub: p }
      }
      case 'tool_complete':
        return { title: `工具完成 · ${e.data?.tool_name}`, sub: e.data?.success === false ? '失败' : '成功' }
      case 'session_created':
        return { title: '会话创建', sub: e.session_id?.slice(0, 8) || '' }
      case 'session_started':
        return { title: '会话开始', sub: '' }
      case 'session_stopped':
        return { title: '会话停止', sub: '' }
      case 'session_error':
        return { title: '会话错误', sub: String(e.data?.error || '') }
      case 'turn_start':
        return { title: '轮次开始', sub: '' }
      case 'turn_complete':
        return { title: '轮次完成', sub: '' }
      default:
        return { title: e.type, sub: '' }
    }
  }

  return (
    <>
      <div className="search">🛡️ 审计 / 活动日志</div>
      <div className="scroll">
        {rows.length === 0 && <div className="search">暂无审计记录</div>}
        {rows.map((e) => {
          const d = describe(e)
          return (
            <div className="item" key={e.event_id}>
              <span className="dot-s" style={{ background: dotColor[e.type] || 'var(--muted2)', width: 7, height: 7, borderRadius: '50%' }} />
              <div className="t">
                <div className="n" style={{ color: e.type === 'permission_request' ? 'var(--warn)' : e.type === 'session_error' ? 'var(--danger)' : 'var(--text)' }}>{d.title}</div>
                <div className="s">{d.sub}</div>
              </div>
              <div className="meta">{time(e.timestamp)}</div>
            </div>
          )
        })}
      </div>
    </>
  )
}

function safeParse(s: string) {
  try {
    return JSON.parse(s)
  } catch {
    return {}
  }
}

function TasksSidebar() {
  const ext = useStore((s) => s.extensions)
  const tasks = ext?.tasks || []
  const fmt = (ts?: number) =>
    ts ? new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false }) : '—'
  const dot: Record<string, string> = {
    active: 'var(--ok)',
    expired: 'var(--muted2)',
    cancelled: 'var(--danger)',
    fired: 'var(--warn)',
  }
  if (tasks.length === 0)
    return (
      <>
        <h3>任务 / 作业</h3>
        <div className="search">
          暂无定时任务
          <br />
          （~/.auracode/scheduled_tasks.json）
          <br />
          可用 <b>/cron create</b> 创建周期性/一次性任务
        </div>
      </>
    )
  return (
    <>
      <h3>任务 / 作业（{tasks.length}）</h3>
      <div className="scroll">
        {tasks.map((t) => (
          <div className="item" key={t.job_id}>
            <span className="dot-s" style={{ background: dot[t.status] || 'var(--muted2)', width: 7, height: 7, borderRadius: '50%' }} />
            <span className="t">
              <div className="n">{t.label || t.prompt.slice(0, 40) || t.job_id}</div>
              <div className="s">
                {t.cron} · {t.recurring ? '周期' : '一次性'}
                {t.durable ? ' · 持久化' : ''} · 触发 {t.fire_count} 次
              </div>
            </span>
            <div className="meta">{fmt(t.next_fire_at)}</div>
          </div>
        ))}
      </div>
    </>
  )
}
