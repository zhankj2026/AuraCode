import { useEffect, useState } from 'react'
import { actions, useStore } from '../state/store'

const NAV = [
  { sec: '通用', items: [['general', '🔄 通用'], ['appearance', '🎨 外观'], ['keys', '⌨️ 快捷键']] },
  { sec: '功能', items: [['model', '🧠 模型'], ['skills', '🧩 技能'], ['mcp', '🔌 MCP'], ['perm', '🛡️ 权限']] },
  { sec: '数据与安全', items: [['data', '💾 数据管理']] },
]

const MODE_NOTES: Record<string, string> = {
  普通: '普通：危险操作需用户确认。日常开发默认。',
  自动: '自动：自动批准安全操作。信任环境/CI 使用。',
  计划: '计划：只读分析，不执行任何修改。',
  绕过: '绕过：跳过所有权限检查。仅调试使用。',
}

/** 技能来源标签与配色（对应主进程 readSkills 的 source 字段） */
const SKILL_SRC_LABEL: Record<'builtin' | 'project' | 'user', string> = {
  builtin: '内置',
  project: '项目',
  user: '用户',
}
const SKILL_SRC_COLOR: Record<'builtin' | 'project' | 'user', { bg: string; fg: string }> = {
  builtin: { bg: 'rgba(88,166,255,.15)', fg: '#58a6ff' },
  project: { bg: 'rgba(163,113,247,.15)', fg: '#a371f7' },
  user: { bg: 'rgba(63,185,80,.15)', fg: '#3fb950' },
}

/** 模型下拉兜底选项（拉取后端 /api/models 失败时使用）。
 *  正常情况下下拉由后端返回的模型目录填充。 */
const MODEL_FALLBACK: Array<{ id: string; note?: string }> = [
  { id: 'GLM-4-Flash', note: '免费 · 实测可用' },
  { id: 'glm-4.7', note: '付费' },
  { id: 'glm-4.6', note: '付费' },
  { id: 'glm-4.5-air', note: '付费' },
  { id: 'GLM-5.3-Flash', note: '当前 Key 已欠费' },
  { id: 'glm-5.3-flashx', note: '当前 Key 已欠费' },
  { id: 'deepseek-chat', note: '需另配 Key' },
]

export function SettingsModal() {
  const open = useStore((s) => s.settingsOpen)
  const mode = useStore((s) => s.mode)
  const ext = useStore((s) => s.extensions)
  const client = useStore((s) => s.client)
  const activeId = useStore((s) => s.activeSessionId)
  const sessions = useStore((s) => s.sessions)
  const [pane, setPane] = useState('general')
  const [bypass, setBypass] = useState(mode === '绕过')
  const [switching, setSwitching] = useState(false)
  const [modelNote, setModelNote] = useState('')
  // 后端真实 LLM 配置 + 模型目录（取代硬编码）
  const [llm, setLlm] = useState<{
    provider: string; model: string; base_url: string; has_api_key: boolean; default_model: string
  } | null>(null)
  const [models, setModels] = useState<Array<{ id: string; provider?: string; note?: string }>>([])
  const [prov, setProv] = useState('')
  const [keyInput, setKeyInput] = useState('')
  const [urlInput, setUrlInput] = useState('')
  const [cfgSaved, setCfgSaved] = useState(false)
  const [saving, setSaving] = useState(false)

  const active = sessions.find((s) => s.session_id === activeId)
  const currentModel = active?.model || ''

  // 进入模型页时拉取后端配置与模型目录
  useEffect(() => {
    if (!open || pane !== 'model' || !client) return
    let alive = true
    ;(async () => {
      try {
        const [cfg, m] = await Promise.all([client!.getLlmConfig(), client!.listModels()])
        if (!alive) return
        setLlm(cfg)
        setProv(cfg.provider || 'openai')
        setUrlInput(cfg.base_url || '')
        setModels(m.models?.length ? m.models : MODEL_FALLBACK)
      } catch (e: any) {
        if (!alive) return
        setModels(MODEL_FALLBACK)
        setModelNote('拉取后端配置失败：' + String(e?.message || e))
      }
    })()
    return () => { alive = false }
  }, [open, pane, client])

  // 面板打开时监听 model_changed，及时刷新提示（会话侧热切换/fallback 都会触发）
  useEffect(() => {
    if (!open) return
    setModelNote('')
    setCfgSaved(false)
  }, [open, pane])

  async function applyModel(m: string) {
    if (!client || !activeId || switching) return
    setSwitching(true)
    setModelNote('切换中…')
    try {
      await client.switchModel(activeId, m)
      const note = models.find((o) => o.id === m)?.note
      setModelNote(`已切换到 ${m}${note ? `（${note}）` : ''}`)
      actions.setToast(`已切换模型：${m}`, 'ok')
    } catch (e: any) {
      const msg = String(e?.message || e)
      setModelNote(/409/.test(msg) ? '切换被拒：会话正在运行或模型未变化' : '切换失败：' + msg)
      actions.setToast('切换模型失败：' + msg, 'error')
    } finally {
      setSwitching(false)
    }
  }

  /** 保存 LLM 配置到后端（落盘 config.yaml）。空 Key 不发送，避免清空已存密钥。 */
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

  /** 设为默认模型：持久化到 config.yaml，新建会话自动采用。 */
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

  if (!open) return null

  function setMode(m: string) {
    actions.setMode(m)
    setBypass(m === '绕过')
  }

  return (
    <div className="mask show" onClick={(e) => e.target === e.currentTarget && actions.closeSettings()}>
      <div className="modal xl">
        <div className="mh" style={{ background: 'var(--bg3)' }}>
          <div className="ic" style={{ background: 'var(--primaryLite)', color: '#fff' }}>⚙</div>
          <div className="ti">设置</div>
        </div>
        <div className="setwrap">
          <div className="setnav">
            {NAV.map((g) => (
              <div key={g.sec}>
                <div className="sec">{g.sec}</div>
                {g.items.map(([k, label]) => (
                  <div key={k} className={`sn ${pane === k ? 'on' : ''}`} onClick={() => setPane(k)}>
                    {label}
                  </div>
                ))}
              </div>
            ))}
          </div>
          <div className="setbody">
            {pane === 'general' && (
              <>
                <Row title="对话记忆" desc="记住对话中的重要信息，让后续回答更贴合项目。" on />
                <Row title="本地记忆与技能" desc="自动记录工作过程并优化技能，数据仅保存在本机。" on />
                <div className="field" style={{ maxWidth: 280 }}>
                  <label>界面语言</label>
                  <select defaultValue="zh"><option value="zh">简体中文</option><option value="en">English</option></select>
                </div>
                <div className="note">开机自启动、界面语言为规划项，当前版本暂未生效。</div>
              </>
            )}
            {pane === 'appearance' && (
              <>
                <div className="field" style={{ maxWidth: 280 }}><label>主题</label><select defaultValue="dark"><option value="dark">深色（默认）</option><option value="light">浅色</option><option value="auto">跟随系统</option></select></div>
                <div className="field" style={{ maxWidth: 280 }}><label>代码字体</label><select defaultValue="mono"><option value="mono">JetBrains Mono</option><option value="consolas">Consolas</option><option value="cascadia">Cascadia Code</option></select></div>
                <Row title="事件流自动折叠" desc="工具调用成功后自动收起详情。" on />
                <div className="note">主题/字体为规划项，当前版本暂未生效。</div>
              </>
            )}
            {pane === 'keys' && (
              <>
                <KeyRow title="发送消息" kbd="Enter" />
                <KeyRow title="换行" kbd="Shift + Enter" />
                <KeyRow title="切换会话" kbd="Ctrl + K" />
                <KeyRow title="命令面板" kbd="Ctrl + P" />
                <KeyRow title="停止当前任务" kbd="Esc" />
              </>
            )}
            {pane === 'model' && (
              <>
                {/* 当前会话模型：切换即时生效（仅空闲可切） */}
                <div className="field" style={{ maxWidth: 360 }}>
                  <label>当前会话模型（切换即时生效）</label>
                  <select
                    value={currentModel}
                    disabled={switching}
                    onChange={(e) => applyModel(e.target.value)}
                  >
                    {currentModel && !models.some((o) => o.id === currentModel) && (
                      <option value={currentModel}>{currentModel}</option>
                    )}
                    {!currentModel && <option value="">（未设置）</option>}
                    {models.map((o) => (
                      <option key={o.id} value={o.id}>{o.id}{o.note ? ` · ${o.note}` : ''}</option>
                    ))}
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

                {/* 引擎 LLM 配置：前端可编辑并持久化到 config.yaml */}
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
                <Row title="流式输出" desc="逐字显示回复（SSE）。" on />
                <button className="btn" style={{ marginTop: 4 }} onClick={() => {
                  actions.setToast(currentModel ? `当前模型 ${currentModel}：以最近一次对话为准（成功即连通）` : '无活动会话', 'info')
                }}>测试连接</button>
              </>
            )}
            {pane === 'skills' && (
              <>
                <div style={{ fontSize: 11.5, color: 'var(--muted)', marginBottom: 8 }}>
                  技能 = 可复用的指令包。来源：工程 skills/（内置）、工程 .auracode/skills（项目）、~/.auracode/skills（用户，SkillHub 安装后在此处）。
                </div>
                {(ext?.skills?.length ?? 0) === 0 && (
                  <div className="search">未扫描到技能（skills/*/SKILL.md）</div>
                )}
                {(ext?.skills ?? []).map((s) => (
                  <div key={`${s.source}:${s.name}`} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <Row title={s.name} desc={s.description || '可复用指令包'} on />
                    </div>
                    <span
                      title={`来源：${SKILL_SRC_LABEL[s.source]}`}
                      style={{
                        flex: '0 0 auto',
                        fontSize: 11,
                        lineHeight: '20px',
                        padding: '0 8px',
                        borderRadius: 10,
                        background: SKILL_SRC_COLOR[s.source].bg,
                        color: SKILL_SRC_COLOR[s.source].fg,
                        border: `1px solid ${SKILL_SRC_COLOR[s.source].fg}`,
                      }}
                    >
                      {SKILL_SRC_LABEL[s.source]}
                    </span>
                  </div>
                ))}
              </>
            )}
            {pane === 'mcp' && (
              <>
                <div style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.7, marginBottom: 12 }}>
                  以下为真实读取到的 MCP 服务器（工程 .mcp.json 与 ~/.auracode/mcp.json）。点击「添加」可在弹窗中新增。
                </div>
                {(ext?.mcp?.length ?? 0) === 0 && (
                  <div className="search">暂无 MCP 服务器配置</div>
                )}
                {(ext?.mcp ?? []).map((m) => (
                  <Row key={`${m.scope}:${m.name}`} title={`${m.name}（${m.scope}）`} desc={`${m.type}${m.command ? ' · ' + m.command : ''}${m.url ? ' · ' + m.url : ''} · ${m.enabled ? '已启用' : '已禁用'}`} on={m.enabled} />
                ))}
                <button className="btn" style={{ marginTop: 4 }} onClick={() => actions.openMcp()}>＋ 添加 MCP 服务器</button>
              </>
            )}
            {pane === 'perm' && (
              <>
                <div style={{ fontSize: 12, color: 'var(--text)', fontWeight: 600, marginBottom: 2 }}>权限模式</div>
                <div className="mseg">
                  {['普通', '自动', '计划', '绕过'].map((m) => (
                    <button key={m} className={mode === m ? 'on' : ''} onClick={() => setMode(m)}>
                      {m}
                    </button>
                  ))}
                </div>
                <div className="note">{MODE_NOTES[mode]}</div>
                <div className="note">权限模式在<b>新建会话时</b>生效（顶部模式选择器同此）。已存在会话的模式不回改。</div>
                {bypass && (
                  <div className="note" style={{ background: '#2a1606', borderColor: '#5a3d12', color: 'var(--warn)' }}>
                    ⚠ 绕过模式将跳过所有权限检查，agent 可直接执行任何写操作。仅用于调试，生产环境慎用。
                  </div>
                )}
                <div style={{ fontSize: 12, fontWeight: 600, margin: '14px 0 6px' }}>规则（v2 支持）</div>
                <div className="mrow"><span className="k">允许　</span><span style={{ color: 'var(--ok)' }}>read_file:* · run_command:git *</span></div>
                <div className="mrow"><span className="k">拒绝　</span><span className="v">run_command:rm *</span></div>
              </>
            )}
            {pane === 'data' && (
              <>
                <Row title="导出全部会话" desc="会话快照存于 ~/.auracode/sessions/*.json，可直接备份该目录。" button="打开目录" onClick={() => actions.setToast('路径：C:\\Users\\you\\.auracode\\sessions\\', 'info')} />
                <Row title="审计日志" desc="本机明文存储，可在活动栏「审计」查看。" button="打开目录" onClick={() => { actions.setActivity('audit'); actions.closeSettings() }} />
                <Row title="清除缓存" desc="清理临时文件与下载缓存。" button="清除" onClick={() => actions.setToast('暂未实现：后端未暴露缓存清理接口', 'info')} />
              </>
            )}
          </div>
        </div>
        <div className="mf">
          <div className="spacer" style={{ flex: 1 }} />
          <button className="btn ok" onClick={() => actions.closeSettings()}>完成</button>
        </div>
      </div>
    </div>
  )
}

function Row({ title, desc, on, button, onClick }: { title: string; desc: string; on?: boolean; button?: string; onClick?: () => void }) {
  const [enabled, setEnabled] = useState(!!on)
  return (
    <div className="setrow">
      <div>
        <div className="srt">{title}</div>
        <div className="srd">{desc}</div>
      </div>
      {button ? (
        <button className="btn" style={{ padding: '5px 12px' }} onClick={onClick}>{button}</button>
      ) : (
        <div className={`toggle ${enabled ? 'on' : ''}`} onClick={() => setEnabled(!enabled)} />
      )}
    </div>
  )
}

function KeyRow({ title, kbd }: { title: string; kbd: string }) {
  return (
    <div className="setrow">
      <div className="srt">{title}</div>
      <span className="kbd">{kbd}</span>
    </div>
  )
}
