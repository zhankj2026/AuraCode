import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

/**
 * 从磁盘读取 AuraCode 的真实扩展配置，供渲染进程「扩展 / 任务」面板展示。
 *
 * 数据全部来自 AuraCode 工程自身的配置文件（与 Python 后端一致，但由主进程直接读盘，
 * 不改动任何 Python 代码）：
 *   - 技能   : <root>/skills/<name>/SKILL.md
 *   - MCP    : <root>/.mcp.json (+ ~/.auracode/mcp.json / enterprise-mcp.json / managed-mcp.json)
 *   - 钩子   : <root>/.auracode/hooks.json (+ ~/.auracode/hooks.json)
 *   - 插件   : <root>/plugins/*.py 中的 ToolPlugin 子类 (+ ~/.auracode/plugins_settings.json)
 *   - 任务   : ~/.auracode/scheduled_tasks.json (CronTool 持久化的定时任务)
 */

export interface SkillInfo {
  name: string
  description: string
  whenToUse?: string
  path: string
}

export interface McpServerInfo {
  name: string
  type: string
  command?: string
  url?: string
  enabled: boolean
  scope: 'project' | 'user' | 'enterprise' | 'managed'
}

export interface HookInfo {
  event: string
  matcher?: string
  command: string
  enabled: boolean
  description?: string
  priority: number
}

export interface PluginInfo {
  name: string
  description: string
  version?: string
  source: 'builtin' | 'project' | 'user'
  enabled?: boolean
}

export interface TaskInfo {
  job_id: string
  cron: string
  prompt: string
  recurring: boolean
  durable: boolean
  status: string
  next_fire_at?: number
  fire_count: number
  label?: string
}

export interface ExtensionsData {
  skills: SkillInfo[]
  mcp: McpServerInfo[]
  hooks: HookInfo[]
  plugins: PluginInfo[]
  tasks: TaskInfo[]
}

const EMPTY: ExtensionsData = {
  skills: [],
  mcp: [],
  hooks: [],
  plugins: [],
  tasks: [],
}

function userConfigDir(): string {
  return path.join(os.homedir(), '.auracode')
}

function readJsonSafe(p: string): any | null {
  try {
    if (!fs.existsSync(p)) return null
    return JSON.parse(fs.readFileSync(p, 'utf-8'))
  } catch {
    return null
  }
}

/** 解析 SKILL.md 的 YAML frontmatter（仅取简单 key: value 行） */
function parseFrontmatter(text: string): Record<string, string> {
  const m = text.match(/^---[ \t]*\r?\n([\s\S]*?)\r?\n---/)
  if (!m) return {}
  const out: Record<string, string> = {}
  for (const line of m[1].split(/\r?\n/)) {
    const mm = line.match(/^([A-Za-z_][\w-]*):\s*(.*)$/)
    if (mm) {
      let v = mm[2].trim()
      v = v.replace(/^["']|["']$/g, '')
      out[mm[1]] = v
    }
  }
  return out
}

function readSkills(root: string): SkillInfo[] {
  const dir = path.join(root, 'skills')
  if (!fs.existsSync(dir)) return []
  const out: SkillInfo[] = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue
    const skillMd = path.join(dir, entry.name, 'SKILL.md')
    if (!fs.existsSync(skillMd)) continue
    const fm = parseFrontmatter(fs.readFileSync(skillMd, 'utf-8'))
    out.push({
      name: fm.name || entry.name,
      description: fm.description || '',
      whenToUse: fm.when_to_use || fm.whenToUse,
      path: `skills/${entry.name}/SKILL.md`,
    })
  }
  return out.sort((a, b) => a.name.localeCompare(b.name))
}

function mcpType(cfg: any): string {
  if (typeof cfg?.type === 'string' && cfg.type) return cfg.type
  if (cfg?.command) return 'stdio'
  if (cfg?.url) return 'http'
  return 'unknown'
}

function readMcp(root: string, userDir: string): McpServerInfo[] {
  const files: { p: string; scope: McpServerInfo['scope'] }[] = [
    { p: path.join(root, '.mcp.json'), scope: 'project' },
    { p: path.join(userDir, 'mcp.json'), scope: 'user' },
    { p: path.join(userDir, 'enterprise-mcp.json'), scope: 'enterprise' },
    { p: path.join(userDir, 'managed-mcp.json'), scope: 'managed' },
  ]
  const out: McpServerInfo[] = []
  for (const { p, scope } of files) {
    const data = readJsonSafe(p)
    const servers = data?.mcpServers
    if (!servers || typeof servers !== 'object') continue
    for (const [name, cfg] of Object.entries<any>(servers)) {
      const disabled = cfg?.disabled === true || cfg?.enabled === false
      let command: string | undefined
      if (cfg?.command) {
        command = [cfg.command, ...(cfg.args || [])].join(' ')
      }
      out.push({
        name,
        type: mcpType(cfg),
        command,
        url: cfg?.url,
        enabled: !disabled,
        scope,
      })
    }
  }
  return out
}

function readHooks(root: string, userDir: string): HookInfo[] {
  const files = [path.join(root, '.auracode', 'hooks.json'), path.join(userDir, 'hooks.json')]
  const out: HookInfo[] = []
  for (const p of files) {
    const data = readJsonSafe(p)
    const hooks = data?.hooks
    if (!Array.isArray(hooks)) continue
    for (const h of hooks) {
      out.push({
        event: h.event || '?',
        matcher: h.matcher,
        command: h.command || '',
        enabled: h.enabled !== false,
        description: h.description,
        priority: typeof h.priority === 'number' ? h.priority : 0,
      })
    }
  }
  return out
}

const PLUGIN_FRAMEWORK = new Set([
  '__init__.py',
  'base.py',
  'loader.py',
  'builtin.py',
  'marketplace.py',
  'plugin_installer.py',
  'registry.py',
  'zip_cache.py',
])

function extractPluginModule(text: string): { name: string; description: string; version: string } | null {
  if (!/class\s+\w+Plugin\s*\(\s*ToolPlugin\s*\)/.test(text)) return null
  const get = (key: string): string | undefined => {
    const prop = new RegExp(`def\\s+${key}[\\s\\S]{0,200}?return\\s+["']([^"']+)["']`)
    const pm = text.match(prop)
    if (pm) return pm[1]
    const assign = new RegExp(`${key}\\s*=\\s*["']([^"']+)["']`)
    const am = text.match(assign)
    if (am) return am[1]
    return undefined
  }
  const name = get('name')
  if (!name) return null
  return { name, description: get('description') || '', version: get('version') || '' }
}

function scanPluginDir(dir: string, source: PluginInfo['source'], acc: Map<string, PluginInfo>) {
  if (!fs.existsSync(dir)) return
  for (const f of fs.readdirSync(dir)) {
    if (!f.endsWith('.py') || f.startsWith('_') || PLUGIN_FRAMEWORK.has(f)) continue
    const mod = extractPluginModule(fs.readFileSync(path.join(dir, f), 'utf-8'))
    if (!mod) continue
    if (!acc.has(mod.name)) {
      acc.set(mod.name, { ...mod, source })
    }
  }
}

function readPlugins(root: string, userDir: string): PluginInfo[] {
  const acc = new Map<string, PluginInfo>()
  scanPluginDir(path.join(root, 'plugins'), 'builtin', acc)
  scanPluginDir(path.join(root, '.auracode', 'plugins'), 'project', acc)
  scanPluginDir(path.join(userDir, 'plugins'), 'user', acc)

  const settings = readJsonSafe(path.join(userDir, 'plugins_settings.json'))
  const enabledMap: Record<string, boolean> = settings?.enabled_plugins || {}
  const out = [...acc.values()]
  for (const p of out) {
    const id = `${p.name}@${p.source}`
    if (typeof enabledMap[id] === 'boolean') p.enabled = enabledMap[id]
  }
  return out.sort((a, b) => a.name.localeCompare(b.name))
}

function readTasks(userDir: string): TaskInfo[] {
  const data = readJsonSafe(path.join(userDir, 'scheduled_tasks.json'))
  if (!data || typeof data !== 'object') return []
  const out: TaskInfo[] = []
  for (const [job_id, j] of Object.entries<any>(data)) {
    out.push({
      job_id,
      cron: j.cron || '',
      prompt: j.prompt || '',
      recurring: j.recurring !== false,
      durable: j.durable === true,
      status: j.status || 'active',
      next_fire_at: typeof j.next_fire_at === 'number' ? j.next_fire_at : undefined,
      fire_count: typeof j.fire_count === 'number' ? j.fire_count : 0,
      label: j.label,
    })
  }
  return out.sort((a, b) => (a.next_fire_at || 0) - (b.next_fire_at || 0))
}

export function collectExtensions(root: string): ExtensionsData {
  if (!root || !fs.existsSync(root)) return EMPTY
  const userDir = userConfigDir()
  return {
    skills: readSkills(root),
    mcp: readMcp(root, userDir),
    hooks: readHooks(root, userDir),
    plugins: readPlugins(root, userDir),
    tasks: readTasks(userDir),
  }
}
