import { useState } from 'react'
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

/** 模型下拉选项。glm-5.3-flashx 是引擎 config.yaml 当前配置的主力模型
 *  （demo10 长任务验证过 25 连锁工具调用）；引擎会读 llm.model 作为
 *  Bridge 会话默认模型（bridge_command._default_model_from_engine_config）。 */
const MODEL_OPTIONS = [
  'GLM-5.3-Flash',
  'glm-5.3-flashx',
  'glm-4.7',
  'glm-4.6',
  'glm-4.5-air',
  'deepseek-chat',
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

  const active = sessions.find((s) => s.session_id === activeId)
  const currentModel = active?.model || ''

  async function applyModel(m: string) {
    if (!client || !activeId) return
    try {
      await client.switchModel(activeId, m)
      actions.setToast(`已切换模型：${m}`, 'ok')
    } catch (e) {
      actions.setToast('切换模型失败：' + (e instanceof Error ? e.message : String(e)), 'error')
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
                <Row title="开机自启动" desc="登录 Windows 后自动启动 AuraCode。" />
                <div className="field" style={{ maxWidth: 280 }}>
                  <label>界面语言</label>
                  <select><option>简体中文</option><option>English</option></select>
                </div>
              </>
            )}
            {pane === 'appearance' && (
              <>
                <div className="field" style={{ maxWidth: 280 }}><label>主题</label><select><option>深色（默认）</option><option>浅色</option><option>跟随系统</option></select></div>
                <div className="field" style={{ maxWidth: 280 }}><label>代码字体</label><select><option>JetBrains Mono</option><option>Consolas</option><option>Cascadia Code</option></select></div>
                <Row title="事件流自动折叠" desc="工具调用成功后自动收起详情。" on />
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
                <div className="field"><label>提供商</label><select><option>智谱 AI（GLM）</option><option>DeepSeek</option><option>OpenAI 兼容</option><option>自定义</option></select></div>
                <div className="field"><label>API Key</label><input type="password" placeholder="未读取：由后端环境变量/AURACODE 配置提供" /></div>
                <div className="field"><label>Base URL</label><input placeholder="由后端配置提供" /></div>
                <div className="field" style={{ maxWidth: 280 }}>
                  <label>当前会话模型（切换即时生效）</label>
                  <select
                    value={currentModel}
                    onChange={(e) => applyModel(e.target.value)}
                  >
                    {currentModel && !MODEL_OPTIONS.includes(currentModel) && (
                      <option value={currentModel}>{currentModel}</option>
                    )}
                    {!currentModel && <option value="">（未设置）</option>}
                    {MODEL_OPTIONS.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>
                <Row title="流式输出" desc="逐字显示回复（SSE）。" on />
                <button className="btn" style={{ marginTop: 4 }} onClick={() => actions.setToast('测试连接：当前后端未暴露探针接口', 'info')}>测试连接</button>
              </>
            )}
            {pane === 'skills' && (
              <>
                <div style={{ fontSize: 11.5, color: 'var(--muted)', marginBottom: 8 }}>
                  技能 = 可复用的指令包，来源于工程 skills/ 目录（真实扫描）。
                </div>
                {(ext?.skills?.length ?? 0) === 0 && (
                  <div className="search">未扫描到技能（skills/*/SKILL.md）</div>
                )}
                {(ext?.skills ?? []).map((s) => (
                  <Row key={s.name} title={s.name} desc={s.description || '可复用指令包'} on />
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
                <Row title="导出全部会话" desc="导出为 JSONL，便于备份与迁移。" button="导出" onClick={() => actions.setToast('导出功能：当前后端未暴露会话导出接口', 'info')} />
                <Row title="审计日志" desc="本机明文存储，可在活动栏「审计」查看。" button="打开目录" onClick={() => { actions.setActivity('audit'); actions.closeSettings() }} />
                <Row title="清除缓存" desc="清理临时文件与下载缓存（约 128 MB）。" button="清除" onClick={() => actions.setToast('清除缓存：当前后端未暴露缓存清理接口', 'info')} />
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
  return (
    <div className="setrow">
      <div>
        <div className="srt">{title}</div>
        <div className="srd">{desc}</div>
      </div>
      {button ? (
        <button className="btn" style={{ padding: '5px 12px' }} onClick={onClick}>{button}</button>
      ) : (
        <div className={`toggle ${on ? 'on' : ''}`} onClick={(e) => (e.currentTarget as HTMLElement).classList.toggle('on')} />
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
