# 快速开始指南

## 🚀 5分钟运行第一个示例

### 1. 安装依赖

```bash
cd opencode
pip install -r requirements.txt
```

### 2. 配置 API 密钥

#### 选项 A: 使用 OpenAI

```bash
# Linux/Mac
export OPENAI_API_KEY="sk-your-api-key"

# Windows PowerShell
$env:OPENAI_API_KEY="sk-your-api-key"
```

#### 选项 B: 使用智谱 GLM (推荐)

```bash
# Linux/Mac
export OPENAI_API_KEY="your-zhipu-api-key"
export OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"

# Windows PowerShell
$env:OPENAI_API_KEY="your-zhipu-api-key"
$env:OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
```

**获取 GLM API Key**: https://open.bigmodel.cn/

### 3. 运行测试

```bash
# 测试 1: 简单对话 (使用 GLM-4)
python cli.py --model glm-4-plus "你好,请介绍一下自己"

# 测试 2: 列出目录
python cli.py --model glm-4-plus "列出当前目录的文件"

# 测试 3: 读取文件
python cli.py --model glm-4-plus "读取 README.md 的内容"

# 测试 4: 使用 bypass 模式(无需确认)
python cli.py --model glm-4-plus --mode bypass "列出当前目录"
```

**常用 GLM 模型**:
- `glm-4-plus` - 最强性能(推荐)
- `glm-4` - 标准版
- `glm-4-air` - 快速响应
- `glm-4-flash` - 超快速度

### 4. 预期输出

```
🚀 Claude Code Python MVP
   Model: gpt-4o
   Permission Mode: normal
   Max Iterations: 20

============================================================

🤖 Assistant: 我来帮你列出当前目录的文件。

✅ Tool Result: 目录: /path/to/opencode

📁 子目录:
  core/
  tools/
  ...

📄 文件:
  cli.py
  README.md
  ...

============================================================

✅ 任务完成
```

---

## 📋 可用命令

### 基本用法

```bash
# 直接传入指令
python cli.py "你的指令"

# 交互式输入
python cli.py
> 你的指令
```

### 权限模式

```bash
# normal 模式(默认) - 写入和命令需确认
python cli.py --mode normal "创建文件"

# auto 模式 - 文件操作自动批准,命令需确认
python cli.py --mode auto "批量修改文件"

# plan 模式 - 禁止所有修改,仅分析
python cli.py --mode plan "分析代码结构"

# bypass 模式 - 完全跳过检查(慎用!)
python cli.py --mode bypass "执行任务"
```

### 其他参数

```bash
# 指定模型 (GLM)
python cli.py --model glm-4-plus "你的指令"
python cli.py --model glm-4-air "快速任务"

# 指定模型 (OpenAI)
python cli.py --model gpt-4o "你的指令"
python cli.py --model gpt-3.5-turbo "你的指令"

# 限制迭代次数
python cli.py --max-iterations 5 "你的指令"
```

---

## 🔧 常见问题

### Q1: 提示 "未设置 OPENAI_API_KEY"

**解决:**
```bash
export OPENAI_API_KEY="sk-your-api-key"
```

### Q2: 工具执行需要确认

**解决:** 使用 `--mode bypass` 或 `--mode auto`:
```bash
python cli.py --mode bypass "创建文件"
```

### Q3: 达到最大迭代次数

**解决:** 增加迭代次数或简化任务:
```bash
python cli.py --max-iterations 30 "复杂任务"
```

### Q4: 如何查看日志?

**解决:** 修改 `cli.py` 中的日志级别:
```python
logging.basicConfig(level=logging.DEBUG)  # 查看详细日志
```

---

## 📚 下一步

- 阅读 [README.md](README.md) 了解项目概况
- 查看 [docs/](docs/) 目录下的架构文档
- 参考 [PROGRESS.md](PROGRESS.md) 了解实施进度

---

**祝使用愉快!** 🎉
