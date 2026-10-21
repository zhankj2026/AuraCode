import { useEffect, useMemo, useRef, useState } from 'react'
import { actions, useStore } from '../state/store'
import type { SkillInfo, FileEntry } from '../api/types'

interface Mention {
  type: 'skill' | 'file'
  /** 触发符（/ 或 @）在 text 中的索引 */
  start: number
  /** 触发符之后、光标之前的查询串（@ 模式下可含 / 表示子目录） */
  query: string
}

/**
 * 检测光标前的「提及」触发：
 *  - /   后面跟 [非空格且非 /] 的字符  → 技能选择
 *  - @   后面跟 [非空格且非 @] 的字符  → 文件选择（query 可含 / 用于子目录导航）
 * 触发符必须位于行首或空白之后，避免误触 URL（http://）或邮箱（a@b）。
 */
function detectMention(text: string, cursor: number): Mention | null {
  const before = text.slice(0, cursor)
  const slash = before.match(/(?:^|\s)(\/)([^\s/]*)$/)
  if (slash) {
    const q = slash[2]
    return { type: 'skill', start: cursor - q.length - 1, query: q }
  }
  const at = before.match(/(?:^|\s)(@)([^\s@]*)$/)
  if (at) {
    const q = at[2]
    return { type: 'file', start: cursor - q.length - 1, query: q }
  }
  return null
}

type Item =
  | { kind: 'skill'; name: string; desc: string; insert: string }
  | { kind: 'file'; name: string; isDir: boolean; relPath: string; insert: string }

export function ChatComposer() {
  const activeId = useStore((s) => s.activeSessionId)
  const client = useStore((s) => s.client)
  const mode = useStore((s) => s.mode)
  const extensions = useStore((s) => s.extensions)

  const [text, setText] = useState('')
  const [cursorPos, setCursorPos] = useState(0)
  const [mention, setMention] = useState<Mention | null>(null)
  const [activeIdx, setActiveIdx] = useState(0)
  const [fileCache, setFileCache] = useState<Record<string, FileEntry[]>>({})
  const [loadingDirs, setLoadingDirs] = useState<Set<string>>(new Set())
  const taRef = useRef<HTMLTextAreaElement>(null)

  // 加载技能清单（供 / 触发）。root 就绪后才会真正拉取。
  useEffect(() => {
    if (activeId) actions.loadExtensions()
  }, [activeId])

  // @ 模式下：query 中最后一个 / 之前为目录，之后为过滤词
  const fileDir =
    mention?.type === 'file'
      ? mention.query.includes('/')
        ? mention.query.split('/').slice(0, -1).join('/')
        : ''
      : ''
  const fileFilter =
    mention?.type === 'file'
      ? (
          mention.query.includes('/')
            ? mention.query.split('/').slice(-1)[0]
            : mention.query
        ).toLowerCase()
      : ''

  // 按需拉取目录列表，按目录路径缓存，避免每次按键都打后端。
  useEffect(() => {
    if (!mention || mention.type !== 'file' || !client || !activeId) return
    if (fileCache[fileDir] || loadingDirs.has(fileDir)) return
    let cancelled = false
    setLoadingDirs((s) => new Set(s).add(fileDir))
    client
      .listFiles(activeId, fileDir)
      .then((fl) => {
        if (!cancelled) setFileCache((c) => ({ ...c, [fileDir]: fl.entries }))
      })
      .catch(() => {
        if (!cancelled) setFileCache((c) => ({ ...c, [fileDir]: [] }))
      })
      .finally(() => {
        if (!cancelled)
          setLoadingDirs((s) => {
            const n = new Set(s)
            n.delete(fileDir)
            return n
          })
      })
    return () => {
      cancelled = true
    }
  }, [mention, fileDir, client, activeId, fileCache, loadingDirs])

  const items = useMemo<Item[]>(() => {
    if (!mention) return []
    if (mention.type === 'skill') {
      const q = mention.query.toLowerCase()
      const skills: SkillInfo[] = extensions?.skills ?? []
      return skills
        .filter(
          (s) =>
            !q ||
            s.name.toLowerCase().includes(q) ||
            (s.description || '').toLowerCase().includes(q),
        )
        .slice(0, 12)
        .map((s) => ({ kind: 'skill', name: s.name, desc: s.description || '', insert: `/${s.name} ` }))
    }
    // 文件模式
    const entries = fileCache[fileDir] ?? []
    return entries
      .filter((e) => !fileFilter || e.name.toLowerCase().includes(fileFilter))
      .sort((a, b) =>
        a.type === b.type ? a.name.localeCompare(b.name) : a.type === 'dir' ? -1 : 1,
      )
      .slice(0, 12)
      .map((e) => {
        const isDir = e.type === 'dir'
        const relPath = fileDir ? `${fileDir}/${e.name}` : e.name
        return {
          kind: 'file',
          name: e.name,
          isDir,
          relPath,
          insert: isDir ? `@${relPath}/` : `@${relPath} `,
        }
      })
  }, [mention, extensions, fileCache, fileDir, fileFilter])

  // 候选项变化时，高亮复位到第一项
  useEffect(() => {
    setActiveIdx(0)
  }, [items])

  function recompute(t: string, c: number) {
    setText(t)
    setCursorPos(c)
    setMention(detectMention(t, c))
  }

  function applyInsertion(insert: string) {
    if (!mention) return
    const start = mention.start
    const end = cursorPos
    const next = text.slice(0, start) + insert + text.slice(end)
    setText(next)
    const newCursor = start + insert.length
    setMention(null)
    requestAnimationFrame(() => {
      const ta = taRef.current
      if (ta) {
        ta.focus()
        ta.setSelectionRange(newCursor, newCursor)
      }
    })
  }

  function selectActive() {
    const it = items[activeIdx]
    if (it) applyInsertion(it.insert)
  }

  function send() {
    const content = text.trim()
    if (!content || !client || !activeId) return
    setText('')
    setMention(null)
    // 本地即时渲染用户消息
    actions.pushEvent({
      event_id: `u_${Date.now()}`,
      type: 'user_message',
      session_id: activeId,
      data: { content },
      timestamp: Date.now() / 1000,
    })
    client.sendMessage(activeId, content).catch((e) => actions.log('发送失败: ' + e))
  }

  function onKeyDown(ev: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (mention && items.length) {
      if (ev.key === 'ArrowDown') {
        ev.preventDefault()
        setActiveIdx((i) => (i + 1) % items.length)
        return
      }
      if (ev.key === 'ArrowUp') {
        ev.preventDefault()
        setActiveIdx((i) => (i - 1 + items.length) % items.length)
        return
      }
      if (ev.key === 'Enter' && !ev.shiftKey) {
        ev.preventDefault()
        selectActive()
        return
      }
      if (ev.key === 'Tab') {
        ev.preventDefault()
        selectActive()
        return
      }
      if (ev.key === 'Escape') {
        ev.preventDefault()
        setMention(null)
        return
      }
    }
    if (ev.key === 'Enter' && !ev.shiftKey) {
      ev.preventDefault()
      send()
    }
  }

  const showPop = !!mention
  const loading =
    mention?.type === 'file' && !fileCache[fileDir] && loadingDirs.has(fileDir)
  const empty = showPop && items.length === 0 && !loading

  return (
    <div className="composer">
      {showPop && (
        <div className="mention-pop">
          <div className="mention-head">
            {mention!.type === 'skill' ? '选择技能（输入 / 触发）' : '选择文件（输入 @ 触发）'}
          </div>
          {loading && <div className="mention-empty">加载中…</div>}
          {empty && (
            <div className="mention-empty">
              {mention!.type === 'skill' ? '无匹配技能' : '无匹配文件'}
            </div>
          )}
          {items.map((it, i) => (
            <div
              key={(it.kind === 'skill' ? 's:' : 'f:') + (it.kind === 'file' ? it.relPath : it.name)}
              className={`mention-item ${i === activeIdx ? 'active' : ''}`}
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => setActiveIdx(i)}
              onClick={() => applyInsertion(it.insert)}
            >
              <span className="mention-ic">
                {it.kind === 'skill' ? '🧩' : it.kind === 'file' && it.isDir ? '📁' : '📄'}
              </span>
              <span className="mention-label">{it.kind === 'file' ? it.relPath : it.name}</span>
              {it.kind === 'skill' && it.desc && (
                <span className="mention-sub">{it.desc}</span>
              )}
            </div>
          ))}
        </div>
      )}
      <div className="cin">
        <textarea
          ref={taRef}
          rows={1}
          placeholder="给 AuraCode 下达任务，输入 / 选技能、@ 选文件…"
          value={text}
          onChange={(ev) =>
            recompute(ev.target.value, ev.target.selectionStart ?? ev.target.value.length)
          }
          onSelect={(ev) => {
            const c = ev.currentTarget.selectionStart ?? 0
            setCursorPos(c)
            setMention(detectMention(text, c))
          }}
          onKeyDown={onKeyDown}
        />
        <button className="send" onClick={send}>
          发送 ▸
        </button>
      </div>
      <div className="hint">
        <span className="ok">● 当前模式：{mode}</span>
        <span>/ 选技能 · @ 选文件 · Enter 发送 · Shift+Enter 换行</span>
      </div>
    </div>
  )
}
