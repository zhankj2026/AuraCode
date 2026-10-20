import { useEffect, useRef, useState } from 'react'
import { actions, useStore } from '../state/store'
import type { SkillhubItem } from '../api/types'

/**
 * SkillHub 技能商店页面（模态）。
 *
 * - 搜索：调 bridge /api/skillhub/search（封装 skillhub CLI --json）
 * - 安装：调 /api/skillhub/install → 落盘到 ~/.auracode/skills/@namespace/slug
 *   （引擎 loader 已支持 @namespace 两层布局）
 * - 安装后提示「新会话自动加载 / 对话让 agent activate_skill 即用」
 */
export function SkillHubModal() {
  const open = useStore((s) => s.skillhubOpen)
  const client = useStore((s) => s.client)
  const [q, setQ] = useState('')
  const [items, setItems] = useState<SkillhubItem[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [err, setErr] = useState('')
  const [installing, setInstalling] = useState<string | null>(null)
  const [installed, setInstalled] = useState<Set<string>>(new Set())
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
      if (!searched && !q) {
        // 首次打开预置一批热门关键词结果，避免空白
        runSearch('代码')
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  if (!open) return null

  async function runSearch(query?: string) {
    const keyword = (query ?? q).trim()
    if (!keyword || !client || loading) return
    setLoading(true)
    setErr('')
    try {
      const r = await client.skillhubSearch(keyword, 24)
      setItems(r.results || [])
      setSearched(true)
      if (!r.results?.length) setErr(`没有找到与「${keyword}」相关的技能`)
    } catch (e: any) {
      setErr('搜索失败：' + (e?.message || e))
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  async function install(item: SkillhubItem) {
    if (!client || installing) return
    const key = item.publicSlug
    setInstalling(key)
    try {
      const r = await client.skillhubInstall(item.publicSlug, item.namespace_handle || '')
      if (r.success) {
        setInstalled((prev) => new Set(prev).add(key))
        item.installed = true
        actions.setToast(`已安装 ${r.installed_name} v${r.version} —— 新会话自动加载`, 'ok')
      }
    } catch (e: any) {
      actions.setToast('安装失败：' + (e?.message || e), 'error')
    } finally {
      setInstalling(null)
    }
  }

  return (
    <div className="mask show" onClick={(e) => e.target === e.currentTarget && actions.closeSkillhub()}>
      <div className="modal xl">
        <div className="mh" style={{ background: 'var(--bg3)' }}>
          <div className="ic" style={{ background: 'var(--primaryLite)', color: '#fff' }}>🧩</div>
          <div className="ti">SkillHub 技能商店</div>
          <span className="sp" />
          <button className="btn" onClick={() => actions.closeSkillhub()}>✕</button>
        </div>

        <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--line)', display: 'flex', gap: 8 }}>
          <input
            ref={inputRef}
            className="sksearch"
            style={{ flex: 1 }}
            placeholder="搜索技能：如 calendar / git / 代码评审 / pdf …"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runSearch()}
          />
          <button className="btn ok" onClick={() => runSearch()} disabled={loading || !q.trim()}>
            {loading ? '搜索中…' : '搜索'}
          </button>
        </div>

        <div className="skhub-tags">
          {['代码', 'git', '测试', '文档', 'pdf', 'web'].map((t) => (
            <button key={t} className="tag" onClick={() => { setQ(t); runSearch(t) }}>{t}</button>
          ))}
        </div>

        <div className="skhub-body">
          {err && <div className="skhub-empty">{err}</div>}
          {!err && !items.length && !loading && (
            <div className="skhub-empty">输入关键词搜索 SkillHub 商店中的技能</div>
          )}
          {items.map((it) => {
            const isInstalled = it.installed || installed.has(it.publicSlug)
            return (
              <div key={it.slug} className="skcard">
                <div className="skcard-head">
                  <span className="skname">{it.name}</span>
                  <span className="skver">v{it.version}</span>
                  {isInstalled && <span className="skbadge">已安装</span>}
                </div>
                <div className="skauthor">@{it.namespace_handle}</div>
                <div className="skdesc">{it.description}</div>
                <div className="skcard-foot">
                  <span className="skslug">{it.publicSlug}</span>
                  <button
                    className={`btn ${isInstalled ? '' : 'ok'}`}
                    disabled={isInstalled || installing === it.publicSlug}
                    onClick={() => install(it)}
                  >
                    {isInstalled ? '已安装' : installing === it.publicSlug ? '安装中…' : '安装'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>

        <div className="mf">
          <div style={{ fontSize: 11, color: 'var(--muted)', padding: '0 14px' }}>
            安装到 ~/.auracode/skills/（用户级，所有项目可用）；新会话自动加载，或对话中说「激活 xxx 技能」立即可用。
          </div>
          <div className="spacer" style={{ flex: 1 }} />
          <button className="btn ok" onClick={() => actions.closeSkillhub()}>完成</button>
        </div>
      </div>
    </div>
  )
}
