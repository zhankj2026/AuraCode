---
name: loop
description: 按周期性间隔运行提示词或斜杠命令（如 /loop 5m /verify，默认 10m）
trigger: 用户主动调用 /loop
when_to_use: 当用户想设置周期性任务、轮询状态、或按间隔重复执行某操作时主动激活（如 "每5分钟检查部署"、"持续运行 /babysit-prs"）。不要用于一次性任务。
argument_hint: "[interval] <prompt>"
allowed_tools: cron_create, cron_delete, cron_list, run_command
---

# Loop: 周期性任务编排

将用户的自然语言间隔描述解析为 Cron 表达式，通过 `cron_create` 调度为周期性定时任务，并立即执行一次。

## 适用场景

- 定期检查服务状态 / 部署结果
- 周期性运行测试或 lint
- 持续轮询 PR 审查 / CI 结果
- 定时执行数据备份或清理
- 周期性 `/verify` 或 `/review`

## 用法

```
/loop [interval] <prompt>
```

**间隔格式**: `Ns`, `Nm`, `Nh`, `Nd`（如 `5m`, `30m`, `2h`, `1d`）。最小粒度 1 分钟。
**默认间隔**: 如果未指定间隔，默认为 `10m`。

## 解析规则（按优先级）

### 规则 1: 前导 token

如果第一个空格分隔的 token 匹配 `^\d+[smhd]$`（如 `5m`, `2h`），则该 token 为间隔，其余为 prompt。

示例:
- `5m /verify` → 间隔 `5m`，prompt `/verify`
- `30m check the deploy` → 间隔 `30m`，prompt `check the deploy`
- `2h run full test suite` → 间隔 `2h`，prompt `run full test suite`

### 规则 2: 尾部 "every" 子句

如果输入以 `every <N><unit>` 或 `every <N> <unit-word>` 结尾（如 `every 20m`, `every 5 minutes`, `every 2 hours`），提取为间隔并从 prompt 中移除。

**仅当 "every" 后跟时间表达式时匹配** — `check every PR` 不含间隔。

示例:
- `check the deploy every 20m` → 间隔 `20m`，prompt `check the deploy`
- `run tests every 5 minutes` → 间隔 `5m`，prompt `run tests`
- `check every PR` → 无间隔匹配 → 应用规则 3

### 规则 3: 默认间隔

如果以上规则都不匹配，间隔为 `10m`，整个输入为 prompt。

示例:
- `check the deploy` → 间隔 `10m`，prompt `check the deploy`
- `check every PR` → 间隔 `10m`，prompt `check every PR`

### 空 prompt

如果解析后 prompt 为空（如用户只输入 `5m`），输出用法提示并停止，不要调用 `cron_create`。

## 间隔 → Cron 表达式转换

支持的后缀: `s`（秒，向上取整到分钟，最小1）, `m`（分钟）, `h`（小时）, `d`（天）。

| 间隔模式 | Cron 表达式 | 说明 |
|----------|------------|------|
| `Nm` (N ≤ 59) | `*/N * * * *` | 每 N 分钟 |
| `Nm` (N ≥ 60) | `0 */H * * *` | 转为小时 (H = N/60, 需整除 24) |
| `Nh` (N ≤ 23) | `0 */N * * *` | 每 N 小时 |
| `Nd` | `0 0 */N * *` | 每 N 天午夜 |
| `Ns` | 视为 `ceil(N/60)m` | cron 最小粒度 1 分钟 |

**不整除处理**: 如果间隔不能整除其单位（如 `7m` → `*/7 * * * *` 在 :56→:00 间距不均；`90m` → 1.5h cron 无法表达），选择最接近的整洁间隔，并在调度前告知用户取整结果。

## 执行流程

### Step 1: 解析输入

1. 将 `$arguments`（用户传给 `/loop` 的参数）按上述规则解析为 `interval` + `prompt`
2. 如果 prompt 为空，输出用法并停止

### Step 2: 转换为 Cron 表达式

按转换表将 interval 转为标准 5 字段 cron 表达式。

### Step 3: 调度任务

调用 `cron_create` 工具:
- `cron`: 上一步的 cron 表达式
- `prompt`: 解析出的 prompt（斜杠命令原样传递）
- `recurring`: `true`
- `label`: `loop: <prompt 前 40 字符>`

### Step 4: 确认

简要告知用户:
- 调度了什么（prompt 摘要）
- Cron 表达式和人类可读的频率（如 "每 5 分钟"）
- 周期性任务 30 天后自动过期
- 可用 `cron_delete` 提前取消（附上 job_id）

### Step 5: 立即执行

**不要等第一次 cron 触发** — 立即执行解析出的 prompt:
- 如果是斜杠命令（以 `/` 开头），通过 `invoke_skill` 工具调用对应 skill
- 否则直接按 prompt 内容执行

## 示例对话

**用户**: `/loop 5m /verify`

**执行**:
1. 解析: 间隔 `5m`，prompt `/verify`
2. Cron: `*/5 * * * *`
3. 调用 `cron_create(cron="*/5 * * * *", prompt="/verify", recurring=true, label="loop: /verify")`
4. 确认: "已调度 /verify，每 5 分钟执行一次（Cron: `*/5 * * * *`）。30 天后自动过期，用 `cron_delete <job_id>` 提前取消。"
5. 立即执行 `/verify`

---

**用户**: `/loop check the deploy every 20m`

**执行**:
1. 解析: 间隔 `20m`，prompt `check the deploy`
2. Cron: `*/20 * * * *`
3. 调度 + 确认 + 立即执行

---

**用户**: `/loop run tests`

**执行**:
1. 解析: 无间隔 → 默认 `10m`，prompt `run tests`
2. Cron: `*/10 * * * *`
3. 调度 + 确认 + 立即执行

## 注意事项

1. **不要用于一次性任务** — 如果用户想执行一次，直接执行，不要创建 cron
2. **斜杠命令原样传递** — `/verify` 不要展开为 "验证代码"，保持 `/verify` 让 cron 调度器处理
3. **间隔最小 1 分钟** — cron 不支持秒级粒度，`30s` 应取整为 `1m`
4. **先调度后执行** — 确保 cron 已创建再立即执行，避免执行完就忘了
5. **告知过期和取消** — 用户需要知道任务不是永久的，以及如何取消
