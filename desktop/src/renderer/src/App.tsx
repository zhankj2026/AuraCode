import { useEffect, useRef, useState } from 'react'
import { actions, useStore } from './state/store'
import { BridgeClient } from './api/client'
import type { BridgeEvent } from './api/types'
import { Header } from './components/Header'
import { ActivityBar } from './components/ActivityBar'
import { Sidebar } from './components/Sidebar'
import { MainArea } from './components/MainArea'
import { Inspector } from './components/Inspector'
import { SettingsModal } from './components/SettingsModal'
import { PermissionModal } from './components/PermissionModal'
import { McpModal } from './components/McpModal'
import { SkillHubModal } from './components/SkillHubModal'

export default function App() {
  const client = useStore((s) => s.client)
  const connected = useStore((s) => s.connected)
  const activeId = useStore((s) => s.activeSessionId)
  const activity = useStore((s) => s.activity)
  const toast = useStore((s) => s.toast)
  const [error, setError] = useState<string | null>(null)
  const streamRef = useRef<Map<string, string>>(new Map())
  // 当前正在流式累积的 assistant 气泡 id：text_chunk 累积到这里，最终由 assistant_message 定稿
  const streamIdRef = useRef<string | null>(null)
  const lastTurnRef = useRef<number>(0)

  // 切换会话时拉取历史事件，补齐审计/改动（WS 连接前产生的事件）
  useEffect(() => {
    if (!client || !activeId) return
    client
      .getEvents(activeId, 0)
      .then((list) => actions.ingestEvents(list))
      .catch(() => {})
  }, [client, activeId])

  // 进入「扩展 / 任务」视图时刷新真实配置（配置可能被外部修改）
  useEffect(() => {
    if (activity === 'ext' || activity === 'tasks') actions.loadExtensions()
  }, [activity])

  // 1) 启动时从主进程拿到后端连接信息，建立客户端；并维护全局事件流（断线自动重连）
  useEffect(() => {
    let ws: WebSocket | null = null
    let cancelled = false
    let retry = 0

    function connectWs(c: BridgeClient) {
      if (cancelled) return
      ws = c.connectEvents(
        (e) => handleEvent(e, c),
        undefined,
        () => {
          // 非主动取消时尝试重连，最多 5 次
          if (cancelled) return
          if (retry++ < 5) {
            setTimeout(() => connectWs(c), 1500)
          } else {
            actions.setToast('实时事件流已断开，请检查后端是否存活', 'error')
          }
        },
      )
    }

    async function boot() {
      try {
        const cfg = await window.auracode.getConfig()
        if (cancelled) return
        const c = new BridgeClient(cfg)
        actions.setConfig(cfg)
        actions.setClient(c)
        actions.setConnected(true)
        // 拉取真实扩展配置（技能/MCP/钩子/插件/定时任务）供「扩展/任务」面板使用
        actions.loadExtensions()

        // 读取上次记住的工作区（重启后恢复），优先用它而非引擎根目录
        let saved = ''
        try {
          saved = (await window.auracode.getWorkspace()) || ''
        } catch {
          /* 读不到就忽略，回落到引擎根目录 */
        }
        if (cancelled) return

        // 首次连接：无会话则自动建一个，方便直接体验
        // 关键修复：work_dir 优先用「上次记住的工作区」，否则才回退引擎根目录，
        // 避免每次启动都回落到 AuraCode 引擎源码目录。
        let list = await c.listSessions()
        if (cancelled) return
        if (list.length === 0) {
          const wd = saved || cfg.root || '.'
          await c.createSession({ work_dir: wd, permission_mode: 'normal' })
          list = await c.listSessions()
        }        actions.setSessions(list)
        // 恢复会话时优先选中「上次工作区」匹配的会话，否则第一个
        const match = saved ? list.find((s) => s.work_dir === saved) : undefined
        actions.selectSession((match || list[0]).session_id)

        // 2) 订阅全局事件流（后端会把所有会话事件广播到这里）
        connectWs(c)
      } catch (e) {
        if (!cancelled) setError('无法连接 AuraCode 后端：' + e)
      }
    }
    boot()
    return () => {
      cancelled = true
      ws?.close()
    }
  }, [])

  function handleEvent(e: BridgeEvent, c: BridgeClient) {
    // 本地发送时已即时渲染用户消息，忽略后端回放的 user_message
    if (e.type === 'user_message') return

    // 权限请求 → 弹窗
    if (e.type === 'permission_request') {
      actions.setPermission(
        {
          request_id: e.data.request_id,
          tool_name: e.data.tool_name,
          tool_input: e.data.tool_input,
          description: e.data.description,
        },
        e.session_id,
      )
      return
    }

    // 实时打字机：text_chunk 累积到当前 assistant 气泡，最终由 assistant_message 定稿。
    // 注意：后端 text_chunk 的载荷字段是 data.content（不是 data.delta），且没有 message_id。
    if (e.type === 'text_chunk') {
      actions.markSeen(e.event_id)
      const turn = (e.data && e.data.turn) || lastTurnRef.current || 0
      lastTurnRef.current = turn
      const id = streamIdRef.current || `a_${e.event_id}`
      streamIdRef.current = id
      const cur = streamRef.current.get(id) || ''
      const next = cur + (e.data?.content || '')
      streamRef.current.set(id, next)
      actions.upsertEvent({
        event_id: id,
        type: 'assistant_message',
        session_id: e.session_id,
        data: { content: next },
        timestamp: e.timestamp,
      })
      return
    }

    // 一轮 assistant 文本的最终定稿（以服务端为准，覆盖流式累积）。
    // 注意：turn_complete 会先于 assistant_message 到达（后者是回合后补发的），
    // 因此这里不能依赖 streamIdRef 一定非空——为空时才新建气泡，非空时原地定稿，
    // 否则同一回复会渲染两次。
    if (e.type === 'assistant_message') {
      actions.markSeen(e.event_id)
      const id = streamIdRef.current || `a_${e.event_id}`
      streamRef.current.set(id, e.data?.content || '')
      actions.upsertEvent({
        event_id: id,
        type: 'assistant_message',
        session_id: e.session_id,
        data: { content: e.data?.content || '' },
        timestamp: e.timestamp,
      })
      return
    }

    // 新一轮开始 → 重置流式气泡，避免与上轮内容串台。
    // （不在 turn_complete 重置：assistant_message 在其后才到，提前重置会导致重复气泡）
    if (e.type === 'turn_start') {
      lastTurnRef.current = (e.data && e.data.turn) || lastTurnRef.current
      streamIdRef.current = null
    }

    // 其余事件（tool_execute / tool_result / result / output / status …）原样入栈，由视图层渲染
    actions.pushEvent(e)
  }

  if (error) {
    return (
      <div className="overlay">
        <div className="big">连接失败</div>
        <div>{error}</div>
        <div style={{ fontSize: 11, color: 'var(--muted2)' }}>
          请确认已安装 Python 且依赖已就绪，或设置环境变量 AURACODE_ROOT / AURACODE_PYTHON。
        </div>
      </div>
    )
  }

  if (!connected || !client) {
    return (
      <div className="overlay">
        <div className="spin" />
        <div className="big">正在启动 AuraCode 后端…</div>
        <div>主进程正在拉起 python cli.py --bridge</div>
      </div>
    )
  }

  return (
    <div className="app">
      <Header />
      <div className="body">
        <ActivityBar />
        <div className="side">
          <Sidebar />
        </div>
        <MainArea />
        <Inspector />
      </div>

      <SettingsModal />
      <PermissionModal />
      <McpModal />
      <SkillHubModal />

      {toast && (
        <div
          className={`toast ${toast.kind}`}
          onClick={() => actions.clearToast()}
          title="点击关闭"
        >
          {toast.msg}
        </div>
      )}
    </div>
  )
}
