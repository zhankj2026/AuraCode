import { useMemo } from 'react'
import type { FileDiff } from '../api/types'

type Row =
  | { kind: 'ctx'; left: string; right: string; lno: number; rno: number }
  | { kind: 'del'; left: string; lno: number }
  | { kind: 'add'; right: string; rno: number }

/**
 * 逐行 LCS diff（Myers 之外的经典 DP 实现）。输入两段文本，输出带行号的
 * 统一视图行序列：ctx/del/add。无第三方依赖，复杂度 O(n*m)，对 2000 行级文件够用。
 */
function diffLines(before: string, after: string): Row[] {
  const a = before.split('\n')
  const b = after.split('\n')
  const n = a.length
  const m = b.length
  // dp[i][j] = a[i..], b[j..] 的最长公共子序列长度
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const rows: Row[] = []
  let i = 0
  let j = 0
  let lno = 1
  let rno = 1
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      rows.push({ kind: 'ctx', left: a[i], right: b[j], lno: lno++, rno: rno++ })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      rows.push({ kind: 'del', left: a[i], lno: lno++ })
      i++
    } else {
      rows.push({ kind: 'add', right: b[j], rno: rno++ })
      j++
    }
  }
  while (i < n) rows.push({ kind: 'del', left: a[i], lno: lno++ })
  while (j < m) rows.push({ kind: 'add', right: b[j], rno: rno++ })
  return rows
}

function countChanges(rows: Row[]) {
  let add = 0
  let del = 0
  for (const r of rows) {
    if (r.kind === 'add') add++
    else if (r.kind === 'del') del++
  }
  return { add, del }
}

export function DiffModal({
  path,
  data,
  onClose,
  onOpenFile,
}: {
  path: string
  data: FileDiff
  onClose: () => void
  onOpenFile: (path: string, content: string) => void
}) {
  const rows = useMemo(() => diffLines(data.before, data.after), [data.before, data.after])
  const { add, del } = useMemo(() => countChanges(rows), [rows])

  return (
    <div className="mask show" onClick={onClose}>
      <div className="modal xl" onClick={(e) => e.stopPropagation()}>
        <div className="mh">
          <div className="ic" style={{ background: 'var(--accent)' }}>⊿</div>
          <div className="ti" style={{ flex: 1, minWidth: 0 }} title={path}>
            文件改动对比 · {path}
          </div>
          <span className="tag green">+{add}</span>
          <span className="tag red">−{del}</span>
          <span className="op" onClick={onClose} title="关闭">✕</span>
        </div>
        <div className="mb" style={{ padding: 0 }}>
          <div className="diffnote">
            {data.source === 'backup'
              ? '改前版本取自本会话工具自动生成的 .bak 备份（进入会话前的原始内容）'
              : '该文件无历史备份，按「全新文件」展示全部为新增'}
            {!data.after_exists && ' · 当前磁盘文件已被删除'}
          </div>
          <div className="diffbody">
            {rows.map((r, idx) => {
              if (r.kind === 'ctx') {
                return (
                  <div className="drow ctx" key={idx}>
                    <span className="dsign"> </span>
                    <span className="dold">{r.lno}</span>
                    <span className="dnew">{r.rno}</span>
                    <span className="dtext">{r.left}</span>
                  </div>
                )
              }
              if (r.kind === 'del') {
                return (
                  <div className="drow del" key={idx}>
                    <span className="dsign">−</span>
                    <span className="dold">{r.lno}</span>
                    <span className="dnew" />
                    <span className="dtext">{r.left}</span>
                  </div>
                )
              }
              return (
                <div className="drow add" key={idx}>
                  <span className="dsign">+</span>
                  <span className="dold" />
                  <span className="dnew">{r.rno}</span>
                  <span className="dtext">{r.right}</span>
                </div>
              )
            })}
          </div>
        </div>
        <div className="mf">
          <span style={{ color: 'var(--muted)', fontSize: 11.5 }}>
            统一视图 · 红=删除 绿=新增
          </span>
          <button
            className="btn"
            onClick={() => onOpenFile(path, data.after)}
            title="在编辑器中打开改后内容"
          >
            在编辑器中打开
          </button>
          <button className="btn ok" onClick={onClose}>
            关闭
          </button>
        </div>
      </div>
    </div>
  )
}
