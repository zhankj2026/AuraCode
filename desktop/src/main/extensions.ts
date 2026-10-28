import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

/**
 * 从磁盘读取/写入 AuraCode 的真实扩展配置，供渲染进程「扩展 / 任务」面板使用。
 *
 * 数据全部来自 AuraCode 工程自身的配置文件（与 Python 后端一致，但由主进程直接读盘，
 * 不改动任何 Python 代码）：
 *   - 技能   : <engineRoot>/skills/<name>/SKILL.md + <workDir>/.auracode/skills + ~/.auracode/skills
 *   - MCP    : <workDir>/.mcp.json (+ ~/.auracode/mcp.json / enterprise-mcp.json / managed-mcp.json)
 *   - 钩子   : <workDir>/.auracode/hooks.json (+ ~/.auracode/hooks.json)
 *   - 插件   : <engineRoot>/plugins/*.py 中的 ToolPlugin 子类 (+ <workDir>/.auracode/plugins + ~/.auracode/plugins)
 *   - 任务   : ~/.auracode/scheduled_tasks.json (CronTool 持久化的定时任务)
 *
 * 双根分离（关键）：engineRoot = 引擎源码目录（内置技能/插件）；workDir = 当前会话的
 * 工作区（项目级 .mcp.json / .auracode/hooks.json 等应该跟随它，而不是引擎根目录——
 * 此前全部用引擎根目录读项目级配置，导致「在工作区里配置」永远不生效）。
 */

export interface SkillInfo {
  name: string
  description: string
  whenToUse?: string
  path: string
  /** 来源：工程内置 skills/ | 项目级 .auracode/skills | 用户级 ~/.auracode/skills（SkillHub 安装目录） */
  source: 'builtin' | 'project' | 'user'
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
  /** 命令超时（秒） */
  timeout?: number
  /** 失败策略: ignore / warn / block */
  onFail?: string
  /** 所在配置文件（区分项目级/用户级，编辑时写回原文件） */
  scope: 'project' | 'user'
  /** 在所在文件中的条目索引（列表操作时定位用） */
  index: number
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

/** 读 JSON，文件不存在时返回空对象（写入前的读取）。解析失败抛异常由调用方处理。 */
function readJsonOrEmpty(p: string): any {
  if (!fs.existsSync(p)) return {}
  return JSON.parse(fs.readFileSync(p, 'utf-8'))
}

function writeJsonSafe(p: string, data: any): void {
  fs.mkdirSync(path.dirname(p), { recursive: true })
  fs.writeFileSync(p, JSON.stringify(data, null, 2), 'utf-8')
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

type SkillSource = SkillInfo['source']

/**
 * 递归扫描一个技能目录，把发现的技能写入 acc（按目录名去重，先到先得）。
 *
 * 支持两种布局（与引擎 skills/loader.py 一致）：
 *   1. <dir>/<skill>/SKILL.md                      —— 原生一层布局
 *   2. <dir>/@namespace/<skill>/SKILL.md           —— SkillHub 安装的两层布局
 *      （skillhub CLI 默认把技能装进 @namespace 命名空间目录，不展开会被漏掉）
 *
 * @param baseDir  真实磁盘目录
 * @param relBase  用于 path 字段的可读相对标识（如 'skills'、'.auracode/skills'、'~/.auracode/skills'）
 * @param source   来源标记
 * @param acc      去重累加器
 */
function scanSkillDir(
  baseDir: string,
  relBase: string,
  source: SkillSource,
  acc: Map<string, SkillInfo>,
) {
  if (!fs.existsSync(baseDir)) return
  let entries: fs.Dirent[]
  try {
    entries = fs.readdirSync(baseDir, { withFileTypes: true })
  } catch {
    return
  }
  for (const entry of entries) {
    if (!entry.isDirectory() || entry.name.startsWith('__')) continue
    const skillPath = path.join(baseDir, entry.name)
    const skillMd = path.join(skillPath, 'SKILL.md')
    if (fs.existsSync(skillMd)) {
      // 一层布局：该目录本身就是技能
      const key = entry.name
      if (acc.has(key)) continue // 去重：内置优先、项目次之、用户最后
      const fm = parseFrontmatter(fs.readFileSync(skillMd, 'utf-8'))
      acc.set(key, {
        name: fm.name || entry.name,
        description: fm.description || '',
        whenToUse: fm.when_to_use || fm.whenToUse,
        path: path.join(relBase, entry.name, 'SKILL.md'),
        source,
      })
    } else if (entry.name.startsWith('@') && fs.statSync(skillPath).isDirectory()) {
      // 两层布局：@namespace 下钻一层
      scanSkillDir(skillPath, path.join(relBase, entry.name), source, acc)
    }
  }
}

function readSkills(engineRoot: string, workDir: string): SkillInfo[] {
  const acc = new Map<string, SkillInfo>()
  // 1. 引擎内置技能：<engineRoot>/skills（优先级最高）
  scanSkillDir(path.join(engineRoot, 'skills'), 'skills', 'builtin', acc)
  // 2. 项目级自定义技能：<workDir>/.auracode/skills（跟随当前工作区）
  scanSkillDir(
    path.join(workDir, '.auracode', 'skills'),
    path.join('.auracode', 'skills'),
    'project',
    acc,
  )
  // 3. 用户级技能：~/.auracode/skills（SkillHub 默认安装目录）
  scanSkillDir(
    path.join(userConfigDir(), 'skills'),
    path.join('.auracode', 'skills'),
    'user',
    acc,
  )
  return [...acc.values()].sort((a, b) => a.name.localeCompare(b.name))
}

function mcpType(cfg: any): string {
  if (typeof cfg?.type === 'string' && cfg.type) return cfg.type
  if (cfg?.command) return 'stdio'
  if (cfg?.url) return 'http'
  return 'unknown'
}

function readMcp(workDir: string): McpServerInfo[] {
  const files: { p: string; scope: McpServerInfo['scope'] }[] = [
    // 项目级跟随会话工作区（与引擎 MCPConfigManager(project_dir=work_dir) 一致）
    { p: path.join(workDir, '.mcp.json'), scope: 'project' },
    { p: path.join(userConfigDir(), 'mcp.json'), scope: 'user' },
    { p: path.join(userConfigDir(), 'enterprise-mcp.json'), scope: 'enterprise' },
    { p: path.join(userConfigDir(), 'managed-mcp.json'), scope: 'managed' },
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

function readHooks(workDir: string): HookInfo[] {
  const files: { p: string; scope: HookInfo['scope'] }[] = [
    // 项目级跟随会话工作区（引擎 HookConfigLoader(project_root=work_dir) 一致）
    { p: path.join(workDir, '.auracode', 'hooks.json'), scope: 'project' },
    { p: path.join(userConfigDir(), 'hooks.json'), scope: 'user' },
  ]
  const out: HookInfo[] = []
  for (const { p, scope } of files) {
    const data = readJsonSafe(p)
    const hooks = data?.hooks
    if (!Array.isArray(hooks)) continue
    hooks.forEach((h: any, index: number) => {
      out.push({
        event: h.event || '?',
        matcher: h.matcher,
        command: h.command || '',
        enabled: h.enabled !== false,
        description: h.description,
        priority: typeof h.priority === 'number' ? h.priority : 0,
        timeout: typeof h.timeout === 'number' ? h.timeout : undefined,
        onFail: h.on_fail,
        scope,
        index,
      })
    })
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

function readPlugins(engineRoot: string, workDir: string): PluginInfo[] {
  const acc = new Map<string, PluginInfo>()
  scanPluginDir(path.join(engineRoot, 'plugins'), 'builtin', acc)
  scanPluginDir(path.join(workDir, '.auracode', 'plugins'), 'project', acc)
  scanPluginDir(path.join(userConfigDir(), 'plugins'), 'user', acc)

  const settings = readJsonSafe(path.join(userConfigDir(), 'plugins_settings.json'))
  const enabledMap: Record<string, boolean> = settings?.enabled_plugins || {}
  const out = [...acc.values()]
  for (const p of out) {
    const id = `${p.name}@${p.source}`
    if (typeof enabledMap[id] === 'boolean') p.enabled = enabledMap[id]
  }
  return out.sort((a, b) => a.name.localeCompare(b.name))
}

function readTasks(): TaskInfo[] {
  const data = readJsonSafe(path.join(userConfigDir(), 'scheduled_tasks.json'))
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

export function collectExtensions(engineRoot: string, workDir?: string): ExtensionsData {
  if (!engineRoot || !fs.existsSync(engineRoot)) return EMPTY
  // workDir 缺省时回退引擎根目录（与旧版行为兼容；正常路径前端总会传当前工作区）
  const wd = workDir && fs.existsSync(workDir) ? workDir : engineRoot
  return {
    skills: readSkills(engineRoot, wd),
    mcp: readMcp(wd),
    hooks: readHooks(wd),
    plugins: readPlugins(engineRoot, wd),
    tasks: readTasks(),
  }
}

// ═══════════════════ 写盘操作（渲染进程配置维护） ═══════════════════

export interface McpUpsertInput {
  workDir: string
  /** 作用域：project → <workDir>/.mcp.json；user → ~/.auracode/mcp.json */
  scope: 'project' | 'user'
  name: string
  transport: string
  command?: string
  args?: string
  url?: string
  env?: string
}

export interface McpUpdateInput {
  workDir: string
  scope: 'project' | 'user'
  oldName: string
  /** 新名称（编辑弹窗改名时用；缺省 = oldName） */
  newName?: string
  /** enabled 缺省 = 不改；否则写入/清除 disabled 标记 */
  enabled?: boolean
  /** 传 newCfg 则整体替换该服务器配置（编辑弹窗保存） */
  newCfg?: { transport: string; command?: string; args?: string; url?: string; env?: string }
}

function mcpScopePath(workDir: string, scope: 'project' | 'user'): string {
  return scope === 'user'
    ? path.join(userConfigDir(), 'mcp.json')
    : path.join(workDir, '.mcp.json')
}

function buildMcpEntry(cfg: {
  transport: string
  command?: string
  args?: string
  url?: string
  env?: string
}): Record<string, any> | { error: string } {
  const entry: Record<string, any> = {}
  if (cfg.transport === 'http' || cfg.transport === 'sse' || cfg.transport === 'ws') {
    entry.type = cfg.transport
    entry.url = (cfg.url || '').trim()
    if (!entry.url) return { error: '远程模式需要 URL' }
  } else {
    entry.type = 'stdio'
    const cmd = (cfg.command || '').trim()
    const args = (cfg.args || '')
      .split(/\s+/)
      .map((s) => s.trim())
      .filter(Boolean)
    if (!cmd) return { error: 'stdio 模式需要启动命令' }
    entry.command = cmd
    if (args.length) entry.args = args
  }
  // 可选环境变量（KEY=VALUE 行格式）
  const env: Record<string, string> = {}
  for (const line of (cfg.env || '').split(/\r?\n/)) {
    const t = line.trim()
    if (!t) continue
    const eq = t.indexOf('=')
    if (eq > 0) env[t.slice(0, eq).trim()] = t.slice(eq + 1).trim()
  }
  if (Object.keys(env).length) entry.env = env
  return entry
}

/** 新增 / 覆盖写入一个 MCP 服务器配置 */
export function upsertMcpServer(input: McpUpsertInput): { ok: boolean; message: string } {
  try {
    if (!input.name?.trim()) return { ok: false, message: '缺少服务器名称' }
    const file = mcpScopePath(input.workDir, input.scope)
    const data = readJsonOrEmpty(file)
    if (typeof data !== 'object' || data === null) return { ok: false, message: '配置文件格式错误（不是 JSON 对象）' }
    if (typeof data.mcpServers !== 'object' || data.mcpServers === null) data.mcpServers = {}

    const built = buildMcpEntry(input)
    if ('error' in built) return { ok: false, message: built.error }

    data.mcpServers[input.name.trim()] = built
    writeJsonSafe(file, data)
    return { ok: true, message: `已写入 ${file}` }
  } catch (err) {
    return { ok: false, message: '写入失败：' + (err instanceof Error ? err.message : String(err)) }
  }
}

/** 启停 / 编辑一个已存在的 MCP 服务器条目 */
export function updateMcpServer(input: McpUpdateInput): { ok: boolean; message: string } {
  try {
    const file = mcpScopePath(input.workDir, input.scope)
    if (!fs.existsSync(file)) return { ok: false, message: `配置文件不存在：${file}` }
    const data = readJsonOrEmpty(file)
    const servers = data?.mcpServers
    if (!servers || typeof servers !== 'object' || !(input.oldName in servers)) {
      return { ok: false, message: `未找到服务器「${input.oldName}」` }
    }

    const targetName = input.newName?.trim() || input.oldName

    if (input.newCfg) {
      // 整体替换配置；enabled 显式给定则按给定，否则保留原启停状态
      const built = buildMcpEntry(input.newCfg)
      if ('error' in built) return { ok: false, message: built.error }
      const wasDisabled = servers[input.oldName].disabled === true
      if (input.enabled === false || (input.enabled === undefined && wasDisabled)) {
        built.disabled = true
      }
      if (targetName !== input.oldName) delete servers[input.oldName]
      servers[targetName] = built
    } else if (input.enabled !== undefined) {
      if (input.enabled) {
        delete servers[input.oldName].disabled
        delete servers[input.oldName].enabled
      } else {
        servers[input.oldName].disabled = true
      }
    } else {
      return { ok: false, message: '没有要执行的操作' }
    }
    writeJsonSafe(file, data)
    return { ok: true, message: `已更新 ${file}` }
  } catch (err) {
    return { ok: false, message: '更新失败：' + (err instanceof Error ? err.message : String(err)) }
  }
}

/** 删除一个 MCP 服务器条目 */
export function deleteMcpServer(
  workDir: string,
  scope: 'project' | 'user',
  name: string,
): { ok: boolean; message: string } {
  try {
    const file = mcpScopePath(workDir, scope)
    if (!fs.existsSync(file)) return { ok: false, message: `配置文件不存在：${file}` }
    const data = readJsonOrEmpty(file)
    const servers = data?.mcpServers
    if (!servers || typeof servers !== 'object' || !(name in servers)) {
      return { ok: false, message: `未找到服务器「${name}」` }
    }
    delete servers[name]
    writeJsonSafe(file, data)
    return { ok: true, message: `已删除「${name}」` }
  } catch (err) {
    return { ok: false, message: '删除失败：' + (err instanceof Error ? err.message : String(err)) }
  }
}

// ── 钩子：整表写入（列表编辑模式：读 → 改 → 全量落盘） ──────────────

export interface HookEntryInput {
  event: string
  matcher?: string
  command: string
  enabled?: boolean
  description?: string
  priority?: number
  timeout?: number
  onFail?: string
}

/**
 * 保存某个 scope 的完整钩子列表（覆盖写）。
 * 字段名与引擎 hooks/config_loader.py 的 HookConfigEntry 完全对齐。
 */
export function saveHooks(
  workDir: string,
  scope: 'project' | 'user',
  hooks: HookEntryInput[],
): { ok: boolean; message: string } {
  try {
    if (!Array.isArray(hooks)) return { ok: false, message: '参数不是数组' }
    const file =
      scope === 'user'
        ? path.join(userConfigDir(), 'hooks.json')
        : path.join(workDir, '.auracode', 'hooks.json')

    const list = hooks.map((h) => {
      const entry: Record<string, any> = {
        event: h.event,
        command: h.command,
        priority: typeof h.priority === 'number' ? h.priority : 0,
        enabled: h.enabled !== false,
      }
      if (h.matcher?.trim()) entry.matcher = h.matcher.trim()
      if (h.description?.trim()) entry.description = h.description.trim()
      if (typeof h.timeout === 'number' && h.timeout > 0) entry.timeout = h.timeout
      if (h.onFail && ['ignore', 'warn', 'block'].includes(h.onFail)) entry.on_fail = h.onFail
      return entry
    })

    writeJsonSafe(file, { hooks: list })
    return { ok: true, message: `已保存 ${list.length} 条钩子到 ${file}` }
  } catch (err) {
    return { ok: false, message: '保存失败：' + (err instanceof Error ? err.message : String(err)) }
  }
}

// ── 插件：启停状态（与 plugins/builtin.py set_plugin_enabled 同一存储） ──

export function setPluginEnabledState(
  name: string,
  source: 'builtin' | 'project' | 'user',
  enabled: boolean,
): { ok: boolean; message: string } {
  try {
    if (!name) return { ok: false, message: '缺少插件名' }
    const file = path.join(userConfigDir(), 'plugins_settings.json')
    const data = readJsonOrEmpty(file)
    if (typeof data !== 'object' || data === null) return { ok: false, message: '设置文件格式错误' }
    if (typeof data.enabled_plugins !== 'object' || data.enabled_plugins === null) {
      data.enabled_plugins = {}
    }
    const id = `${name}@${source}`
    if (enabled) {
      delete data.enabled_plugins[id] // 回到默认启用
    } else {
      data.enabled_plugins[id] = false
    }
    writeJsonSafe(file, data)
    return {
      ok: true,
      message: `${enabled ? '已启用' : '已禁用'} ${id}（新会话生效）`,
    }
  } catch (err) {
    return { ok: false, message: '保存失败：' + (err instanceof Error ? err.message : String(err)) }
  }
}
