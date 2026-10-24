import { useCallback, useEffect, useRef, useState } from 'react'
import { actions, useStore } from '../state/store'

/** 模型目录兜底选项（拉取后端 /api/models 失败时使用）。 */
const MODEL_FALLBACK: Array<{ id: string; provider?: string; note?: string }> = [
  { id: 'GLM-4-Flash', provider: 'zhipu', note: '免费 · 实测可用' },
  { id: 'glm-4.7', provider: 'zhipu', note: '付费' },
  { id: 'glm-4.6', provider: 'zhipu', note: '付费' },
  { id: 'glm-4.5-air', provider: 'zhipu', note: '付费' },
  { id: 'GLM-5.3-Flash', provider: 'zhipu', note: '当前 Key 已欠费' },
  { id: 'glm-5.3-flashx', provider: 'zhipu', note: '当前 Key 已欠费' },
  { id: 'deepseek-chat', provider: 'deepseek', note: '需另配 Key' },
]

function provIcon(p?: string): string {
  switch ((p || '').toLowerCase()) {
    case 'openai': return '🟢'
    case 'zhipu': case 'glm': return '🔷'
    case 'deepseek': return '🔶'
    case 'moonshot': case 'kimi': return '🌙'
    case 'qwen': case 'dashscope': return '🟠'
    case 'siliconflow': return '💎'
    case 'volcano': case 'ark': return '🌋'
    case 'anthropic': case 'claude': return '🟣'
    default: return '🤖'
  }
}

function badgeClass(note?: string): string {
  if (!note) return 'tag'
  if (note.includes('欠费')) return 'tag red'
  if (note.includes('免费') || note.includes('折扣') || note.includes('限免')) return 'tag green'
  return 'tag'
}

export function Header() {
  const sessions = useStore((s) => s.sessions)
  const activeId = useStore((s) => s.activeSessionId)
  const tempSession = useStore((s) => s.tempSession)
  const mode = useStore((s) => s.mode)
  const client = useStore((s) => s.client)
  const customModels = useStore((s) => s.customModels)
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [recent, setRecent] = useState<string[]>([])

  const [modelOpen, setModelOpen] = useState(false)
  const [catalog, setCatalog] = useState<Array<{ id: string; provider?: string; note?: string }>>([])
  const [mloading, setMloading] = useState(false)
  const [switching, setSwitching] = useState(false)
  const [mq, setMq] = useState('')

  const loadRecent = useCallback(() => {
    window.auracode
      .getWorkspaceRecent()
      .then(setRecent)
      .catch(() => setRecent([]))
  }, [])

  const active = sessions.find((s) => s.session_id === activeId)
  const model = active?.model || '未设置'
  const usage = `轮次 ${active?.round_count ?? 0} · 事件 ${active?.event_count ?? 0}`
  const ref = useRef<HTMLDivElement>(null)
  const mref = useRef<HTMLDivElement>(null)

  const current = (active?.work_dir || '').trim()
  const shown = recent.filter((w) => w !== current).slice(0, 10)
  const filtered = q
    ? shown.filter((w) => w.toLowerCase().includes(q.toLowerCase()))
    : shown

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
      if (mref.current && !mref.current.contains(e.target as Node)) setModelOpen(false)
    }
    document.addEventListener('click', onDoc)
    return () => document.removeEventListener('click', onDoc)
  }, [])

  // 每次打开下拉都重新拉取「最近工作区」历史（含本次会话刚记录的）
  useEffect(() => {
    if (open) loadRecent()
  }, [open, loadRecent])

  // 模型下拉打开时拉取模型目录
  useEffect(() => {
    if (!modelOpen || !client) return
    let alive = true
    setMloading(true)
    client
      .listModels()
      .then((m) => {
        if (!alive) return
        setCatalog(m.models?.length ? m.models : MODEL_FALLBACK)
        setMloading(false)
      })
      .catch(() => {
        if (!alive) return
        setCatalog(MODEL_FALLBACK)
        setMloading(false)
      })
    return () => { alive = false }
  }, [modelOpen, client])

  function pick(dir: string) {
    actions.switchToWorkdir(dir)
    setOpen(false)
    setQ('')
    loadRecent()
  }
  function openLocal() {
    actions.openWorkspace()
    setOpen(false)
    setQ('')
    loadRecent()
  }
  function temp() {
    actions.newTempSession()
    setOpen(false)
  }

  async function pickModel(value: string) {
    if (!client || !activeId) {
      actions.setToast('请先选择一个会话', 'info')
      return
    }
    // 归档会话不能直接切模型（后端无活跃实例）。归档现在在专门的管理页
    // （对话侧栏底部「📦 历史归档」入口），需先 ↩ 恢复为活跃会话再切换。
    const sess = sessions.find((s) => s.session_id === activeId)
    if (sess?.archived) {
      actions.setToast('归档会话不可直接操作：请到「历史归档」页先恢复为可用会话', 'info')
      setModelOpen(false)
      return
    }
    if (switching) return
    setSwitching(true)
    try {
      if (value.startsWith('custom:')) {
        const cm = customModels.find((c) => `custom:${c.id}` === value)
        if (!cm) return
        await client.switchModel(activeId, cm.model, cm.base_url, cm.api_key)
        actions.updateSessionModel(activeId, cm.model)
        actions.setToast(`已切换模型：${cm.model}`, 'ok')
      } else {
        await client.switchModel(activeId, value)
        actions.updateSessionModel(activeId, value)
        actions.setToast(`已切换模型：${value}`, 'ok')
      }
    } catch (e: any) {
      actions.setToast('切换失败：' + String(e?.message || e), 'error')
    } finally {
      setSwitching(false)
      setModelOpen(false)
    }
  }

  const mf = catalog.filter((o) =>
    !mq || o.id.toLowerCase().includes(mq.toLowerCase()),
  )
  const cf = customModels.filter(
    (c) => !mq || c.name.toLowerCase().includes(mq.toLowerCase()) || c.model.toLowerCase().includes(mq.toLowerCase()),
  )

  return (
    <header>
      <div className="logo">
        <span className="dot" />
        AuraCode
      </div>

      <div style={{ position: 'relative' }} ref={ref}>
        <button className="ws" onClick={() => setOpen((v) => !v)} title={tempSession ? '临时会话' : current}>
          {tempSession ? '💭 临时会话' : `📁 ${current || '未选择工作区'}`}
          <span style={{ color: 'var(--muted)', fontSize: 10 }}>▾</span>
        </button>
        {open && (
          <div className="wsmenu show">
            <div className="wsearch">
              <input
                autoFocus
                placeholder="搜索工作区路径…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Escape') setOpen(false)
                }}
              />
            </div>

            {tempSession ? (
              <div className="wi on">
                💭 临时会话<span className="tag green">当前</span>
              </div>
            ) : current ? (
              <div className="wi on">
                📁 <span className="nm">{current}</span>
                <span className="tag green">当前</span>
              </div>
            ) : null}

            {filtered.length > 0 && <div className="wgroup">最近工作区</div>}
            {filtered.map((w) => (
              <div key={w} className="wi" onClick={() => pick(w)}>
                📁 <span className="nm">{w}</span>
              </div>
            ))}
            {filtered.length === 0 && q && <div className="wi muted">无匹配工作区</div>}

            <div className="sep" />
            <div className="wi" onClick={openLocal}>📂 浏览文件夹…</div>
            <div className="wi" onClick={temp}>💭 无工作区临时会话</div>
          </div>
        )}
      </div>

      <div className="seg">
        {['普通', '自动', '计划'].map((m) => (
          <button key={m} className={mode === m ? 'on' : ''} onClick={() => actions.setMode(m)}>
            {m}
          </button>
        ))}
      </div>

      <div className="spacer" />

      <div style={{ position: 'relative' }} ref={mref}>
        <button className="pill" onClick={() => setModelOpen((v) => !v)} title="选择模型">
          <span className="k">模型</span>
          <span className="v">{model}</span> ▾
        </button>
        {modelOpen && (
          <div className="wsmenu show modelmenu">
            <div className="wsearch">
              <input
                autoFocus
                placeholder="搜索模型…"
                value={mq}
                onChange={(e) => setMq(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Escape') setModelOpen(false)
                }}
              />
            </div>

            {mloading && <div className="wi muted">加载模型目录…</div>}
            {!mloading && mf.length > 0 && <div className="wgroup">内置模型</div>}
            {!mloading && mf.map((o) => (
              <div
                key={o.id}
                className={`wi ${model === o.id ? 'on' : ''}`}
                onClick={() => pickModel(o.id)}
              >
                <span className="mi-ic">{provIcon(o.provider)}</span>
                <span className="nm">{o.id}</span>
                {o.note && <span className={badgeClass(o.note)}>{o.note}</span>}
                {model === o.id && <span className="tag green">当前</span>}
              </div>
            ))}

            {!mloading && cf.length > 0 && <div className="wgroup">自定义模型</div>}
            {!mloading && cf.map((c) => (
              <div
                key={c.id}
                className={`wi ${model === c.model ? 'on' : ''}`}
                onClick={() => pickModel(`custom:${c.id}`)}
              >
                <span className="mi-ic">◇</span>
                <span className="nm">{c.name}</span>
                <span className="tag green">自定义</span>
                {model === c.model && <span className="tag">当前</span>}
              </div>
            ))}

            {!mloading && mf.length === 0 && cf.length === 0 && (
              <div className="wi muted">无匹配模型</div>
            )}

            <div className="sep" />
            <div className="wi" onClick={() => { setModelOpen(false); actions.setActivity('models') }}>
              🧩 管理自定义模型…
            </div>
          </div>
        )}
      </div>
      <button className="pill" title="当前会话用量">
        <span className="k">用量</span>
        <span className="v">{usage}</span>
      </button>
      <button className="iconbtn" title="设置" onClick={() => actions.openSettings()}>
        ⚙
      </button>
    </header>
  )
}
