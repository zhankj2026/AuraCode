import { useEffect, useState } from 'react'
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
  return <TasksSidebar />
}

function ChatSidebar() {
  const sessions = useStore((s) => s.sessions)
  const activeId = useStore((s) => s.activeSessionId)

  return (
    <>
      <button className="btn-primary" onClick={() => actions.newSession()}>
        ＋ 新会话
      </button>
      <div className="search">🔍 搜索会话</div>
      <div className="scroll">
        {sessions.map((s) => (
          <div
            key={s.session_id}
            className={`item ${activeId === s.session_id ? 'active' : ''}`}
            onClick={() => actions.selectSession(s.session_id)}
          >
            <span
              className="dot-s"
              style={{ background: activeId === s.session_id ? 'var(--accentLite)' : '#3a4a66', width: 7, height: 7, borderRadius: '50%' }}
            />
            <div className="t">
              <div className="n">{s.title || '(未命名会话)'}</div>
              <div className="s">{s.round_count} 轮 · {s.model || '—'} · {s.state}</div>
            </div>
          </div>
        ))}
        {sessions.length === 0 && <div className="search">暂无会话，点击上方新建</div>}
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
        {extTab === 'MCP' && <McpList data={data.mcp} />}
        {extTab === '技能' && <SkillList data={data.skills} />}
        {extTab === '插件' && <PluginList data={data.plugins} />}
        {extTab === '钩子' && <HookList data={data.hooks} />}
      </div>
    </>
  )
}

function McpList({ data }: { data: McpServerInfo[] }) {
  if (data.length === 0)
    return (
      <div className="search">
        暂无 MCP 服务器配置
        <br />
        （项目 .mcp.json 或 ~/.auracode/mcp.json）
      </div>
    )
  return (
    <>
      <button className="btn-primary" onClick={() => actions.openMcp()}>
        🔌 连接 MCP 服务器
      </button>
      {data.map((m) => (
        <div className="item" key={`${m.scope}:${m.name}`}>
          <span className="t">
            <div className="n">{m.name}</div>
            <div className="s">
              {m.type}
              {m.command ? ' · ' + m.command : ''}
              {m.url ? ' · ' + m.url : ''}
            </div>
          </span>
          <span className={`tag ${m.enabled ? 'green' : 'red'}`}>{m.enabled ? '已启用' : '已禁用'}</span>
        </div>
      ))}
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

function PluginList({ data }: { data: PluginInfo[] }) {
  if (data.length === 0) return <div className="search">未扫描到插件模块（plugins/*.py 中的 ToolPlugin）</div>
  return data.map((p) => (
    <div className="item" key={`${p.source}:${p.name}`}>
      <span className="t">
        <div className="n">
          {p.name}
          {p.version ? ` v${p.version}` : ''}
        </div>
        <div className="s">{p.description}</div>
      </span>
      <span className="meta">{p.source}</span>
      {p.enabled === true && <span className="tag green">启用</span>}
      {p.enabled === false && <span className="tag red">禁用</span>}
    </div>
  ))
}

function HookList({ data }: { data: HookInfo[] }) {
  if (data.length === 0)
    return (
      <div className="search">
        暂无钩子配置
        <br />
        （.auracode/hooks.json）
      </div>
    )
  return data.map((h, i) => (
    <div className="item" key={i}>
      <span className="t">
        <div className="n">
          {h.event}
          {h.matcher ? ` · ${h.matcher}` : ''}
        </div>
        <div className="s">{h.command}</div>
      </span>
      <span className={`tag ${h.enabled ? 'green' : 'red'}`}>{h.enabled ? '启用' : '禁用'}</span>
    </div>
  ))
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
