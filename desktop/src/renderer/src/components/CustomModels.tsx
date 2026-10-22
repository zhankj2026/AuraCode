import { useEffect, useState } from 'react'
import { actions, useStore } from '../state/store'
import type { CustomModel } from '../api/types'

type FormState = {
  id: string | null
  name: string
  provider: string
  base_url: string
  api_key: string
  model: string
  tools: boolean
  image: boolean
  thinking: boolean
  supplement: string
}

/** 常用供应商：选中的同时预填接口地址（自定义除外）。 */
const PROVIDERS: Array<{ id: string; name: string; icon: string; url: string }> = [
  { id: 'openai', name: 'OpenAI', icon: '🟢', url: 'https://api.openai.com/v1/chat/completions' },
  { id: 'zhipu', name: '智谱 AI（GLM）', icon: '🔷', url: 'https://open.bigmodel.cn/api/paas/v4/chat/completions' },
  { id: 'deepseek', name: 'DeepSeek', icon: '🔶', url: 'https://api.deepseek.com/v1/chat/completions' },
  { id: 'moonshot', name: 'Moonshot（Kimi）', icon: '🌙', url: 'https://api.moonshot.cn/v1/chat/completions' },
  { id: 'qwen', name: '通义千问（DashScope）', icon: '🟠', url: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions' },
  { id: 'siliconflow', name: '硅基流动（SiliconFlow）', icon: '💎', url: 'https://api.siliconflow.cn/v1/chat/completions' },
  { id: 'volcano', name: '火山方舟（Volcano）', icon: '🌋', url: 'https://ark.cn-beijing.volces.com/api/v3/chat/completions' },
  { id: 'custom', name: '自定义（手动填写）', icon: '◇', url: '' },
]

const EMPTY: FormState = {
  id: null,
  name: '',
  provider: 'openai',
  base_url: '',
  api_key: '',
  model: '',
  tools: false,
  image: false,
  thinking: false,
  supplement: '',
}

function uid(): string {
  return 'm_' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4)
}

export function CustomModels() {
  const models = useStore((s) => s.customModels)
  const [editing, setEditing] = useState<FormState | null>(null)
  const [showKey, setShowKey] = useState(false)

  useEffect(() => {
    actions.loadCustomModels()
  }, [])

  function openAdd() {
    setShowKey(false)
    setEditing({ ...EMPTY, id: null })
  }
  function openEdit(m: CustomModel) {
    setShowKey(false)
    setEditing({
      id: m.id,
      name: m.name,
      provider: m.provider,
      base_url: m.base_url,
      api_key: m.api_key,
      model: m.model,
      tools: !!m.capabilities?.tools,
      image: !!m.capabilities?.image,
      thinking: !!m.capabilities?.thinking,
      supplement: m.supplement || '',
    })
  }

  async function onDelete(m: CustomModel) {
    if (!confirm(`确定删除自定义模型「${m.name}」？`)) return
    const next = models.filter((x) => x.id !== m.id)
    await actions.saveCustomModels(next)
    actions.setToast(`已删除「${m.name}」`, 'ok')
  }

  async function onSave(f: FormState) {
    if (!f.name.trim() || !f.base_url.trim() || !f.model.trim()) {
      actions.setToast('请填写模型名称、接口地址和模型名称', 'error')
      return
    }
    const entry: CustomModel = {
      id: f.id || uid(),
      name: f.name.trim(),
      provider: f.provider,
      base_url: f.base_url.trim(),
      api_key: f.api_key.trim(),
      model: f.model.trim(),
      capabilities: { tools: f.tools, image: f.image, thinking: f.thinking },
      supplement: f.supplement.trim() || undefined,
    }
    const exists = models.some((x) => x.id === entry.id)
    const next = exists ? models.map((x) => (x.id === entry.id ? entry : x)) : [...models, entry]
    await actions.saveCustomModels(next)
    setEditing(null)
    actions.setToast(exists ? `已更新「${entry.name}」` : `已添加「${entry.name}」`, 'ok')
  }

  return (
    <div className="custommodels">
      <div className="cm-head">
        <div>
          <div className="cm-title">自定义模型</div>
          <div className="cm-sub">
            模型添加后会自动写入到本地 <code>~/.auracode/models.json</code> 文件中。
          </div>
        </div>
        <button className="btn-primary" onClick={openAdd}>＋ 添加模型</button>
      </div>

      <div className="cm-list">
        {models.length === 0 && (
          <div className="search">暂无自定义模型，点击右上角「添加模型」配置一个大模型接入点。</div>
        )}
        {models.map((m) => (
          <div className="cm-item" key={m.id}>
            <span className="cm-diamond">◇</span>
            <div className="cm-info">
              <div className="cm-name">{m.name}</div>
              <div className="cm-meta">
                <span className="tag">自定义</span>
                <span className="cm-url">{m.base_url}</span>
              </div>
            </div>
            <div className="cm-ops">
              <span className="op" title="编辑" onClick={() => openEdit(m)}>✎</span>
              <span className="op" title="复制接口信息" onClick={() => {
                navigator.clipboard?.writeText(`${m.model} | ${m.base_url}`)
                actions.setToast('已复制接口信息', 'ok')
              }}>🔗</span>
              <span className="op danger" title="删除" onClick={() => onDelete(m)}>🗑</span>
            </div>
          </div>
        ))}
      </div>

      {editing && (
        <ModelDialog
          form={editing}
          showKey={showKey}
          setShowKey={setShowKey}
          onClose={() => setEditing(null)}
          onSave={onSave}
        />
      )}
    </div>
  )
}

function ModelDialog({
  form,
  showKey,
  setShowKey,
  onClose,
  onSave,
}: {
  form: FormState
  showKey: boolean
  setShowKey: (v: boolean) => void
  onClose: () => void
  onSave: (f: FormState) => void
}) {
  const [f, setF] = useState<FormState>(form)
  const [testing, setTesting] = useState(false)
  const [test, setTest] = useState<{ ok: boolean; msg: string } | null>(null)

  function patch(p: Partial<FormState>) {
    setF((prev) => ({ ...prev, ...p }))
  }

  async function testConnection() {
    if (!f.base_url.trim() || !f.model.trim()) {
      setTest({ ok: false, msg: '请先填写接口地址和模型名称' })
      return
    }
    const url = f.base_url.trim()
    setTesting(true)
    setTest(null)
    const t0 = performance.now()
    try {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), 20000)
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(f.api_key.trim() ? { Authorization: `Bearer ${f.api_key.trim()}` } : {}),
        },
        body: JSON.stringify({
          model: f.model.trim(),
          messages: [{ role: 'user', content: 'ping' }],
          max_tokens: 1,
          stream: false,
        }),
        signal: controller.signal,
      })
      clearTimeout(timer)
      const ms = Math.round(performance.now() - t0)
      const text = await res.text()
      if (res.ok) {
        setTest({ ok: true, msg: `连接成功（${ms} ms），HTTP ${res.status}` })
      } else {
        setTest({ ok: false, msg: `HTTP ${res.status}（${ms} ms）：${text.slice(0, 200)}` })
      }
    } catch (e: any) {
      const ms = Math.round(performance.now() - t0)
      const name = e?.name === 'AbortError' ? '超时（20s）' : String(e?.message || e)
      setTest({ ok: false, msg: `连接失败（${ms} ms）：${name}` })
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="mask show" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal lg">
        <div className="mh" style={{ background: 'var(--bg3)' }}>
          <div className="ic" style={{ background: 'var(--primaryLite)', color: '#fff' }}>🧠</div>
          <div className="ti">{f.id ? '编辑模型' : '添加模型'}</div>
        </div>
        <div className="setbody" style={{ maxHeight: '64vh', overflowY: 'auto' }}>
          <div className="field" style={{ maxWidth: 360 }}>
            <label>供应商（OpenAI 兼容协议，选常用供应商可自动填接口地址）</label>
            <select value={f.provider} onChange={(e) => {
              const p = PROVIDERS.find((x) => x.id === e.target.value)
              patch({ provider: e.target.value, ...(p && p.url ? { base_url: p.url } : {}) })
            }}>
              {PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>{p.icon} {p.name}</option>
              ))}
            </select>
          </div>
          <div className="field" style={{ maxWidth: 520 }}>
            <label>接口地址</label>
            <input
              placeholder="https://api.example.com/v1/chat/completions"
              value={f.base_url}
              onChange={(e) => patch({ base_url: e.target.value })}
            />
          </div>
          <div className="field" style={{ maxWidth: 520 }}>
            <label>API Key</label>
            <div className="keyrow">
              <input
                type={showKey ? 'text' : 'password'}
                placeholder="输入你的 API Key"
                value={f.api_key}
                onChange={(e) => patch({ api_key: e.target.value })}
              />
              <span className="eye" onClick={() => setShowKey(!showKey)}>{showKey ? '👁' : '🔒'}</span>
              <button className="btn" disabled={testing} onClick={testConnection}>
                {testing ? '测试中…' : '测试连接'}
              </button>
            </div>
            {test && (
              <div className={`note ${test.ok ? 'ok' : 'err'}`}>
                {test.ok ? '✓ ' : '✗ '}{test.msg}
              </div>
            )}
          </div>
          <div className="field" style={{ maxWidth: 520 }}>
            <label>模型名称</label>
            <input
              placeholder="输入模型参数值，例如 gpt-4o 或 openai/gpt-4o"
              value={f.model}
              onChange={(e) => patch({ model: e.target.value })}
            />
          </div>

          <div style={{ height: 1, background: 'var(--border)', margin: '14px 0' }} />
          <div style={{ fontSize: 12, fontWeight: 600, margin: '4px 0 8px', color: 'var(--text)' }}>
            高级配置
          </div>
          <div className="cm-caps">
            <label className="cap"><input type="checkbox" checked={f.tools} onChange={(e) => patch({ tools: e.target.checked })} /> 工具调用</label>
            <label className="cap"><input type="checkbox" checked={f.image} onChange={(e) => patch({ image: e.target.checked })} /> 图片输入</label>
            <label className="cap"><input type="checkbox" checked={f.thinking} onChange={(e) => patch({ thinking: e.target.checked })} /> 思考模式</label>
          </div>
          <div className="field" style={{ maxWidth: 520, marginTop: 10 }}>
            <label>自定义补充</label>
            <textarea
              rows={2}
              placeholder="可选，自由文本，原样透传备用"
              value={f.supplement}
              onChange={(e) => patch({ supplement: e.target.value })}
            />
          </div>
        </div>
        <div className="mf">
          <div className="spacer" style={{ flex: 1 }} />
          <button className="btn" onClick={onClose}>取消</button>
          <button className="btn ok" onClick={() => onSave(f)}>保存</button>
        </div>
      </div>
    </div>
  )
}
