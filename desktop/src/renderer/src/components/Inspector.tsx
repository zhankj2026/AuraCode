import { actions, useStore } from '../state/store'
import { parseFileChanges, computeUsage } from '../api/client'
import { readTextFull } from '../api/fsread'
import type { FileChange } from '../api/types'

export function Inspector() {
  const inspector = useStore((s) => s.inspector)
  const open = useStore((s) => s.inspectorOpen)
  return (
    <div className={`insp ${open ? '' : 'hidden'}`}>
      <div className="ih">
        {['改动', '上下文', '用量'].map((t) => (
          <div key={t} className={`it ${inspector === t ? 'on' : ''}`} onClick={() => actions.setInspector(t as any)}>
            {t}
          </div>
        ))}
        <button
          className="insp-close"
          title="收起右侧面板"
          onClick={() => actions.toggleInspector()}
        >
          ⟩
        </button>
      </div>
      <div className="iscroll">
        {inspector === '改动' && <Changes />}
        {inspector === '上下文' && <Context />}
        {inspector === '用量' && <Usage />}
      </div>
    </div>
  )
}

function firstLines(s: string, n = 40): string[] {
  const lines = (s || '').split('\n')
  if (lines.length <= n) return lines
  return [...lines.slice(0, n), `… (共 ${lines.length} 行)`]
}

function Changes() {
  const events = useStore((s) => s.events)
  const activeId = useStore((s) => s.activeSessionId)
  const openFiles = useStore((s) => s.openFiles)
  const client = useStore((s) => s.client)
  const workDir = useStore(
    (s) => (s.sessions.find((x) => x.session_id === s.activeSessionId)?.work_dir || '').trim(),
  )

  // 真实改动：从事件流解析 agent 的文件写入(write_file)/替换(replace_in_file)
  const all = parseFileChanges(events.filter((e) => e.session_id === activeId))
  const byPath = new Map<string, FileChange>()
  for (const c of all) byPath.set(c.path, c) // 同一文件保留最后一次改动
  const changes = [...byPath.values()]
  const unsaved = openFiles.filter((f) => f.dirty)

  async function openChange(path: string) {
    if (!client || !activeId) return
    try {
      // 整文件读取，避免 200 行截断导致打开的内容不完整
      const r = await readTextFull(client, activeId, workDir, path)
      actions.openFile(path, r.content)
    } catch {
      actions.openFile(path, '')
    }
  }

  return (
    <div className="card">
      <div className="ct">本次会话改动（{changes.length}）</div>
      {changes.length === 0 && <div className="search">暂无 agent 改动记录</div>}
      {changes.map((c) => (
        <div key={c.path}>
          <div className="chg" onClick={() => openChange(c.path)}>
            <span className="st" style={{ color: c.kind === 'write' ? 'var(--ok)' : 'var(--warn)' }}>
              {c.kind === 'write' ? '＋' : '✎'}
            </span>
            <span className="nm">{c.path}</span>
            <span style={{ color: 'var(--muted)', fontSize: 11 }}>查看 ▸</span>
          </div>
          <div className="diff">
            <div className="dh">
              <span>{c.path}</span>
              <span>{c.kind === 'write' ? '写入' : '替换'}</span>
            </div>
            {c.kind === 'replace' ? (
              <>
                {firstLines(c.oldText || '').map((l, i) => (
                  <pre className="del" key={`o${i}`}>- {l}</pre>
                ))}
                {firstLines(c.newText || '').map((l, i) => (
                  <pre className="add" key={`n${i}`}>+ {l}</pre>
                ))}
              </>
            ) : (
              <pre className="add">{firstLines(c.content || '').join('\n')}</pre>
            )}
          </div>
        </div>
      ))}

      {unsaved.length > 0 && (
        <>
          <div className="ct" style={{ marginTop: 12 }}>未保存的本地改动（{unsaved.length}）</div>
          {unsaved.map((f) => (
            <div className="chg" key={f.path} onClick={() => actions.setActiveTab(f.path)}>
              <span className="st" style={{ color: 'var(--warn)' }}>●</span>
              <span className="nm">{f.path}</span>
              <span style={{ color: 'var(--muted)', fontSize: 11 }}>未保存</span>
            </div>
          ))}
        </>
      )}
    </div>
  )
}

function Context() {
  const events = useStore((s) => s.events)
  const activeId = useStore((s) => s.activeSessionId)
  // 真实数据：统计当前会话各类事件的数量，反映“上下文里都有什么”。
  // 注意：本桥接层不提供 Token 级计数，因此这里展示的是真实可观测的事件构成，而非编造的数字。
  const mine = events.filter((e) => e.session_id === activeId)
  const count = (t: string) => mine.filter((e) => e.type === t).length
  const groups = [
    { label: '用户消息', n: count('user_message'), color: 'var(--primaryLite)' },
    { label: '助手消息', n: count('assistant_message'), color: 'var(--accentLite)' },
    { label: '工具调用', n: count('tool_execute'), color: 'var(--warn)' },
    { label: '权限请求', n: count('permission_request'), color: 'var(--danger)' },
    { label: '其他事件', n: mine.length - count('user_message') - count('assistant_message') - count('tool_execute') - count('permission_request'), color: 'var(--muted2)' },
  ]
  const max = Math.max(1, ...groups.map((g) => g.n))
  return (
    <div className="card">
      <div className="ct">会话构成（{mine.length} 条事件）</div>
      {mine.length === 0 && <div className="search">暂无事件，发送消息或运行工具后这里会实时更新</div>}
      {groups.map((g) => (
        <div key={g.label}>
          <div className="kv">
            <span>{g.label}</span>
            <b>{g.n}</b>
          </div>
          <div className="bar">
            <i style={{ width: `${(g.n / max) * 100}%`, background: g.color }} />
          </div>
        </div>
      ))}
      <div className="note" style={{ marginTop: 8 }}>
        说明：当前桥接层只广播事件流，不提供 Token 级统计，故此处展示真实可观测的事件构成。
      </div>
    </div>
  )
}

function Usage() {
  const mode = useStore((s) => s.mode)
  const workspace = useStore((s) => s.workspace)
  const sessions = useStore((s) => s.sessions)
  const activeId = useStore((s) => s.activeSessionId)
  const events = useStore((s) => s.events)
  const active = sessions.find((s) => s.session_id === activeId)
  // 实时派生：从事件流算轮次/事件数，避免读取不刷新的 sessions 快照（曾导致永远显示 0）
  const { eventCount, roundCount } = computeUsage(events, activeId)
  return (
    <div className="card">
      <div className="ct">会话用量（实时）</div>
      <div className="kv"><span>会话 ID</span><b style={{ fontSize: 11 }}>{activeId ? activeId.slice(0, 8) : '—'}</b></div>
      <div className="kv"><span>轮次</span><b>{roundCount}</b></div>
      <div className="kv"><span>事件总数</span><b>{eventCount}</b></div>
      <div className="kv"><span>状态</span><b>{active?.state || '—'}</b></div>
      <div className="kv"><span>模型</span><b>{active?.model || '未设置'}</b></div>
      <div className="kv"><span>权限模式</span><b>{mode}</b></div>
      <div className="kv"><span>工作区</span><b style={{ fontSize: 11 }}>{workspace || '（临时会话）'}</b></div>
    </div>
  )
}
