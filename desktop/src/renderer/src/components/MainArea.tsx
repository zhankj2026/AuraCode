import { useEffect, useMemo, useRef, useState } from 'react'
import { actions, useStore } from '../state/store'
import type { BridgeEvent } from '../api/types'
import { CodeEditor } from './CodeEditor'
import { HtmlPreview } from './HtmlPreview'
import { ChatComposer } from './ChatComposer'
import { CustomModels } from './CustomModels'
import { ImagePreview, MarkdownPreview, OfficePreview } from './FilePreview'
import { renderMarkdown } from '../lib/md'

export function MainArea() {
  const activeTab = useStore((s) => s.activeTab)
  const openFiles = useStore((s) => s.openFiles)
  const activity = useStore((s) => s.activity)

  // 文件 Tab 仅在「文件」活动或当前打开文件时显示
  const showFiles = activity === 'files' || openFiles.length > 0
  const chatTitle = useStore(
    (s) => s.sessions.find((x) => x.session_id === s.activeSessionId)?.title || '对话',
  )

  // 自定义模型管理是独立全屏面板，不套用对话/文件 Tab
  if (activity === 'models') {
    return (
      <div className="main">
        <CustomModels />
      </div>
    )
  }

  // 归档管理页：归档列表在左侧 Sidebar，主区显示选中的归档内容查看器
  if (activity === 'archives') {
    return (
      <div className="main">
        <ArchiveViewer />
      </div>
    )
  }

  return (
    <div className="main">
      <div className="tabstrip">
        <div className={`ctab ${activeTab === 'chat' ? 'on' : ''}`} onClick={() => actions.setActiveTab('chat')}>
          💬 {chatTitle}
        </div>
        {openFiles.map((f) => (
          <div
            key={f.path}
            className={`ctab ${activeTab === f.path ? 'on' : ''}`}
            onClick={() => actions.setActiveTab(f.path)}
          >
            📄 {f.path.split('/').pop()}
            {f.dirty && <span className="dot" />}
            <span
              className="x"
              onClick={(e) => {
                e.stopPropagation()
                actions.closeFile(f.path)
              }}
            >
              ✕
            </span>
          </div>
        ))}
      </div>

      {activeTab === 'chat' ? <ChatThread /> : <FileEditor key={activeTab} path={activeTab} />}
    </div>
  )
}

function ChatThread() {
  const activeId = useStore((s) => s.activeSessionId)
  const allEvents = useStore((s) => s.events)
  const stageRef = useRef<HTMLDivElement>(null)
  /** 是否贴底（距底 < 40px）。用户上翻阅读历史时暂停自动跟随，回到底部再恢复 */
  const stickBottomRef = useRef(true)

  // 本会话要渲染的事件。user_message 可能「本地即时渲染 + 后端回放」重复，按 (会话,内容) 去重一次。
  const events = useMemo(() => {
    const seenU = new Set<string>()
    return allEvents
      .filter((e) => e.session_id === activeId)
      .filter((e) =>
        ['user_message', 'assistant_message', 'tool_execute', 'tool_result', 'result', 'output', 'status', 'history_restored',
         'api_retry', 'turn_retry', 'fallback_activated'].includes(
          e.type,
        ),
      )
      .filter((e) => {
        if (e.type === 'user_message') {
          const k = e.session_id + '|' + (e.data?.content ?? '')
          if (seenU.has(k)) return false
          seenU.add(k)
        }
        return true
      })
  }, [allEvents, activeId])

  // 用户手动滚动 → 更新"是否贴底"标记（程序滚动不触发：置 ignore 标记）
  const programScrollRef = useRef(false)
  useEffect(() => {
    const el = stageRef.current
    if (!el) return
    const onScroll = () => {
      if (programScrollRef.current) {
        programScrollRef.current = false
        return
      }
      const dist = el.scrollHeight - el.scrollTop - el.clientHeight
      stickBottomRef.current = dist < 40
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  // 自动跟随：新事件 OR 流式内容增长（最后一条 assistant_message 的长度变化）都触发。
  // 关键修复：此前只依赖 events.length，text_chunk 原地 upsert 长度不变 → 打字过程永不滚动。
  const lastStreamLen = useMemo(() => {
    const last = events[events.length - 1]
    if (last && last.type === 'assistant_message') return String(last.data?.content ?? '').length
    return 0
  }, [events])

  useEffect(() => {
    if (!stickBottomRef.current) return
    const el = stageRef.current
    if (!el) return
    programScrollRef.current = true
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    // smooth 滚动结束前的中间滚动位置不该重置贴底标记，用超时兜底清掉程序标记
    setTimeout(() => {
      programScrollRef.current = false
      stickBottomRef.current = true
    }, 400)
  }, [events.length, lastStreamLen])

  // 切换会话 → 重置为贴底跟随（新会话从头展示最底部）
  useEffect(() => {
    stickBottomRef.current = true
    const el = stageRef.current
    if (el) {
      programScrollRef.current = true
      el.scrollTo({ top: el.scrollHeight })
      setTimeout(() => (programScrollRef.current = false), 100)
    }
  }, [activeId])

  return (
    <>
      <div className="ctoolbar">
        <span className="muted">{events.length} 条消息</span>
        <span className="sp" />
        <button
          className="tbtn"
          title="清空当前会话的对话上下文（保留 token/费用统计），下一轮对话从空白历史重新开始"
          onClick={() => {
            if (confirm('确定清空当前会话的对话上下文？该操作不可撤销。')) {
              actions.clearContext()
              actions.setToast('已清空上下文', 'ok')
            }
          }}
        >
          🧹 清空上下文
        </button>
      </div>
      <div id="stage">
        <div className="thread" ref={stageRef}>
          {events.length === 0 && (
            <div className="overlay">
              <div className="big">开始与 AuraCode 对话</div>
              <div>在下方输入任务，例如：给 auth 模块加单元测试</div>
            </div>
          )}
          {events.map((e) => (
            <EventView key={e.event_id} e={e} />
          ))}
        </div>
      </div>
      <ChatComposer />
    </>
  )
}

function EventView({ e }: { e: BridgeEvent }) {
  const d = (e.data || {}) as any
  const toggle = (ev: any) =>
    (ev.currentTarget.parentElement as HTMLElement).classList.toggle('open')

  if (e.type === 'user_message') {
    return (
      <div className="msg user">
        <div className="who">你</div>
        <div className="bubble">{String(d.content ?? '')}</div>
      </div>
    )
  }
  if (e.type === 'assistant_message') {
    return (
      <div className="msg ai">
        <div className="who">AuraCode</div>
        {/* 助手消息按 Markdown 格式化渲染（安全：lib/md 先 escape 再替换） */}
        <div
          className="bubble md-body"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(String(d.content ?? '')) }}
        />
      </div>
    )
  }
  if (e.type === 'tool_execute') {
    // 参数结构化展示：优先展示常用键，剩余以格式化 JSON 呈现，均限高可滚
    const args =
      typeof d.arguments === 'string' ? d.arguments : JSON.stringify(d.arguments ?? {}, null, 2)
    let pretty = args
    try {
      pretty = typeof d.arguments === 'string' ? JSON.stringify(JSON.parse(d.arguments), null, 2) : args
    } catch { /* 保留原样 */ }
    const a = (typeof d.arguments === 'object' && d.arguments) || safeParse(args)
    const target =
      a?.path || a?.file_path || a?.pattern || a?.url || a?.query ||
      (a?.command ? String(a.command).slice(0, 80) : '')
    return (
      <div className="ev open">
        <div className="eh" onClick={toggle}>
          <span className="ic t">⚙</span>
          <span className="tt">工具调用 · {String(d.tool_name ?? '')}</span>
          {target && <span className="tg" title={String(target)}>{String(target)}</span>}
          <span className="tm" />
        </div>
        <div className="body">
          <pre className="ecode-lite">{pretty}</pre>
        </div>
      </div>
    )
  }
  if (e.type === 'tool_result') {
    const content = String(d.content ?? '')
    const empty = content.trim() === ''
    return (
      <div className="ev">
        <div className="eh" onClick={toggle}>
          <span className="ic r">↩</span>
          <span className="tt">工具结果</span>
          <span className="tg">{content.length > 60 ? `${content.length} 字符` : ''}</span>
          <span className="tm" />
        </div>
        <div className="body">
          {/* 空结果不再渲染成一块空白黑框，改为轻量占位，避免气泡间出现莫名空白横线 */}
          {empty ? <div className="muted" style={{ padding: '2px 0' }}>（无输出）</div> : <pre className="ecode-lite">{content}</pre>}
        </div>
      </div>
    )
  }
  if (e.type === 'result') {
    const ok = d.success
    const msg = !ok ? d.error || '执行失败' : d.summary || d.result || '已完成'
    return (
      <div className={`sysline ${ok ? 'ok' : 'err'}`}>
        {ok ? '✓ 完成' : '✗ 失败'}：{String(msg ?? '').slice(0, 300)}
        {d.duration_ms ? (
          <span className="muted"> · {(Number(d.duration_ms) / 1000).toFixed(1)}s</span>
        ) : null}
      </div>
    )
  }
  if (e.type === 'output') {
    const text = String(d.text ?? '')
    const empty = text.trim() === ''
    return (
      <div className="ev">
        <div className="eh" onClick={toggle}>
          <span className="ic r">⌨</span>
          <span className="tt">输出</span>
          <span className="tm" />
        </div>
        <div className="body">
          {/* 空输出同样不渲染空白黑框，改为占位，避免气泡间莫名空白横线 */}
          {empty ? <div className="muted" style={{ padding: '2px 0' }}>（无输出）</div> : <pre className="out">{text}</pre>}
        </div>
      </div>
    )
  }
  if (e.type === 'status') {
    const kind = String(d.kind ?? 'info')
    const isWarn = kind === 'warning' || kind === 'error'
    return <div className={`sysline ${isWarn ? 'warn' : 'muted'}`}>{String(d.message ?? '')}</div>
  }
  // LLM API 重试（429 限流最常见）：给出醒目提示，别让用户以为卡死了。
  // 数据来自后端 llm_client：{attempt, max_retries, wait_seconds, error, category, is_rate_limit}
  if (e.type === 'api_retry' || e.type === 'turn_retry') {
    const is429 = d.is_rate_limit || d.category === 'rate_limit'
    const err = String(d.error ?? '')
    // 智谱 1113 = 余额不足，重试无意义，直接明示
    const broke = /1113|余额不足/.test(err)
    return (
      <div className={`sysline ${broke ? 'err' : is429 ? 'warn' : 'muted'}`}>
        {broke ? '💳 账户余额不足（429/1113），请到开放平台充值或切换模型'
          : is429
            ? `⏳ API 限流（429），${d.wait_seconds ?? '?'}s 后第 ${d.attempt ?? '?'}/${d.max_retries ?? '?'} 次重试…`
            : `⚠️ API ${d.category ?? '故障'}，${d.wait_seconds ?? '?'}s 后重试（${d.attempt ?? '?'}/${d.max_retries ?? '?'}）`}
        {!broke && err && <span className="muted"> · {err.slice(0, 140)}</span>}
      </div>
    )
  }
  if (e.type === 'fallback_activated') {
    return (
      <div className="sysline warn">
        ⇄ 主模型不可用，已切换备用模型：{String(d.model ?? '')}
        {d.reason ? <span className="muted"> · {String(d.reason)}</span> : null}
      </div>
    )
  }
  if (e.type === 'history_restored') {
    return (
      <div className="sysline ok">
        ⟲ 已续接上次会话（{d.messages} 条消息 · {d.turn_count} 轮）— 可直接继续未完成的任务
      </div>
    )
  }
  return null
}

function safeParse(s: string) {
  try {
    return JSON.parse(s)
  } catch {
    return null
  }
}

function FileEditor({ path }: { path: string }) {
  const client = useStore((s) => s.client)
  const activeId = useStore((s) => s.activeSessionId)
  const file = useStore((s) => s.openFiles.find((f) => f.path === path))
  const kind = fileKind(path)
  // 图片/Office 不可编辑只有预览；MD/HTML 默认预览可切代码；其余进编辑器
  const [tab, setTab] = useState<'code' | 'preview'>(
    kind === 'code' ? 'code' : 'preview',
  )

  if (!file) return <div id="stage"><div className="overlay">文件不存在</div></div>

  function onChange(v: string) {
    actions.updateFileContent(path, v)
    if (!file!.dirty) actions.markDirty(path, true)
  }
  async function save() {
    if (!client || !activeId) return
    await client.writeFile(activeId, path, file!.content)
    actions.markDirty(path, false)
  }

  const showSeg = kind === 'md' || kind === 'html' // 可在 代码/预览 间切换
  const inPreview = tab === 'preview'

  return (
    <div id="stage">
      <div className="editor">
        <div className="ebar">
          <span className="fn">{path}</span>
          {file.dirty && <span className="dirty">● 未保存</span>}
          <span className="sp" />
          {showSeg && (
            <div className="seg mini">
              <button className={tab === 'code' ? 'on' : ''} onClick={() => setTab('code')}>代码</button>
              <button className={tab === 'preview' ? 'on' : ''} onClick={() => setTab('preview')}>预览</button>
            </div>
          )}
          {kind !== 'image' && kind !== 'office' && (
            <button className="save" onClick={save}>
              保存
            </button>
          )}
        </div>
        {kind === 'image' ? (
          <ImagePreview path={path} />
        ) : kind === 'office' ? (
          <OfficePreview path={path} />
        ) : kind === 'html' && inPreview ? (
          <HtmlPreview path={path} />
        ) : kind === 'md' && inPreview ? (
          <MarkdownPreview path={path} />
        ) : (
          <CodeEditor path={path} value={file.content} onChange={onChange} />
        )}
      </div>
    </div>
  )
}

/** 按扩展名分类文件 → 决定预览器 */
function fileKind(path: string): 'image' | 'md' | 'html' | 'office' | 'code' {
  const p = path.toLowerCase()
  if (/\.(png|jpe?g|gif|webp|bmp|svg|ico)$/.test(p)) return 'image'
  if (/\.md$/.test(p) || /\.markdown$/.test(p)) return 'md'
  if (/\.html?$/.test(p)) return 'html'
  if (/\.(docx|pptx)$/.test(p)) return 'office'
  return 'code'
}

/** 归档内容查看器（只读）：显示归档会话的 user/assistant 消息 */
function ArchiveViewer() {
  const viewer = useStore((s) => s.archiveViewer)
  if (!viewer) {
    return (
      <div className="stage" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted2)' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>📦</div>
          <div>从左侧选择一个归档会话，点击 👁 查看内容</div>
          <div style={{ fontSize: 11, marginTop: 8 }}>↩ 恢复为可用会话 · ✕ 永久删除归档</div>
        </div>
      </div>
    )
  }
  return (
    <div className="stage" style={{ padding: '16px 20px', overflow: 'auto' }}>
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
        <b style={{ fontSize: 14 }}>{viewer.title}</b>
        <span className="tag">只读归档</span>
        <span style={{ flex: 1 }} />
        <button
          className="btn"
          style={{ padding: '4px 12px' }}
          onClick={() => actions.resumeSession(viewer.id)}
        >
          ↩ 恢复为可用会话
        </button>
        <button className="btn" style={{ padding: '4px 12px' }} onClick={() => actions.closeArchiveViewer()}>
          关闭
        </button>
      </div>
      {viewer.messages.length === 0 && <div style={{ color: 'var(--muted2)' }}>（无可展示的消息）</div>}
      {viewer.messages.map((m, i) => (
        <div key={i} style={{ marginBottom: 12 }}>
          <div
            style={{
              fontSize: 11,
              color: m.role === 'user' ? 'var(--accentLite)' : 'var(--ok)',
              marginBottom: 3,
            }}
          >
            {m.role === 'user' ? '👤 用户' : '🤖 助手'}
          </div>
          <div
            style={{
              background: m.role === 'user' ? 'var(--bg2)' : 'var(--bg3)',
              border: '1px solid var(--line)',
              borderRadius: 8,
              padding: '8px 12px',
              fontSize: 13,
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              maxHeight: 400,
              overflow: 'auto',
            }}
          >
            {m.content}
          </div>
        </div>
      ))}
    </div>
  )
}
