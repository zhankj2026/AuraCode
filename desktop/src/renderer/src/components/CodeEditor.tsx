import { useEffect, useRef } from 'react'
import { EditorView, basicSetup } from 'codemirror'
import { EditorState, Compartment } from '@codemirror/state'
import { oneDark } from '@codemirror/theme-one-dark'

/**
 * 轻量 CodeMirror 6 封装：代码高亮 + 行号 + 可编辑。
 * - 语言按文件扩展名动态 import（@codemirror/language-data），
 *   只打包用到的语言，bundle 友好。
 * - 受控模式：外部 value 变化（如切换文件）会同步进编辑器；
 *   编辑器内输入通过 onChange 回传，避免光标跳动（仅当值真正不同才写入）。
 */

const langCompartment = new Compartment()

/** 扩展名 → 语言包映射（动态加载，Vite 自动代码分割） */
async function loadLanguage(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  try {
    switch (ext) {
      case 'ts':
      case 'tsx':
        return (await import('@codemirror/lang-javascript')).javascript({ typescript: true, jsx: ext === 'tsx' })
      case 'js':
      case 'mjs':
      case 'cjs':
      case 'jsx':
        return (await import('@codemirror/lang-javascript')).javascript({ jsx: ext === 'jsx' })
      case 'json':
        return (await import('@codemirror/lang-json')).json()
      case 'html':
      case 'htm':
        return (await import('@codemirror/lang-html')).html()
      case 'css':
        return (await import('@codemirror/lang-css')).css()
      case 'md':
      case 'markdown':
        return (await import('@codemirror/lang-markdown')).markdown()
      case 'py':
        return (await import('@codemirror/lang-python')).python()
      case 'java':
        return (await import('@codemirror/lang-java')).java()
      case 'xml':
      case 'svg':
        return (await import('@codemirror/lang-xml')).xml()
      case 'yaml':
      case 'yml':
        return (await import('@codemirror/lang-yaml')).yaml()
      default:
        return null
    }
  } catch {
    return null
  }
}

export function CodeEditor({
  path,
  value,
  onChange,
}: {
  path: string
  value: string
  onChange: (v: string) => void
}) {
  const hostRef = useRef<HTMLDivElement>(null)
  const viewRef = useRef<EditorView | null>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  // 创建/销毁编辑器实例（每个文件路径一个实例，切文件重建——简单可靠）
  useEffect(() => {
    if (!hostRef.current) return
    let cancelled = false

    const view = new EditorView({
      state: EditorState.create({
        doc: value,
        extensions: [
          basicSetup,
          oneDark,
          langCompartment.of([]),
          EditorView.updateListener.of((u) => {
            if (u.docChanged) onChangeRef.current(u.state.doc.toString())
          }),
          EditorView.theme({
            '&': { height: '100%', fontSize: '12.5px' },
            '.cm-scroller': { fontFamily: 'var(--mono)', overflow: 'auto' },
            '.cm-gutters': { backgroundColor: '#0c1220', border: 'none' },
          }),
        ],
      }),
      parent: hostRef.current,
    })
    viewRef.current = view

    // 异步加载语言并注入
    loadLanguage(path).then((lang) => {
      if (cancelled || !lang) return
      view.dispatch({
        effects: langCompartment.reconfigure(lang),
      })
    })

    return () => {
      cancelled = true
      view.destroy()
      viewRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path])

  // 外部 value 更新（非本编辑器输入导致的差异）→ 同步进编辑器
  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    const cur = view.state.doc.toString()
    if (cur !== value) {
      view.dispatch({
        changes: { from: 0, to: cur.length, insert: value },
      })
    }
  }, [value])

  return <div ref={hostRef} className="cm-host" />
}
