import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

/**
 * 自定义模型（用户在前台「设置 → 自定义模型」里添加的接入点）。
 * 数据持久化在 ~/.auracode/models.json，与主进程扩展配置同目录，
 * 不依赖任何 Python 代码；渲染进程通过 IPC 读写，引擎只需在切换会话模型时
 * 拿到完整 base_url/api_key 即可路由（无需此文件）。
 */

export interface CustomModel {
  id: string
  name: string
  /** 供应商标识（openai / zhipu / deepseek / moonshot / qwen / siliconflow / volcano / custom …），仅用于展示与预设端点 */
  provider: string
  /** 接口地址（完整 chat/completions 端点，如 https://api.example.com/v1/chat/completions） */
  base_url: string
  api_key: string
  /** 模型名称（如 gpt-4o / glm-4.6） */
  model: string
}

function modelsPath(): string {
  return path.join(os.homedir(), '.auracode', 'models.json')
}

export function readCustomModels(): CustomModel[] {
  try {
    const p = modelsPath()
    if (!fs.existsSync(p)) return []
    const data = JSON.parse(fs.readFileSync(p, 'utf-8'))
    if (!Array.isArray(data)) return []
    return data.filter(
      (m) => m && typeof m.id === 'string' && typeof m.model === 'string',
    ) as CustomModel[]
  } catch {
    return []
  }
}

export function writeCustomModels(models: CustomModel[]): void {
  const dir = path.join(os.homedir(), '.auracode')
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  fs.writeFileSync(modelsPath(), JSON.stringify(models, null, 2), 'utf-8')
}
