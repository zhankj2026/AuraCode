export {}

declare global {
  interface Window {
    auracode: {
      getConfig: () => Promise<{
        host: string
        port: number
        token: string
        root: string
      }>
      restartBackend: () => Promise<unknown>
      getExtensions: (root: string) => Promise<{
        skills: { name: string; description: string; whenToUse?: string; path: string; source: 'builtin' | 'project' | 'user' }[]
        mcp: { name: string; type: string; command?: string; url?: string; enabled: boolean; scope: 'project' | 'user' | 'enterprise' | 'managed' }[]
        hooks: { event: string; matcher?: string; command: string; enabled: boolean; description?: string; priority: number }[]
        plugins: { name: string; description: string; version?: string; source: 'builtin' | 'project' | 'user'; enabled?: boolean }[]
        tasks: { job_id: string; cron: string; prompt: string; recurring: boolean; durable: boolean; status: string; next_fire_at?: number; fire_count: number; label?: string }[]
      }>
      selectDirectory: () => Promise<string | null>
      getWorkspace: () => Promise<string | null>
      setWorkspace: (dir: string | null) => Promise<string | null>
      /** 最近打开的工作区历史（最多 10 条，最近优先） */
      getWorkspaceRecent: () => Promise<string[]>
      readText: (
        root: string,
        rel: string,
      ) => Promise<{ ok: boolean; content?: string; lines?: number; size?: number; error?: string }>
      addMcp: (cfg: {
        root: string
        name: string
        transport: string
        command?: string
        args?: string
        url?: string
      }) => Promise<{ ok: boolean; message: string }>
      /** 自定义模型：读取/写入 ~/.auracode/models.json */
      getCustomModels: () => Promise<{ ok: boolean; models: import('./api/types').CustomModel[]; error?: string }>
      setCustomModels: (models: import('./api/types').CustomModel[]) => Promise<{ ok: boolean; message: string }>
    }
  }
}
