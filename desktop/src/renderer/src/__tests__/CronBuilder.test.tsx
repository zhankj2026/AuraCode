import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CronBuilder } from '../components/CronBuilder'

describe('CronBuilder 可视化构建器', () => {
  it('默认（每天 09:00）渲染表达式与描述', () => {
    const onChange = vi.fn()
    render(<CronBuilder value="0 9 * * *" onChange={onChange} />)
    expect(screen.getByText('0 9 * * *')).toBeInTheDocument()
    expect(screen.getByText('每天 09:00', { selector: '.cron-desc' })).toBeInTheDocument()
  })

  it('点击预设 → 表达式与描述同步更新', () => {
    const onChange = vi.fn()
    render(<CronBuilder value="0 9 * * *" onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: '每周一 09:00' }))
    expect(onChange).toHaveBeenCalledWith('0 9 * * 1')
    expect(screen.getByText('0 9 * * 1')).toBeInTheDocument()
    expect(screen.getByText('每星期一 09:00')).toBeInTheDocument()
  })

  it('高级模式：非法表达式给出错误提示', () => {
    const onChange = vi.fn()
    render(<CronBuilder value="0 9 * * *" onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: '高级' }))
    const input = screen.getByLabelText('cron 表达式（高级）')
    fireEvent.change(input, { target: { value: 'xyz' } })
    expect(screen.getByText(/cron 表达式不合法/)).toBeInTheDocument()
  })

  it('高级模式：合法表达式更新描述', () => {
    const onChange = vi.fn()
    render(<CronBuilder value="0 9 * * *" onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: '高级' }))
    const input = screen.getByLabelText('cron 表达式（高级）')
    fireEvent.change(input, { target: { value: '0 9 * * 1-5' } })
    expect(screen.queryByText(/cron 表达式不合法/)).toBeNull()
    expect(screen.getByText('每工作日（周一至周五） 09:00')).toBeInTheDocument()
  })

  it('向导模式：切换频率为「周」出现星期选择', () => {
    const onChange = vi.fn()
    render(<CronBuilder value="0 9 * * *" onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: '周' }))
    expect(screen.getByText('星期')).toBeInTheDocument()
    // 默认勾选周一
    expect(onChange).toHaveBeenCalledWith('0 9 * * 1')
  })
})
