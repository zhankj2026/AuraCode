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
      /** 后端就绪状态：ready=已确认启动成功 */
      getBackendStatus: () => Promise<{
        ready: boolean
        config: { host: string; port: number; token: string; root: string } | null
      }>
      restartBackend: () => Promise<unknown>
      /** 扩展配置读取：engineRoot=引擎根目录（内置技能/插件），workDir=会话工作区（项目级配置） */
      getExtensions: (engineRoot: string, workDir?: string) => Promise<{
        skills: { name: string; description: string; whenToUse?: string; path: string; source: 'builtin' | 'project' | 'user' }[]
        mcp: { name: string; type: string; command?: string; url?: string; enabled: boolean; scope: 'project' | 'user' | 'enterprise' | 'managed' }[]
        hooks: {
          event: string
          matcher?: string
          command: string
          enabled: boolean
          description?: string
          priority: number
          timeout?: number
          onFail?: string
          scope: 'project' | 'user'
          index: number
        }[]
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
      /** 新增/覆盖一个 MCP 服务器配置（scope: project → <workDir>/.mcp.json；user → ~/.auracode/mcp.json） */
      upsertMcp: (cfg: {
        workDir: string
        scope: 'project' | 'user'
        name: string
        transport: string
        command?: string
        args?: string
        url?: string
        env?: string
      }) => Promise<{ ok: boolean; message: string }>
      /** 启停/编辑一个已存在的 MCP 服务器条目 */
      updateMcp: (input: {
        workDir: string
        scope: 'project' | 'user'
        oldName: string
        newName?: string
        enabled?: boolean
        newCfg?: { transport: string; command?: string; args?: string; url?: string; env?: string }
      }) => Promise<{ ok: boolean; message: string }>
      /** 删除一个 MCP 服务器条目 */
      deleteMcp: (workDir: string, scope: 'project' | 'user', name: string) =>
        Promise<{ ok: boolean; message: string }>
      /** 保存某 scope 的完整钩子列表（覆盖写） */
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
      ) => Promise<{ ok: boolean; message: string }>
      /** 插件启停（~/.auracode/plugins_settings.json，新会话生效） */
      setPluginEnabled: (
        name: string,
        source: 'builtin' | 'project' | 'user',
        enabled: boolean,
      ) => Promise<{ ok: boolean; message: string }>
      /** 自定义模型：读取/写入 ~/.auracode/models.json */
      getCustomModels: () => Promise<{ ok: boolean; models: import('./api/types').CustomModel[]; error?: string }>
      setCustomModels: (models: import('./api/types').CustomModel[]) => Promise<{ ok: boolean; message: string }>
    }
  }
}
