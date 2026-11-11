import { contextBridge, ipcRenderer } from 'electron'

/**
 * 只暴露最小、明确的能力给渲染进程：
 *  - 读取后端连接配置（host/port/token），用于调 REST 与 WS；
 *  - 重启后端（如 token 失效时）。
 * 渲染进程自行用 fetch / WebSocket 连 127.0.0.1，不依赖 Node 能力。
 */
contextBridge.exposeInMainWorld('auracode', {
  getConfig: () => ipcRenderer.invoke('bridge:config'),
  /** 后端就绪状态：ready=已确认启动成功，config=连接信息（未就绪时可能为 null） */
  getBackendStatus: () =>
    ipcRenderer.invoke('backend:status') as Promise<{
      ready: boolean
      config: { host: string; port: number; token: string; root: string } | null
    }>,
  restartBackend: () => ipcRenderer.invoke('backend:restart'),
  /** 拉取后端运行日志缓冲（落盘路径 + 内存缓冲），供「运行日志」面板 catch-up */
  getBackendLogs: () =>
    ipcRenderer.invoke('backend:logs') as Promise<{
      path: string
      logs: Array<{ ts: number; line: string }>
    }>,
  /** 订阅后端日志的实时推送；返回反订阅函数 */
  onBackendLog: (cb: (entry: { ts: number; line: string }) => void) => {
    const listener = (_e: unknown, entry: { ts: number; line: string }) => cb(entry)
    ipcRenderer.on('backend:log', listener)
    return () => ipcRenderer.removeListener('backend:log', listener)
  },
  getExtensions: (engineRoot: string, workDir?: string) =>
    ipcRenderer.invoke('extensions:list', engineRoot, workDir),
  selectDirectory: () => ipcRenderer.invoke('dialog:selectDirectory'),
  /** 新增/覆盖一个 MCP 服务器（scope: project → <workDir>/.mcp.json；user → ~/.auracode/mcp.json） */
  upsertMcp: (cfg: {
    workDir: string
    scope: 'project' | 'user'
    name: string
    transport: string
    command?: string
    args?: string
    url?: string
    env?: string
  }) => ipcRenderer.invoke('mcp:upsert', cfg),
  /** 启停/编辑一个已存在的 MCP 服务器条目 */
  updateMcp: (input: {
    workDir: string
    scope: 'project' | 'user'
    oldName: string
    newName?: string
    enabled?: boolean
    newCfg?: { transport: string; command?: string; args?: string; url?: string; env?: string }
  }) => ipcRenderer.invoke('mcp:update', input),
  /** 删除一个 MCP 服务器条目 */
  deleteMcp: (workDir: string, scope: 'project' | 'user', name: string) =>
    ipcRenderer.invoke('mcp:delete', workDir, scope, name),
  /** 保存某 scope 的完整钩子列表（覆盖写，字段与引擎 HookConfigEntry 对齐） */
  saveHooks: (
    workDir: string,
    scope: 'project' | 'user',
    hooks: Array<{
      event: string
      matcher?: string
      command: string
      enabled?: boolean
      description?: string
      priority?: number
      timeout?: number
      onFail?: string
    }>,
  ) => ipcRenderer.invoke('hooks:save', workDir, scope, hooks),
  /** 插件启停（写 ~/.auracode/plugins_settings.json，新会话生效） */
  setPluginEnabled: (name: string, source: 'builtin' | 'project' | 'user', enabled: boolean) =>
    ipcRenderer.invoke('plugin:setEnabled', name, source, enabled),
  getWorkspace: () => ipcRenderer.invoke('workspace:get'),
  setWorkspace: (dir: string | null) => ipcRenderer.invoke('workspace:set', dir),
  // 最近打开的工作区历史（最多 10 条，最近优先）
  getWorkspaceRecent: () => ipcRenderer.invoke('workspace:recent:get'),
  // 整文件读取（无行数截断）。root=工作区绝对路径, rel=相对路径。
  readText: (root: string, rel: string) => ipcRenderer.invoke('fs:readText', root, rel),
  // 图片二进制读取 → data URL（预览用）
  readDataUrl: (root: string, rel: string) => ipcRenderer.invoke('fs:readDataUrl', root, rel),
  // Office 文档（docx/pptx）→ HTML 预览（内置 Python 纯 stdlib 转换）
  officePreview: (root: string, rel: string) => ipcRenderer.invoke('fs:officePreview', root, rel),
  // 自定义模型：读写 ~/.auracode/models.json
  getCustomModels: () => ipcRenderer.invoke('models:list'),
  setCustomModels: (models: any[]) => ipcRenderer.invoke('models:save', models),
})
