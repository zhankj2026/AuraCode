import { useState } from 'react'
import { actions, useStore } from '../state/store'
import type { PermissionReq } from '../api/types'

/** 超长文本截断（附截断说明），保证任何输入都不会撑爆界面 */
function cap(s: string, n: number): string {
  if (s.length <= n) return s
  return s.slice(0, n) + `\n…（已截断显示，完整内容共 ${s.length} 字符，可滚动查看前 ${n} 字符）`
}

/** 按 key 展示的优先字段：每个常见工具挑最有信息量的参数单独成行 */
const KEY_FIELDS = ['path', 'file_path', 'command', 'pattern', 'url', 'query']

/** 权限弹窗的参数展示：结构化摘要 + 可滚动全文，绝不撑爆弹窗 */
function ToolInputView({ input }: { input: Record<string, any> }) {
  const [showAll, setShowAll] = useState(false)

  // 1) 关键短字段逐行展示（路径/命令等，本身就是有界长度）
  const keyRows: [string, string][] = []
  for (const k of KEY_FIELDS) {
    const v = input?.[k]
    if (typeof v === 'string' && v) keyRows.push([k, cap(v, 300)])
  }

  // 2) 大体积字段（content/old_string/new_string…）放进可滚动块
  const BIG_KEYS = ['content', 'old_string', 'new_string', 'old_text', 'new_text', 'replacement']
  const bigParts: string[] = []
  for (const k of BIG_KEYS) {
    const v = input?.[k]
    if (typeof v === 'string' && v) bigParts.push(`── ${k}（${v.length} 字符）──\n${cap(v, 20000)}`)
  }

  const rest = { ...input }
  KEY_FIELDS.forEach((k) => delete rest[k])
  BIG_KEYS.forEach((k) => delete rest[k])
  const restJson = Object.keys(rest).length
    ? cap(JSON.stringify(rest, null, 2), 4000)
    : ''

  return (
    <>
      {keyRows.map(([k, v]) => (
        <div className="mrow" key={k}>
          <span className="k">{k}　</span>
          <span className="v" style={{ wordBreak: 'break-all' }}>{v}</span>
        </div>
      ))}
      {bigParts.map((p, i) => (
        <pre className="mpre" key={i}>{p}</pre>
      ))}
      {restJson && !showAll && (
        <div className="mrow" style={{ cursor: 'pointer' }} onClick={() => setShowAll(true)}>
          <span className="v">▸ 其他参数（{Object.keys(rest).length} 项，点击展开）</span>
        </div>
      )}
      {restJson && showAll && <pre className="mpre">{restJson}</pre>}
    </>
  )
}

export function PermissionModal() {
  const permission = useStore((s) => s.permission)
  const sessionId = useStore((s) => s.permissionSession)
  const client = useStore((s) => s.client)
  const [remember, setRemember] = useState(false)

  if (!permission) return null

  async function respond(behavior: 'allow' | 'deny') {
    if (client && sessionId) {
      try {
        await client.respondPermission(sessionId, permission!.request_id, behavior, remember ? 'remember' : '')
      } catch (e) {
        actions.log('权限回复失败: ' + e)
      }
    }
    actions.setPermission(null)
  }

  return (
    <div className="mask show">
      <div className="modal">
        <div className="mh">
          <div className="ic">⚠</div>
          <div className="ti">权限确认 · {permission.tool_name}</div>
        </div>
        <div className="mb">
          <ToolInputView input={permission.tool_input || {}} />
          {permission.description && (
            <div style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.6 }}>
              {cap(permission.description, 400)}
            </div>
          )}
        </div>
        <div className="mf">
          <label className="ck">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
            本次会话始终允许此操作
          </label>
          <button className="btn danger" onClick={() => respond('deny')}>
            拒绝
          </button>
          <button className="btn ok" onClick={() => respond('allow')}>
            允许
          </button>
        </div>
      </div>
    </div>
  )
}
