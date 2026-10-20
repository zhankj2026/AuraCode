import type { BridgeClient } from './client'

/**
 * 整文件读取：优先走主进程 IPC（读磁盘，完全不做行数截断），
 * 拿不到时退回后端 REST（显式请求 2000 行，是后端 le 上限）。
 *
 * 为什么需要它：
 * 后端 /api/sessions/{id}/files/content 的 max_lines 默认值只有 200。
 * demo6 的 entities.js(505 行)/game.js(488)/ui.js(425)/systems.js(224) 一旦被
 * 截到 200 行就是残缺源码（括号不闭合），编辑器保存会写坏文件、HTML 预览注入
 * 后必然 SyntaxError，最终表现为「预览空白、本地浏览器却正常」。
 */
export interface FullText {
  content: string
  /** 是否仍被截断（REST 兜底且超过 2000 行时为 true） */
  truncated: boolean
  error?: string
}

function isAbsolutePath(p: string): boolean {
  return /^[a-zA-Z]:[\\/]/.test(p) || /^\\\\/.test(p) || p.startsWith('/')
}

export async function readTextFull(
  client: BridgeClient | null,
  sessionId: string | null,
  workDir: string,
  relPath: string,
): Promise<FullText> {
  // 1) IPC 优先：全量读盘
  const ipc = (window as any).auracode?.readText
  if (typeof ipc === 'function' && workDir && isAbsolutePath(workDir)) {
    try {
      const r = await ipc(workDir, relPath)
      if (r?.ok && typeof r.content === 'string') {
        return { content: r.content, truncated: false }
      }
      if (r && !r.ok && r.error) {
        // 落到 REST 再试一次（例如路径含符号链接等），失败信息留到最后
      }
    } catch {
      /* 忽略，走 REST 兜底 */
    }
  }

  // 2) REST 兜底
  if (client && sessionId) {
    try {
      const r = await client.readFile(sessionId, relPath, 2000)
      return { content: r?.content ?? '', truncated: !!r?.truncated }
    } catch (e: any) {
      return { content: '', truncated: false, error: String(e?.message || e) }
    }
  }

  return { content: '', truncated: false, error: `无法读取：${relPath}` }
}
