import { ReactNode, useEffect, useMemo, useState } from 'react'
import { actions, useStore } from '../state/store'
import { readTextFull } from '../api/fsread'
import { CronCreateModal } from './CronCreateModal'
import { CronEditModal } from './CronEditModal'
import type { FileEntry, McpServerInfo, SkillInfo, PluginInfo, HookInfo, TaskInfo } from '../api/types'
import { AUDIT_EVENT_TYPES, buildAuditTurns, fmtDuration } from '../lib/audit'

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

// ── 审计视图：按轮次分组的明细日志 ──────────────────────────────
// 分组/配对逻辑在 ../lib/audit.ts（可单测）；这里只做展示与展开交互。

function AuditSidebar() {
  const events = useStore((s) => s.events)
  const activeId = useStore((s) => s.activeSessionId)
  // 轮次展开状态：undefined = 走默认（最近 2 个轮次展开）；条目默认收起
  const [turnOpen, setTurnOpen] = useState<Record<string, boolean>>({})
  const [entryOpen, setEntryOpen] = useState<Record<string, boolean>>({})
  // pre 内容"展开全部"状态
  const [fullText, setFullText] = useState<Record<string, boolean>>({})

  const turns = useMemo(() => {
    const rows = events
      .filter((e) => e.session_id === activeId || !activeId)
      .filter((e) => AUDIT_EVENT_TYPES.includes(e.type))
    return buildAuditTurns(rows)
  }, [events, activeId])

  const time = (t: number) => new Date(t * 1000).toLocaleTimeString('zh-CN', { hour12: false })
  const statusStyle: Record<string, { color: string; icon: string }> = {
    running: { color: 'var(--warn)', icon: '⏳' },
    success: { color: 'var(--ok)', icon: '✔' },
    fail: { color: 'var(--danger)', icon: '✖' },
    info: { color: 'var(--muted2)', icon: '·' },
  }

  // 展示按时间倒序（最新轮次在最上），默认展开最近 2 个轮次
  const display = useMemo(() => [...turns].reverse(), [turns])

  const toggle = (
    set: React.Dispatch<React.SetStateAction<Record<string, boolean>>>,
    key: string,
  ) => set((m) => ({ ...m, [key]: !(m[key] ?? false) }))

  return (
    <>
      <div className="search">🛡️ 审计 · 轮次明细（{turns.length} 轮）</div>
      <div className="scroll">
        {display.length === 0 && (
          <div className="search">暂无审计记录
            <br />发起对话后这里会记录每轮的工具调用、参数与结果
          </div>
        )}
        {display.map((t, idx) => {
          const defaultOpen = idx < 2
          const open = turnOpen[t.key] ?? defaultOpen
          const dur = t.endTs && t.startTs ? t.endTs - t.startTs : 0
          const toolCount = t.entries.filter((e) => e.kind === 'tool').length
          const running = t.entries.some((e) => e.status === 'running')
          return (
            <div className="audit-turn" key={t.key || idx}>
              <div
                className="audit-head"
                onClick={() => toggle(setTurnOpen, t.key)}
                title={t.userPrompt}
              >
                <span className="audit-caret">{open ? '▾' : '▸'}</span>
                <span className="t">
                  <div className="n">
                    {t.turnNo !== null ? `第 ${t.turnNo} 轮` : t.userPrompt ? '进行中' : '系统'}
                    {running && <span style={{ color: 'var(--warn)' }}> · 运行中</span>}
                    <span className="audit-sum">
                      {toolCount > 0 ? ` · ${toolCount} 个工具` : ''}
                      {dur > 0 ? ` · ${fmtDuration(dur)}` : ''}
                    </span>
                  </div>
                  {t.userPrompt && (
                    <div className="s audit-prompt">👤 {t.userPrompt.slice(0, 60)}</div>
                  )}
                  {!open && t.preview && (
                    <div className="s audit-preview">{t.preview.slice(0, 60)}</div>
                  )}
                </span>
              </div>
              {open && (
                <div className="audit-body">
                  {t.userPrompt && t.userPrompt.length > 60 && (
                    <div className="audit-entry">
                      <span className="audit-ic">👤</span>
                      <div className="t">
                        <div className="audit-fulltext">{t.userPrompt}</div>
                      </div>
                    </div>
                  )}
                  {t.entries.length === 0 && !t.userPrompt && (
                    <div className="audit-entry"><span className="audit-ic">·</span><div className="t"><div className="s">（无活动）</div></div></div>
                  )}
                  {t.entries.map((en) => {
                    const st = statusStyle[en.status] || statusStyle.info
                    const eOpen = entryOpen[en.key] ?? false
                    const expandable = en.detail.length > 0
                    return (
                      <div className="audit-entry" key={en.key}>
                        <div
                          className={`audit-row ${expandable ? 'clickable' : ''}`}
                          onClick={() => expandable && toggle(setEntryOpen, en.key)}
                        >
                          <span className="audit-ic" style={{ color: st.color }}>{st.icon}</span>
                          <div className="t">
                            <div className="n">
                              {en.title}
                              {en.duration != null && (
                                <span className="audit-sum"> · {fmtDuration(en.duration)}</span>
                              )}
                            </div>
                            {en.sub && <div className="s">{en.sub}</div>}
                          </div>
                          <div className="meta">{time(en.ts)}</div>
                        </div>
                        {eOpen && expandable && (
                          <div className="audit-detail">
                            {en.detail.map((sec, si) => {
                              const fk = `${en.key}_${si}`
                              const long = sec.text.length > 400 || sec.text.split('\n').length > 10
                              const showFull = fullText[fk] ?? false
                              const text = showFull || !long ? sec.text : sec.text.split('\n').slice(0, 10).join('\n').slice(0, 400)
                              return (
                                <div className="audit-sec" key={fk}>
                                  <div className="audit-sec-lbl">
                                    {sec.label}
                                    {long && (
                                      <button
                                        type="button"
                                        className="audit-more"
                                        onClick={() => toggle(setFullText, fk)}
                                      >
                                        {showFull ? '收起' : '展开全部'}
                                      </button>
                                    )}
                                  </div>
                                  <pre className={sec.tone === 'err' ? 'err' : ''}>{text}</pre>
                                </div>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    )
                  })}
                  {t.preview && (
                    <div className="audit-entry">
                      <span className="audit-ic">🤖</span>
                      <div className="t">
                        <div className="s audit-preview">{t.preview}</div>
                      </div>
                    </div>
                  )}
                </div>
              )}
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
  const activeSessionId = useStore((s) => s.activeSessionId)
  const sessions = useStore((s) => s.sessions)
  const client = useStore((s) => s.client)
  const [open, setOpen] = useState(false)
  const [busyId, setBusyId] = useState('')
  const [editing, setEditing] = useState<TaskInfo | null>(null)
  const fmt = (ts?: number) =>
    ts ? new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false }) : '—'
  const dot: Record<string, string> = {
    active: 'var(--ok)',
    paused: 'var(--warn)',
    expired: 'var(--muted2)',
    cancelled: 'var(--danger)',
    fired: 'var(--warn)',
  }
  // 任务操作统一走 bridge REST（调度器在 bridge 进程内存中，直接改
  // scheduled_tasks.json 会被其下次落盘覆盖）。成功后刷新扩展列表。
  const op = async (jobId: string, fn: (id: string) => Promise<unknown>, okMsg: string) => {
    if (busyId) return
    if (!client) {
      actions.setToast('后端未连接，无法操作定时任务', 'error')
      return
    }
    setBusyId(jobId)
    try {
      await fn(jobId)
      actions.setToast(okMsg, 'ok')
      actions.loadExtensions()
    } catch (e) {
      actions.setToast(e instanceof Error ? e.message : String(e), 'error')
    } finally {
      setBusyId('')
    }
  }
  const del = (t: TaskInfo) => {
    if (busyId || !client) return
    const c = client
    if (!window.confirm(`确定删除定时任务「${t.label || t.prompt.slice(0, 30) || t.job_id}」？删除后不可恢复。`)) return
    void op(t.job_id, (id) => c.deleteCron(id), '定时任务已删除')
  }
  const pauseOrResume = (t: TaskInfo, resume: boolean) => {
    if (!client) return
    const c = client
    if (resume) void op(t.job_id, (id) => c.resumeCron(id), '定时任务已恢复')
    else void op(t.job_id, (id) => c.pauseCron(id), '定时任务已暂停')
  }
  return (
    <>
      <h3>任务 / 作业（{tasks.length}）</h3>
      <button
        className="btn-primary"
        style={{ marginBottom: 8 }}
        onClick={() => setOpen(true)}
      >
        ⏰ 新建定时任务
      </button>
      <div className="scroll">
        {tasks.length === 0 && (
          <div className="search">
            暂无定时任务
            <br />
            （~/.auracode/scheduled_tasks.json）
            <br />
            点上方按钮创建，或用 <b>/cron create</b>
          </div>
        )}
        {tasks.map((t) => (
          <div className="item" key={t.job_id} style={{ cursor: 'default' }}>
            <span className="dot-s" style={{ background: dot[t.status] || 'var(--muted2)', width: 7, height: 7, borderRadius: '50%' }} />
            <span className="t">
              <div className="n">{t.label || t.prompt.slice(0, 40) || t.job_id}</div>
              <div className="s">
                {t.cron} · {t.recurring ? '周期' : '一次性'}
                {t.durable ? ' · 持久化' : ''} · 触发 {t.fire_count} 次
                {t.session_id ? ` · 会话 ${t.session_id.slice(0, 6)}` : ''}
                {t.status === 'paused' ? ' · 已暂停' : ''}
              </div>
            </span>
            {t.status === 'paused' ? (
              <button
                className="cron-op"
                title="恢复任务（下次触发时间从现在重算）"
                disabled={busyId === t.job_id}
                onClick={() => pauseOrResume(t, true)}
              >
                ▶
              </button>
            ) : (
              <button
                className="cron-op"
                title="暂停任务（保留配置，不再触发）"
                disabled={busyId === t.job_id}
                onClick={() => pauseOrResume(t, false)}
              >
                ⏸
              </button>
            )}
            <button
              className="cron-op"
              title="编辑任务（表达式/提示词/类型/关联会话）"
              disabled={busyId === t.job_id}
              onClick={() => setEditing(t)}
            >
              ✏️
            </button>
            <button
              className="cron-op danger"
              title="删除任务（不可恢复）"
              disabled={busyId === t.job_id}
              onClick={() => del(t)}
            >
              🗑
            </button>
            <div className="meta">{t.status === 'paused' ? '已暂停' : fmt(t.next_fire_at)}</div>
          </div>
        ))}
      </div>
      {open && (
        <CronCreateModal
          activeSessionId={activeSessionId}
          sessions={sessions}
          client={client}
          onClose={() => setOpen(false)}
          onToast={(m, k) => actions.setToast(m, k)}
          onCreated={() => actions.loadExtensions()}
        />
      )}
      {editing && (
        <CronEditModal
          task={editing}
          sessions={sessions}
          client={client}
          onClose={() => setEditing(null)}
          onToast={(m, k) => actions.setToast(m, k)}
          onUpdated={() => actions.loadExtensions()}
        />
      )}
    </>
  )
}

// CronCreateModal 已抽到 ./CronCreateModal.tsx（含可视化 cron 构建器 CronBuilder）
