# 智谱 GLM 模型配置指南

Claude Code Python MVP 已支持智谱 AI 的 GLM 系列模型,使用 OpenAI 兼容的 API 接口。

---

## 🚀 快速开始

### 1. 获取 API Key

访问智谱 AI 开放平台: https://open.bigmodel.cn/

1. 注册/登录账号
2. 进入"API Keys"页面
3. 创建新的 API Key
4. 复制保存(只显示一次)

### 2. 配置环境变量

#### Windows PowerShell

```powershell
$env:OPENAI_API_KEY="your-zhipu-api-key"
$env:OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
```

#### Linux/Mac

```bash
export OPENAI_API_KEY="your-zhipu-api-key"
export OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
```

### 3. 运行测试

```bash
python cli.py --model glm-4-plus "你好,请介绍一下自己"
```

---

## 📋 可用模型

| 模型 | 特点 | 适用场景 | 价格 |
|------|------|----------|------|
| **glm-4-plus** | 最强性能 | 复杂任务、代码生成 | ¥0.1/1K tokens |
| **glm-4** | 标准版 | 通用任务 | ¥0.05/1K tokens |
| **glm-4-air** | 快速响应 | 日常对话、简单任务 | ¥0.01/1K tokens |
| **glm-4-flash** | 超快速度 | 高并发、实时应用 | ¥0.001/1K tokens |

**推荐**: 开发阶段使用 `glm-4-plus`,测试时使用 `glm-4-air` 节省成本。

---

## 🔧 配置方式

### 方式 1: 环境变量(推荐)

```bash
# 临时设置(当前会话)
$env:OPENAI_API_KEY="your-key"
$env:OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"

# 永久设置(添加到系统环境变量)
# Windows: 系统属性 → 高级 → 环境变量
# Linux/Mac: 添加到 ~/.bashrc 或 ~/.zshrc
```

### 方式 2: CLI 参数

```bash
python cli.py \
  --model glm-4-plus \
  "你的指令"
```

### 方式 3: 配置文件

编辑 `config.yaml`:

```yaml
llm:
  provider: openai
  model: glm-4-plus
  base_url: https://open.bigmodel.cn/api/paas/v4
  api_key: "your-zhipu-api-key"
```

---

## 💰 价格参考

**GLM-4-Plus** (2026年价格):
- 输入: ¥0.05 / 1K tokens
- 输出: ¥0.1 / 1K tokens

**示例成本**:
- 简单对话 (~1K tokens): ¥0.15
- 代码分析 (~10K tokens): ¥1.5
- 复杂任务 (~50K tokens): ¥7.5

**省钱技巧**:
1. 开发测试使用 `glm-4-air` 或 `glm-4-flash`
2. 设置 `--max-iterations 5` 限制迭代次数
3. 使用 `--mode plan` 仅分析不执行

---

## ⚙️ 高级配置

### 调整温度参数

```python
# 在 core/agent_loop.py 中修改
response = self.client.chat.completions.create(
    model=self.model,
    messages=self.messages,
    tools=self.tools,
    temperature=0.2,  # 降低创造性,提高准确性
    max_tokens=4096
)
```

**温度建议**:
- `0.0-0.3`: 代码生成、事实查询
- `0.4-0.7`: 创意写作、头脑风暴
- `0.8-1.0`: 诗歌、故事创作

### 设置最大 Token

```bash
# CLI 参数
python cli.py --model glm-4-plus --max-tokens 8192 "长任务"
```

或在代码中修改 `max_tokens` 参数。

---

## 🔍 常见问题

### Q1: 提示 "Invalid API Key"

**原因**: API Key 错误或未设置

**解决**:
```bash
# 检查是否设置
echo $env:OPENAI_API_KEY  # Windows
echo $OPENAI_API_KEY      # Linux/Mac

# 重新设置
$env:OPENAI_API_KEY="your-correct-key"
```

### Q2: 提示 "Connection timeout"

**原因**: 网络连接问题

**解决**:
1. 检查网络连接
2. 确认 `OPENAI_BASE_URL` 设置为 `https://open.bigmodel.cn/api/paas/v4`
3. 尝试使用代理

### Q3: 响应速度慢

**原因**: 模型选择或网络延迟

**解决**:
1. 使用更快的模型: `glm-4-air` 或 `glm-4-flash`
2. 检查网络延迟
3. 减少 `max_tokens` 参数

### Q4: 如何查看 Token 使用量?

**方法**: 查看日志输出

```
INFO - Token usage: prompt=1234, completion=567, total=1801
```

或在智谱 AI 控制台查看用量统计。

---

## 📊 性能对比

| 指标 | GLM-4-Plus | GPT-4o | 说明 |
|------|------------|--------|------|
| 中文理解 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | GLM 对中文优化更好 |
| 代码生成 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | GPT-4o 略优 |
| 响应速度 | ⭐⭐⭐⭐ | ⭐⭐⭐ | GLM 国内访问更快 |
| 价格 | ⭐⭐⭐⭐⭐ | ⭐⭐ | GLM 更便宜 |
| 工具调用 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 两者都支持良好 |

**结论**: 
- 中文任务 → GLM-4-Plus
- 英文任务 → GPT-4o
- 成本敏感 → GLM-4-Air

---

## 🎯 最佳实践

### 1. 开发环境

```bash
# 使用 GLM-4-Plus,正常模式
$env:OPENAI_API_KEY="your-key"
$env:OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"

python cli.py --model glm-4-plus "你的任务"
```

### 2. 测试环境

```bash
# 使用 GLM-4-Air,bypass 模式
python cli.py --model glm-4-air --mode bypass "测试任务"
```

### 3. 生产环境

```bash
# 使用 GLM-4,auto 模式
python cli.py --model glm-4 --mode auto "生产任务"
```

---

## 🔗 相关链接

- **智谱 AI 官网**: https://www.zhipuai.cn/
- **开放平台**: https://open.bigmodel.cn/
- **API 文档**: https://open.bigmodel.cn/dev/api
- **价格详情**: https://open.bigmodel.cn/pricing
- **技术支持**: https://open.bigmodel.cn/support

---

## 📝 更新日志

- **2026-04-05**: 初始版本,支持 GLM-4 系列模型
- 默认模型改为 `glm-4-plus`
- 添加 GLM 配置指南

---

**祝使用愉快!** 🚀
