// ── 审计 · 轮次明细构建逻辑 ──────────────────────────────────
// 从事件流构建按轮次分组的审计明细（比会话记录更细：每个工具调用的
// 参数摘要/结果元数据/错误/耗时都可展开查看）。
//
// 系统实际情况约束：
// - 后端 tool_execute/tool_complete 不携带 call id，只能按「名称 + 运行中」
//   就近配对（逆序找最近的同名 running 条目）
// - tool_complete.result 是元数据字典（char_count/line_count/truncated 等），
//   不是完整工具输出——完整输出在会话记录里，审计展示元数据 + 错误
// - tool_execute.arguments 是 _arg_brief 截断后的字符串，可能是非完整 JSON
// - 用户提示词来自 user_message 事件（本地回显 + 历史回放都会进事件流）

export interface AuditEntry {
  key: string
  kind: 'tool' | 'perm' | 'system' | 'error' | 'cron'
  status: 'running' | 'success' | 'fail' | 'info'
  name: string
  title: string
  sub: string
  ts: number
  /** 展开后的明细段（参数/结果/错误），空 = 无可展开内容 */
  detail: { label: string; text: string; tone?: 'err' }[]
  duration?: number
}

export interface AuditTurn {
  key: string
  turnNo: number | null
  userPrompt: string
  preview: string
  startTs: number
  endTs?: number
  entries: AuditEntry[]
}

export const AUDIT_EVENT_TYPES = [
  'turn_start',
  'turn_complete',
  'user_message',
  'tool_execute',
  'tool_complete',
  'permission_request',
  'permission_response',
  'session_error',
  'api_retry',
  'cron_triggered',
  'cron_completed',
  'model_changed',
]

export function parseArgsBrief(raw: unknown): string {
  if (raw == null) return ''
  if (typeof raw !== 'string') return JSON.stringify(raw, null, 2)
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw // _arg_brief 截断后的非完整 JSON，原样展示
  }
}

export function fmtDuration(sec: number): string {
  if (sec < 1) return `${Math.round(sec * 1000)}ms`
  if (sec < 60) return `${sec.toFixed(1)}s`
  return `${Math.floor(sec / 60)}m${Math.round(sec % 60)}s`
}

export function buildAuditTurns(events: any[]): AuditTurn[] {
  const blank = (): AuditTurn => ({
    key: '',
    turnNo: null,
    userPrompt: '',
    preview: '',
    startTs: 0,
    entries: [],
  })
  const turns: AuditTurn[] = []
  let cur = blank()

  const pushEntry = (en: AuditEntry) => {
    if (!cur.startTs) cur.startTs = en.ts
    cur.entries.push(en)
  }
  const closeTurn = (ts?: number) => {
    if (cur.turnNo !== null || cur.userPrompt || cur.entries.length) {
      if (ts && !cur.endTs) cur.endTs = ts
      if (!cur.key) cur.key = `t${cur.turnNo ?? 'x'}_${cur.entries[0]?.key ?? cur.startTs}`
      turns.push(cur)
    }
    cur = blank()
  }

  for (const e of events) {
    const d = e.data || {}
    switch (e.type) {
      case 'user_message': {
        const content = String(d.content || '')
        // 当前轮已占用 → 另起新轮（用户消息只出现在轮首）
        if (cur.turnNo !== null || cur.userPrompt || cur.entries.length) closeTurn()
        cur.userPrompt = content
        cur.startTs = e.timestamp
        break
      }
      case 'turn_start': {
        if (cur.turnNo !== null || cur.entries.length) closeTurn()
        if (cur.turnNo === null) cur.turnNo = typeof d.turn === 'number' ? d.turn : null
        if (!cur.startTs) cur.startTs = e.timestamp
        break
      }
      case 'tool_execute': {
        const args = parseArgsBrief(d.arguments)
        const brief = args.replace(/\s+/g, ' ').slice(0, 90)
        pushEntry({
          key: e.event_id,
          kind: 'tool',
          status: 'running',
          name: String(d.tool_name || ''),
          title: String(d.tool_name || '工具'),
          sub: brief,
          ts: e.timestamp,
          detail: args ? [{ label: '参数', text: args }] : [],
        })
        break
      }
      case 'tool_complete': {
        const args = parseArgsBrief(d.arguments)
        // 事件不带 call id，配对策略：
        // 1) 同名且参数串完全一致的 running 条目（并行同名工具的精确匹配）
        // 2) 退化为同名逆序就近（参数被截断时）
        // 3) 无匹配 → 自建完成条目（历史回放缺 tool_execute 的场景）
        let target: AuditEntry | undefined
        for (let i = cur.entries.length - 1; i >= 0; i--) {
          const en = cur.entries[i]
          if (
            en.kind === 'tool' && en.status === 'running' && en.name === d.tool_name &&
            en.detail[0]?.text === args
          ) {
            target = en
            break
          }
        }
        if (!target) {
          for (let i = cur.entries.length - 1; i >= 0; i--) {
            const en = cur.entries[i]
            if (en.kind === 'tool' && en.status === 'running' && en.name === d.tool_name) {
              target = en
              break
            }
          }
        }
        const success = d.success !== false
        const detail: AuditEntry['detail'] = []
        if (args) detail.push({ label: '参数', text: args })
        const meta = d.result
        if (meta != null && Object.keys(meta).length > 0) {
          detail.push({ label: '结果', text: JSON.stringify(meta, null, 2) })
        }
        const err = String(d.error || '')
        if (err) detail.push({ label: '错误', text: err, tone: 'err' })
        if (target) {
          target.status = success ? 'success' : 'fail'
          target.duration = Math.max(0, e.timestamp - target.ts)
          target.detail = detail
        } else {
          pushEntry({
            key: e.event_id,
            kind: 'tool',
            status: success ? 'success' : 'fail',
            name: String(d.tool_name || ''),
            title: String(d.tool_name || '工具'),
            sub: args.replace(/\s+/g, ' ').slice(0, 90),
            ts: e.timestamp,
            detail,
          })
        }
        break
      }
      case 'permission_request':
        pushEntry({
          key: e.event_id,
          kind: 'perm',
          status: 'info',
          name: 'permission',
          title: '权限请求',
          sub: `${d.tool_name || ''}${d.description ? ' · ' + d.description : ''}`.slice(0, 100),
          ts: e.timestamp,
          detail: d.description ? [{ label: '说明', text: String(d.description) }] : [],
        })
        break
      case 'permission_response':
        pushEntry({
          key: e.event_id,
          kind: 'perm',
          status: d.behavior === 'allow' ? 'success' : 'fail',
          name: 'permission',
          title: d.behavior === 'allow' ? '权限允许' : '权限拒绝',
          sub: String(d.message || ''),
          ts: e.timestamp,
          detail: [],
        })
        break
      case 'session_error':
        pushEntry({
          key: e.event_id,
          kind: 'error',
          status: 'fail',
          name: 'error',
          title: '会话错误',
          sub: String(d.error || '').slice(0, 120),
          ts: e.timestamp,
          detail: d.error ? [{ label: '错误', text: String(d.error), tone: 'err' }] : [],
        })
        break
      case 'api_retry':
        pushEntry({
          key: e.event_id,
          kind: 'system',
          status: 'info',
          name: 'api_retry',
          title: `API 重试 (${d.attempt ?? '?'}/${d.max_retries ?? '?'})`,
          sub: String(d.error || '').slice(0, 100),
          ts: e.timestamp,
          detail: d.error ? [{ label: '原因', text: String(d.error) }] : [],
        })
        break
      case 'cron_triggered':
        pushEntry({
          key: e.event_id,
          kind: 'cron',
          status: 'info',
          name: 'cron',
          title: '⏰ 定时任务触发',
          sub: String(d.label || d.job_id || '').slice(0, 80),
          ts: e.timestamp,
          detail: d.prompt ? [{ label: '提示词', text: String(d.prompt) }] : [],
        })
        break
      case 'cron_completed':
        pushEntry({
          key: e.event_id,
          kind: 'cron',
          status: d.success === false ? 'fail' : 'success',
          name: 'cron',
          title: d.success === false ? '⏰ 定时任务失败' : '⏰ 定时任务完成',
          sub: String(d.error || d.summary || '').slice(0, 100),
          ts: e.timestamp,
          detail: d.summary ? [{ label: '结果', text: String(d.summary) }] : [],
        })
        break
      case 'model_changed':
        pushEntry({
          key: e.event_id,
          kind: 'system',
          status: 'info',
          name: 'model',
          title: '模型切换',
          sub: `${d.old_model || '?'} → ${d.new_model || '?'}`,
          ts: e.timestamp,
          detail: [],
        })
        break
      case 'turn_complete':
        cur.preview = String(d.content_preview || '')
        closeTurn(e.timestamp)
        break
      default:
        break
    }
  }
  closeTurn()
  return turns
}
