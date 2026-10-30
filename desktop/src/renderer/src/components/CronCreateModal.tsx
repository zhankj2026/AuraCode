import { useState } from 'react'
import { CronBuilder } from './CronBuilder'
import { validateCron } from '../lib/cronUtils'

export interface NewCronSession {
  session_id: string
  title: string
  work_dir: string
}

interface Props {
  activeSessionId: string | null
  sessions: NewCronSession[]
  client: any
  onClose: () => void
  onToast?: (msg: string, kind?: 'error' | 'info' | 'ok') => void
  onCreated?: () => void
}

export function CronCreateModal({
  activeSessionId,
  sessions,
  client,
  onClose,
  onToast,
  onCreated,
}: Props) {
  const [prompt, setPrompt] = useState('')
  const [cron, setCron] = useState('0 9 * * *')
  const [recurring, setRecurring] = useState(true)
  const [binding, setBinding] = useState<'current' | 'new' | 'adhoc'>('adhoc')
  const [busy, setBusy] = useState(false)

  const toast = (m: string, k: 'error' | 'info' | 'ok' = 'info') => onToast?.(m, k)

  async function submit() {
    if (!client) return toast('后端未连接', 'error')
    if (!prompt.trim() || !cron.trim()) return toast('请填写提示词与 cron 表达式', 'error')
    if (!validateCron(cron.trim())) return toast('cron 表达式不合法，请检查', 'error')
    setBusy(true)
    try {
      const workDir =
        binding === 'current'
          ? sessions.find((s) => s.session_id === activeSessionId)?.work_dir || '.'
          : '.'
      let sessionId = ''
      if (binding === 'current') {
        sessionId = activeSessionId || ''
      } else if (binding === 'new') {
        // 先建一个专用会话并立即绑定，后续触发都复用它
        const r = await client.createSession({
          work_dir: workDir,
          permission_mode: 'auto',
          restore_history: false,
        })
        sessionId = r.session_id
      }
      const res = await client.createCron({
        cron: cron.trim(),
        prompt: prompt.trim(),
        recurring,
        durable: true,
        session_id: sessionId,
        work_dir: workDir,
      })
      toast(
        `已创建定时任务 ${res.job_id.slice(0, 6)}，下次触发：${res.next_fire}`,
        'ok',
      )
      onCreated?.()
      onClose()
    } catch (e: any) {
      toast('创建失败：' + (e?.message || e), 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mask show" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal lg cron-modal">
        <div className="mh">
          <div className="ic">⏰</div>
          <div className="ti">新建定时任务</div>
          <button
            type="button"
            className="iconbtn"
            style={{ marginLeft: 'auto' }}
            onClick={onClose}
            disabled={busy}
            aria-label="关闭"
          >
            ✕
          </button>
        </div>

        <div className="mb">
          <label className="field">
            <span>提示词（触发时自动执行的指令）</span>
            <textarea
              className="inp"
              rows={3}
              value={prompt}
              placeholder="例如：汇总今天 git 提交并写到 report.md"
              onChange={(e) => setPrompt(e.target.value)}
            />
          </label>

          <div className="field">
            <span>执行频率（下面可视化选即可，无需手写 cron）</span>
            <CronBuilder value={cron} onChange={setCron} disabled={busy} />
          </div>

          <div className="cron-row">
            <div className="cron-col">
              <span className="cron-lbl">类型</span>
              <div className="mseg">
                <button
                  type="button"
                  className={recurring ? 'on' : ''}
                  disabled={busy}
                  onClick={() => setRecurring(true)}
                >
                  周期性
                </button>
                <button
                  type="button"
                  className={!recurring ? 'on' : ''}
                  disabled={busy}
                  onClick={() => setRecurring(false)}
                >
                  一次性
                </button>
              </div>
            </div>
            <div className="cron-col">
              <span className="cron-lbl">关联会话（结果展示位置）</span>
              <select
                className="inp"
                aria-label="关联会话"
                value={binding}
                disabled={busy}
                onChange={(e) => setBinding(e.target.value as any)}
              >
                <option value="adhoc">每次触发新建会话</option>
                <option value="current">绑定当前会话</option>
                <option value="new">新建专用会话并绑定</option>
              </select>
            </div>
          </div>
        </div>

        <div className="mf">
          <span className="cron-hint">
            创建后任务持久化到 ~/.auracode/scheduled_tasks.json，后台按表达式自动触发。
          </span>
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button type="button" className="btn ok" onClick={submit} disabled={busy || !prompt.trim()}>
            {busy ? '创建中…' : '创建'}
          </button>
        </div>
      </div>
    </div>
  )
}
