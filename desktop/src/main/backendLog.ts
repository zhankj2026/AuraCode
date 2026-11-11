import * as fs from 'fs'
import * as path from 'path'
import type { BrowserWindow } from 'electron'

/**
 * 后端（python cli.py --bridge）运行日志的中转与持久化。
 *
 * 设计要点：
 *  - 内存环形缓冲（上限 CAP），供前端面板打开时一次性 catch-up；
 *  - 同时落盘到 userData/auracode-backend.log，关掉 UI 也能事后查证；
 *  - 通过 webContents.send('backend:log', entry) 实时推到渲染进程（窗口存在时）。
 *
 * 这样在「别的电脑」上无需开终端，也能在客户端内看到后端的真实输出，
 * 例如空闲清理误杀空会话时打印的 `Stale session cleaned up: <id> (idle_timeout)`。
 */
export interface LogEntry {
  ts: number
  line: string
}

const CAP = 3000

let buffer: LogEntry[] = []
let stream: fs.WriteStream | null = null
let win: BrowserWindow | null = null
let logFilePath = ''

export const backendLog = {
  /** 在 app ready 后调用：确定落盘路径并打开追加流 */
  init(userDataDir: string) {
    logFilePath = path.join(userDataDir, 'auracode-backend.log')
    try {
      stream = fs.createWriteStream(logFilePath, { flags: 'a' })
      stream.on('error', (e) => console.error('[backendLog] 写入失败:', e))
    } catch (e) {
      console.error('[backendLog] 无法创建日志文件', e)
      stream = null
    }
  },

  /** 绑定/解绑当前主窗口（用于实时推送）。窗口重建时重新 attach 即可 */
  attachWindow(w: BrowserWindow | null) {
    win = w
  },

  get path(): string {
    return logFilePath
  },

  /** 返回当前缓冲（拷贝），供前端面板打开时 catch-up */
  getBuffer(): LogEntry[] {
    return buffer.slice()
  },

  /** 接收后端一行原始输出：拆行、加时间戳、落盘、推前端 */
  push(raw: string) {
    const ts = Date.now()
    const lines = String(raw)
      .split('\n')
      .map((l) => l.replace(/\r$/, '').trimEnd())
      .filter((l) => l.length > 0)
    for (const line of lines) {
      const entry: LogEntry = { ts, line }
      buffer.push(entry)
      if (buffer.length > CAP) buffer.shift()
      if (stream) {
        stream.write(`${new Date(ts).toISOString()} ${line}\n`)
      }
      if (win && !win.isDestroyed()) {
        try {
          win.webContents.send('backend:log', entry)
        } catch {
          /* 窗口正在销毁等竞态，忽略 */
        }
      }
    }
  },
}
