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
        skills: { name: string; description: string; whenToUse?: string; path: string }[]
        mcp: { name: string; type: string; command?: string; url?: string; enabled: boolean; scope: 'project' | 'user' | 'enterprise' | 'managed' }[]
        hooks: { event: string; matcher?: string; command: string; enabled: boolean; description?: string; priority: number }[]
        plugins: { name: string; description: string; version?: string; source: 'builtin' | 'project' | 'user'; enabled?: boolean }[]
        tasks: { job_id: string; cron: string; prompt: string; recurring: boolean; durable: boolean; status: string; next_fire_at?: number; fire_count: number; label?: string }[]
      }>
      selectDirectory: () => Promise<string | null>
      getWorkspace: () => Promise<string | null>
      setWorkspace: (dir: string | null) => Promise<string | null>
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
    }
  }
}
