import { useSyncExternalStore } from 'react'
import { BridgeClient } from '../api/client'
import type {
  BridgeConfig,
  SessionInfo,
  BridgeEvent,
  PermissionReq,
  Activity,
  InspectorTab,
  ChatMessage,
  OpenFile,
  ExtensionsData,
  CommandInfo,
} from '../api/types'

export interface AppState {
  config: BridgeConfig | null
  client: BridgeClient | null
  connected: boolean
  sessions: SessionInfo[]
  activeSessionId: string | null
  messages: Record<string, ChatMessage[]>
  events: BridgeEvent[]
  permission: PermissionReq | null
  permissionSession: string | null
  activity: Activity
  extTab: string
  inspector: InspectorTab
  openFiles: OpenFile[]
  activeTab: string
  mode: string
  settingsOpen: boolean
  mcpOpen: boolean
  skillhubOpen: boolean
  log: string[]
  workspace: string
  tempSession: boolean
  extensions: ExtensionsData | null
  /** 引擎内置命令清单（GET /api/commands），供 # 命令自动补全 */
  commands: CommandInfo[]
  /** 顶部轻提示：用于把后台操作（如打开工作区）的真实成败反馈给用户，而不是静默吞掉 */
  toast: { msg: string; kind: 'error' | 'info' | 'ok' } | null
}

const initial: AppState = {
  config: null,
  client: null,
  connected: false,
  sessions: [],
  activeSessionId: null,
  messages: {},
  events: [],
  permission: null,
  permissionSession: null,
  activity: 'chat',
  extTab: 'MCP',
  inspector: '改动',
  openFiles: [],
  activeTab: 'chat',
  mode: '普通',
  settingsOpen: false,
  mcpOpen: false,
  skillhubOpen: false,
  log: [],
  workspace: 'auracode-src',
  tempSession: false,
  extensions: null,
  commands: [],
  toast: null,
}

let state: AppState = initial
const listeners = new Set<() => void>()
const seen = new Set<string>()
function emit() {
  listeners.forEach((l) => l())
}
export function getState() {
  return state
}
export function subscribe(l: () => void) {
  listeners.add(l)
  return () => {
    listeners.delete(l)
  }
}
export function setState(patch: Partial<AppState>) {
  state = { ...state, ...patch }
  emit()
}

/** 用选择器订阅状态。选择器应返回稳定引用或原始值，避免无谓重渲染。 */
export function useStore<T>(selector: (s: AppState) => T): T {
  return useSyncExternalStore(
    subscribe,
    () => selector(state),
    () => selector(initial),
  )
}

let msgSeq = 0
function nextId() {
  return `m${Date.now()}_${msgSeq++}`
}

// ── 业务动作 ────────────────────────────────────────────────────────
export const actions = {
  setClient(client: BridgeClient) {
    setState({ client })
  },
  setConfig(config: BridgeConfig) {
    setState({ config })
  },
  setConnected(v: boolean) {
    setState({ connected: v })
  },
  setSessions(sessions: SessionInfo[]) {
    setState({ sessions })
  },
  /** 会话模型变更后同步本地状态（热切换成功 / model_changed 事件）。
   *  此前 model 只在 listSessions 快照里，热切换后下拉框仍显示旧值，
   *  用户再次切换极易触发后端 409「模型未变化」。 */
  updateSessionModel(sessionId: string, model: string) {
    if (!sessionId || !model) return
    if (!state.sessions.some((s) => s.session_id === sessionId)) return
    setState({
      sessions: state.sessions.map((s) =>
        s.session_id === sessionId ? { ...s, model } : s,
      ),
    })
  },
  selectSession(id: string | null) {
    const sess = id ? state.sessions.find((s) => s.session_id === id) : null
    const wd = sess?.work_dir || ''
    setState({
      activeSessionId: id,
      activeTab: 'chat',
      workspace: wd,
      tempSession: false,
    })
    // 记住当前工作区，下次启动自动恢复（回退到引擎根目录前先恢复用户上次的选择）
    if (wd) actions.persistWorkspace(wd)
  },
  /** 把当前工作区路径落盘到主进程（userData/workspace.json），重启后自动恢复 */
  async persistWorkspace(dir: string | null) {
    try {
      await window.auracode.setWorkspace(dir)
    } catch (e) {
      console.warn('[workspace] 持久化失败', e)
    }
  },
  pushMessage(sessionId: string, msg: Omit<ChatMessage, 'id' | 'ts'>) {
    const list = state.messages[sessionId] || []
    const full: ChatMessage = { ...msg, id: nextId(), ts: Date.now() }
    setState({ messages: { ...state.messages, [sessionId]: [...list, full] } })
    return full
  },
  appendToMessage(sessionId: string, id: string, chunk: string) {
    const list = state.messages[sessionId] || []
    const next = list.map((m) =>
      m.id === id ? { ...m, content: m.content + chunk } : m,
    )
    setState({ messages: { ...state.messages, [sessionId]: next } })
  },
  finalizeMessage(sessionId: string, id: string) {
    const list = state.messages[sessionId] || []
    const next = list.map((m) =>
      m.id === id ? { ...m, streaming: false } : m,
    )
    setState({ messages: { ...state.messages, [sessionId]: next } })
  },
  pushEvent(e: BridgeEvent) {
    if (seen.has(e.event_id)) return
    seen.add(e.event_id)
    const events = [...state.events, e].slice(-2000)
    setState({ events })
  },
  /** 按 event_id 合并：用于流式文本逐块累积到同一条 assistant 消息 */
  upsertEvent(e: BridgeEvent) {
    seen.add(e.event_id)
    const idx = state.events.findIndex((x) => x.event_id === e.event_id)
    let events: BridgeEvent[]
    if (idx >= 0) {
      events = state.events.slice()
      events[idx] = e
    } else {
      events = [...state.events, e].slice(-2000)
    }
    setState({ events })
  },
  /** 批量并入历史事件（会话切换时拉取），自动去重 */
  ingestEvents(list: BridgeEvent[]) {
    const fresh = list.filter((e) => !seen.has(e.event_id))
    if (fresh.length === 0) return
    fresh.forEach((e) => seen.add(e.event_id))
    const events = [...state.events, ...fresh].slice(-2000)
    setState({ events })
  },
  /**
   * 标记后端事件 id 已被消费（不产生渲染条目）。
   * 用于 text_chunk / assistant_message 被流式合并进同一条气泡后，
   * 仍能在会话切换 ingestEvents 重放时按真实 event_id 去重，避免同内容重复渲染。
   */
  markSeen(eventId: string) {
    seen.add(eventId)
  },
  setPermission(p: PermissionReq | null, sessionId: string | null = null) {
    setState({ permission: p, permissionSession: sessionId })
  },
  setActivity(a: Activity) {
    setState({ activity: a })
  },
  setExtTab(t: string) {
    setState({ extTab: t })
  },
  setInspector(t: InspectorTab) {
    setState({ inspector: t })
  },
  setMode(m: string) {
    setState({ mode: m })
  },
  openSettings() {
    setState({ settingsOpen: true })
  },
  closeSettings() {
    setState({ settingsOpen: false })
  },
  openMcp() {
    setState({ mcpOpen: true, settingsOpen: false })
  },
  closeMcp() {
    setState({ mcpOpen: false })
  },
  openSkillhub() {
    setState({ skillhubOpen: true })
  },
  closeSkillhub() {
    setState({ skillhubOpen: false })
  },
  setWorkspace(name: string, temp = false) {
    setState({ workspace: name, tempSession: temp })
  },
  log(line: string) {
    setState({ log: [...state.log, line].slice(-200) })
  },
  openFile(path: string, content: string) {
    const existing = state.openFiles.find((f) => f.path === path)
    if (existing) {
      setState({ activeTab: path })
      return
    }
    setState({
      openFiles: [...state.openFiles, { path, dirty: false, content }],
      activeTab: path,
    })
  },
  closeFile(path: string) {
    const openFiles = state.openFiles.filter((f) => f.path !== path)
    const activeTab = state.activeTab === path ? 'chat' : state.activeTab
    setState({ openFiles, activeTab })
  },
  updateFileContent(path: string, content: string) {
    const openFiles = state.openFiles.map((f) =>
      f.path === path ? { ...f, content } : f,
    )
    setState({ openFiles })
  },
  markDirty(path: string, dirty: boolean) {
    const openFiles = state.openFiles.map((f) =>
      f.path === path ? { ...f, dirty } : f,
    )
    setState({ openFiles })
  },
  setActiveTab(t: string) {
    setState({ activeTab: t })
  },
  /** 顶部轻提示。kind=error 时红色，info 灰色，ok 绿色。3.5s 后自动消失。 */
  setToast(msg: string, kind: 'error' | 'info' | 'ok' = 'info') {
    setState({ toast: { msg, kind } })
    if (kind !== 'error') {
      setTimeout(() => {
        if (getState().toast?.msg === msg) setState({ toast: null })
      }, 3500)
    }
  },
  clearToast() {
    setState({ toast: null })
  },
  /** 顶部模式选择器（普通/自动/计划/绕过）映射为会话 permission_mode。
   *  修复：此前硬编码 normal，每次 write_file/run_command 都弹权限窗打断长任务；
   *  顶部选择器形同虚设。现在建会话时真正生效。 */
  currentPermissionMode(): string {
    switch (state.mode) {
      case '自动': return 'auto'
      case '计划': return 'plan'
      case '绕过': return 'bypass'
      default: return 'normal'
    }
  },
  /** 打开原生目录选择器，选中的真实路径作为新会话的工作区 */
  async openWorkspace() {
    const c = state.client
    if (!c) return
    try {
      const dir = await window.auracode.selectDirectory()
      if (!dir) {
        // 用户取消选择，不算错误，不弹提示
        return
      }
      actions.setToast(`正在用「${dir}」创建工作区…`, 'info')
      const r = await c.createSession({ work_dir: dir, permission_mode: actions.currentPermissionMode() })
      const list = await c.listSessions()
      actions.setSessions(list)
      actions.selectSession(r.session_id)
      actions.setToast(`已切换到工作区：${dir}`, 'ok')
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      console.warn('[workspace] 打开文件夹失败', e)
      actions.setToast('打开文件夹失败：' + msg, 'error')
    }
  },
  /** 切换到某工作区：复用同工作区的已有会话，否则新建 */
  async switchToWorkdir(workDir: string) {
    const c = state.client
    if (!c) return
    const existing = state.sessions.find((s) => s.work_dir === workDir)
    if (existing) {
      actions.selectSession(existing.session_id)
      return
    }
    try {
      const r = await c.createSession({ work_dir: workDir, permission_mode: actions.currentPermissionMode() })
      const list = await c.listSessions()
      actions.setSessions(list)
      actions.selectSession(r.session_id)
      actions.setToast(`已切换到工作区：${workDir}`, 'ok')
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      actions.setToast('切换工作区失败：' + msg, 'error')
    }
  },
  /** 新建无工作区的临时会话 */
  async newTempSession() {
    const c = state.client
    if (!c) return
    try {
      const r = await c.createSession({ work_dir: '.', permission_mode: 'normal', restore_history: false })
      const list = await c.listSessions()
      actions.setSessions(list)
      actions.selectSession(r.session_id)
      setState({ tempSession: true, workspace: '' })
      actions.persistWorkspace(null)
      actions.setToast('已新建临时会话（无工作区）', 'ok')
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      actions.setToast('新建临时会话失败：' + msg, 'error')
    }
  },
  /** 新建会话：继承当前/上次工作区（默认上次记住的工作区，没有则回退引擎根目录）。
   *  显式 restore_history:false —— 「新会话」= 全新开始，不回灌历史归档；
   *  续接历史发生在 boot 恢复 / 切换工作区（后端默认 restore_history:true）。 */
  async newSession() {
    const c = state.client
    if (!c) return
    const wd = state.workspace || state.config?.root || '.'
    try {
      const r = await c.createSession({
        work_dir: wd,
        permission_mode: actions.currentPermissionMode(),
        restore_history: false,
      })
      const list = await c.listSessions()
      actions.setSessions(list)
      actions.selectSession(r.session_id) // selectSession 会顺带持久化工作区
      actions.setToast(`已新建会话（工作区：${wd}）`, 'ok')
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      actions.setToast('新建会话失败：' + msg, 'error')
    }
  },
  setExtensions(data: ExtensionsData) {
    setState({ extensions: data })
  },
  /** 从主进程拉取真实扩展配置（技能/MCP/钩子/插件/定时任务） */
  async loadExtensions() {
    const root = state.config?.root
    if (!root) return
    try {
      const data = await window.auracode.getExtensions(root)
      setState({ extensions: data })
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      console.warn('[extensions] 加载失败', e)
      actions.setToast('扩展配置加载失败：' + msg, 'error')
    }
  },
  /** 从后端拉取引擎内置命令清单（供 # 命令自动补全） */
  async loadCommands() {
    const c = state.client
    if (!c) return
    try {
      const cmds = await c.listCommands()
      setState({ commands: cmds })
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      console.warn('[commands] 加载失败', e)
    }
  },
}
