import { actions, useStore } from '../state/store'
import type { Activity } from '../api/types'

const ITEMS: { key: Activity; icon: string; label: string }[] = [
  { key: 'chat', icon: '💬', label: '对话' },
  { key: 'files', icon: '🗂️', label: '文件' },
  { key: 'ext', icon: '🧩', label: '扩展' },
  { key: 'audit', icon: '🛡️', label: '审计' },
  { key: 'tasks', icon: '⚙️', label: '任务' },
  { key: 'models', icon: '🧠', label: '模型' },
]

export function ActivityBar() {
  const activity = useStore((s) => s.activity)
  return (
    <div className="actbar">
      {ITEMS.map((it) => (
        <div
          key={it.key}
          className={`act ${activity === it.key ? 'on' : ''}`}
          onClick={() => actions.setActivity(it.key)}
        >
          <span>{it.icon}</span>
          <span className="lbl">{it.label}</span>
        </div>
      ))}
    </div>
  )
}
