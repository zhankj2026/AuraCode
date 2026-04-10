# OpenCode 使用指南

**版本**: 1.0  
**日期**: 2026-04-06  
**状态**: ✅ Phase 0-6 全部完成 (16个工具)

---

## 快速开始

### 1. 环境准备

```bash
# 进入 opencode 目录
cd opencode

# 安装依赖
pip install -r requirements.txt
```

### 2. 运行 CLI

```bash
# 启动交互式会话
python cli.py

# 或直接提问
python cli.py "分析当前项目的代码结构"
```

---

## 工具列表 (16个)

### 📂 文件操作工具 (4个)

#### 1. `read_file` - 读取文件
```python
read_file(file_path="src/main.py", start_line=1, end_line=50)
```

**参数**:
- `file_path` (必需): 文件路径
- `start_line` (可选): 起始行号,默认 1
- `end_line` (可选): 结束行号,默认到文件末尾

**示例**:
```
读取整个文件:
read_file(file_path="config.yaml")

读取指定行:
read_file(file_path="main.py", start_line=10, end_line=30)
```

---

#### 2. `write_file` - 写入文件
```python
write_file(file_path="output.txt", content="Hello World", mode="overwrite")
```

**参数**:
- `file_path` (必需): 文件路径
- `content` (必需): 文件内容
- `mode` (可选): `overwrite`(覆盖) 或 `append`(追加),默认 `overwrite`

**示例**:
```
创建新文件:
write_file(file_path="README.md", content="# 项目说明")

追加内容:
write_file(file_path="log.txt", content="新日志", mode="append")
```

---

#### 3. `list_directory` - 列出目录
```python
list_directory(dir_path="src/", recursive=False)
```

**参数**:
- `dir_path` (必需): 目录路径
- `recursive` (可选): 是否递归,默认 `False`

**示例**:
```
列出当前目录:
list_directory(dir_path=".")

递归列出所有文件:
list_directory(dir_path="src/", recursive=True)
```

---

#### 4. `run_command` - 执行命令
```python
run_command(command="python --version", timeout=30)
```

**参数**:
- `command` (必需): 要执行的命令
- `timeout` (可选): 超时时间(秒),默认 30

**示例**:
```
查看 Python 版本:
run_command(command="python --version")

运行测试:
run_command(command="pytest tests/", timeout=60)

安装依赖:
run_command(command="pip install requests", timeout=120)
```

**权限**: 需要用户确认 (execute 级别)

---

### 🔍 代码搜索工具 (4个)

#### 5. `grep` - 内容搜索
```python
grep(pattern="def login", path="src/", case_sensitive=True)
```

**参数**:
- `pattern` (必需): 搜索模式(支持正则)
- `path` (可选): 搜索路径,默认当前目录
- `case_sensitive` (可选): 是否区分大小写,默认 `True`

**示例**:
```
搜索函数定义:
grep(pattern="def \\w+", path="src/")

搜索类名:
grep(pattern="class \\w+", path="src/models/")

不区分大小写搜索:
grep(pattern="error", case_sensitive=False)
```

---

#### 6. `find` - 文件查找
```python
find(pattern="*.py", path="src/", file_type="file")
```

**参数**:
- `pattern` (必需): 文件名模式
- `path` (可选): 搜索路径
- `file_type` (可选): `file`/`directory`/`all`,默认 `file`

**示例**:
```
查找所有 Python 文件:
find(pattern="*.py", path="src/")

查找所有目录:
find(pattern="test*", file_type="directory")
```

---

#### 7. `analyze_file` - 文件分析
```python
analyze_file(file_path="src/main.py")
```

**参数**:
- `file_path` (必需): 文件路径

**返回**:
- 文件统计信息(行数、字符数)
- 代码结构(函数、类、导入)
- 复杂度分析

**示例**:
```
分析 Python 文件:
analyze_file(file_path="src/main.py")

分析 TypeScript 文件:
analyze_file(file_path="src/components/App.tsx")
```

---

#### 8. `search_web` - 网络搜索
```python
search_web(query="Python async best practices", num_results=5)
```

**参数**:
- `query` (必需): 搜索查询
- `num_results` (可选): 结果数量,默认 5

---

### ✏️ 代码编辑工具 (4个)

#### 9. `replace_in_file` - 替换文件内容
```python
replace_in_file(
    file_path="src/main.py",
    old_text="def old_function():",
    new_text="def new_function():"
)
```

**参数**:
- `file_path` (必需): 文件路径
- `old_text` (必需): 要替换的文本
- `new_text` (必需): 新文本

**示例**:
```
重命名函数:
replace_in_file(
    file_path="src/utils.py",
    old_text="def calc(x, y):",
    new_text="def calculate(x, y):"
)

修改逻辑:
replace_in_file(
    file_path="src/main.py",
    old_text="if x > 0:",
    new_text="if x >= 0:"
)
```

**安全特性**:
- 自动备份原文件到 `.backup/` 目录
- 显示差异预览
- 支持撤销 (undo_edit)

---

#### 10. `undo_edit` - 撤销编辑
```python
undo_edit(file_path="src/main.py")
```

**参数**:
- `file_path` (必需): 文件路径

**示例**:
```
撤销最后一次编辑:
undo_edit(file_path="src/main.py")

查看编辑历史:
undo_edit(file_path="src/main.py", show_history=True)
```

---

#### 11. `fetch_url` - 获取网页内容
```python
fetch_url(url="https://api.github.com/repos/user/repo")
```

**参数**:
- `url` (必需): 网页 URL

---

### 🔧 代码验证工具 (4个)

#### 12. `lint` - 代码检查
```python
lint(file_path="src/main.py", linter="flake8")
```

**参数**:
- `file_path` (必需): 文件路径
- `linter` (可选): 检查工具,默认 `flake8`

**示例**:
```
Python 代码检查:
lint(file_path="src/main.py", linter="flake8")

TypeScript 代码检查:
lint(file_path="src/app.ts", linter="eslint")
```

---

#### 13. `run_tests` - 运行测试
```python
run_tests(test_path="tests/", framework="pytest")
```

**参数**:
- `test_path` (必需): 测试路径
- `framework` (可选): 测试框架,默认 `pytest`

**示例**:
```
运行所有测试:
run_tests(test_path="tests/")

运行特定测试文件:
run_tests(test_path="tests/test_main.py")

使用 unittest:
run_tests(test_path="tests/", framework="unittest")
```

---

### 🤖 高级工具 (4个 - Phase 6)

#### 14. `spawn_subagent` - 创建并行子Agent
```python
spawn_subagent(task="分析 src/ 目录下的所有模块", model="glm-4-plus")
```

**参数**:
- `task` (必需): 任务描述
- `model` (可选): 使用的模型,默认 `glm-4-plus`
- `run_in_background` (可选): 是否后台运行,默认 `True`

**示例**:
```
后台运行(推荐):
spawn_subagent(
    task="分析代码库的依赖关系",
    run_in_background=True
)
# 返回: ✅ Subagent 已启动 (ID: abc12345)

同步运行(等待完成):
spawn_subagent(
    task="生成项目文档",
    run_in_background=False
)
# 返回: 完整结果
```

**并行任务示例**:
```python
# 启动多个并行任务
handle1 = spawn_subagent(task="分析模块 A")
handle2 = spawn_subagent(task="分析模块 B")
handle3 = spawn_subagent(task="分析模块 C")

# 稍后获取结果
result1 = join_subagent(agent_id="handle1的ID")
result2 = join_subagent(agent_id="handle2的ID")
result3 = join_subagent(agent_id="handle3的ID")
```

---

#### 15. `join_subagent` - 获取子Agent结果
```python
join_subagent(agent_id="abc12345", timeout=60)
```

**参数**:
- `agent_id` (必需): Agent ID
- `timeout` (可选): 超时时间(秒),默认无限等待

**示例**:
```
等待完成并获取结果:
result = join_subagent(agent_id="abc12345")

设置超时:
result = join_subagent(agent_id="abc12345", timeout=120)
```

---

#### 16. `list_subagents` - 列出所有子Agent
```python
list_subagents(status="running")
```

**参数**:
- `status` (可选): 过滤状态 (`running`/`completed`/`failed`)

**示例**:
```
列出所有:
list_subagents()

只看运行中的:
list_subagents(status="running")

查看已完成的:
list_subagents(status="completed")
```

**额外工具**: `subagent_stats` - 查看统计信息

---

## 完整工作流示例

### 场景 1: 代码重构

```
用户: "将 src/utils.py 中的 calc 函数重命名为 calculate,并更新所有引用"

AI 执行:
1. analyze_file(file_path="src/utils.py")
   → 分析函数结构

2. grep(pattern="calc", path="src/")
   → 找到所有引用位置

3. replace_in_file(
       file_path="src/utils.py",
       old_text="def calc(x, y):",
       new_text="def calculate(x, y):"
   )
   → 更新定义

4. 对每个引用文件执行 replace_in_file
   → 更新所有调用处

5. run_tests(test_path="tests/")
   → 验证没有破坏功能
```

---

### 场景 2: 并行代码分析

```
用户: "分析 src/ 目录下的所有模块并生成报告"

AI 执行:
1. list_directory(dir_path="src/", recursive=True)
   → 找到所有模块

2. 并行启动分析任务:
   spawn_subagent(task="分析 src/auth/ 模块")
   spawn_subagent(task="分析 src/api/ 模块")
   spawn_subagent(task="分析 src/models/ 模块")
   spawn_subagent(task="分析 src/utils/ 模块")

3. list_subagents(status="running")
   → 查看进度

4. 等待完成后获取结果:
   join_subagent(agent_id="...")
   join_subagent(agent_id="...")
   ...

5. 汇总所有结果生成完整报告
```

---

### 场景 3: Bug 修复

```
用户: "修复登录功能的超时问题"

AI 执行:
1. grep(pattern="def login", path="src/")
   → 定位登录函数

2. read_file(file_path="src/auth/login.py")
   → 阅读代码

3. grep(pattern="timeout", path="src/auth/")
   → 查找超时相关代码

4. analyze_file(file_path="src/auth/login.py")
   → 分析代码结构

5. replace_in_file(...)
   → 修复问题

6. lint(file_path="src/auth/login.py")
   → 代码检查

7. run_tests(test_path="tests/test_auth.py")
   → 运行测试验证
```

---

## 权限系统

工具分为 3 个权限级别:

### 🟢 `read` - 只读操作
- 无需用户确认,直接执行
- 工具: `read_file`, `list_directory`, `grep`, `find`, `analyze_file` 等

### 🟡 `write` - 写操作
- 可能需要确认(取决于配置)
- 工具: `write_file`, `replace_in_file`, `undo_edit`

### 🔴 `execute` - 执行操作
- **必须**用户确认
- 工具: `run_command`, `spawn_subagent`

---

## 配置

### 配置文件: `.opencode/config.yaml`

```yaml
# LLM 配置
model: "glm-4-plus"
max_iterations: 20

# 权限模式
permission_mode: "auto"  # auto/deny/accept

# Subagent 配置
subagent:
  max_concurrent: 5  # 最大并发数

# 工具配置
tools:
  lint:
    default_linter: "flake8"
  tests:
    default_framework: "pytest"
```

---

## 最佳实践

### ✅ 推荐做法

1. **并行任务使用 Subagent**
   ```python
   # 好: 并行执行
   spawn_subagent(task="分析模块 A")
   spawn_subagent(task="分析模块 B")
   ```

2. **编辑前先备份**
   ```python
   # replace_in_file 自动备份到 .backup/
   ```

3. **修改后运行测试**
   ```python
   replace_in_file(...)
   run_tests(test_path="tests/")  # 验证
   ```

4. **使用 grep 定位,再精确编辑**
   ```python
   grep(pattern="old_function")
   replace_in_file(file_path="...")
   ```

### ❌ 避免做法

1. **不要直接写大文件**
   ```python
   # 不好: 一次性写 1000 行
   write_file(file_path="big.py", content="...1000行...")
   
   # 好: 分步骤创建
   write_file(file_path="big.py", content="# 第一部分")
   replace_in_file(file_path="big.py", old_text="...", new_text="...")
   ```

2. **不要在同步模式启动太多任务**
   ```python
   # 不好: 顺序执行,很慢
   spawn_subagent(task="A", run_in_background=False)
   spawn_subagent(task="B", run_in_background=False)
   
   # 好: 并行执行
   spawn_subagent(task="A")
   spawn_subagent(task="B")
   join_subagent(agent_id="A的ID")
   join_subagent(agent_id="B的ID")
   ```

---

## 测试

运行测试套件:

```bash
# 运行所有测试
python test_phase6_tools.py

# 运行特定 Phase 测试
python test_phase1_tools.py
python test_phase2_tools.py
python test_phase3_tools.py
```

---

## 故障排除

### 问题: Subagent 卡住

```python
# 查看运行中的任务
list_subagents(status="running")

# 设置超时获取结果
join_subagent(agent_id="xxx", timeout=60)

# 查看统计
subagent_stats()
```

### 问题: 编辑失败

```python
# 查看错误信息
# → 通常是 old_text 不匹配

# 先读取文件确认内容
read_file(file_path="...")

# 撤销失败的编辑
undo_edit(file_path="...")
```

### 问题: 权限拒绝

```python
# 检查权限模式
# → 在配置中设置 permission_mode: "auto"

# 或手动确认 execute 级别的工具调用
```

---

## 下一步

- 查看 `docs/code.md` 了解完整架构
- 查看各 Phase 的测试文件了解详细用法
- 根据需求扩展新工具

---

**文档版本**: 1.0  
**最后更新**: 2026-04-06  
**工具总数**: 16 个  
**系统状态**: ✅ L4 能力层级 (完整)
