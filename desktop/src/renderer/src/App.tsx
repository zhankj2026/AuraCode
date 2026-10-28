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
  // 重试连接计数器：点「重试连接」时 +1，重新触发启动握手（不重载页面）
  const [retryKey, setRetryKey] = useState(0)
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

  // 1) 启动握手：先确认主进程后端已就绪，再做一次真实 REST 握手；
  //    期间自动重试，覆盖「后端冷启动慢 / 瞬间未就绪」的竞态，避免一次性失败进死屏。
  //    只有握手成功才 setConnected(true)，让「正在启动」遮罩自然持续到真正可用。
  useEffect(() => {
    let ws: WebSocket | null = null
    let cancelled = false
    let retry = 0
    const delay = (ms: number) => new Promise((r) => setTimeout(r, ms))

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
      // 最多约 90s 的握手重试窗口（60 次 × 1.5s），覆盖冷启动/后端超时后再起来的情况
      for (let attempt = 0; attempt < 60; attempt++) {
        if (cancelled) return
        try {
          const status = await window.auracode.getBackendStatus()
          // 后端还没拉起（冷启动 / start 超时）—稍后重试，保持「正在启动」遮罩
          if (!status.ready || !status.config) {
            await delay(1500)
            continue
          }
          const cfg = status.config
          const c = new BridgeClient(cfg)
          // 真正握手：先打一次状态接口，确认端口/Token 实际可用，再拉会话列表
          await c.getStatus()
          if (cancelled) return
          let list = await c.listSessions()
          if (cancelled) return

          // 握手成功才置为已连接（此前是乐观置位，瞬间失败即死屏）
          actions.setConfig(cfg)
          actions.setClient(c)
          actions.setConnected(true)
          actions.loadExtensions()
          // 启动即加载自定义模型清单——否则顶栏模型下拉看不到自定义模型
          actions.loadCustomModels()

          // 读取上次记住的工作区（重启后恢复）
          let saved = ''
          try {
            saved = (await window.auracode.getWorkspace()) || ''
          } catch {
            /* 读不到就忽略，回落到引擎根目录 */
          }
          if (cancelled) return

          if (list.length === 0) {
            const wd = saved || cfg.root || '.'
            await c.createSession({ work_dir: wd, permission_mode: 'normal' })
            list = await c.listSessions()
          }
          actions.setSessions(list)
          const match = saved ? list.find((s) => s.work_dir === saved) : undefined
          actions.selectSession((match || list[0]).session_id)

          // 2) 订阅全局事件流
          connectWs(c)
          return
        } catch (e) {
          // 单次握手失败（后端瞬间未就绪的竞态）：重试
          await delay(1500)
        }
      }
      if (!cancelled) setError('无法连接 AuraCode 后端：启动超时或网络不可达，可点「重试连接」')
    }
    boot()
    return () => {
      cancelled = true
      ws?.close()
    }
  }, [retryKey])

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

    // 会话模型热切换/回落：只同步侧栏与设置面板的模型显示，不入事件流
    if (e.type === 'model_changed') {
      actions.updateSessionModel(e.session_id, String(e.data?.new_model || ''))
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
      actions.setSessionRunning(e.session_id, true)
    }

    // 轮次完成/会话出错 → 清运行态（「■ 结束」按钮隐藏）
    if (e.type === 'turn_complete' || e.type === 'session_error') {
      actions.setSessionRunning(e.session_id, false)
    }

    // 会话结束事件（stop/完成）同样清运行态
    if (e.type === 'session_stopped') {
      actions.setSessionRunning(e.session_id, false)
    }

    // 其余事件（tool_execute / tool_result / result / output / status …）原样入栈，由视图层渲染
    actions.pushEvent(e)
  }

  if (error) {
    return (
      <div className="overlay">
        <div className="big">连接失败</div>
        <div>{error}</div>
        <div style={{ fontSize: 11, color: 'var(--muted2)', marginBottom: 12 }}>
          请确认已安装 Python 且依赖已就绪，或设置环境变量 AURACODE_ROOT / AURACODE_PYTHON。
        </div>
        <button
          className="btn ok"
          onClick={async () => {
            setError(null)
            try {
              await window.auracode.restartBackend()
            } catch {
              /* 忽略重启失败，交给下方重试握手 */
            }
            setRetryKey((k) => k + 1)
          }}
        >
          重试连接
        </button>
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
