import { useEffect, useMemo, useState } from 'react'
import { actions, useStore } from '../state/store'
import { readTextFull } from '../api/fsread'

/**
 * HTML 预览：iframe srcdoc + sandbox 渲染。
 *
 * 设计要点（以及踩过的坑）：
 * 1. demo6 是 index.html + css/style.css + js/*.js 的纯静态结构，没有服务器，
 *    所以必须把相对引用的 <link>/<script> 内联进来才能跑。
 * 2. 内联必须拿「整文件」。后端 /files/content 默认 max_lines=200，
 *    entities.js(505 行) 被截断后括号不闭合 → SyntaxError → 整个游戏脚本崩掉 → 白屏。
 *    现在统一走 readTextFull（主进程全量读盘）。
 * 3. 不能用 src.replace(tag, code) 直接把代码塞进模板串，因为替换串里的
 *    `$&`、`` $` ``、`$'`、`$1` 会被 String.replace 当成占位符吃掉，
 *    实测会把某些 JS 片段改坏。这里一律用 () => 形式的函数替换器。
 * 4. 白屏最难的是「看不出为什么」。所以在 srcdoc 头部注入一小段错误采集脚本，
 *    任何运行时/语法错误都会在预览区底部弹一条红色浮层，直接看到文件名+行号+信息。
 * 5. sandbox 不给 allow-same-origin：iframe 处于不透明源，拿不到宿主文档。
 *    项目里若有 localStorage 之类的访问，需自行 try/catch（demo6 的 utils.storage 已包）。
 */
export function HtmlPreview({ path }: { path: string }) {
  const client = useStore((s) => s.client)
  const activeId = useStore((s) => s.activeSessionId)
  const sessions = useStore((s) => s.sessions)
  const file = useStore((s) => s.openFiles.find((f) => f.path === path))
  const [html, setHtml] = useState('')
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [stat, setStat] = useState({ css: 0, js: 0, failed: [] as string[] })

  // 当前会话的工作区绝对路径，用于主进程全量读盘
  const workDir = useMemo(() => {
    const s = sessions.find((x) => x.session_id === activeId)
    return (s?.work_dir || '').trim()
  }, [sessions, activeId])

  // index.html 所在目录（相对工作区），用于拼依赖路径
  const dir = useMemo(() => {
    const i = path.lastIndexOf('/')
    return i > 0 ? path.slice(0, i) : ''
  }, [path])

  useEffect(() => {
    let cancelled = false

    async function build() {
      if (!file) return
      setStatus('loading')
      setStat({ css: 0, js: 0, failed: [] })

      let src = file.content
      const failed: string[] = []
      let cssCount = 0
      let jsCount = 0

      const resolveRel = (raw: string) => {
        const clean = raw.split('?')[0].split('#')[0]
        return dir ? `${dir}/${clean}` : clean
      }
      const isRemote = (u: string) =>
        /^(https?:)?\/\//i.test(u) || /^data:/i.test(u) || /^blob:/i.test(u)

      // ── 内联样式表 ───────────────────────────────────────────────
      const linkRe = /<link\b[^>]*>/gi
      for (const m of [...src.matchAll(linkRe)]) {
        const tag = m[0]
        const hrefM = tag.match(/\bhref\s*=\s*["']([^"']+)["']/i)
        if (!hrefM || isRemote(hrefM[1])) continue
        const rel = resolveRel(hrefM[1])
        const r = await readTextFull(client, activeId, workDir, rel)
        if (r.content) {
          const safe = r.content
          src = src.replace(linkRe, (all) => (all === tag ? `<style>\n${safe}\n</style>` : all))
          cssCount++
        } else {
          failed.push(rel)
        }
      }

      // ── 内联脚本 ─────────────────────────────────────────────────
      // 兼容 <script src="x"></script>、带 defer/async、带属性换行等情况
      const scriptRe = /<script\b([^>]*)\bsrc\s*=\s*["']([^"']+)["']([^>]*)>\s*<\/script>/gi
      for (const m of [...src.matchAll(scriptRe)]) {
        const tag = m[0]
        const attrs = `${m[1]} ${m[3]}`
        const s = m[2]
        if (isRemote(s)) continue
        const rel = resolveRel(s)
        const r = await readTextFull(client, activeId, workDir, rel)
        if (r.content) {
          // 防止脚本内容里出现 </script> 提前闭合
          const js = r.content.replace(/<\/script>/gi, '<\\/script>')
          const isModule = /\btype\s*=\s*["']module["']/i.test(attrs)
          if (isModule) {
            // module 里常见相对 import，内联后会失基，直接保留原标签并记录
            failed.push(`${rel} (module)`);
            continue
          }
          src = src.replace(scriptRe, (all) => (all === tag ? `<script>\n${js}\n</script>` : all))
          jsCount++
        } else {
          failed.push(rel)
        }
      }

      src = injectErrorProbe(src)

      if (cancelled) return
      setHtml(src)
      setStat({ css: cssCount, js: jsCount, failed })
      setStatus(failed.length ? 'error' : 'ready')
    }

    build()
    return () => {
      cancelled = true
    }
    // file.content 变化（保存/编辑）时重建预览
  }, [client, activeId, path, workDir, file?.content])

  if (!file) return <div className="overlay">文件不存在</div>

  return (
    <div className="preview-wrap">
      <div className="pbar">
        <span className="phint">
          👁 HTML 预览
          {status === 'loading' && ' · 组装中…'}
          {status !== 'loading' && ` · 内联 ${stat.css} CSS / ${stat.js} JS`}
          {stat.failed.length > 0 && ` · ${stat.failed.length} 项失败`}
        </span>
        <span className="sp" />
        <button
          className="save"
          onClick={() => actions.setToast('预览已随文件内容自动刷新', 'info')}
        >
          刷新
        </button>
      </div>
      {stat.failed.length > 0 && (
        <div className="pfail">
          未能内联：{stat.failed.join('、')}
          <span className="pfail-tip">（相对路径需在工作区内；module 脚本会保留原引用）</span>
        </div>
      )}
      <iframe
        title="html-preview"
        className="pframe"
        sandbox="allow-scripts allow-modals allow-forms"
        srcDoc={html}
      />
    </div>
  )
}

/**
 * 在 <head> 内注入错误采集探针：把运行时/语法错误显示成底部红色浮层。
 * 没有它，白屏就真的只是一片白，无从判断是哪个文件出的问题。
 */
function injectErrorProbe(src: string): string {
  const probe = `<script>
(function(){
  var shown = 0;
  function report(title, detail){
    try {
      shown++;
      var box = document.getElementById('__aura_err');
      if (!box) {
        box = document.createElement('div');
        box.id = '__aura_err';
        box.setAttribute('style', [
          'position:fixed','left:0','right:0','bottom:0','max-height:45%','overflow:auto',
          'background:rgba(120,20,20,.94)','color:#ffdede','font:12px/1.5 ui-monospace,Consolas,monospace',
          'padding:8px 10px','z-index:2147483647','border-top:1px solid #ff6b6b','white-space:pre-wrap'
        ].join(';'));
        (document.body || document.documentElement).appendChild(box);
      }
      var line = document.createElement('div');
      line.textContent = '✕ ' + title + (detail ? ' — ' + detail : '');
      box.appendChild(line);
    } catch(e) {}
  }
  window.addEventListener('error', function(e){
    var t = e.target;
    if (t && t !== window && (t.src || t.href)) {
      report('资源加载失败', (t.src || t.href));
      return;
    }
    report(e.message || '脚本错误', (e.filename || 'inline') + ':' + (e.lineno || 0) + ':' + (e.colno || 0));
  }, true);
  window.addEventListener('unhandledrejection', function(e){
    var r = e.reason;
    report('未捕获的 Promise 异常', (r && (r.message || r)) + '');
  });
  window.addEventListener('load', function(){
    if (shown === 0) { try { console.log('[auracode] 预览加载完成，无错误'); } catch(e){} }
  });
})();
</script>`

  // 放在 <head> 最前面，保证早于业务脚本注册监听
  if (/<head[^>]*>/i.test(src)) return src.replace(/<head[^>]*>/i, (m) => `${m}\n${probe}`)
  if (/<html[^>]*>/i.test(src)) return src.replace(/<html[^>]*>/i, (m) => `${m}\n${probe}`)
  return probe + src
}
