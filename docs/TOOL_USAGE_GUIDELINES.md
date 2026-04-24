# 工具使用指南

## 核心原则

**不要**在有相关专用工具时使用 `run_command` 执行对应操作。使用专用工具可以让用户更好地理解和审查你的工作。这对协助用户至关重要。

## 文件操作

| 操作 | 使用专用工具 ✅ | 避免使用 run_command ❌ |
|------|-----------------|----------------------|
| 读取文件 | `read_file` | `cat`, `head`, `tail`, `sed` |
| 写入文件 | `write_file` | `echo ... > file`, heredoc |
| 替换内容 | `replace_in_file` | `sed`, `awk` |
| 列出目录 | `list_directory` | `ls`, `dir` |
| 查找文件 | `find` | `find` 命令（虽然同名，但工具接口更友好） |
| 搜索内容 | `grep` | `grep`, `rg` 命令 |
| 分析代码 | `analyze_file` | 手动解析代码结构 |
| 代码检查 | `lint` | `ruff`, `eslint` 等直接命令 |
| 运行测试 | `run_tests` | `pytest`, `jest` 等直接命令 |
| 撤销编辑 | `undo_edit` | 手动恢复备份 |

## 代码操作

| 操作 | 使用专用工具 ✅ | 说明 |
|------|-----------------|------|
| 替换文本 | `replace_in_file` | 精确替换，支持预览，自动备份 |
| 静态分析 | `lint` | 支持 Python (ruff) 和 JavaScript (eslint) |
| 运行测试 | `run_tests` | 支持 pytest, jest, unittest，失败时自动重试 |
| 分析结构 | `analyze_file` | 分析 Python 文件的类/函数/导入 |

## 智能操作

| 操作 | 使用专用工具 ✅ | 说明 |
|------|-----------------|------|
| 创建子 Agent | `spawn_subagent` | 并行执行独立任务 |
| 规划任务 | `plan_agent` | 探索代码库并制定实现计划 |
| 激活技能 | `activate_skill` | 为特定任务注入专业知识 |
| 停用技能 | `deactivate_skill` | 移除不再需要的技能 |

## 记忆系统

| 操作 | 使用专用工具 ✅ | 说明 |
|------|-----------------|------|
| 保存记忆 | `save_memory` | 记录用户信息、反馈、项目信息等 |
| 加载记忆 | `load_memory` | 读取指定记忆的完整内容 |
| 列出记忆 | `list_memories` | 显示所有或特定类型的记忆 |
| 搜索记忆 | `search_memories` | 根据关键词搜索 |
| 相关记忆 | `get_relevant_memories` | 根据上下文智能获取相关记忆 |
| 删除记忆 | `delete_memory` | 删除指定记忆（不可逆） |
| 记忆摘要 | `get_memory_summary` | 获取所有记忆的概览 |

## 何时使用 run_command

`run_command` 应该保留给**真正需要 shell** 的场景：

### ✅ 适合使用 run_command 的场景

```python
# 1. Git 操作
run_command(command="git status")
run_command(command="git diff HEAD~1")

# 2. 包管理器
run_command(command="pip install -r requirements.txt")
run_command(command="npm install")

# 3. 系统操作
run_command(command="ps aux | grep python")
run_command(command="docker ps")

# 4. 复杂管道
run_command(command="cat file.txt | sort | uniq -c")

# 5. 需要环境变量
run_command(command="echo $PATH")

# 6. 交互式命令
run_command(command="python -i script.py")
```

### ❌ 不适合使用 run_command 的场景

```python
# 1. 读取文件 → 用 read_file
run_command(command="cat file.txt")  # ❌
read_file(file_path="file.txt")      # ✅

# 2. 写入文件 → 用 write_file
run_command(command="echo 'hello' > file.txt")  # ❌
write_file(file_path="file.txt", content="hello")  # ✅

# 3. 替换内容 → 用 replace_in_file
run_command(command="sed -i 's/foo/bar/g' file.txt")  # ❌
replace_in_file(file_path="file.txt", old="foo", new="bar")  # ✅

# 4. 列出目录 → 用 list_directory
run_command(command="ls -la")  # ❌
list_directory(path=".")       # ✅

# 5. 搜索文件 → 用 find 或 grep
run_command(command="find . -name '*.py'")  # ❌
find(path=".", pattern="*.py")              # ✅

# 6. 搜索内容 → 用 grep
run_command(command="grep -r 'TODO' src/")  # ❌
grep(pattern="TODO", path="src/")           # ✅

# 7. 运行测试 → 用 run_tests
run_command(command="pytest")  # ❌
run_tests(test_framework="pytest")  # ✅

# 8. 代码检查 → 用 lint
run_command(command="ruff check .")  # ❌
lint(tool="ruff", path=".")          # ✅
```

## 优势对比

### 专用工具的优势

1. **结构化输出** - 返回解析后的数据，不是原始文本
2. **跨平台兼容** - 自动处理 Windows/Linux 差异
3. **权限控制** - 可针对不同工具设置不同权限级别
4. **语义清晰** - 意图明确，易于审查
5. **错误处理** - 针对特定场景优化的错误信息
6. **自动功能** - 如 replace_in_file 自动备份、undo_edit 撤销等

### 示例：结构化输出对比

```python
# ❌ run_command - 原始文本
run_command(command="ls -la")
# 返回: "total 16\ndrwxr-xr-x 2 user group 4096 Jan 1 12:00 .\n..."
# 需要手动解析

# ✅ list_directory - 结构化数据
list_directory(path=".")
# 返回: {
#   "name": ".",
#   "type": "directory",
#   "children": [
#     {"name": "file.txt", "type": "file", "size": 1024},
#     ...
#   ]
# }
# 可直接使用
```

## 决策流程

当你需要执行操作时，按以下顺序思考：

```
1. 是否有专用工具？
   ├─ 有 → 使用专用工具
   └─ 没有 → 继续

2. 是否可以通过组合现有工具完成？
   ├─ 是 → 组合使用工具
   └─ 否 → 继续

3. 是否真正需要 shell 能力？
   ├─ 是（如管道、环境变量、Git等） → 使用 run_command
   └─ 否 → 考虑是否应该实现新的专用工具
```

## 完整工具列表

系统当前提供的所有工具：

### 文件操作
- `read_file` - 读取文件
- `write_file` - 写入文件
- `replace_in_file` - 替换文件内容
- `undo_edit` - 撤销编辑
- `list_directory` - 列出目录
- `find` - 查找文件
- `grep` - 搜索文件内容
- `analyze_file` - 分析代码结构

### 开发工具
- `lint` - 静态代码分析
- `run_tests` - 运行测试套件
- `run_command` - 执行 Shell 命令

### AI 能力
- `spawn_subagent` - 创建子 Agent
- `plan_agent` - 规划 Agent
- `join_subagent` - 等待子 Agent 完成

### 技能系统
- `activate_skill` - 激活技能
- `deactivate_skill` - 停用技能
- `list_skills` - 列出技能
- `show_available_skills` - 显示技能详情
- `get_active_skills` - 获取已激活技能

### 记忆系统
- `save_memory` - 保存记忆
- `load_memory` - 加载记忆
- `list_memories` - 列出记忆
- `search_memories` - 搜索记忆
- `delete_memory` - 删除记忆
- `get_memory_summary` - 获取记忆摘要
- `get_relevant_memories` - 获取相关记忆

### 工具管理
- `edit_history` - 查看编辑历史
- `list_subagents` - 列出子 Agent
- `subagent_stats` - 获取子 Agent 统计
