import { describe, expect, it } from 'vitest'
import { AUDIT_EVENT_TYPES, buildAuditTurns, fmtDuration, parseArgsBrief } from '../lib/audit'

let seq = 0
const ev = (type: string, data: any, timestamp: number, session_id = 's1') => ({
  event_id: `e${++seq}`,
  type,
  session_id,
  data,
  timestamp,
})

describe('buildAuditTurns 轮次分组', () => {
  it('完整一轮：用户消息 + 工具调用配对 + 助手预览 + 轮耗时', () => {
    const turns = buildAuditTurns([
      ev('user_message', { content: '修复登录 bug' }, 100),
      ev('turn_start', { turn: 1 }, 101),
      ev('tool_execute', { tool_name: 'read_file', arguments: '{"path":"a.py"}' }, 102),
      ev('tool_complete', {
        tool_name: 'read_file',
        arguments: '{"path":"a.py"}',
        success: true,
        result: { char_count: 120, line_count: 5 },
        error: '',
      }, 103.5),
      ev('turn_complete', { turn: 1, content_preview: '已修复', tool_calls: 1 }, 105),
    ])
    expect(turns).toHaveLength(1)
    const t = turns[0]
    expect(t.turnNo).toBe(1)
    expect(t.userPrompt).toBe('修复登录 bug')
    expect(t.preview).toBe('已修复')
    expect(t.endTs).toBe(105)
    expect(t.entries).toHaveLength(1)
    const tool = t.entries[0]
    expect(tool.kind).toBe('tool')
    expect(tool.status).toBe('success')
    expect(tool.duration).toBeCloseTo(1.5)
    expect(tool.detail.map((d) => d.label)).toEqual(['参数', '结果'])
  })

  it('失败工具：status=fail 且带错误明细段', () => {
    const turns = buildAuditTurns([
      ev('turn_start', { turn: 1 }, 1),
      ev('tool_execute', { tool_name: 'read_file', arguments: '{"path":"x"}' }, 2),
      ev('tool_complete', {
        tool_name: 'read_file',
        arguments: '{"path":"x"}',
        success: false,
        result: {},
        error: 'FS_NOT_REGULAR_FILE',
      }, 3),
      ev('turn_complete', { turn: 1, content_preview: '', tool_calls: 1 }, 4),
    ])
    const tool = turns[0].entries[0]
    expect(tool.status).toBe('fail')
    const errSec = tool.detail.find((d) => d.label === '错误')
    expect(errSec?.text).toBe('FS_NOT_REGULAR_FILE')
    expect(errSec?.tone).toBe('err')
    // 空结果元数据不生成"结果"段
    expect(tool.detail.map((d) => d.label)).toEqual(['参数', '错误'])
  })

  it('同名多工具并行：按逆序就近配对，互不串扰', () => {
    const turns = buildAuditTurns([
      ev('turn_start', { turn: 1 }, 1),
      ev('tool_execute', { tool_name: 'read_file', arguments: '{"path":"a"}' }, 2),
      ev('tool_execute', { tool_name: 'read_file', arguments: '{"path":"b"}' }, 3),
      ev('tool_complete', { tool_name: 'read_file', arguments: '{"path":"a"}', success: true, result: { char_count: 1 }, error: '' }, 4),
      ev('tool_complete', { tool_name: 'read_file', arguments: '{"path":"b"}', success: true, result: { char_count: 2 }, error: '' }, 5),
      ev('turn_complete', { turn: 1, content_preview: '', tool_calls: 2 }, 6),
    ])
    const tools = turns[0].entries
    expect(tools).toHaveLength(2)
    expect(tools.every((t) => t.status === 'success')).toBe(true)
    // 参数段区分两条：第一条配对的是先发起的 a（结果 char_count=1）
    expect(tools[0].detail[0].text).toContain('"a"')
    expect(tools[1].detail[0].text).toContain('"b"')
  })

  it('tool_complete 无匹配 running 条目时自建完成条目（历史回放缺 tool_execute 的场景）', () => {
    const turns = buildAuditTurns([
      ev('turn_start', { turn: 1 }, 1),
      ev('tool_complete', { tool_name: 'grep', arguments: '{"q":"x"}', success: true, result: { match_count: 3 }, error: '' }, 2),
      ev('turn_complete', { turn: 1, content_preview: '', tool_calls: 1 }, 3),
    ])
    expect(turns[0].entries).toHaveLength(1)
    expect(turns[0].entries[0].status).toBe('success')
    expect(turns[0].entries[0].detail[0].label).toBe('参数')
  })

  it('多轮对话：轮次号、用户提示词归属正确', () => {
    const turns = buildAuditTurns([
      ev('user_message', { content: '第一问' }, 1),
      ev('turn_start', { turn: 1 }, 2),
      ev('tool_execute', { tool_name: 'list_dir', arguments: '{}' }, 3),
      ev('tool_complete', { tool_name: 'list_dir', arguments: '{}', success: true, result: { file_count: 2 }, error: '' }, 4),
      ev('turn_complete', { turn: 1, content_preview: '答一', tool_calls: 1 }, 5),
      ev('user_message', { content: '第二问' }, 6),
      ev('turn_start', { turn: 2 }, 7),
      ev('turn_complete', { turn: 2, content_preview: '答二', tool_calls: 0 }, 8),
    ])
    expect(turns).toHaveLength(2)
    expect(turns[0].turnNo).toBe(1)
    expect(turns[0].userPrompt).toBe('第一问')
    expect(turns[1].turnNo).toBe(2)
    expect(turns[1].userPrompt).toBe('第二问')
    expect(turns[1].entries).toHaveLength(0)
  })

  it('权限/错误/重试/cron 等系统事件进对应轮次', () => {
    const turns = buildAuditTurns([
      ev('user_message', { content: '跑命令' }, 1),
      ev('turn_start', { turn: 1 }, 2),
      ev('permission_request', { tool_name: 'run_command', description: '执行 npm test' }, 3),
      ev('permission_response', { behavior: 'allow', message: '' }, 4),
      ev('tool_execute', { tool_name: 'run_command', arguments: '{"cmd":"npm test"}' }, 5),
      ev('tool_complete', { tool_name: 'run_command', arguments: '{"cmd":"npm test"}', success: false, result: {}, error: 'exit 1' }, 6),
      ev('api_retry', { attempt: 1, max_retries: 5, error: 'rate limit' }, 7),
      ev('cron_triggered', { job_id: 'j1', label: '日报' }, 8),
      ev('cron_completed', { job_id: 'j1', success: false, error: 'boom' }, 9),
      ev('session_error', { error: 'interrupted' }, 10),
    ])
    expect(turns).toHaveLength(1)
    const kinds = turns[0].entries.map((e) => e.kind)
    expect(kinds).toEqual(['perm', 'perm', 'tool', 'system', 'cron', 'cron', 'error'])
    expect(turns[0].entries[3].title).toContain('API 重试')
    expect(turns[0].entries[5].status).toBe('fail')
  })

  it('仅会话级事件（无 turn_start）也成组展示', () => {
    const turns = buildAuditTurns([
      ev('cron_triggered', { job_id: 'j9', label: '孤任务' }, 1),
      ev('cron_completed', { job_id: 'j9', success: true, summary: 'done' }, 2),
    ])
    expect(turns).toHaveLength(1)
    expect(turns[0].turnNo).toBeNull()
    expect(turns[0].userPrompt).toBe('')
    expect(turns[0].entries).toHaveLength(2)
  })

  it('turn_complete 后紧跟 turn_start 不会丢轮或产生空组', () => {
    const turns = buildAuditTurns([
      ev('turn_start', { turn: 1 }, 1),
      ev('turn_complete', { turn: 1, content_preview: 'a', tool_calls: 0 }, 2),
      ev('turn_start', { turn: 2 }, 3),
      ev('turn_complete', { turn: 2, content_preview: 'b', tool_calls: 0 }, 4),
    ])
    expect(turns).toHaveLength(2)
    expect(turns.map((t) => t.turnNo)).toEqual([1, 2])
  })
})

describe('辅助函数', () => {
  it('parseArgsBrief：合法 JSON 美化，截断串原样', () => {
    expect(parseArgsBrief('{"a":1}')).toBe('{\n  "a": 1\n}')
    expect(parseArgsBrief('{"a":1')).toBe('{"a":1')
    expect(parseArgsBrief(null)).toBe('')
    expect(parseArgsBrief({ a: 1 })).toBe('{\n  "a": 1\n}')
  })

  it('fmtDuration 分段展示', () => {
    expect(fmtDuration(0.05)).toBe('50ms')
    expect(fmtDuration(1.5)).toBe('1.5s')
    expect(fmtDuration(125)).toBe('2m5s')
  })

  it('AUDIT_EVENT_TYPES 覆盖工具/轮次/权限/错误事件', () => {
    for (const t of ['turn_start', 'tool_execute', 'tool_complete', 'user_message', 'session_error']) {
      expect(AUDIT_EVENT_TYPES).toContain(t)
    }
  })
})
