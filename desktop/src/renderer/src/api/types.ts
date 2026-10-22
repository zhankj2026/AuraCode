export interface BridgeConfig {
  host: string
  port: number
  token: string
  root: string
}

export type SessionState =
  | 'idle'
  | 'running'
  | 'requires_action'
  | 'completed'
  | 'failed'

export interface SessionInfo {
  session_id: string
  state: SessionState
  work_dir: string
  model: string
  created_at: number
  event_count: number
  last_activity: number
  title: string
  current_activity?: { type: string; summary: string } | null
  round_count: number
}

export interface BridgeEvent {
  event_id: string
  type: string
  session_id: string
  data: any
  timestamp: number
}

export interface PermissionReq {
  request_id: string
  tool_name: string
  tool_input: Record<string, any>
  description: string
}

export interface FileNode {
  name: string
  path: string
  type: 'file' | 'dir' | 'image' | 'binary'
  children?: FileNode[]
}

export interface FileEntry {
  name: string
  type: 'dir' | 'file' | 'unknown'
  size: number
  modified: number
}

/** GET /api/sessions/{id}/files 的返回 */
export interface FileListing {
  path: string
  entries: FileEntry[]
}

/** GET /api/sessions/{id}/files/content 的返回 */
export interface FileContent {
  path: string
  content: string
  lines: number
  truncated: boolean
  ext: string
  size: number
}

/** 一次文件改动（由后端 tool_execute 事件解析得到，真实数据） */
export interface FileChange {
  path: string
  kind: 'write' | 'replace'
  oldText?: string
  newText?: string
  content?: string
  ts: number
}

export type PermissionMode = '普通' | '自动' | '计划' | '绕过'
export type Activity = 'chat' | 'files' | 'ext' | 'audit' | 'tasks' | 'models'
export type InspectorTab = '改动' | '上下文' | '用量'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  ts: number
  streaming?: boolean
}

export interface OpenFile {
  path: string
  dirty: boolean
  content: string
}

/** 真实扩展配置（由主进程从磁盘读取 AuraCode 工程配置得到） */
export interface SkillInfo {
  name: string
  description: string
  whenToUse?: string
  path: string
  /** 来源：工程内置 skills/ | 项目级 .auracode/skills | 用户级 ~/.auracode/skills */
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

// ── SkillHub 技能商店 ─────────────────────────────────────────
export interface SkillhubItem {
  slug: string
  publicSlug: string
  name: string
  description: string
  version: string
  source: string
  installed?: boolean
  namespace_handle?: string
}
export interface SkillhubSearchResult {
  query: string
  results: SkillhubItem[]
  total: number
}
export interface SkillhubInstallResult {
  success: boolean
  slug: string
  installed_name: string
  version: string
  target_dir: string
  note: string
}

// ── LLM 配置（前端可编辑并持久化到引擎 config.yaml）──────────────
export interface LlmConfig {
  provider: string
  model: string
  base_url: string
  has_api_key: boolean
  default_model: string
}
/** 写入时只发非空字段；api_key 为空串表示清空（前端仅在有输入时发送） */
export interface LlmConfigInput {
  provider?: string
  model?: string
  base_url?: string
  api_key?: string
}
export interface ModelCatalogItem {
  id: string
  provider: string
  note: string
}

/** 引擎内置命令（GET /api/commands 返回），供前端 # 命令自动补全 */
export interface CommandInfo {
  name: string
  description: string
  category: string
  args_help?: string
}

/** 自定义模型：用户在「模型」面板里添加的大模型接入点，落盘 ~/.auracode/models.json */
export interface CustomModel {
  id: string
  name: string
  /** 供应商标识（openai / zhipu / deepseek / moonshot / qwen / siliconflow / volcano / custom …），仅用于展示与预设端点 */
  provider: string
  /** 接口地址（完整 chat/completions 端点） */
  base_url: string
  api_key: string
  /** 模型名称（如 gpt-4o / glm-4.6） */
  model: string
}
