import type {
  BridgeConfig,
  SessionInfo,
  BridgeEvent,
  PermissionReq,
  FileListing,
  FileContent,
  FileChange,
} from './types'

/**
 * 从事件流中解析出本次会话的真实文件改动。
 * 数据源：后端 tool_execute 事件（已解析的 arguments），
 *   - write_file      → {path, content}           整文件写入
 *   - replace_in_file → {path, old_text, new_text} 精确替换
 * 不依赖任何新增后端接口。
 */
export function parseFileChanges(events: BridgeEvent[]): FileChange[] {
  const changes: FileChange[] = []
  for (const e of events) {
    if (e.type !== 'tool_execute') continue
    let args: any = e.data?.arguments
    if (typeof args === 'string') {
      try {
        args = JSON.parse(args)
      } catch {
        args = {}
      }
    }
    if (!args || typeof args !== 'object') continue
    const name = e.data?.tool_name
    if (name === 'write_file' && args.path) {
      changes.push({
        path: String(args.path),
        kind: 'write',
        content: typeof args.content === 'string' ? args.content : '',
        ts: e.timestamp,
      })
    } else if (name === 'replace_in_file' && args.path) {
      changes.push({
        path: String(args.path),
        kind: 'replace',
        oldText: typeof args.old_text === 'string' ? args.old_text : '',
        newText: typeof args.new_text === 'string' ? args.new_text : '',
        ts: e.timestamp,
      })
    }
  }
  return changes
}

/**
 * 对 AuraCode Bridge 后端的 REST + WebSocket 客户端。
 * 全部走 127.0.0.1 loopback + Bearer token，与现有后端一一对应。
 */
export class BridgeClient {
  config: BridgeConfig

  constructor(config: BridgeConfig) {
    this.config = config
  }

  private url(p: string) {
    return `http://${this.config.host}:${this.config.port}${p}`
  }

  private headers(extra: Record<string, string> = {}) {
    return {
      Authorization: `Bearer ${this.config.token}`,
      'Content-Type': 'application/json',
      ...extra,
    }
  }

  async getStatus() {
    const r = await fetch(this.url('/api/status'), { headers: this.headers() })
    return r.json()
  }

  async listSessions(): Promise<SessionInfo[]> {
    const r = await fetch(this.url('/api/sessions'), { headers: this.headers() })
    if (!r.ok) throw new Error(await r.text())
    return r.json()
  }

  async createSession(body: {
    work_dir?: string
    model?: string
    permission_mode?: string
    max_iterations?: number | null
    api_key?: string | null
    base_url?: string | null
    restore_history?: boolean
  }) {
    const r = await fetch(this.url('/api/sessions'), {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify(body),
    })
    if (!r.ok) {
      const text = await r.text().catch(() => '')
      throw new Error(`创建会话失败 (HTTP ${r.status}): ${text || r.statusText}`)
    }
    const data = (await r.json()) as { session_id?: string; state?: string }
    if (!data.session_id) {
      throw new Error(`后端未返回 session_id，响应：${JSON.stringify(data)}`)
    }
    return { session_id: data.session_id, state: data.state }
  }

  async sendMessage(sessionId: string, content: string, attachments: any[] = []) {
    const r = await fetch(this.url(`/api/sessions/${sessionId}/message`), {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ content, attachments }),
    })
    return r.json()
  }

  async respondPermission(
    sessionId: string,
    request_id: string,
    behavior: 'allow' | 'deny',
    message = '',
  ) {
    const r = await fetch(this.url(`/api/sessions/${sessionId}/permission`), {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ request_id, behavior, message }),
    })
    return r.json()
  }

  async stopSession(sessionId: string) {
    const r = await fetch(this.url(`/api/sessions/${sessionId}/stop`), {
      method: 'POST',
      headers: this.headers(),
    })
    return r.json()
  }

  async interrupt(sessionId: string) {
    const r = await fetch(this.url(`/api/sessions/${sessionId}/interrupt`), {
      method: 'POST',
      headers: this.headers(),
    })
    return r.json()
  }

  async switchModel(sessionId: string, model: string) {
    const r = await fetch(this.url(`/api/sessions/${sessionId}/model`), {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ model }),
    })
    return r.json()
  }

  async deleteSession(sessionId: string) {
    const r = await fetch(this.url(`/api/sessions/${sessionId}`), {
      method: 'DELETE',
      headers: this.headers(),
    })
    return r.json()
  }

  async listFiles(sessionId: string, subdir = ''): Promise<FileListing> {
    const r = await fetch(
      this.url(
        `/api/sessions/${sessionId}/files?path=${encodeURIComponent(subdir)}`,
      ),
      { headers: this.headers() },
    )
    return (await r.json()) as FileListing
  }

  /**
   * 读取文件内容。
   * 注意：后端 max_lines 默认只有 200 行，超过的部分会被静默截断。
   * 之前不传该参数 ⇒ demo6 的 entities.js(505)/game.js(488)/ui.js(425) 等
   * 只拿到前 200 行，编辑器里显示不全、保存还会把文件写坏；HTML 预览注入
   * 残缺 JS 后直接 SyntaxError，表现为白屏。这里默认请求后端上限 2000 行。
   */
  async readFile(sessionId: string, p: string, maxLines = 2000): Promise<FileContent> {
    const r = await fetch(
      this.url(
        `/api/sessions/${sessionId}/files/content?path=${encodeURIComponent(p)}&max_lines=${maxLines}`,
      ),
      { headers: this.headers() },
    )
    return (await r.json()) as FileContent
  }

  async writeFile(sessionId: string, p: string, content: string) {
    const r = await fetch(this.url(`/api/sessions/${sessionId}/files`), {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ path: p, type: 'file', content }),
    })
    return r.json()
  }

  async deleteFile(sessionId: string, p: string) {
    const r = await fetch(
      this.url(`/api/sessions/${sessionId}/files?path=${encodeURIComponent(p)}`),
      { method: 'DELETE', headers: this.headers() },
    )
    return r.json()
  }

  async renameFile(sessionId: string, oldPath: string, newPath: string) {
    const r = await fetch(this.url(`/api/sessions/${sessionId}/files/rename`), {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ old_path: oldPath, new_path: newPath }),
    })
    return r.json()
  }

  async getEvents(sessionId: string, since = 0): Promise<BridgeEvent[]> {
    const r = await fetch(
      this.url(`/api/sessions/${sessionId}/events?since=${since}`),
      { headers: this.headers() },
    )
    return r.json()
  }

  /** 订阅事件流。sid 省略则订阅全局事件。返回 WebSocket 以便关闭。 */
  connectEvents(
    onMessage: (e: BridgeEvent) => void,
    sessionId?: string,
    onClose?: () => void,
  ): WebSocket {
    const base = `ws://${this.config.host}:${this.config.port}`
    const path = sessionId
      ? `/ws/sessions/${sessionId}/events`
      : '/ws/events'
    const ws = new WebSocket(`${base}${path}?token=${this.config.token}`)
    ws.onmessage = (ev) => {
      try {
        onMessage(JSON.parse(ev.data) as BridgeEvent)
      } catch {
        /* ignore */
      }
    }
    ws.onerror = () => console.warn('[ws] connection error')
    ws.onclose = () => {
      console.warn('[ws] connection closed')
      onClose?.()
    }
    return ws
  }
}
