import { useEffect, useRef, useState } from 'react'
import { actions, useStore } from '../state/store'

/**
 * 后端运行日志面板（左侧「📜 日志」）。
 *
 * 进入即订阅主进程中转的后端输出（python cli.py --bridge），并一次性 catch-up
 * 主进程内存缓冲。重点用于排查「别的电脑上装好打不开 / 没有会话」类问题：
 * 若出现 `Stale session cleaned up: <id> (idle_timeout)` 或
 * `Periodic cleanup: N sessions removed`，基本可锁定为空闲清理把刚自动创建的
 * 空会话误杀了（last_activity=0 的 bug），相关行会高亮成红色。
 */
export function BackendLog() {
  const logs = useStore((s) => s.backendLogs)
  const ref = useRef<HTMLDivElement>(null)
  const stickRef = useRef(true)
  const [logPath, setLogPath] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let unsub: (() => void) | undefined
    window.auracode
      .getBackendLogs()
      .then((r) => {
        actions.setBackendLogs(r.logs)
        setLogPath(r.path)
      })
      .catch(() => {})
    try {
      unsub = window.auracode.onBackendLog((e) => actions.appendBackendLog(e))
    } catch {
      /* 不支持时静默降级 */
    }
    return () => unsub?.()
  }, [])

  // 贴底时自动跟随；用户上翻阅读则暂停
  useEffect(() => {
    if (!stickRef.current || !ref.current) return
    ref.current.scrollTop = ref.current.scrollHeight
  }, [logs])

  function classify(line: string): string {
    if (/idle_timeout|Stale session cleaned up|Periodic cleanup|Traceback|Error:|失败|Exception/i.test(line))
      return 'err'
    if (/warn|WARN|超时|timeout/i.test(line)) return 'warn'
    return ''
  }

  async function copyAll() {
    try {
      await navigator.clipboard.writeText(logs.map((l) => l.line).join('\n'))
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      actions.setToast('复制失败：剪贴板不可用', 'error')
    }
  }

  return (
    <div className="backend-log">
      <div className="ctoolbar">
        <span className="muted">后端运行日志（实时）</span>
        {logPath && (
          <span className="muted" style={{ fontSize: 11 }} title={logPath}>
            落盘：{logPath.split(/[\\/]/).pop()}
          </span>
        )}
        <span className="sp" />
        <button className="tbtn" onClick={copyAll}>
          {copied ? '已复制' : '复制'}
        </button>
        <button className="tbtn" onClick={() => actions.clearBackendLogs()}>
          清空显示
        </button>
      </div>
      <div
        className="blog"
        ref={ref}
        onScroll={(e) => {
          const el = e.currentTarget
          stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40
        }}
      >
        {logs.length === 0 && (
          <div className="overlay">
            <div className="big">暂无日志</div>
            <div>启动后端后这里会实时显示 python cli.py --bridge 的输出</div>
            <div style={{ fontSize: 11, marginTop: 8 }}>
              排查「没有会话」：留意红色高亮的 <code>idle_timeout</code> / <code>Periodic cleanup</code> 行
            </div>
          </div>
        )}
        {logs.map((l, i) => (
          <div key={i} className={`bline ${classify(l.line)}`}>
            <span className="ts">{new Date(l.ts).toLocaleTimeString()}</span>
            <span className="ln">{l.line}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
