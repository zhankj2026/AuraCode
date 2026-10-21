import { useEffect, useMemo, useRef, useState } from 'react'
import { actions, useStore } from '../state/store'
import type { BridgeEvent } from '../api/types'
import { CodeEditor } from './CodeEditor'
import { HtmlPreview } from './HtmlPreview'
import { ChatComposer } from './ChatComposer'

export function MainArea() {
  const activeTab = useStore((s) => s.activeTab)
  const openFiles = useStore((s) => s.openFiles)
  const activity = useStore((s) => s.activity)

  // 文件 Tab 仅在「文件」活动或当前打开文件时显示
  const showFiles = activity === 'files' || openFiles.length > 0
  const chatTitle = useStore(
    (s) => s.sessions.find((x) => x.session_id === s.activeSessionId)?.title || '对话',
  )

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
        <div className="bubble">{String(d.content ?? '')}</div>
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
    return (
      <div className="ev">
        <div className="eh" onClick={toggle}>
          <span className="ic r">↩</span>
          <span className="tt">工具结果</span>
          <span className="tg">{content.length > 60 ? `${content.length} 字符` : ''}</span>
          <span className="tm" />
        </div>
        <div className="body">
          <pre className="ecode-lite">{content}</pre>
        </div>
      </div>
    )
  }
  if (e.type === 'result') {
    const ok = d.success
    const msg = !ok ? d.error || '执行出错' : d.summary || d.result || '已完成'
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
    return (
      <div className="ev">
        <div className="eh" onClick={toggle}>
          <span className="ic r">⌨</span>
          <span className="tt">输出</span>
          <span className="tm" />
        </div>
        <div className="body">
          <pre className="out">{String(d.text ?? '')}</pre>
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
  const isHtml = /\.html?$/i.test(path)
  // HTML 文件默认直接进预览（用户诉求：index.html 打开就能看效果），需要改代码再切「代码」
  const [tab, setTab] = useState<'code' | 'preview'>(isHtml ? 'preview' : 'code')

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

  return (
    <div id="stage">
      <div className="editor">
        <div className="ebar">
          <span className="fn">{path}</span>
          {file.dirty && <span className="dirty">● 未保存</span>}
          <span className="sp" />
          {isHtml && (
            <div className="seg mini">
              <button className={tab === 'code' ? 'on' : ''} onClick={() => setTab('code')}>代码</button>
              <button className={tab === 'preview' ? 'on' : ''} onClick={() => setTab('preview')}>预览</button>
            </div>
          )}
          <button className="save" onClick={save}>
            保存
          </button>
        </div>
        {isHtml && tab === 'preview' ? (
          <HtmlPreview path={path} />
        ) : (
          <CodeEditor path={path} value={file.content} onChange={onChange} />
        )}
      </div>
    </div>
  )
}
