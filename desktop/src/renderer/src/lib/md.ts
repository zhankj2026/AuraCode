/**
 * md.ts — 零依赖 Markdown → HTML 渲染器（对话气泡与 .md 文件预览共用）
 *
 * 设计原则：
 * 1. 安全第一：先整段 HTML escape，再做 MD 替换 → 产出无原生标签注入。
 * 2. 零依赖：不引 react-markdown/marked，纯函数 ~200 行。
 * 3. 覆盖对话高频语法：标题/无序有序列表/代码块(```)/行内代码/粗体/斜体/
 *    删除线/链接/图片/引用/分隔线/表格/任务列表。
 */

function esc(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/** 行内元素：行内代码 > 图片 > 链接 > 粗体 > 斜体 > 删除线 */
function inline(s: string): string {
  // 行内代码先保护（内部不再做其他替换）
  const codes: string[] = []
  let t = s.replace(/`([^`\n]+)`/g, (_m, c) => {
    codes.push(`<code>${c}</code>`)
    return `\u0000${codes.length - 1}\u0000`
  })
  t = t.replace(/!\[([^\]]*)\]\(([^)\s]+)[^)]*\)/g, '<img alt="$1" src="$2" />')
  t = t.replace(
    /\[([^\]]+)\]\(([^)\s]+)[^)]*\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>',
  )
  t = t.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
  t = t.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>')
  t = t.replace(/~~([^~\n]+)~~/g, '<del>$1</del>')
  // 还原行内代码
  t = t.replace(/\u0000(\d+)\u0000/g, (_m, i) => codes[Number(i)] || '')
  return t
}

/** 块级解析：逐行状态机 */
export function renderMarkdown(src: string): string {
  const lines = esc(src || '').split('\n')
  const out: string[] = []
  let i = 0
  let listType: 'ul' | 'ol' | null = null

  const closeList = () => {
    if (listType) {
      out.push(`</${listType}>`)
      listType = null
    }
  }

  while (i < lines.length) {
    const line = lines[i]

    // 代码块 ```
    if (/^```/.test(line.trim())) {
      closeList()
      const lang = line.trim().slice(3).trim()
      const buf: string[] = []
      i++
      while (i < lines.length && !/^```/.test(lines[i].trim())) {
        buf.push(lines[i])
        i++
      }
      i++ // 跳过结尾 ```
      out.push(
        `<pre class="md-pre"${lang ? ` data-lang="${lang}"` : ''}><code>${buf.join('\n')}</code></pre>`,
      )
      continue
    }

    // 空行
    if (!line.trim()) {
      closeList()
      i++
      continue
    }

    // 标题 #~######
    const h = line.match(/^(#{1,6})\s+(.*)$/)
    if (h) {
      closeList()
      const lv = h[1].length
      out.push(`<h${lv}>${inline(h[2])}</h${lv}>`)
      i++
      continue
    }

    // 分隔线
    if (/^(\*\s*){3,}$/.test(line.trim()) || /^(-\s*){3,}$/.test(line.trim())) {
      closeList()
      out.push('<hr/>')
      i++
      continue
    }

    // 引用 >
    if (/^&gt;\s?/.test(line)) {
      closeList()
      const buf: string[] = []
      while (i < lines.length && /^&gt;\s?/.test(lines[i])) {
        buf.push(lines[i].replace(/^&gt;\s?/, ''))
        i++
      }
      out.push(`<blockquote>${inline(buf.join(' '))}</blockquote>`)
      continue
    }

    // 表格 | a | b |
    if (/\|.+\|/.test(line) && i + 1 < lines.length && /^\|?[\s:|-]+\|?$/.test(lines[i + 1].trim())) {
      closeList()
      const head = line.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
      i += 2
      const rows: string[][] = []
      while (i < lines.length && /\|.+\|/.test(lines[i])) {
        rows.push(
          lines[i].trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim()),
        )
        i++
      }
      const thead = `<tr>${head.map((c) => `<th>${inline(c)}</th>`).join('')}</tr>`
      const tbody = rows
        .map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join('')}</tr>`)
        .join('')
      out.push(`<table><thead>${thead}</thead><tbody>${tbody}</tbody></table>`)
      continue
    }

    // 无序/任务列表
    const ul = line.match(/^(\s*)[-*]\s+(.*)$/)
    if (ul) {
      if (listType !== 'ul') {
        closeList()
        out.push('<ul>')
        listType = 'ul'
      }
      const task = ul[2].match(/^\[([ xX])\]\s+(.*)$/)
      if (task) {
        const done = task[1].toLowerCase() === 'x'
        out.push(
          `<li class="task"><input type="checkbox" disabled ${done ? 'checked' : ''}/> ${inline(task[2])}</li>`,
        )
      } else {
        out.push(`<li>${inline(ul[2])}</li>`)
      }
      i++
      continue
    }

    // 有序列表
    const ol = line.match(/^(\s*)\d+[.)]\s+(.*)$/)
    if (ol) {
      if (listType !== 'ol') {
        closeList()
        out.push('<ol>')
        listType = 'ol'
      }
      out.push(`<li>${inline(ol[2])}</li>`)
      i++
      continue
    }

    // 普通段落（连续非空行合并）
    closeList()
    const buf: string[] = [line]
    i++
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^(#{1,6})\s/.test(lines[i]) &&
      !/^```/.test(lines[i].trim()) &&
      !/^&gt;/.test(lines[i]) &&
      !/^(\s*)[-*]\s+/.test(lines[i]) &&
      !/^(\s*)\d+[.)]\s+/.test(lines[i])
    ) {
      buf.push(lines[i])
      i++
    }
    out.push(`<p>${inline(buf.join('\n')).replace(/\n/g, '<br/>')}</p>`)
  }
  closeList()
  return out.join('\n')
}
