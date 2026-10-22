import { contextBridge, ipcRenderer } from 'electron'

/**
 * 只暴露最小、明确的能力给渲染进程：
 *  - 读取后端连接配置（host/port/token），用于调 REST 与 WS；
 *  - 重启后端（如 token 失效时）。
 * 渲染进程自行用 fetch / WebSocket 连 127.0.0.1，不依赖 Node 能力。
 */
contextBridge.exposeInMainWorld('auracode', {
  getConfig: () => ipcRenderer.invoke('bridge:config'),
  restartBackend: () => ipcRenderer.invoke('backend:restart'),
  getExtensions: (root: string) => ipcRenderer.invoke('extensions:list', root),
  selectDirectory: () => ipcRenderer.invoke('dialog:selectDirectory'),
  addMcp: (cfg: { root: string; name: string; transport: string; command?: string; args?: string; url?: string }) =>
    ipcRenderer.invoke('mcp:add', cfg),
  getWorkspace: () => ipcRenderer.invoke('workspace:get'),
  setWorkspace: (dir: string | null) => ipcRenderer.invoke('workspace:set', dir),
  // 最近打开的工作区历史（最多 10 条，最近优先）
  getWorkspaceRecent: () => ipcRenderer.invoke('workspace:recent:get'),
  // 整文件读取（无行数截断）。root=工作区绝对路径, rel=相对路径。
  readText: (root: string, rel: string) => ipcRenderer.invoke('fs:readText', root, rel),
  // 自定义模型：读写 ~/.auracode/models.json
  getCustomModels: () => ipcRenderer.invoke('models:list'),
  setCustomModels: (models: any[]) => ipcRenderer.invoke('models:save', models),
})
