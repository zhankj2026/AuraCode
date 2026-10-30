import { useEffect, useState } from 'react'
import {
  CRON_PRESETS,
  describeCron,
  nextFire,
  validateCron,
} from '../lib/cronUtils'

export type WizardFreq = 'minute' | 'hour' | 'day' | 'week' | 'month'

export interface WizardState {
  freq: WizardFreq
  step: number // 分钟频率：每 N 分钟
  minute: number // 小时/天/周/月：第几分钟
  hour: number // 天/周/月：小时
  dom: number // 月：几号
  dows: number[] // 周：星期集合（0=周日 … 6=周六）
}

const DEFAULT_WIZ: WizardState = {
  freq: 'day',
  step: 1,
  minute: 0,
  hour: 9,
  dom: 1,
  dows: [1],
}

function buildCron(w: WizardState): string {
  switch (w.freq) {
    case 'minute':
      return `*/${w.step} * * * *`
    case 'hour':
      return `${w.minute} * * * *`
    case 'day':
      return `${w.minute} ${w.hour} * * *`
    case 'week':
      return `${w.minute} ${w.hour} * * ${[...w.dows].sort((a, b) => a - b).join(',')}`
    case 'month':
      return `${w.minute} ${w.hour} ${w.dom} * *`
  }
}

const PRESET_WIZ: Record<string, WizardState> = {
  minutely: { freq: 'minute', step: 1, minute: 0, hour: 9, dom: 1, dows: [1] },
  hourly: { freq: 'hour', step: 1, minute: 0, hour: 9, dom: 1, dows: [1] },
  daily9: { freq: 'day', step: 1, minute: 0, hour: 9, dom: 1, dows: [1] },
  weeklyMon9: { freq: 'week', step: 1, minute: 0, hour: 9, dom: 1, dows: [1] },
  monthly1: { freq: 'month', step: 1, minute: 0, hour: 9, dom: 1, dows: [1] },
  weekday9: { freq: 'week', step: 1, minute: 0, hour: 9, dom: 1, dows: [1, 2, 3, 4, 5] },
}

const DOW_LABELS = ['日', '一', '二', '三', '四', '五', '六']
const pad2 = (n: number) => String(n).padStart(2, '0')

interface Props {
  value: string
  onChange: (cron: string) => void
  disabled?: boolean
}

export function CronBuilder({ value, onChange, disabled }: Props) {
  const [mode, setMode] = useState<'wizard' | 'advanced'>('wizard')
  const [wiz, setWiz] = useState<WizardState>(DEFAULT_WIZ)
  const [custom, setCustom] = useState(value)

  // 当前生效表达式：向导模式由 wiz 推导，高级模式用 custom
  const effective = mode === 'advanced' ? custom.trim() : buildCron(wiz)

  useEffect(() => {
    if (effective !== value) onChange(effective)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effective])

  const activePreset = CRON_PRESETS.find((p) => p.cron === value)?.key
  const valid = validateCron(effective)
  const desc = describeCron(effective)
  const nf = valid ? nextFire(effective) : null
  const nextStr = nf
    ? nf
        .toLocaleString('zh-CN', { hour12: false })
        .replace(/\//g, '-')
        .replace(',', '')
    : '表达式无效'

  const setWizField = (patch: Partial<WizardState>) =>
    setWiz((w) => ({ ...w, ...patch }))

  const toggleDow = (d: number) =>
    setWiz((w) => ({
      ...w,
      dows: w.dows.includes(d) ? w.dows.filter((x) => x !== d) : [...w.dows, d],
    }))

  const pickPreset = (key: string) => {
    const w = PRESET_WIZ[key]
    if (w) {
      setWiz(w)
      setMode('wizard')
    }
  }

  const switchToAdvanced = () => {
    setCustom(effective)
    setMode('advanced')
  }

  return (
    <div className="cron-builder">
      {/* 快捷预设 */}
      <div className="cron-presets">
        {CRON_PRESETS.map((p) => (
          <button
            key={p.key}
            type="button"
            className={`cron-chip ${activePreset === p.key ? 'on' : ''}`}
            disabled={disabled}
            onClick={() => pickPreset(p.key)}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* 模式切换 */}
      <div className="cron-modeseg">
        <button
          type="button"
          className={mode === 'wizard' ? 'on' : ''}
          disabled={disabled}
          onClick={() => setMode('wizard')}
        >
          向导
        </button>
        <button
          type="button"
          className={mode === 'advanced' ? 'on' : ''}
          disabled={disabled}
          onClick={switchToAdvanced}
        >
          高级
        </button>
      </div>

      {mode === 'wizard' ? (
        <div className="cron-wiz">
          <div className="cron-freq">
            {(['minute', 'hour', 'day', 'week', 'month'] as WizardFreq[]).map((f) => (
              <button
                key={f}
                type="button"
                className={wiz.freq === f ? 'on' : ''}
                disabled={disabled}
                onClick={() => setWizField({ freq: f })}
              >
                {f === 'minute' ? '分钟' : f === 'hour' ? '小时' : f === 'day' ? '天' : f === 'week' ? '周' : '月'}
              </button>
            ))}
          </div>

          <div className="cron-ctl">
            {wiz.freq === 'minute' && (
              <label>
                每
                <input
                  className="inp mini"
                  type="number"
                  min={1}
                  max={59}
                  value={wiz.step}
                  disabled={disabled}
                  onChange={(e) => setWizField({ step: clamp(+e.target.value, 1, 59) })}
                />
                分钟
              </label>
            )}

            {wiz.freq === 'hour' && (
              <label>
                每小时的第
                <select
                  className="inp mini"
                  value={wiz.minute}
                  disabled={disabled}
                  onChange={(e) => setWizField({ minute: +e.target.value })}
                >
                  {Array.from({ length: 60 }, (_, i) => (
                    <option key={i} value={i}>
                      {pad2(i)} 分
                    </option>
                  ))}
                </select>
              </label>
            )}

            {(wiz.freq === 'day' || wiz.freq === 'week' || wiz.freq === 'month') && (
              <>
                <label>
                  时间
                  <select
                    className="inp mini"
                    value={wiz.hour}
                    disabled={disabled}
                    onChange={(e) => setWizField({ hour: +e.target.value })}
                  >
                    {Array.from({ length: 24 }, (_, i) => (
                      <option key={i} value={i}>
                        {pad2(i)} 时
                      </option>
                    ))}
                  </select>
                  <select
                    className="inp mini"
                    value={wiz.minute}
                    disabled={disabled}
                    onChange={(e) => setWizField({ minute: +e.target.value })}
                  >
                    {Array.from({ length: 60 }, (_, i) => (
                      <option key={i} value={i}>
                        {pad2(i)} 分
                      </option>
                    ))}
                  </select>
                </label>

                {wiz.freq === 'week' && (
                  <div className="cron-dows">
                    星期
                    {DOW_LABELS.map((lab, d) => (
                      <button
                        key={d}
                        type="button"
                        className={`cron-dow ${wiz.dows.includes(d) ? 'on' : ''}`}
                        disabled={disabled || (wiz.dows.length === 1 && wiz.dows.includes(d))}
                        onClick={() => toggleDow(d)}
                      >
                        {lab}
                      </button>
                    ))}
                  </div>
                )}

                {wiz.freq === 'month' && (
                  <label>
                    每月
                    <input
                      className="inp mini"
                      type="number"
                      min={1}
                      max={31}
                      value={wiz.dom}
                      disabled={disabled}
                      onChange={(e) => setWizField({ dom: clamp(+e.target.value, 1, 31) })}
                    />
                    号
                  </label>
                )}
              </>
            )}
          </div>
        </div>
      ) : (
        <div className="cron-advanced">
          <input
            className={`inp ${valid ? '' : 'err'}`}
            aria-label="cron 表达式（高级）"
            value={custom}
            disabled={disabled}
            placeholder="例如：0 9 * * 1-5"
            onChange={(e) => setCustom(e.target.value)}
          />
          {!valid && <div className="cron-err">cron 表达式不合法，需为 5 字段：分 时 日 月 周</div>}
        </div>
      )}

      {/* 实时预览 */}
      <div className="cron-preview">
        <div className="cron-expr">
          <span className="k">表达式</span>
          <code>{effective}</code>
        </div>
        <div className="cron-desc">{desc}</div>
        <div className="cron-next">
          <span className="k">下次触发</span>
          <span className={valid ? '' : 'bad'}>{nextStr}</span>
        </div>
      </div>
    </div>
  )
}

function clamp(n: number, lo: number, hi: number): number {
  if (!Number.isFinite(n)) return lo
  return Math.min(hi, Math.max(lo, n))
}
