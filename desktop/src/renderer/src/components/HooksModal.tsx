import { useEffect, useState } from 'react'
import { actions, useStore } from '../state/store'
import type { HookInfo } from '../api/types'

/**
 * 钩子管理弹窗（完整 CRUD）。
 * - 项目级：<工作区>/.auracode/hooks.json；用户级：~/.auracode/hooks.json
 * - 字段与引擎 hooks/config_loader.py 的 HookConfigEntry 一一对应
 *   （event/matcher/command/priority/timeout/enabled/description/on_fail）
 * - 事件名取自引擎 hooks/manager.py 的 HOOK_EVENTS 清单
 */
const HOOK_EVENTS = [
  'PreToolUse',
  'PostToolUse',
  'PostToolUseFailure',
  'ToolError',
  'SessionStart',
  'SessionEnd',
  'Stop',
  'UserMessage',
  'Notification',
  'SubagentStart',
  'SubagentStop',
  'PreCompact',
  'PostCompact',
  'ContextWarning',
]

/** 与事件匹配的常用工具名建议（仅展示提示用） */
const TOOL_MATCHERS = ['read_file', 'write_file', 'replace_in_file', 'run_command', 'list_directory', 'search_files', 'web_fetch']

interface EditableHook {
  event: string
  matcher: string
  command: string
  enabled: boolean
  description: string
  priority: number
  timeout: number
  onFail: string
}

function emptyHook(): EditableHook {
  return {
    event: 'PreToolUse',
    matcher: '',
    command: '',
    enabled: true,
    description: '',
    priority: 0,
    timeout: 10,
    onFail: 'ignore',
  }
}

function fromInfo(h: HookInfo): EditableHook {
  return {
    event: h.event,
    matcher: h.matcher || '',
    command: h.command,
    enabled: h.enabled,
    description: h.description || '',
    priority: h.priority,
    timeout: h.timeout || 10,
    onFail: h.onFail || 'ignore',
  }
}

export function HooksModal() {
  const open = useStore((s) => s.hooksOpen)
  const ext = useStore((s) => s.extensions)
  const workDir = useStore(
    (s) => s.sessions.find((x) => x.session_id === s.activeSessionId)?.work_dir || '',
  )
  const [scope, setScope] = useState<'project' | 'user'>('project')
  const [hooks, setHooks] = useState<EditableHook[]>([])
  const [busy, setBusy] = useState(false)

  // 打开时按 scope 载入现有钩子（本地编辑副本，保存时整表写回）
  useEffect(() => {
    if (!open) return
    const list = (ext?.hooks || []).filter((h) => h.scope === scope)
    setHooks(list.map(fromInfo))
  }, [open, scope])
  // eslint-disable-next-line react-hooks/exhaustive-deps

  if (!open) return null

  const targetFile =
    scope === 'user' ? '~/.auracode/hooks.json' : `${workDir || '(当前工作区)'}/.auracode/hooks.json`

  function patch(i: number, p: Partial<EditableHook>) {
    setHooks((hs) => hs.map((h, idx) => (idx === i ? { ...h, ...p } : h)))
  }

  async function save() {
    if (!workDir && scope === 'project') {
      actions.setToast('当前无工作区，请选择「用户」作用域或先打开工作区', 'error')
      return
    }
    // 客户端校验：事件名合法、命令非空
    for (const [i, h] of hooks.entries()) {
      if (!HOOK_EVENTS.includes(h.event)) {
        actions.setToast(`第 ${i + 1} 条：事件「${h.event}」无效`, 'error')
        return
      }
      if (!h.command.trim()) {
        actions.setToast(`第 ${i + 1} 条：命令不能为空`, 'error')
        return
      }
    }
    setBusy(true)
    try {
      const res = await window.auracode.saveHooks(
        workDir,
        scope,
        hooks.map((h) => ({
          event: h.event,
          matcher: h.matcher.trim() || undefined,
          command: h.command.trim(),
          enabled: h.enabled,
          description: h.description.trim() || undefined,
          priority: h.priority,
          timeout: h.timeout,
          onFail: h.onFail,
        })),
      )
      if (res.ok) {
        actions.setToast(`已保存 ${hooks.length} 条钩子（新会话生效）`, 'ok')
        actions.loadExtensions()
        actions.closeHooks()
      } else {
        actions.setToast('保存失败：' + res.message, 'error')
      }
    } catch (e) {
      actions.setToast('保存失败：' + (e instanceof Error ? e.message : String(e)), 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mask show" onClick={(e) => e.target === e.currentTarget && actions.closeHooks()}>
      <div className="modal xl">
        <div className="mh" style={{ background: 'var(--bg3)' }}>
          <div className="ic" style={{ background: 'var(--primaryLite)', color: '#fff' }}>🪝</div>
          <div className="ti">钩子管理</div>
          <span className="sp" />
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value as 'project' | 'user')}
            style={{ marginRight: 8 }}
          >
            <option value="project">项目级</option>
            <option value="user">用户级</option>
          </select>
          <button className="btn" onClick={() => actions.closeHooks()}>✕</button>
        </div>

        <div className="mb" style={{ overflow: 'auto', maxHeight: 'calc(80vh - 150px)' }}>
          <div className="note" style={{ marginBottom: 8 }}>
            写入 <b>{targetFile}</b>；命令支持变量替换 {'{tool_name}'} 与输入参数占位符，失败策略 on_fail=ignore/warn/block（block 会拦截工具执行）。保存后新会话生效。
          </div>

          {hooks.length === 0 && (
            <div className="skhub-empty" style={{ padding: '18px 0' }}>
              该作用域暂无钩子，点击下方「＋ 添加钩子」新建
            </div>
          )}

          {hooks.map((h, i) => (
            <div
              key={i}
              style={{
                border: '1px solid var(--line)',
                borderRadius: 8,
                padding: '10px 12px',
                marginBottom: 10,
                background: 'var(--bg2)',
              }}
            >
              <div style={{ display: 'flex', gap: 8, marginBottom: 6, alignItems: 'center' }}>
                <span className="tag" style={{ flexShrink: 0 }}>#{i + 1}</span>
                <select value={h.event} onChange={(e) => patch(i, { event: e.target.value })} style={{ flex: 1 }}>
                  {HOOK_EVENTS.map((ev) => (
                    <option key={ev} value={ev}>{ev}</option>
                  ))}
                </select>
                <select
                  value={h.matcher}
                  onChange={(e) => patch(i, { matcher: e.target.value })}
                  style={{ flex: 1 }}
                  title="只在该工具触发时执行（留空 = 所有工具）"
                >
                  <option value="">匹配所有工具</option>
                  {TOOL_MATCHERS.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                <button
                  className={`btn ${h.enabled ? 'ok' : ''}`}
                  style={{ flexShrink: 0, padding: '3px 10px' }}
                  onClick={() => patch(i, { enabled: !h.enabled })}
                >
                  {h.enabled ? '启用' : '禁用'}
                </button>
                <button
                  className="btn"
                  style={{ flexShrink: 0, padding: '3px 10px' }}
                  onClick={() => setHooks((hs) => hs.filter((_, idx) => idx !== i))}
                >
                  ✕
                </button>
              </div>
              <textarea
                value={h.command}
                placeholder="要执行的 Shell 命令，如 echo {tool_name} >> hooks.log"
                onChange={(e) => patch(i, { command: e.target.value })}
                style={{ width: '100%', minHeight: 44, fontFamily: 'var(--mono, monospace)', resize: 'vertical' }}
              />
              <div style={{ display: 'flex', gap: 8, marginTop: 6, alignItems: 'center' }}>
                <input
                  value={h.description}
                  placeholder="描述（可选）"
                  onChange={(e) => patch(i, { description: e.target.value })}
                  style={{ flex: 1 }}
                />
                <select value={h.onFail} onChange={(e) => patch(i, { onFail: e.target.value })} title="失败策略">
                  <option value="ignore">失败忽略</option>
                  <option value="warn">失败警告</option>
                  <option value="block">失败拦截</option>
                </select>
                <input
                  type="number"
                  value={h.priority}
                  onChange={(e) => patch(i, { priority: Number(e.target.value) || 0 })}
                  style={{ width: 64 }}
                  title="优先级（越大越先执行）"
                />
                <input
                  type="number"
                  value={h.timeout}
                  onChange={(e) => patch(i, { timeout: Number(e.target.value) || 10 })}
                  style={{ width: 64 }}
                  title="超时（秒）"
                />
              </div>
            </div>
          ))}

          <button
            className="btn"
            style={{ width: '100%' }}
            onClick={() => setHooks((hs) => [...hs, emptyHook()])}
          >
            ＋ 添加钩子
          </button>
        </div>

        <div className="mf">
          <div style={{ fontSize: 11, color: 'var(--muted)', padding: '0 14px' }}>
            {hooks.length} 条 · {scope === 'user' ? '用户级（所有项目生效）' : '项目级（仅当前工作区）'}
          </div>
          <div className="spacer" style={{ flex: 1 }} />
          <button className="btn" onClick={() => actions.closeHooks()} disabled={busy}>取消</button>
          <button className="btn ok" onClick={save} disabled={busy}>
            {busy ? '保存中…' : '保存全部'}
          </button>
        </div>
      </div>
    </div>
  )
}
