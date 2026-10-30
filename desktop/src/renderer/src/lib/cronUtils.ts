/**
 * cronUtils —— 纯前端 cron 工具（无外部依赖）
 *
 * 与后端 tools/builtin/cron_tool.py 的 5 字段语义保持一致：
 *   分 时 日 月 周（周 0=周日 … 6=周六）
 *
 * 提供：
 *  - parseCron / validateCron        解析与校验
 *  - describeCron                    生成人类可读中文描述（如「每天 09:00」）
 *  - nextFire                       计算下次触发时间（前端实时预览，无需后端）
 *  - CRON_PRESETS                    可视化构建器的快捷预设
 */

export type CronField =
  | { type: 'all' }
  | { type: 'step'; step: number } // */N
  | { type: 'values'; values: number[] } // 显式列表（含范围 / 单值）

export interface ParsedCron {
  minute: CronField
  hour: CronField
  dom: CronField
  month: CronField
  dow: CronField
}

const RANGES: Record<keyof ParsedCron, [number, number]> = {
  minute: [0, 59],
  hour: [0, 23],
  dom: [1, 31],
  month: [1, 12],
  dow: [0, 6],
}

function fieldMatches(f: CronField, v: number): boolean {
  if (f.type === 'all') return true
  if (f.type === 'step') return v % f.step === 0
  return f.values.includes(v)
}

function parseField(
  part: string,
  name: keyof ParsedCron,
): CronField {
  const [lo, hi] = RANGES[name]
  const p = part.trim()
  if (p === '') throw new Error(`empty field: ${name}`)
  if (p === '*') return { type: 'all' }

  // */N
  if (p.startsWith('*/')) {
    const step = parseInt(p.slice(2), 10)
    if (!Number.isFinite(step) || step <= 0) throw new Error(`bad step: ${p}`)
    return { type: 'step', step }
  }

  const values = new Set<number>()
  for (const seg of p.split(',')) {
    const s = seg.trim()
    if (s === '') throw new Error(`empty segment in ${p}`)

    // 形如 a-b 或 a-b/N
    if (s.includes('-')) {
      const [rangePart, stepStr] = s.split('/')
      const step = stepStr ? parseInt(stepStr, 10) : 1
      const [a, b] = rangePart.split('-').map((x) => parseInt(x, 10))
      if (!Number.isFinite(a) || !Number.isFinite(b) || !Number.isFinite(step) || step <= 0)
        throw new Error(`bad range: ${s}`)
      for (let v = a; v <= b; v += step) values.add(v)
    }
    // 形如 a/N（从 a 起每 N）
    else if (s.includes('/')) {
      const [startStr, stepStr] = s.split('/')
      const start = parseInt(startStr, 10)
      const step = parseInt(stepStr, 10)
      if (!Number.isFinite(start) || !Number.isFinite(step) || step <= 0)
        throw new Error(`bad step expr: ${s}`)
      for (let v = start; v <= hi; v += step) values.add(v)
    } else {
      values.add(parseInt(s, 10))
    }
  }

  for (const v of values) {
    if (!Number.isFinite(v) || v < lo || v > hi)
      throw new Error(`value ${v} out of range [${lo}-${hi}] for ${name}`)
  }
  return { type: 'values', values: [...values].sort((a, b) => a - b) }
}

export function parseCron(expr: string): ParsedCron {
  const parts = expr.trim().split(/\s+/)
  if (parts.length !== 5)
    throw new Error(`cron 需要 5 个字段，得到 ${parts.length}`)
  return {
    minute: parseField(parts[0], 'minute'),
    hour: parseField(parts[1], 'hour'),
    dom: parseField(parts[2], 'dom'),
    month: parseField(parts[3], 'month'),
    dow: parseField(parts[4], 'dow'),
  }
}

export function validateCron(expr: string): boolean {
  try {
    parseCron(expr)
    return true
  } catch {
    return false
  }
}

function matches(p: ParsedCron, dt: Date): boolean {
  return (
    fieldMatches(p.minute, dt.getMinutes()) &&
    fieldMatches(p.hour, dt.getHours()) &&
    fieldMatches(p.dom, dt.getDate()) &&
    fieldMatches(p.month, dt.getMonth() + 1) &&
    fieldMatches(p.dow, dt.getDay())
  )
}

/** 计算从 from 之后最近的一次触发时间（含 from 所在分钟之后）。 */
export function nextFire(expr: string, from: Date = new Date()): Date | null {
  let p: ParsedCron
  try {
    p = parseCron(expr)
  } catch {
    return null
  }
  const dt = new Date(from)
  dt.setSeconds(0, 0)
  dt.setMinutes(dt.getMinutes() + 1)
  // 最多扫描约一年（525960 分钟）
  for (let i = 0; i < 525960; i++) {
    if (matches(p, dt)) return new Date(dt)
    dt.setMinutes(dt.getMinutes() + 1)
  }
  return null
}

const DOW_NAMES = ['日', '一', '二', '三', '四', '五', '六']
const pad2 = (n: number) => String(n).padStart(2, '0')

function isAll(f: CronField): boolean {
  return f.type === 'all'
}

function dowText(values: number[]): string {
  const sorted = [...values].sort((a, b) => a - b)
  if (sorted.length === 5 && [1, 2, 3, 4, 5].every((d) => sorted.includes(d)))
    return '工作日（周一至周五）'
  if (sorted.length === 1) return '星期' + DOW_NAMES[sorted[0]]
  return '星期' + sorted.map((d) => DOW_NAMES[d]).join('、')
}

/** 生成人类可读的中文描述。 */
export function describeCron(expr: string): string {
  let p: ParsedCron
  try {
    p = parseCron(expr)
  } catch {
    return `自定义（${expr}）`
  }
  const { minute, hour, dom, month, dow } = p

  const allAll = isAll(minute) && isAll(hour) && isAll(dom) && isAll(month) && isAll(dow)
  if (allAll) return '每分钟'

  // 每 N 分钟
  if (
    minute.type === 'step' &&
    isAll(hour) && isAll(dom) && isAll(month) && isAll(dow)
  )
    return `每 ${minute.step} 分钟`

  // 每小时第 M 分
  if (
    minute.type === 'values' && minute.values.length === 1 &&
    isAll(hour) && isAll(dom) && isAll(month) && isAll(dow)
  )
    return minute.values[0] === 0 ? '每小时整点' : `每小时的第 ${minute.values[0]} 分`

  // 每天 HH:MM
  if (
    minute.type === 'values' && minute.values.length === 1 &&
    hour.type === 'values' && hour.values.length === 1 &&
    isAll(dom) && isAll(month) && isAll(dow)
  )
    return `每天 ${pad2(hour.values[0])}:${pad2(minute.values[0])}`

  // 每周 X HH:MM
  if (
    minute.type === 'values' && minute.values.length === 1 &&
    hour.type === 'values' && hour.values.length === 1 &&
    isAll(dom) && isAll(month) && dow.type === 'values'
  )
    return `每${dowText(dow.values)} ${pad2(hour.values[0])}:${pad2(minute.values[0])}`

  // 每月 D 号 HH:MM
  if (
    minute.type === 'values' && minute.values.length === 1 &&
    hour.type === 'values' && hour.values.length === 1 &&
    dom.type === 'values' && dom.values.length === 1 &&
    isAll(month) && isAll(dow)
  )
    return `每月 ${dom.values[0]} 号 ${pad2(hour.values[0])}:${pad2(minute.values[0])}`

  return `自定义（${expr}）`
}

export interface CronPreset {
  key: string
  label: string
  cron: string
}

/** 可视化构建器的快捷预设。 */
export const CRON_PRESETS: CronPreset[] = [
  { key: 'minutely', label: '每分钟', cron: '*/1 * * * *' },
  { key: 'hourly', label: '每小时', cron: '0 * * * *' },
  { key: 'daily9', label: '每天 09:00', cron: '0 9 * * *' },
  { key: 'weeklyMon9', label: '每周一 09:00', cron: '0 9 * * 1' },
  { key: 'monthly1', label: '每月 1 号 09:00', cron: '0 9 1 * *' },
  { key: 'weekday9', label: '工作日 09:00', cron: '0 9 * * 1-5' },
]
