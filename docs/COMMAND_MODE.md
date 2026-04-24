# CLI 命令模式文档

## 概述

cli.py 现在支持两种模式：
1. **对话模式**: 与 AI 进行自然语言交互
2. **命令模式**: 直接执行预定义命令

## 命令模式

### 基本语法

```bash
python cli.py --command <command> [args...]
```

### 可用命令

#### 1. analyze - 分析代码

分析代码文件或目录的结构。

```bash
# 分析单个文件
python cli.py --command analyze cli.py

# 分析目录
python cli.py --command analyze .

# 分析特定目录
python cli.py --command analyze core/
```

**输出**:
- 文件统计信息
- 类和函数列表
- 导入模块
- 代码结构分析

#### 2. test - 运行测试

运行项目测试。

```bash
# 运行当前目录的测试
python cli.py --command test

# 运行指定目录的测试
python cli.py --command test tests/
```

**输出**:
- 测试发现
- 测试执行结果
- 失败测试详情

#### 3. lint - 代码检查

对代码进行静态分析。

```bash
# 检查当前目录
python cli.py --command lint

# 检查指定目录
python cli.py --command lint core/
```

**输出**:
- 代码质量问题
- 潜在 bug
- 风格建议

#### 4. skills - 技能管理

管理 AI 技能系统。

```bash
# 列出所有可用技能
python cli.py --command skills list

# 激活技能
python cli.py --command skills activate python-standards

# 停用技能
python cli.py --command skills deactivate python-standards

# 显示已激活的技能
python cli.py --command skills active
```

**可用技能**:
- `python-standards`: Python 编码规范和最佳实践
- `git-workflow`: Git 工作流和提交规范

#### 5. plugins - 插件信息

显示已加载的插件和钩子。

```bash
python cli.py --command plugins
```

**输出**:
- 已加载的插件列表
- 已注册的钩子列表

#### 6. status - 系统状态

显示系统整体状态。

```bash
python cli.py --command status
```

**输出**:
- 插件系统状态
- 钩子系统状态
- 技能系统状态
- 工具总数
- Subagent 状态

#### 7. subagents - Subagent 管理

管理并行任务执行。

```bash
# 显示 Subagent 概览
python cli.py --command subagents

# 列出所有 Subagent
python cli.py --command subagents list

# 显示统计信息
python cli.py --command subagents stats
```

#### 8. help - 显示帮助

显示命令帮助信息。

```bash
python cli.py --command help
```

## 对话模式

### 基本语法

```bash
# 交互式输入
python cli.py

# 命令行输入
python cli.py "帮我分析这个项目"

# 指定模型
python cli.py "重构代码" --model glm-4-plus
```

### 权限模式

```bash
# normal: 正常模式（默认）
python cli.py "执行命令" --mode normal

# auto: 自动模式（自动允许）
python cli.py "执行命令" --mode auto

# plan: 计划模式（只读）
python cli.py "分析代码" --mode plan

# bypass: 绕过模式（无限制）
python cli.py "执行操作" --mode bypass
```

## 常用场景

### 场景 1: 代码分析

```bash
# 使用命令模式快速分析
python cli.py --command analyze .

# 使用对话模式深度分析
python cli.py "分析这个项目的架构，找出潜在问题"
```

### 场景 2: 质量检查

```bash
# 先 lint 检查
python cli.py --command lint

# 再运行测试
python cli.py --command test

# 最后让 AI 提供改进建议
python cli.py --mode skills activate python-standards
python cli.py "根据检查结果，提供代码改进建议"
```

### 场景 3: Git 提交

```bash
# 激活 Git 工作流技能
python cli.py --command skills activate git-workflow

# 生成提交信息
python cli.py "根据当前修改生成符合规范的提交信息"
```

### 场景 4: 项目重构

```bash
# 1. 激活相关技能
python cli.py --command skills activate python-standards

# 2. 分析代码
python cli.py --command analyze core/

# 3. 执行重构
python cli.py "重构 core/agent_loop.py，遵循 PEP 8 规范"
```

## 高级用法

### 组合命令

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="your-key"; python cli.py --command status

# Linux/Mac
OPENAI_API_KEY="your-key" python cli.py --command status
```

### 批处理

```bash
# 创建批处理脚本 analyze.bat
@echo off
python cli.py --command analyze .
python cli.py --command lint
python cli.py --command test
```

### 别名设置

```bash
# Linux/Mac - 添加到 ~/.bashrc
alias ai-status='python cli.py --command status'
alias ai-analyze='python cli.py --command analyze'
alias ai-test='python cli.py --command test'

# 使用
ai-status
ai-analyze .
```

## 输出说明

### 成功执行
```
✅ 命令执行成功
```

### 失败执行
```
❌ 命令执行失败: 错误原因
```

### 系统状态图标
- ✅ 启用/成功
- ❌ 禁用/失败
- 🔄 运行中
- 📊 状态信息
- 🔍 搜索/分析
- 🧪 测试
- 🔌 插件
- 🤖 AI/Subagent
- 📖 帮助

## 故障排除

### 问题: 命令不识别

```bash
# 查看可用命令
python cli.py --command help
```

### 问题: API Key 错误

```bash
# 检查环境变量
echo $OPENAI_API_KEY  # Linux/Mac
echo $env:OPENAI_API_KEY  # Windows PowerShell
```

### 问题: 模型不可用

```bash
# 尝试其他模型
python cli.py "测试" --model glm-4-plus
python cli.py "测试" --model glm-4-air
```

## 最佳实践

1. **开发前**: 使用 `analyze` 了解项目结构
2. **编码时**: 激活 `python-standards` 技能
3. **提交前**: 使用 `lint` 和 `test` 检查
4. **调试时**: 使用 `status` 查看系统状态
5. **协作时**: 激活 `git-workflow` 技能

---

**相关文档**:
- [使用指南](USAGE_GUIDE.md)
- [技能系统](SKILL_FINAL_DESIGN.md)
- [README](../README.md)
