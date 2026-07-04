# 定时任务调度（Loop 特性）

AuraCode 提供基于 Cron 调度的周期性任务编排系统，支持自然语言间隔解析和立即执行。

---

## 概述

Loop 特性允许用户设置周期性执行的任务，适用于：

- 定期检查服务状态 / 部署结果
- 周期性运行测试或 lint
- 持续轮询 PR 审查 / CI 结果
- 定时执行数据备份或清理
- 周期性 `/verify` 或 `/review`

---

## 基本用法

```
/loop [interval] <prompt>
```

**参数说明**：
- `interval`（可选）：执行间隔，格式为 `Ns`, `Nm`, `Nh`, `Nd`
- `prompt`：要执行的提示词或斜杠命令

**默认值**：如果未指定间隔，默认为 `10m`（10 分钟）

---

## 间隔解析规则

AuraCode 使用三级优先级规则解析用户输入：

### 规则 1: 前导 Token

如果第一个空格分隔的 token 匹配 `^\d+[smhd]$`（如 `5m`, `2h`），则该 token 为间隔。

**示例**：
- `5m /verify` → 间隔 `5m`，prompt `/verify`
- `30m check the deploy` → 间隔 `30m`，prompt `check the deploy`
- `2h run full test suite` → 间隔 `2h`，prompt `run full test suite`

### 规则 2: 尾部 "every" 子句

如果输入以 `every <N><unit>` 或 `every <N> <unit-word>` 结尾，提取为间隔。

**示例**：
- `check the deploy every 20m` → 间隔 `20m`，prompt `check the deploy`
- `run tests every 5 minutes` → 间隔 `5m`，prompt `run tests`
- `check every PR` → 无间隔匹配（`every` 后不是时间表达式）

### 规则 3: 默认间隔

如果以上规则都不匹配，间隔为 `10m`，整个输入为 prompt。

**示例**：
- `check the deploy` → 间隔 `10m`，prompt `check the deploy`
- `check every PR` → 间隔 `10m`，prompt `check every PR`

---

## Cron 表达式转换

支持的间隔后缀：
- `s`（秒）— 向上取整到分钟，最小 1 分钟
- `m`（分钟）
- `h`（小时）
- `d`（天）

### 转换表

| 间隔格式 | Cron 表达式 | 说明 |
|----------|------------|------|
| `Nm` (N ≤ 59) | `*/N * * * *` | 每 N 分钟 |
| `Nm` (N ≥ 60) | `0 */H * * *` | 转为小时 (H = N/60) |
| `Nh` (N ≤ 23) | `0 */N * * *` | 每 N 小时 |
| `Nd` | `0 0 */N * *` | 每 N 天午夜 |
| `Ns` | 视为 `ceil(N/60)m` | 秒级取整到分钟 |

### 不整除处理

如果间隔不能整除其单位（如 `7m` → `*/7 * * * *`），选择最接近的整洁间隔，并在调度前告知用户。

---

## 执行流程

### Step 1: 解析输入

1. 将用户输入解析为 `interval` + `prompt`
2. 如果 prompt 为空，输出用法并停止

### Step 2: 转换为 Cron 表达式

按转换表将 interval 转为标准 5 字段 cron 表达式。

### Step 3: 调度任务

调用 `cron_create` 工具：
- `cron`: cron 表达式
- `prompt`: 解析出的 prompt
- `recurring`: `true`
- `label`: `loop: <prompt 前 40 字符>`

### Step 4: 确认

告知用户：
- 调度了什么（prompt 摘要）
- Cron 表达式和人类可读的频率
- 30 天后自动过期
- 如何取消（`cron_delete <job_id>`）

### Step 5: 立即执行

**不等第一次 cron 触发**，立即执行解析出的 prompt：
- 如果是斜杠命令（以 `/` 开头），调用对应 skill
- 否则直接按 prompt 内容执行

---

## 使用示例

### 示例 1: 周期性验证

```
用户: /loop 5m /verify

执行:
1. 解析: 间隔 5m，prompt /verify
2. Cron: */5 * * * *
3. 调度任务
4. 确认: "已调度 /verify，每 5 分钟执行一次"
5. 立即执行 /verify
```

### 示例 2: 自然语言间隔

```
用户: /loop check the deploy every 20m

执行:
1. 解析: 间隔 20m，prompt check the deploy
2. Cron: */20 * * * *
3. 调度 + 确认 + 立即执行
```

### 示例 3: 默认间隔

```
用户: /loop run tests

执行:
1. 解析: 无间隔 → 默认 10m
2. Cron: */10 * * * *
3. 调度 + 确认 + 立即执行
```

---

## 管理定时任务

### 查看所有任务

```
/cron
```

输出示例：
```
活跃的定时任务:
1. [job_abc123] loop: /verify
   Cron: */5 * * * *
   下次执行: 2026-06-02 15:30
   创建时间: 2026-06-02 14:00
   
2. [job_def456] loop: check deploy
   Cron: */20 * * * *
   下次执行: 2026-06-02 15:40
```

### 取消任务

```
/cron delete <job_id>
```

示例：
```
/cron delete job_abc123
```

---

## 注意事项

1. **不要用于一次性任务** — 一次性任务直接执行，不要创建 cron
2. **斜杠命令原样传递** — `/verify` 保持原样，让 cron 调度器处理
3. **间隔最小 1 分钟** — cron 不支持秒级粒度，`30s` 应取整为 `1m`
4. **先调度后执行** — 确保 cron 已创建再立即执行
5. **30 天自动过期** — 周期性任务不是永久的，到期后自动停止

---

## 相关工具

- `cron_create` — 创建定时任务
- `cron_delete` — 删除定时任务
- `cron_list` — 列出所有定时任务

---

## 参见

- [命令参考](../commands.md) — 查看所有可用命令
- [技能系统](../skills.md) — 了解技能如何工作
- [动态工作流](batch-workflow.md) — 大规模并行变更编排
