import { useState } from 'react'
import { CronBuilder } from './CronBuilder'
import { validateCron } from '../lib/cronUtils'
import type { TaskInfo } from '../api/types'

export interface EditCronSession {
  session_id: string
  title: string
  work_dir: string
}

interface Props {
  task: TaskInfo
  sessions: EditCronSession[]
  client: any
  onClose: () => void
  onToast?: (msg: string, kind?: 'error' | 'info' | 'ok') => void
  onUpdated?: () => void
}

/** 编辑定时任务：预填现有配置，部分字段提交（cron 变更时后端重算下次触发时间）。
 *  复用 CronBuilder 与 CronCreateModal 的表单样式。 */
export function CronEditModal({
  task,
  sessions,
  client,
  onClose,
  onToast,
  onUpdated,
}: Props) {
  const [prompt, setPrompt] = useState(task.prompt)
  const [cron, setCron] = useState(task.cron)
  const [recurring, setRecurring] = useState(task.recurring)
  const [label, setLabel] = useState(task.label || '')
  // 关联会话：'adhoc' = 每次触发新建会话（session_id 置空），否则为具体会话 id
  const [binding, setBinding] = useState<string>(task.session_id || 'adhoc')
  const [busy, setBusy] = useState(false)

  const toast = (m: string, k: 'error' | 'info' | 'ok' = 'info') => onToast?.(m, k)

  async function submit() {
    if (!client) return toast('后端未连接', 'error')
    if (!prompt.trim()) return toast('提示词不能为空', 'error')
    if (!validateCron(cron.trim())) return toast('cron 表达式不合法，请检查', 'error')
    setBusy(true)
    try {
      const res = await client.updateCron(task.job_id, {
        cron: cron.trim(),
        prompt: prompt.trim(),
        recurring,
        label: label.trim(),
        session_id: binding === 'adhoc' ? '' : binding,
      })
      toast(
        `已修改定时任务，下次触发：${res.next_fire}` +
          (task.status === 'paused' ? '（任务当前处于暂停状态）' : ''),
        'ok',
      )
      onUpdated?.()
      onClose()
    } catch (e: any) {
      toast('修改失败：' + (e?.message || e), 'error')
    } finally {
      setBusy(false)
    }
  }

  const knownBinding = task.session_id && sessions.some((s) => s.session_id === task.session_id)

  return (
    <div className="mask show" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal lg cron-modal">
        <div className="mh">
          <div className="ic">✏️</div>
          <div className="ti">
            编辑定时任务
            {task.label ? ` · ${task.label}` : ` · ${task.job_id.slice(0, 6)}`}
          </div>
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
          {task.status === 'paused' && (
            <div className="cron-hint" style={{ marginBottom: 8 }}>
              ⏸ 该任务当前处于暂停状态，修改保存后仍保持暂停（▶ 恢复后按新配置触发）。
            </div>
          )}

          <label className="field">
            <span>提示词（触发时自动执行的指令）</span>
            <textarea
              className="inp"
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </label>

          <div className="field">
            <span>执行频率（修改后从下个匹配时间重新计算触发）</span>
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
              <span className="cron-lbl">标签（可选，侧栏显示用）</span>
              <input
                className="inp"
                value={label}
                placeholder="例如：每日日报"
                disabled={busy}
                onChange={(e) => setLabel(e.target.value)}
              />
            </div>
          </div>

          <div className="field">
            <span className="cron-lbl">关联会话（结果展示位置）</span>
            <select
              className="inp"
              aria-label="关联会话"
              value={binding}
              disabled={busy}
              onChange={(e) => setBinding(e.target.value)}
            >
              <option value="adhoc">每次触发新建会话</option>
              {task.session_id && !knownBinding && (
                <option value={task.session_id}>
                  原绑定会话 {task.session_id.slice(0, 6)}（当前不在线）
                </option>
              )}
              {sessions.map((s) => (
                <option key={s.session_id} value={s.session_id}>
                  {s.title || s.work_dir || s.session_id.slice(0, 8)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mf">
          <span className="cron-hint">
            修改立即生效并同步落盘；周期性任务改表达式后 30 天有效期重新计算。
          </span>
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button
            type="button"
            className="btn ok"
            onClick={submit}
            disabled={busy || !prompt.trim()}
          >
            {busy ? '保存中…' : '保存修改'}
          </button>
        </div>
      </div>
    </div>
  )
}
