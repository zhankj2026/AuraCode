import { app, BrowserWindow, ipcMain, dialog, Tray, Menu, nativeImage } from 'electron'
import * as path from 'path'
import * as fs from 'fs'
import { createBackend } from './backend'
import { collectExtensions } from './extensions'
import { readCustomModels, writeCustomModels, CustomModel } from './models'

const backend = createBackend()
let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null
/** 真正退出标志：仅「退出登录」/ 系统关机走这条路径，关窗只是隐藏 */
let isQuiting = false
/** 后端是否已成功拉起并确认就绪 */
let backendReady = false

// 内联托盘图标（navy 底 + cyan 「</>」），base64 解码后用 nativeImage，
// 避免依赖打包/开发两套资源路径布局。
const TRAY_ICON_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAA50lEQVR42u3asRHCMAwF0L8BHSMwA8uzFx0cJQVUSJbJK3zp4uhdzpZs5XS+PI48AgAAAAAAAAAAAAAAgCXjeru/PQ8D8Ar40/h7gG/BdyNkYvCdCJkafBdCJgffgZDpwVcj3QiZmOR0ImRqhteFkMnpbQdCpuf21e/PDoVN5TzZpaqrmi87lbQV85YCrEyyygAmlLC//AZ/gDXALiAPkAmqBVSDzgOcCDkTdCrsXsDNkLtBt8P6A3SI6BHSJaZPUKcoAAAAAAAAAAAAgAOMJy6RRiifuFcqAAAAAElFTkSuQmCC'

function createTray() {
  if (tray) return
  const img = nativeImage.createFromBuffer(Buffer.from(TRAY_ICON_BASE64, 'base64'))
  tray = new Tray(img)
  tray.setToolTip('AuraCode')
  const contextMenu = Menu.buildFromTemplate([
    {
      label: '打开 AuraCode',
      click: () => {
        if (!mainWindow) createWindow()
        mainWindow?.show()
        mainWindow?.focus()
      },
    },
    { type: 'separator' },
    {
      label: '退出登录',
      click: () => {
        // 真正退出：标记 isQuiting 让 close 事件放行，触发 before-quit 停后端。
        isQuiting = true
        app.quit()
      },
    },
  ])
  tray.setContextMenu(contextMenu)
  // Windows：左键单击 / 双击都直接唤出主窗口
  tray.on('click', () => {
    if (!mainWindow) createWindow()
    mainWindow?.show()
    mainWindow?.focus()
  })
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1320,
    height: 860,
    minWidth: 920,
    minHeight: 600,
    backgroundColor: '#0F1626',
    title: 'AuraCode',
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  if (process.env.ELECTRON_RENDERER_URL) {
    mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'))
  }

  // 关窗不退出：拦截 close，未真正退出时隐藏窗口并保留在托盘（仿 WorkBuddy）。
  mainWindow.on('close', (e) => {
    if (!isQuiting) {
      e.preventDefault()
      mainWindow?.hide()
      return
    }
    mainWindow = null
  })
}

app.whenReady().then(async () => {
  try {
    await backend.start((line) => console.log('[bridge]', line))
    backendReady = true
  } catch (e) {
    console.error('[bridge] 启动失败:', e)
    backendReady = false
  }
  createWindow()
  createTray()

  app.on('activate', () => {
    // macOS 点击 dock 图标：窗口被隐藏（或不存在）时唤出
    if (!mainWindow) {
      createWindow()
    } else {
      mainWindow.show()
    }
  })
})

// 关掉所有窗口不再退出程序：窗口只是被隐藏，进程留在托盘常驻。
app.on('window-all-closed', () => {
  /* 常驻托盘，不 quit */
})

// 真正退出前：停掉后端子进程，避免孤儿进程。仅「退出登录」会走到这里。
app.on('before-quit', () => {
  isQuiting = true
  backend.stop()
})

// ── IPC：向 renderer 暴露后端连接信息 ──────────────────────────────
ipcMain.handle('bridge:config', () => backend.getConfig())

// 后端就绪状态：渲染端据此决定是否重试连接 / 提示启动失败（而非盲目发起连接）。
ipcMain.handle('backend:status', () => ({
  ready: backendReady,
  config: backend.getConfig(),
}))

// ── IPC：工作区持久化（记住上次使用的工作目录，重启后自动恢复）──
// 注意：这里的「工作区」是会话真正的工作目录（work_dir），与引擎根目录（cli.py 所在目录）分开。
// 默认 auto-create / 新会话会优先使用「上次记住的工作区」，避免每次启动都回落到引擎源码目录。
function workspaceConfigPath(): string {
  return path.join(app.getPath('userData'), 'workspace.json')
}
function readWorkspace(): { lastWorkspace: string | null; recent: string[] } {
  try {
    const p = workspaceConfigPath()
    if (!fs.existsSync(p)) return { lastWorkspace: null, recent: [] }
    const obj = JSON.parse(fs.readFileSync(p, 'utf-8'))
    const recent = Array.isArray(obj.recent) ? obj.recent.filter((x: any) => typeof x === 'string') : []
    return {
      lastWorkspace:
        typeof obj.lastWorkspace === 'string' && obj.lastWorkspace ? obj.lastWorkspace : null,
      recent: recent.slice(0, 10),
    }
  } catch {
    return { lastWorkspace: null, recent: [] }
  }
}
function writeWorkspace(lastWorkspace: string | null, recent: string[]) {
  try {
    fs.writeFileSync(
      workspaceConfigPath(),
      JSON.stringify({ lastWorkspace: lastWorkspace || null, recent: recent.slice(0, 10) }, null, 2),
      'utf-8',
    )
  } catch (err) {
    console.error('[workspace] 写入失败:', err)
  }
}
/** 把 dir 记录到「最近打开的工作区」历史：去重、置顶、最多保留 10 条 */
function pushRecent(dir: string): string[] {
  if (!dir) return readWorkspace().recent
  const { lastWorkspace, recent } = readWorkspace()
  const next = [dir, ...recent.filter((w) => w !== dir)].slice(0, 10)
  writeWorkspace(lastWorkspace, next)
  return next
}
ipcMain.handle('workspace:get', () => readWorkspace().lastWorkspace)
ipcMain.handle('workspace:set', (_e, dir: string | null) => {
  // 切换工作区时同步维护「最近打开」历史（置顶 + 去重 + 上限 10）
  const next = dir ? [dir, ...readWorkspace().recent.filter((w) => w !== dir)].slice(0, 10) : readWorkspace().recent
  writeWorkspace(dir, next)
  return dir
})
ipcMain.handle('workspace:recent:get', () => readWorkspace().recent)

// ── IPC：整文件读取（不做行数截断）────────────────────────────────────
// 背景：后端 /files/content 默认 max_lines=200（上限 2000），而 demo6 的
// entities.js(505 行)/game.js(488)/ui.js(425)/systems.js(224) 都超了 200 行，
// 前端拿到的内容是被腰斩的，注入 iframe 后必然 SyntaxError → HTML 预览白屏。
// 这里直接在主进程按 (工作区根目录, 相对路径) 读全文件，彻底摆脱行数上限。
// 安全：强制做目录包含校验，禁止 ../ 逃逸出工作区；超 8MB 拒绝，避免卡死渲染进程。
ipcMain.handle('fs:readText', (_e, root: string, rel: string) => {
  try {
    if (!root || !rel) return { ok: false, error: '缺少参数' }
    const rootAbs = path.resolve(root)
    const target = path.resolve(rootAbs, rel)
    const relCheck = path.relative(rootAbs, target)
    if (relCheck.startsWith('..') || path.isAbsolute(relCheck)) {
      return { ok: false, error: '路径越界' }
    }
    const st = fs.statSync(target)
    if (!st.isFile()) return { ok: false, error: '不是文件' }
    if (st.size > 8 * 1024 * 1024) {
      return { ok: false, error: `文件过大（${(st.size / 1048576).toFixed(1)}MB）` }
    }
    const content = fs.readFileSync(target, 'utf8')
    return {
      ok: true,
      content,
      lines: content.length ? content.split('\n').length : 0,
      size: st.size,
    }
  } catch (err: any) {
    return { ok: false, error: String(err?.message || err) }
  }
})

ipcMain.handle('backend:restart', async () => {
  backend.stop()
  return await backend.start((line) => console.log('[bridge]', line))
})

// ── IPC：二进制文件读取（转 data URL）── 供图片预览。同样做越界/大小校验。
ipcMain.handle('fs:readDataUrl', (_e, root: string, rel: string) => {
  try {
    if (!root || !rel) return { ok: false, error: '缺少参数' }
    const rootAbs = path.resolve(root)
    const target = path.resolve(rootAbs, rel)
    const relCheck = path.relative(rootAbs, target)
    if (relCheck.startsWith('..') || path.isAbsolute(relCheck)) {
      return { ok: false, error: '路径越界' }
    }
    const st = fs.statSync(target)
    if (!st.isFile()) return { ok: false, error: '不是文件' }
    if (st.size > 24 * 1024 * 1024) {
      return { ok: false, error: `文件过大（${(st.size / 1048576).toFixed(1)}MB）` }
    }
    const buf = fs.readFileSync(target)
    const ext = path.extname(target).toLowerCase().replace('.', '')
    const mimes: Record<string, string> = {
      png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif',
      webp: 'image/webp', bmp: 'image/bmp', svg: 'image/svg+xml', ico: 'image/x-icon',
    }
    const mime = mimes[ext] || 'application/octet-stream'
    return { ok: true, dataUrl: `data:${mime};base64,${buf.toString('base64')}`, size: st.size }
  } catch (err: any) {
    return { ok: false, error: String(err?.message || err) }
  }
})

// ── IPC：Office 文档 → HTML 预览（docx/pptx → 纯 stdlib Python 转换）──
// 用内置 Python 跑 desktop/resources/engine/tools/officedoc2html.py（零三方依赖，
// zipfile+ElementTree 解包 OOXML）。失败时返回错误，前端展示降级提示。
ipcMain.handle('fs:officePreview', async (_e, root: string, rel: string) => {
  try {
    if (!root || !rel) return { ok: false, error: '缺少参数' }
    const rootAbs = path.resolve(root)
    const target = path.resolve(rootAbs, rel)
    const relCheck = path.relative(rootAbs, target)
    if (relCheck.startsWith('..') || path.isAbsolute(relCheck)) {
      return { ok: false, error: '路径越界' }
    }
    const st = fs.statSync(target)
    if (!st.isFile()) return { ok: false, error: '不是文件' }
    if (st.size > 40 * 1024 * 1024) {
      return { ok: false, error: `文件过大（${(st.size / 1048576).toFixed(1)}MB）` }
    }

    // 定位内置 Python 与转换脚本（兼容 dev 与打包后资源布局）
    const pyCandidates = [
      path.join(process.resourcesPath || '', 'python', 'python.exe'),
      path.join(__dirname, '../../resources/python/python.exe'),
    ]
    const scriptCandidates = [
      path.join(process.resourcesPath || '', 'engine', 'tools', 'officedoc2html.py'),
      path.join(__dirname, '../../resources/engine/tools/officedoc2html.py'),
    ]
    let py = ''
    for (const c of pyCandidates) {
      if (c && fs.existsSync(c)) { py = c; break }
    }
    let script = ''
    for (const c of scriptCandidates) {
      if (c && fs.existsSync(c)) { script = c; break }
    }
    if (!py || !script) {
      return { ok: false, error: '内置 Python 或转换脚本缺失' }
    }

    const { execFile } = require('child_process')
    const result = await new Promise<{ ok: boolean; html?: string; error?: string }>((resolve) => {
      execFile(
        py, [script, target],
        { timeout: 30_000, maxBuffer: 64 * 1024 * 1024, windowsHide: true },
        (err: any, stdout: string, stderr: string) => {
          if (err) {
            resolve({ ok: false, error: `${String(err?.message || err)}${stderr ? ' / ' + stderr.slice(0, 200) : ''}` })
          } else {
            resolve({ ok: true, html: stdout })
          }
        },
      )
    })
    return result
  } catch (err: any) {
    return { ok: false, error: String(err?.message || err) }
  }
})

// ── IPC：读取真实扩展配置（技能/MCP/钩子/插件/定时任务），供「扩展/任务」面板使用 ──
ipcMain.handle('extensions:list', (_e, root: string) => {
  try {
    return collectExtensions(root)
  } catch (err) {
    console.error('[extensions] 读取失败:', err)
    return { skills: [], mcp: [], hooks: [], plugins: [], tasks: [] }
  }
})

// ── IPC：自定义模型（前台「设置 → 自定义模型」增删改，落盘 ~/.auracode/models.json）──
ipcMain.handle('models:list', () => {
  try {
    return { ok: true, models: readCustomModels() }
  } catch (err) {
    return { ok: false, models: [], error: String(err) }
  }
})
ipcMain.handle('models:save', (_e, models: CustomModel[]) => {
  try {
    if (!Array.isArray(models)) return { ok: false, message: '参数不是数组' }
    writeCustomModels(models)
    return { ok: true, message: `已保存 ${models.length} 个自定义模型` }
  } catch (err) {
    return { ok: false, message: '保存失败：' + (err instanceof Error ? err.message : String(err)) }
  }
})

// ── IPC：原生目录选择器，供「切换工作区」使用 ──
// 关键修复：务必给对话框传入父窗口。
// 当 BrowserWindow.getFocusedWindow() 返回 null（某些 Windows 焦点状态下常见）时，
// 无父窗口的 showOpenDialog 会在主窗口「背后」弹出，用户看不到 = 表现为“点了没反应”。
// 因此这里回退到 mainWindow / 任意已存在窗口作为父窗口，保证对话框始终置顶可见。
ipcMain.handle('dialog:selectDirectory', async () => {
  const win =
    BrowserWindow.getFocusedWindow() ||
    mainWindow ||
    BrowserWindow.getAllWindows()[0] ||
    null
  const options: Electron.OpenDialogOptions = {
    title: '选择工作区文件夹',
    properties: ['openDirectory', 'createDirectory'],
  }
  const result = win
    ? await dialog.showOpenDialog(win, options)
    : await dialog.showOpenDialog(options)
  if (result.canceled || result.filePaths.length === 0) return null
  return result.filePaths[0]
})

// ── IPC：把 MCP 服务器配置真正写入工程 .mcp.json（磁盘落盘，不改动任何 Python）──
// 这样「扩展 → MCP → 连接 MCP 服务器」弹窗里的“连接”能真正生效，并即时刷新左侧列表。
ipcMain.handle('mcp:add', (_e, cfg: { root: string; name: string; transport: string; command?: string; args?: string; url?: string }) => {
  try {
    if (!cfg.root || !cfg.name) return { ok: false, message: '缺少 root 或 name' }
    const file = path.join(cfg.root, '.mcp.json')
    let data: any = {}
    if (fs.existsSync(file)) {
      try {
        data = JSON.parse(fs.readFileSync(file, 'utf-8'))
      } catch {
        data = {}
      }
    }
    if (typeof data !== 'object' || data === null) data = {}
    if (typeof data.mcpServers !== 'object' || data.mcpServers === null) data.mcpServers = {}

    const entry: Record<string, string | string[]> = {}
    if (cfg.transport === 'http' || cfg.transport === 'sse' || cfg.transport === 'websocket') {
      entry.type = cfg.transport === 'websocket' ? 'ws' : cfg.transport
      entry.url = cfg.url || ''
    } else {
      entry.type = 'stdio'
      const cmd = (cfg.command || '').trim()
      const args = (cfg.args || '')
        .split(/\s+/)
        .map((s) => s.trim())
        .filter(Boolean)
      if (!cmd) return { ok: false, message: 'stdio 模式需要启动命令' }
      entry.command = cmd
      if (args.length) entry.args = args
    }
    data.mcpServers[cfg.name] = entry
    fs.writeFileSync(file, JSON.stringify(data, null, 2), 'utf-8')
    return { ok: true, message: `已写入 ${file}` }
  } catch (err) {
    return { ok: false, message: '写入失败：' + (err instanceof Error ? err.message : String(err)) }
  }
})
