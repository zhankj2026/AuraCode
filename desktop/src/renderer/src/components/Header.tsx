import { useEffect, useRef, useState } from 'react'
import { actions, useStore } from '../state/store'

export function Header() {
  const sessions = useStore((s) => s.sessions)
  const activeId = useStore((s) => s.activeSessionId)
  const tempSession = useStore((s) => s.tempSession)
  const mode = useStore((s) => s.mode)
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')

  const active = sessions.find((s) => s.session_id === activeId)
  const model = active?.model || '未设置'
  const usage = `轮次 ${active?.round_count ?? 0} · 事件 ${active?.event_count ?? 0}`
  const ref = useRef<HTMLDivElement>(null)

  const current = (active?.work_dir || '').trim()
  const recent = Array.from(
    new Set(sessions.map((s) => (s.work_dir || '').trim()).filter(Boolean)),
  ).filter((w) => w !== current)
  const filtered = q
    ? recent.filter((w) => w.toLowerCase().includes(q.toLowerCase()))
    : recent

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('click', onDoc)
    return () => document.removeEventListener('click', onDoc)
  }, [])

  function pick(dir: string) {
    actions.switchToWorkdir(dir)
    setOpen(false)
    setQ('')
  }
  function openLocal() {
    actions.openWorkspace()
    setOpen(false)
    setQ('')
  }
  function temp() {
    actions.newTempSession()
    setOpen(false)
  }

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

      <button className="pill" onClick={() => actions.openSettings()} title="模型设置">
        <span className="k">模型</span>
        <span className="v">{model}</span> ▾
      </button>
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
