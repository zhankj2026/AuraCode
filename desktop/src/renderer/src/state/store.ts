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
  CustomModel,
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
  /** 右侧面板（Inspector）是否展开。默认展开；可经顶栏按钮或面板内收起按钮切换。 */
  inspectorOpen: boolean
  openFiles: OpenFile[]
  activeTab: string
  mode: string
  settingsOpen: boolean
  mcpOpen: boolean
  /** MCP 编辑器弹窗：null=新增，否则编辑该服务器（含 scope 定位） */
  mcpEdit: { name: string; scope: 'project' | 'user' } | null
  skillhubOpen: boolean
  /** 钩子管理弹窗 */
  hooksOpen: boolean
  log: string[]
  workspace: string
  tempSession: boolean
  extensions: ExtensionsData | null
  /** 引擎内置命令清单（GET /api/commands），供 # 命令自动补全 */
  commands: CommandInfo[]
  /** 自定义模型清单（前台「设置 → 自定义模型」添加，落盘 ~/.auracode/models.json） */
  customModels: CustomModel[]
  /** 顶部轻提示：用于把后台操作（如打开工作区）的真实成败反馈给用户，而不是静默吞掉 */
  toast: { msg: string; kind: 'error' | 'info' | 'ok' } | null
  /** 当前会话是否正在生成回复（turn_start → true，turn_complete/session_error → false）。
   *  驱动发送区「■ 结束」按钮的显示。按 session 记录，切换会话时自动正确。 */
  runningSessions: Record<string, boolean>
  /** 归档会话列表（专门的归档管理页数据源，与活跃会话列表分离） */
  archives: SessionInfo[]
  /** 归档查看器状态：null=关闭，否则显示该归档的消息 */
  archiveViewer: { id: string; title: string; messages: Array<{ role: string; content: string }> } | null
  /** 后端运行日志（实时）：来自主进程中转的 python cli.py --bridge 输出 */
  backendLogs: Array<{ ts: number; line: string }>
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
  inspectorOpen: true,
  openFiles: [],
  activeTab: 'chat',
  mode: '普通',
  settingsOpen: false,
  mcpOpen: false,
  mcpEdit: null,
  skillhubOpen: false,
  hooksOpen: false,
  log: [],
  workspace: 'auracode-src',
  tempSession: false,
  extensions: null,
  commands: [],
  customModels: [],
  toast: null,
  runningSessions: {},
  archives: [],
  archiveViewer: null,
  backendLogs: [],
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
  /** 后端清理了会话（session_expired 事件 / 定期对账发现消失）：
   *  从列表移除；若是当前会话则切到剩余第一个，避免侧栏停留幽灵 idle 会话 */
  sessionExpired(sessionId: string, reason = '') {
    if (!state.sessions.some((s) => s.session_id === sessionId)) return
    const list = state.sessions.filter((s) => s.session_id !== sessionId)
    const running = { ...state.runningSessions }
    delete running[sessionId]
    setState({ sessions: list, runningSessions: running })
    if (state.activeSessionId === sessionId) {
      actions.selectSession(list[0]?.session_id ?? null)
      if (!list[0]) setState({ events: [], messages: {} })
      actions.setToast(
        reason === 'idle_timeout'
          ? '当前会话空闲过久，已被后端自动清理（历史可在「历史归档」页找回）'
          : '当前会话已被后端清理，已切换会话',
        'info',
      )
    }
  },
  /** 定期对账：拉取后端真实会话列表并同步（静默失败不打扰）。
   *  WS 断连重试 5 次失败后 session_expired 事件收不到，这是兜底通道。 */
  async refreshSessions() {
    const c = state.client
    if (!c) return
    try {
      const list = await c.listSessions()
      const cur = state.sessions
      // 先逐个移除后端已消失的会话（sessionExpired 内部处理运行态清理
      // 与当前会话切换），再整体对齐，顺序不能反
      const gone = cur.filter(
        (s) => !list.some((n) => n.session_id === s.session_id),
      )
      for (const s of gone) actions.sessionExpired(s.session_id, 'reconcile')
      // 有实际变化才更新，避免每 60s 无谓重渲染
      const changed =
        gone.length > 0 ||
        cur.length !== list.length ||
        list.some((n) => {
          const o = cur.find((s) => s.session_id === n.session_id)
          return (
            !o || o.state !== n.state || o.round_count !== n.round_count || o.title !== n.title
          )
        })
      if (changed) setState({ sessions: list })
    } catch {
      /* 后端瞬时不达：保持现状，下轮再试 */
    }
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
  /** 点击归档会话：恢复为活跃会话并选中（历史消息由后端回放事件流补齐） */
  async resumeSession(id: string) {
    const c = state.client
    if (!c) return
    const sess = state.sessions.find((s) => s.session_id === id)
    if (!sess?.archived) {
      // 活跃会话直接选中
      actions.selectSession(id)
      return
    }
    try {
      actions.setToast('正在恢复历史会话…', 'info')
      const r = await c.resumeSession(id)
      const list = await c.listSessions()
      actions.setSessions(list)
      actions.selectSession(r.session_id)
      actions.setActivity('chat')
      // 后端 resume 返回时回放已完成，立即拉齐历史事件
      // （不依赖 App.tsx 的切换 effect——那个在 events 非空时也只拉一次，
      //  与 resume 的时序竞争会漏内容）
      try {
        const evs = await c.getEvents(r.session_id, 0)
        actions.ingestEvents(evs)
      } catch {
        /* 历史拉取失败不阻断；WS 流仍可用 */
      }
      // 恢复后刷新归档列表（归档文件仍在，但该条目已恢复为活跃会话）
      actions.loadArchives()
      actions.setToast('已恢复历史会话', 'ok')
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      actions.setToast('恢复会话失败：' + msg, 'error')
    }
  },
  /** 删除会话：活跃（停+移除）与归档文件一并清理；删的是当前会话则切到第一个可用会话 */
  async deleteSession(id: string) {
    const c = state.client
    if (!c) return
    try {
      await c.deleteSession(id)
      const list = await c.listSessions()
      actions.setSessions(list)
      if (state.activeSessionId === id) {
        // 删除的是当前会话：切到剩余的第一个（无则清空选中态）
        actions.selectSession(list[0]?.session_id ?? null)
        if (!list[0]) {
          setState({ events: [], messages: {} })
        }
      }
      actions.setToast('已删除会话', 'ok')
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      actions.setToast('删除会话失败：' + msg, 'error')
    }
  },
  /** 把当前工作区路径落盘到主进程（userData/workspace.json），重启后自动恢复 */
  async persistWorkspace(dir: string | null) {
    try {
      await window.auracode.setWorkspace(dir)
    } catch (e) {
      console.warn('[workspace] 持久化失败', e)
    }
  },
  /** 标记会话运行态（turn_start/turn_complete 事件驱动；「结束」按钮的显示依据） */
  setSessionRunning(sessionId: string, running: boolean) {
    setState({ runningSessions: { ...state.runningSessions, [sessionId]: running } })
  },
  /** 手动归档当前/指定会话：停止+写盘+从活跃列表移除（切到剩余第一个） */
  async archiveSession(id: string) {
    const c = state.client
    if (!c) return
    try {
      await c.archiveSession(id)
      const list = await c.listSessions()
      actions.setSessions(list)
      if (state.activeSessionId === id) {
        actions.selectSession(list[0]?.session_id ?? null)
        if (!list[0]) setState({ events: [], messages: {} })
      }
      actions.setToast('已归档会话（可在「历史归档」页查看/恢复）', 'ok')
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      actions.setToast('归档失败：' + msg, 'error')
    }
  },
  /** 拉取归档列表（归档管理页） */
  async loadArchives() {
    const c = state.client
    if (!c) return
    try {
      const list = await c.listArchives()
      setState({ archives: list })
    } catch (e) {
      console.warn('[archives] 加载失败', e)
    }
  },
  /** 打开归档查看器（只读消息） */
  async openArchiveViewer(id: string) {
    const c = state.client
    if (!c) return
    const meta = state.archives.find((a) => a.session_id === id)
    try {
      const r = await c.getArchiveMessages(id)
      setState({
        archiveViewer: { id, title: meta?.title || '(未命名)', messages: r.messages },
      })
    } catch (e) {
      actions.setToast('读取归档内容失败：' + String(e), 'error')
    }
  },
  closeArchiveViewer() {
    setState({ archiveViewer: null })
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
  /** 切换右侧面板的展开/收起；面板上「收起」按钮与顶栏「面板」按钮共用。 */
  toggleInspector() {
    setState({ inspectorOpen: !state.inspectorOpen })
  },
  setInspectorOpen(v: boolean) {
    setState({ inspectorOpen: v })
  },
  setMode(m: string) {
    setState({ mode: m })
    // 顶部模式选择器（普通/自动/计划/绕过）需实时作用于「正在运行」的会话，
    // 否则仅影响新建会话 —— 表现为切到「绕过」后仍弹 run_command 权限窗。
    const c = state.client
    const sid = state.activeSessionId
    if (c && sid) {
      const mode = actions.currentPermissionMode()
      c.setPermissionMode(sid, mode).catch((e) => {
        console.warn('[setMode] 推送权限模式失败', e)
      })
    }
  },
  /** 清空当前会话的对话上下文（消息历史），保留 token/cost 累计。
   *  后端清空会话内存历史，前端同步移除本地事件与消息，界面立即回到空白。 */
  clearContext() {
    const c = state.client
    const sid = state.activeSessionId
    if (c && sid) {
      c.clearContext(sid).catch((e) => console.warn('[clearContext] 失败', e))
    }
    if (!sid) return
    const events = state.events.filter((e) => e.session_id !== sid)
    const messages = { ...state.messages }
    delete messages[sid]
    setState({ events, messages })
  },
  openSettings() {
    setState({ settingsOpen: true })
  },
  closeSettings() {
    setState({ settingsOpen: false })
  },
  openMcp() {
    setState({ mcpOpen: true, settingsOpen: false, mcpEdit: null })
  },
  closeMcp() {
    setState({ mcpOpen: false, mcpEdit: null })
  },
  /** 编辑已有 MCP 服务器（列表的 ✎ 按钮进入） */
  openMcpEdit(name: string, scope: 'project' | 'user') {
    setState({ mcpOpen: true, settingsOpen: false, mcpEdit: { name, scope } })
  },
  openSkillhub() {
    setState({ skillhubOpen: true })
  },
  closeSkillhub() {
    setState({ skillhubOpen: false })
  },
  openHooks() {
    setState({ hooksOpen: true })
  },
  closeHooks() {
    setState({ hooksOpen: false })
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
  /** 追加一条后端日志（实时推送）。限制内存上限避免无限增长。 */
  appendBackendLog(entry: { ts: number; line: string }) {
    const next = state.backendLogs.slice()
    next.push(entry)
    if (next.length > 3000) next.splice(0, next.length - 3000)
    setState({ backendLogs: next })
  },
  /** 用主进程缓冲整体替换（面板打开时 catch-up，避免与实时推送重复） */
  setBackendLogs(list: Array<{ ts: number; line: string }>) {
    setState({ backendLogs: list.slice(-3000) })
  },
  /** 仅清空前端显示（不影响主进程落盘文件） */
  clearBackendLogs() {
    setState({ backendLogs: [] })
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
  /** 当前会话的工作区绝对路径（项目级扩展配置的基准；无会话时回退引擎根目录） */
  currentWorkDir(): string {
    const sess = state.sessions.find((s) => s.session_id === state.activeSessionId)
    if (sess?.work_dir) return sess.work_dir
    return state.config?.root || '.'
  },
  /** 从主进程拉取真实扩展配置（技能/MCP/钩子/插件/定时任务）。
   *  engineRoot=引擎根目录（内置资源）；workDir=当前会话工作区（项目级配置跟随它）。 */
  async loadExtensions() {
    const engineRoot = state.config?.root
    if (!engineRoot) return
    try {
      const data = await window.auracode.getExtensions(engineRoot, actions.currentWorkDir())
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
  /** 从主进程读取自定义模型清单（~/.auracode/models.json） */
  async loadCustomModels() {
    try {
      const res = await window.auracode.getCustomModels()
      if (res?.ok && Array.isArray(res.models)) {
        setState({ customModels: res.models })
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      console.warn('[customModels] 加载失败', e)
    }
  },
  /** 持久化自定义模型清单（整表写入）；写后刷新本地状态 */
  async saveCustomModels(models: CustomModel[]) {
    try {
      const res = await window.auracode.setCustomModels(models)
      if (res?.ok) {
        setState({ customModels: models })
      } else if (res?.message) {
        actions.setToast('保存自定义模型失败：' + res.message, 'error')
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      actions.setToast('保存自定义模型失败：' + msg, 'error')
    }
  },
}
