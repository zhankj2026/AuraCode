import { useEffect, useState } from 'react'
import { actions, useStore } from '../state/store'
import type { CustomModel } from '../api/types'

type FormState = {
  id: string | null
  name: string
  provider: 'openai' | 'custom'
  base_url: string
  api_key: string
  model: string
  tools: boolean
  image: boolean
  thinking: boolean
  supplement: string
}

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

/** 模型目录兜底选项（拉取后端 /api/models 失败时使用）。 */
const MODEL_FALLBACK: Array<{ id: string; note?: string }> = [
  { id: 'GLM-4-Flash', note: '免费 · 实测可用' },
  { id: 'glm-4.7', note: '付费' },
  { id: 'glm-4.6', note: '付费' },
  { id: 'glm-4.5-air', note: '付费' },
  { id: 'GLM-5.3-Flash', note: '当前 Key 已欠费' },
  { id: 'glm-5.3-flashx', note: '当前 Key 已欠费' },
  { id: 'deepseek-chat', note: '需另配 Key' },
]

export function CustomModels() {
  const models = useStore((s) => s.customModels)
  const client = useStore((s) => s.client)
  const sessions = useStore((s) => s.sessions)
  const activeId = useStore((s) => s.activeSessionId)
  const [editing, setEditing] = useState<FormState | null>(null)
  const [showKey, setShowKey] = useState(false)

  // 引擎 LLM 配置 + 当前会话模型（从原「设置 → 模型」合并而来，统一在此管理，消除与设置的重复）
  const [catalog, setCatalog] = useState<Array<{ id: string; note?: string }>>([])
  const [llm, setLlm] = useState<{ provider: string; model: string; base_url: string; has_api_key: boolean; default_model: string } | null>(null)
  const [prov, setProv] = useState('')
  const [keyInput, setKeyInput] = useState('')
  const [urlInput, setUrlInput] = useState('')
  const [cfgSaved, setCfgSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const [switching, setSwitching] = useState(false)
  const [modelNote, setModelNote] = useState('')

  const active = sessions.find((s) => s.session_id === activeId)
  const currentModel = active?.model || ''

  useEffect(() => {
    actions.loadCustomModels()
  }, [])

  // 进入面板时拉取后端 LLM 配置与模型目录
  useEffect(() => {
    if (!client) return
    let alive = true
    ;(async () => {
      try {
        const [cfg, m] = await Promise.all([client!.getLlmConfig(), client!.listModels()])
        if (!alive) return
        setLlm(cfg)
        setProv(cfg.provider || 'openai')
        setUrlInput(cfg.base_url || '')
        setCatalog(m.models?.length ? m.models : MODEL_FALLBACK)
      } catch (e: any) {
        if (!alive) return
        setCatalog(MODEL_FALLBACK)
        setModelNote('拉取后端配置失败：' + String(e?.message || e))
      }
    })()
    return () => { alive = false }
  }, [client])

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

  async function applyModel(model: string, baseUrl?: string, apiKey?: string) {
    if (!client || !activeId || switching) return
    setSwitching(true)
    setModelNote('切换中…')
    try {
      await client.switchModel(activeId, model, baseUrl, apiKey)
      actions.updateSessionModel(activeId, model)
      setModelNote(`已切换到 ${model}`)
      actions.setToast(`已切换模型：${model}`, 'ok')
    } catch (e: any) {
      const msg = String(e?.message || e)
      setModelNote('切换失败：' + msg)
      actions.setToast('切换模型失败：' + msg, 'error')
    } finally {
      setSwitching(false)
    }
  }

  function onPickModel(value: string) {
    if (value.startsWith('custom:')) {
      const cm = models.find((c) => `custom:${c.id}` === value)
      if (cm) applyModel(cm.model, cm.base_url, cm.api_key)
      return
    }
    applyModel(value)
  }

  async function saveLlmConfig() {
    if (!client || saving) return
    setSaving(true)
    setCfgSaved(false)
    try {
      const patch: Record<string, string> = { provider: prov, base_url: urlInput }
      if (keyInput.trim()) patch.api_key = keyInput.trim()
      const cfg = await client.putLlmConfig(patch)
      setLlm(cfg)
      setKeyInput('')
      setCfgSaved(true)
      actions.setToast('LLM 配置已保存（新会话生效）', 'ok')
    } catch (e: any) {
      actions.setToast('保存失败：' + String(e?.message || e), 'error')
    } finally {
      setSaving(false)
    }
  }

  async function setDefaultModel(m: string) {
    if (!client || !m) return
    try {
      const cfg = await client.putLlmConfig({ model: m })
      setLlm(cfg)
      actions.setToast(`已设为默认模型：${m}（新建会话生效）`, 'ok')
    } catch (e: any) {
      actions.setToast('设置默认失败：' + String(e?.message || e), 'error')
    }
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

      <div style={{ height: 1, background: 'var(--border)', margin: '18px 0' }} />
      <div className="cm-head">
        <div>
          <div className="cm-title">会话与引擎</div>
          <div className="cm-sub">切换当前会话模型，或配置全局引擎 LLM（API Key / Base URL），与上方自定义模型统一管理。</div>
        </div>
      </div>

      <div className="field" style={{ maxWidth: 360, marginTop: 8 }}>
        <label>当前会话模型（切换即时生效）</label>
        <select value={currentModel} disabled={switching} onChange={(e) => onPickModel(e.target.value)}>
          {currentModel && !catalog.some((o) => o.id === currentModel) && !models.some((c) => c.model === currentModel) && (
            <option value={currentModel}>{currentModel}（自定义）</option>
          )}
          {!currentModel && <option value="">（未设置）</option>}
          {catalog.map((o) => (
            <option key={o.id} value={o.id}>{o.id}{o.note ? ` · ${o.note}` : ''}</option>
          ))}
          {models.length > 0 && (
            <optgroup label="自定义模型">
              {models.map((c) => (
                <option key={c.id} value={`custom:${c.id}`}>{c.name} · {c.model}</option>
              ))}
            </optgroup>
          )}
        </select>
      </div>
      {modelNote && <div className="note">{modelNote}</div>}
      {llm && llm.default_model && (
        <div className="note">默认模型（新建会话采用）：<b>{llm.default_model}</b></div>
      )}
      <button
        className="btn"
        style={{ marginTop: 4 }}
        disabled={!currentModel || switching || currentModel === llm?.default_model}
        onClick={() => setDefaultModel(currentModel)}
      >
        设为默认（新建会话生效）
      </button>

      <div style={{ height: 1, background: 'var(--border)', margin: '14px 0' }} />

      <div style={{ fontSize: 12, fontWeight: 600, margin: '4px 0 2px', color: 'var(--text)' }}>引擎 LLM 配置（保存后新会话生效）</div>
      <div className="field" style={{ maxWidth: 320 }}>
        <label>提供商</label>
        <select value={prov} onChange={(e) => setProv(e.target.value)}>
          <option value="openai">OpenAI 兼容（智谱/DeepSeek/自建）</option>
          <option value="zhipu">智谱 AI（GLM）</option>
          <option value="deepseek">DeepSeek</option>
        </select>
      </div>
      <div className="field" style={{ maxWidth: 460 }}>
        <label>API Key{llm?.has_api_key ? '（已设置，留空不改动）' : '（未设置）'}</label>
        <input
          type="password"
          placeholder={llm?.has_api_key ? '已保存，输入新值以更新，留空保持不变' : '在此输入 API Key'}
          value={keyInput}
          onChange={(e) => setKeyInput(e.target.value)}
        />
      </div>
      <div className="field" style={{ maxWidth: 460 }}>
        <label>Base URL</label>
        <input
          placeholder="https://open.bigmodel.cn/api/coding/paas/v4"
          value={urlInput}
          onChange={(e) => setUrlInput(e.target.value)}
        />
      </div>
      <button className="btn ok" style={{ marginTop: 4 }} disabled={saving} onClick={saveLlmConfig}>
        {saving ? '保存中…' : '保存配置'}
      </button>
      {cfgSaved && <div className="note" style={{ color: 'var(--ok)' }}>已保存。正在运行的会话不受影响，新建会话生效。</div>}
      <div className="note">配置保存在引擎 config.yaml 的 llm.* 段，桌面重启后依然有效；运行中的会话需新建才会采用。</div>
      <div className="setrow" style={{ maxWidth: 460 }}>
        <div>
          <div className="srt">流式输出</div>
          <div className="srd">逐字显示回复（SSE）。</div>
        </div>
        <div className="toggle on" />
      </div>
      <button className="btn" style={{ marginTop: 4 }} onClick={() => {
        actions.setToast(currentModel ? `当前模型 ${currentModel}：以最近一次对话为准（成功即连通）` : '无活动会话', 'info')
      }}>测试连接</button>

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
            <label>供应商（仅支持 OpenAI 兼容协议 API）</label>
            <select value={f.provider} onChange={(e) => patch({ provider: e.target.value as 'openai' | 'custom' })}>
              <option value="openai">◇ OpenAI 兼容</option>
              <option value="custom">◇ 自定义</option>
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
