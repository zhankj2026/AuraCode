import { describe, it, expect } from 'vitest'
import {
  validateCron,
  describeCron,
  nextFire,
  parseCron,
} from '../lib/cronUtils'

describe('cronUtils 解析与校验', () => {
  it('合法表达式通过校验', () => {
    expect(validateCron('0 9 * * *')).toBe(true)
    expect(validateCron('*/5 * * * *')).toBe(true)
    expect(validateCron('0 9 * * 1-5')).toBe(true)
    expect(validateCron('30 8 1,15 * 0')).toBe(true)
  })

  it('非法表达式被拒绝', () => {
    expect(validateCron('bad')).toBe(false)
    expect(validateCron('* * * *')).toBe(false) // 只有 4 字段
    expect(validateCron('99 9 * * *')).toBe(false) // 分钟越界
    expect(validateCron('0 9 * * 9')).toBe(false) // 星期越界
  })

  it('parseCron 正确解析字段', () => {
    const p = parseCron('5,10 8-9 * * 1')
    expect(p.minute).toEqual({ type: 'values', values: [5, 10] })
    expect(p.hour).toEqual({ type: 'values', values: [8, 9] })
    expect(p.dow).toEqual({ type: 'values', values: [1] })
  })
})

describe('describeCron 人类可读描述', () => {
  it('覆盖常见模式', () => {
    expect(describeCron('* * * * *')).toBe('每分钟')
    expect(describeCron('*/5 * * * *')).toBe('每 5 分钟')
    expect(describeCron('0 * * * *')).toBe('每小时整点')
    expect(describeCron('30 * * * *')).toBe('每小时的第 30 分')
    expect(describeCron('0 9 * * *')).toBe('每天 09:00')
    expect(describeCron('0 9 * * 1')).toBe('每星期一 09:00')
    expect(describeCron('0 9 * * 1-5')).toBe('每工作日（周一至周五） 09:00')
    expect(describeCron('0 9 1 * *')).toBe('每月 1 号 09:00')
    expect(describeCron('15 14 1,15 * 0')).toBe('自定义（15 14 1,15 * 0）')
  })
})

describe('nextFire 下次触发时间', () => {
  it('当天未到 → 当天触发', () => {
    const from = new Date(2026, 0, 1, 8, 0, 0) // 1 月 1 日 08:00
    const nf = nextFire('0 9 * * *', from)!
    expect(nf.getFullYear()).toBe(2026)
    expect(nf.getMonth()).toBe(0)
    expect(nf.getDate()).toBe(1)
    expect(nf.getHours()).toBe(9)
    expect(nf.getMinutes()).toBe(0)
  })

  it('当天已过 → 次日触发', () => {
    const from = new Date(2026, 0, 1, 10, 0, 0)
    const nf = nextFire('0 9 * * *', from)!
    expect(nf.getDate()).toBe(2)
    expect(nf.getHours()).toBe(9)
  })

  it('按星期过滤', () => {
    // 2026-01-01 是周四，0 9 * * 5（周五）→ 下一个周五是 1 月 2 日
    const from = new Date(2026, 0, 1, 8, 0, 0)
    const nf = nextFire('0 9 * * 5', from)!
    expect(nf.getDate()).toBe(2)
    expect(nf.getDay()).toBe(5)
    expect(nf.getHours()).toBe(9)
  })

  it('非法表达式返回 null', () => {
    expect(nextFire('bad', new Date())).toBeNull()
  })
})
