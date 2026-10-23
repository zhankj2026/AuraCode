/**
 * FilePreview.tsx — 统一文件预览：图片 / Markdown / Office（docx/pptx）
 *
 * - 图片: IPC fs:readDataUrl → data URL → <img>
 * - Markdown: 主进程整读文本 → renderMarkdown（lib/md.ts）→ 沙箱 HTML
 * - Office: IPC fs:officePreview → 内置 Python 纯 stdlib 转换 → 沙箱 HTML
 * 路径安全由 IPC 层保证（目录包含校验 + 大小上限）。
 */
import { useEffect, useMemo, useState } from 'react'
import { useStore } from '../state/store'
import { renderMarkdown } from '../lib/md'

const api = (window as any).auracode

/** 图片预览 */
export function ImagePreview({ path }: { path: string }) {
  const sessions = useStore((s) => s.sessions)
  const activeId = useStore((s) => s.activeSessionId)
  const [dataUrl, setDataUrl] = useState('')
  const [err, setErr] = useState('')
  const workDir = useMemo(
    () => (sessions.find((x) => x.session_id === activeId)?.work_dir || '').trim(),
    [sessions, activeId],
  )

  useEffect(() => {
    let cancelled = false
    setErr('')
    setDataUrl('')
    ;(async () => {
      if (!api?.readDataUrl || !workDir) return
      const r = await api.readDataUrl(workDir, path)
      if (cancelled) return
      if (r?.ok) setDataUrl(r.dataUrl)
      else setErr(String(r?.error || '读取失败'))
    })()
    return () => {
      cancelled = true
    }
  }, [workDir, path])

  if (err) return <div className="fp-err">图片读取失败：{err}</div>
  if (!dataUrl) return <div className="fp-loading">加载图片…</div>
  return (
    <div className="fp-image">
      <img src={dataUrl} alt={path} />
    </div>
  )
}

/** Markdown 预览（沙箱 iframe，样式与对话气泡一致的 .md-body） */
export function MarkdownPreview({ path }: { path: string }) {
  const file = useStore((s) => s.openFiles.find((f) => f.path === path))
  const html = useMemo(() => renderMarkdown(file?.content || ''), [file?.content])
  return (
    <div className="fp-md md-body" dangerouslySetInnerHTML={{ __html: html }} />
  )
}

/** Office（docx/pptx）预览：IPC 调内置 Python 转换 → 沙箱渲染 */
export function OfficePreview({ path }: { path: string }) {
  const sessions = useStore((s) => s.sessions)
  const activeId = useStore((s) => s.activeSessionId)
  const [html, setHtml] = useState('')
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [err, setErr] = useState('')
  const workDir = useMemo(
    () => (sessions.find((x) => x.session_id === activeId)?.work_dir || '').trim(),
    [sessions, activeId],
  )

  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    setHtml('')
    ;(async () => {
      if (!api?.officePreview || !workDir) {
        setErr('预览能力不可用（需新版桌面端）')
        setStatus('error')
        return
      }
      const r = await api.officePreview(workDir, path)
      if (cancelled) return
      if (r?.ok && r.html) {
        setHtml(r.html)
        setStatus('ready')
      } else {
        setErr(String(r?.error || '转换失败'))
        setStatus('error')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [workDir, path])

  if (status === 'loading') return <div className="fp-loading">文档转换中…（内置 Python）</div>
  if (status === 'error')
    return (
      <div className="fp-err">
        Office 预览失败：{err}
        <div className="fp-hint">
          支持 .docx/.pptx（文本+图片）；旧版 .doc/.ppt 请先另存为新格式。
        </div>
      </div>
    )
  // 注意：officePreview 的 HTML 完全由我们自己的 Python 转换器生成——
  // 无 <script>、无外链资源、图片均为内联 data URL，内容可信。
  // 原先带 sandbox="allow-same-origin"，会让子帧落入沙箱渲染上下文，
  // 无法回退到系统 CJK 字体（微软雅黑等），导致中文显示为豆腐块（tofu）。
  // 去掉 sandbox 使其与宿主窗口共用同一渲染进程与字体集，中文即可正常显示。
  return (
    <iframe
      className="fp-office"
      title={path}
      srcDoc={html}
      style={{ width: '100%', flex: 1, border: 'none', background: '#fff' }}
    />
  )
}
