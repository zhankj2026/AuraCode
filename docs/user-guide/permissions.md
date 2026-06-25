# 权限管理

AuraCode 提供四级权限模式，通过参数级 allow/deny 规则精确控制 AI 的操作边界。

---

## 权限模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `normal` | 默认模式 — 危险操作需用户确认 | 日常开发 |
| `auto` | 自动模式 — 自动批准安全操作 | 信任环境/CI |
| `plan` | 计划模式 — 只读分析，不执行修改 | 代码审查/调研 |
| `bypass` | 绕过模式 — 跳过所有权限检查 | 调试/测试 |

### 切换模式

```bash
# 启动时指定
python cli.py --mode auto

# 运行时切换
> /permissions mode auto
```

---

## 规则配置

规则格式为 `工具名:参数模式`，支持通配符 `*`。

### config.yaml

```yaml
permissions:
  mode: normal
  allow_rules:
    - "read_file:*"          # 允许读取所有文件
    - "run_command:git *"    # 允许所有 git 命令
    - "write_file:src/*"     # 只允许写 src/ 下的文件
  deny_rules:
    - "run_command:rm -rf"   # 禁止危险删除
    - "run_command:sudo *"   # 禁止 sudo
    - "write_file:*.env"     # 禁止修改环境变量文件
```

### 运行时管理

```
> /permissions

当前模式: normal

Allow 规则:
  ✅ read_file:*
  ✅ run_command:git *
  ✅ write_file:src/*

Deny 规则:
  ❌ run_command:rm -rf
  ❌ run_command:sudo *
  ❌ write_file:*.env
```

```
# 添加规则
> /permissions add allow "run_command:npm *"

# 移除规则
> /permissions remove deny "write_file:*.env"
```

---

## 规则匹配优先级

当 allow 和 deny 规则冲突时，**deny 优先**：

```
allow: "run_command:*"      # 允许所有命令
deny:  "run_command:rm *"   # 但禁止 rm 命令

→ run_command: ls         ✅ 匹配 allow
→ run_command: rm file    ❌ 匹配 deny（deny 优先）
```

---

## 危险操作确认

在 `normal` 模式下，以下操作会弹出确认提示：

- 执行 Shell 命令（`run_command`）
- 写入文件（`write_file`、`replace_in_file`）
- 删除文件

```
⚠️  权限确认

  工具: run_command
  参数: rm -rf build/

  当前无匹配的 allow 规则，是否允许?
  [y] 允许  [n] 拒绝  [a] 本次会话始终允许此操作
```

---

## 相关命令

| 命令 | 说明 |
|------|------|
| `/permissions` | 查看当前权限配置 |
| `/permissions mode <mode>` | 切换权限模式 |
| `/permissions add allow <rule>` | 添加 allow 规则 |
| `/permissions add deny <rule>` | 添加 deny 规则 |
| `/permissions remove allow <rule>` | 移除 allow 规则 |
| `/permissions remove deny <rule>` | 移除 deny 规则 |
