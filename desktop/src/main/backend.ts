import { spawn, ChildProcess } from 'child_process'
import * as path from 'path'
import * as fs from 'fs'
import * as crypto from 'crypto'

export interface BridgeConfig {
  host: string
  port: number
  token: string
  /** 被驱动的 AuraCode Python 工程根目录（含 cli.py） */
  root: string
}

/**
 * 在 Electron 主进程里拉起已有的 AuraCode Bridge 后端。
 * 关键约束（来自 grill 决策 + 后端实测）：
 *  - 用 `python cli.py --bridge` 启动，不改动任何 Python 代码；
 *  - 绑定 127.0.0.1 loopback，端口可配置；
 *  - 每次启动生成随机 auth token，经 IPC 下发给 renderer，renderer 用它调 REST/WS；
 *  - 通过轮询 /api/status 等待后端就绪。
 */
export function createBackend() {
  let proc: ChildProcess | null = null
  let config: BridgeConfig | null = null

  /**
   * 解析 Python 解释器路径，优先级：
   *   1) AURACODE_PYTHON 环境变量（调试/覆盖）
   *   2) 内置 portable Python：<resources>/python/python.exe（生产分发）
   *   3) 系统 python / python3（未打包时的兜底）
   */
  function pythonCmd(): string {
    if (process.env.AURACODE_PYTHON) return process.env.AURACODE_PYTHON
    if (process.resourcesPath) {
      const bundled = path.join(process.resourcesPath, 'python', 'python.exe')
      if (fs.existsSync(bundled)) return bundled
    }
    return process.platform === 'win32' ? 'python' : 'python3'
  }

  /**
   * 定位包含 cli.py 的 AuraCode 引擎根目录，优先级：
   *   1) AURACODE_ROOT 环境变量
   *   2) 内置引擎：<resources>/engine（生产分发，与 portable python 同级）
   *   3) dev：out/main -> 仓库根（cli.py 在 desktop 的上一级）
   *   4) cwd / 上一级
   */
  function guessRoot(): string {
    const candidates = [
      process.env.AURACODE_ROOT,
    ]
    if (process.resourcesPath) {
      candidates.push(path.join(process.resourcesPath, 'engine'))
    }
    candidates.push(
      path.resolve(__dirname, '../../..'), // dev: out/main -> repo root
      path.resolve(process.cwd(), '..'),
      process.cwd(),
    )
    for (const c of candidates) {
      if (c && fs.existsSync(path.join(c, 'cli.py'))) return c
    }
    return process.cwd()
  }

  async function waitForReady(host: string, port: number, token: string, timeoutMs = 25000) {
    const url = `http://${host}:${port}/api/status`
    const deadline = Date.now() + timeoutMs
    while (Date.now() < deadline) {
      try {
        const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
        if (r.ok) return
      } catch {
        /* not up yet */
      }
      await new Promise((res) => setTimeout(res, 300))
    }
    throw new Error('AuraCode 后端在限定时间内未就绪')
  }

  async function start(onLog?: (line: string) => void): Promise<BridgeConfig> {
    const root = guessRoot()
    const token = crypto.randomBytes(24).toString('hex')
    const port = Number(process.env.AURACODE_PORT || 8765)
    const host = process.env.AURACODE_HOST || '127.0.0.1'
    config = { host, port, token, root }

    const py = pythonCmd()
    const args = [
      'cli.py',
      '--bridge',
      '--bridge-host', host,
      '--bridge-port', String(port),
      '--bridge-token', token,
    ]
    proc = spawn(py, args, {
      cwd: root,
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    })

    const pump = (buf: Buffer) => {
      String(buf)
        .split('\n')
        .map((l) => l.trim())
        .filter(Boolean)
        .forEach((l) => onLog?.(l))
    }
    proc.stdout?.on('data', pump)
    proc.stderr?.on('data', pump)
    proc.on('exit', (code) => onLog?.(`[bridge] process exited with code ${code}`))

    await waitForReady(host, port, token)
    return config
  }

  function stop() {
    if (proc) {
      try {
        proc.kill('SIGTERM')
      } catch {
        /* ignore */
      }
      proc = null
    }
  }

  return { start, stop, getConfig: () => config }
}
