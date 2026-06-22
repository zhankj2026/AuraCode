"""
编程式内置 Skill 注册入口

通过 SkillManager.register_programmatic_skill() 注册需要运行时
动态生成 prompt 的 Skill。与声明式 SKILL.md 并存。

当前内置编程式 Skill:
- api-dev: 语言检测 + API 开发辅助（对标 Claude Code claudeApi.ts）
- lorem-ipsum: 长上下文测试填充（对标 Claude Code loremIpsum.ts）
"""

import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 语言检测器（对标 Claude Code claudeApi.ts detectLanguage）
# ═══════════════════════════════════════════════════════════

LANGUAGE_INDICATORS: Dict[str, List[str]] = {
    "python":     [".py", "requirements.txt", "pyproject.toml", "setup.py", "Pipfile", "poetry.lock"],
    "typescript": [".ts", ".tsx", "tsconfig.json", "package.json"],
    "javascript": [".js", ".jsx", "package.json"],
    "java":       [".java", "pom.xml", "build.gradle"],
    "go":         [".go", "go.mod"],
    "rust":       [".rs", "Cargo.toml"],
    "ruby":       [".rb", "Gemfile"],
    "csharp":     [".cs", ".csproj"],
    "php":        [".php", "composer.json"],
}

# 各语言的 API 开发核心指南（精简版，实际使用 web_fetch 获取最新文档）
API_GUIDELINES: Dict[str, str] = {
    "python": """### Python SDK 核心用法

```python
# 安装: pip install anthropic
import anthropic

client = anthropic.Anthropic()  # 自动读取 ANTHROPIC_API_KEY

# 基础调用
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello, Claude"}]
)
print(message.content[0].text)

# 流式调用
with client.messages.stream(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}]
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)

# 工具调用
tools = [{"name": "get_weather", "description": "Get weather",
          "input_schema": {"type": "object",
                          "properties": {"city": {"type": "string"}}}}]
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "Weather in NYC?"}]
)
```

**关键概念:**
- `messages.create()` — 单次调用
- `messages.stream()` — 流式输出（上下文管理器）
- `tools` 参数 — 函数调用/工具使用
- `system` 参数 — 系统提示
- Prompt Caching — 通过 `cache_control` 字段缓存重复内容
""",
    "typescript": """### TypeScript SDK 核心用法

```typescript
// 安装: npm install @anthropic-ai/sdk
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();  // 自动读取 ANTHROPIC_API_KEY

// 基础调用
const message = await client.messages.create({
  model: 'claude-sonnet-4-20250514',
  max_tokens: 1024,
  messages: [{ role: 'user', content: 'Hello, Claude' }],
});
console.log(message.content[0].text);

// 流式调用
const stream = client.messages.stream({
  model: 'claude-sonnet-4-20250514',
  max_tokens: 1024,
  messages: [{ role: 'user', content: 'Hello' }],
});
for await (const event of stream) {
  if (event.type === 'content_block_delta') {
    process.stdout.write(event.delta.text);
  }
}

// 工具调用
const tools = [{ name: 'get_weather', description: 'Get weather',
  input_schema: { type: 'object',
    properties: { city: { type: 'string' } } } }];
```

**关键概念:**
- `messages.create()` — 单次调用
- `messages.stream()` — 流式输出（AsyncIterable）
- `tools` 参数 — 函数调用/工具使用
- `system` 参数 — 系统提示
- Prompt Caching — 通过 `cache_control` 字段
""",
    "go": """### Go SDK 核心用法

```go
// 安装: go get github.com/anthropics/anthropic-sdk-go
import "github.com/anthropics/anthropic-sdk-go"

client := anthropic.NewClient()  // 自动读取 ANTHROPIC_API_KEY

message, err := client.Messages.New(ctx, anthropic.MessageNewParams{
    Model:     anthropic.F(anthropic.ModelClaudeSonnet420250514),
    MaxTokens: anthropic.F(int64(1024)),
    Messages: anthropic.F([]anthropic.MessageParam{
        anthropic.NewUserMessage(anthropic.NewTextBlock("Hello")),
    }),
})
```
""",
}

# 通用 API 概念（所有语言共享）
SHARED_API_GUIDE = """
## 通用 API 概念

### 消息结构
- `role: "user"` — 用户消息
- `role: "assistant"` — 模型回复
- `role: "system"` (或顶层 `system` 参数) — 系统提示

### 核心参数
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `model` | 模型选择 | 按需选择 |
| `max_tokens` | 最大输出 token | 1024 |
| `temperature` | 随机性 (0-1) | 1.0 |
| `top_p` | 核采样 | 1.0 |
| `top_k` | Top-K 采样 | -1 (关闭) |

### 流式响应事件
- `message_start` — 消息开始
- `content_block_start` — 内容块开始
- `content_block_delta` — 增量文本
- `content_block_stop` — 内容块结束
- `message_delta` — 消息级元数据
- `message_stop` — 消息结束

### Prompt Caching（降低成本）
- 在 messages 的 content block 中添加 `cache_control: {"type": "ephemeral"}`
- 缓存有效期: 5 分钟
- 缓存命中时输入 token 费用降低 90%

### 工具使用（Function Calling）
1. 定义 `tools` 数组（name + description + input_schema）
2. 发送请求，模型返回 `tool_use` content block
3. 执行工具，将结果作为 `tool_result` 消息发回
4. 模型基于工具结果继续推理

### 最佳实践
- 系统提示放在最前面，定义模型角色和约束
- 使用结构化输出要求明确的 JSON schema
- 长对话定期压缩上下文
- 错误处理: 捕获 `APIError`, `RateLimitError`, `APIStatusError`
"""


def _detect_project_language(cwd: str = None) -> Optional[str]:
    """
    检测当前项目的主要编程语言。

    扫描工作目录的文件扩展名和配置文件，返回最可能使用的语言。
    """
    if cwd is None:
        cwd = os.getcwd()

    try:
        entries = os.listdir(cwd)
    except OSError:
        return None

    for lang, indicators in LANGUAGE_INDICATORS.items():
        for indicator in indicators:
            if indicator.startswith('.'):
                # 文件扩展名: 检查是否有匹配的文件
                if any(e.endswith(indicator) for e in entries):
                    return lang
            else:
                # 配置文件名: 精确匹配
                if indicator in entries:
                    return lang
    return None


# ═══════════════════════════════════════════════════════════
# api-dev Skill prompt 生成器
# ═══════════════════════════════════════════════════════════

def _api_dev_prompt(args: str) -> str:
    """
    api-dev skill 的 prompt 生成函数。

    运行时检测项目语言，注入对应语言的 SDK 指南。
    """
    lang = _detect_project_language()
    lang_label = lang or "unknown"

    sections = [
        "# API Development Assistant",
        "",
        f"**Detected project language:** {lang_label}",
        "",
        "You are helping the user build applications with the Claude API / Anthropic SDK.",
        "Provide language-specific code examples, best practices, and troubleshooting.",
    ]

    # 注入语言特定指南
    if lang and lang in API_GUIDELINES:
        sections.append("")
        sections.append(API_GUIDELINES[lang])
    elif lang == "java":
        sections.append("")
        sections.append("""### Java SDK 核心用法

```java
// Maven: com.anthropic:anthropic-java
import com.anthropic.client.AnthropicClient;
import com.anthropic.client.AnthropicClientImpl;

AnthropicClient client = new AnthropicClientImpl();
// 使用 client.messages().create(...) 调用 API
```
""")
    elif lang == "rust":
        sections.append("")
        sections.append("""### Rust SDK 核心用法

```rust
// Cargo.toml: anthropic = "0.1"
use anthropic::{Client, Message};

let client = Client::new();  // 读取 ANTHROPIC_API_KEY
let response = client.messages().create(...)
    .await?;
```
""")
    elif lang == "ruby":
        sections.append("")
        sections.append("""### Ruby SDK 核心用法

```ruby
# gem install anthropic
require 'anthropic'

client = Anthropic::Client.new(api_key: ENV['ANTHROPIC_API_KEY'])
response = client.messages.create(
  model: 'claude-sonnet-4-20250514',
  max_tokens: 1024,
  messages: [{ role: 'user', content: 'Hello' }]
)
```
""")
    elif lang == "csharp":
        sections.append("")
        sections.append("""### C# SDK 核心用法

```csharp
// NuGet: Anthropic.SDK
using Anthropic.SDK;

var client = new AnthropicClient();
var response = await client.Messages.CreateAsync(new MessageRequest {
    Model = "claude-sonnet-4-20250514",
    MaxTokens = 1024,
    Messages = new[] { new Message { Role = "user", Content = "Hello" } }
});
```
""")

    # 通用指南
    sections.append("")
    sections.append(SHARED_API_GUIDE)

    # 用户请求
    if args:
        sections.append("")
        sections.append(f"## User Request\n\n{args}")

    # 提示使用 web_fetch 获取最新文档
    sections.append("")
    sections.append("## 获取最新文档")
    sections.append("")
    sections.append("如果需要最新的 API 文档或 SDK 参考，使用 `web_fetch` 工具访问:")
    sections.append("- Python SDK: https://docs.anthropic.com/en/api/python-sdk")
    sections.append("- TypeScript SDK: https://docs.anthropic.com/en/api/typescript-sdk")
    sections.append("- API Reference: https://docs.anthropic.com/en/api/messages")
    sections.append("")
    sections.append("## 常见陷阱")
    sections.append("")
    sections.append("- 不要在 `system` 参数中放用户输入（可能被注入攻击）")
    sections.append("- 流式响应需要正确处理连接断开和重试")
    sections.append("- `max_tokens` 是输出上限，不是总 token 限制")
    sections.append("- 工具调用需要验证返回结果后再发给模型")

    return "\n".join(sections)


# ═══════════════════════════════════════════════════════════
# lorem-ipsum Skill prompt 生成器
# ═══════════════════════════════════════════════════════════

# 经验证的单 token 英文单词列表
ONE_TOKEN_WORDS = [
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "have",
    "has", "had", "do", "does", "did", "will", "would", "can", "could",
    "may", "might", "must", "shall", "should", "make", "get", "got", "go",
    "went", "come", "see", "know", "take", "think", "look", "want", "use",
    "find", "give", "tell", "work", "call", "try", "ask", "need", "feel",
    "seem", "leave", "put", "time", "year", "day", "way", "man", "thing",
    "life", "hand", "part", "place", "case", "point", "fact", "good", "new",
    "first", "last", "long", "great", "little", "own", "other", "old",
    "right", "big", "high", "small", "large", "next", "early", "young",
    "few", "public", "bad", "same", "able", "in", "on", "at", "to", "for",
    "of", "with", "from", "by", "about", "like", "through", "over",
    "before", "between", "under", "since", "without", "and", "or", "but",
    "if", "than", "because", "as", "until", "while", "so", "though",
    "both", "each", "when", "where", "why", "how", "not", "now", "just",
    "more", "also", "here", "there", "then", "only", "very", "well",
    "back", "still", "even", "much", "too", "such", "never", "again",
    "most", "once", "off", "away", "down", "out", "up", "test", "code",
    "data", "file", "line", "text", "word", "number", "system", "program",
    "set", "run", "value", "name", "type", "state", "end", "start",
]

import random

def _generate_lorem_ipsum(target_tokens: int) -> str:
    """生成近似 target_tokens 个 token 的填充文本。"""
    tokens = 0
    result = []
    while tokens < target_tokens:
        sentence_len = 10 + random.randint(0, 10)
        sentence = []
        for _ in range(sentence_len):
            if tokens >= target_tokens:
                break
            sentence.append(random.choice(ONE_TOKEN_WORDS))
            tokens += 1
        result.append(" ".join(sentence) + ".")
        if random.random() < 0.2 and tokens < target_tokens:
            result.append("")  # 段落分隔
    return "\n".join(result)


def _lorem_ipsum_prompt(args: str) -> str:
    """lorem-ipsum skill 的 prompt 生成函数。"""
    try:
        count = int(args.strip()) if args.strip() else 10000
    except ValueError:
        return (
            "Invalid token count. Please provide a positive number.\n"
            "Usage: /lorem-ipsum [token_count]\n"
            "Example: /lorem-ipsum 50000"
        )

    count = max(1, min(count, 500000))  # 限制 1-500000

    if count < int(args.strip()) if args.strip().isdigit() else False:
        return (
            f"Requested {args.strip()} tokens, capped at 500,000 for safety.\n\n"
            + _generate_lorem_ipsum(count)
        )

    return _generate_lorem_ipsum(count)


# ═══════════════════════════════════════════════════════════
# 统一注册入口
# ═══════════════════════════════════════════════════════════

def register_all(manager):
    """
    注册所有编程式内置 Skill。

    由 SkillManager._load_programmatic_skills() 自动调用。

    Args:
        manager: SkillManager 实例
    """
    # 1. api-dev: API 开发辅助（语言检测 + SDK 指南）
    manager.register_programmatic_skill(
        name="api-dev",
        description=(
            "Build apps with the Claude API / Anthropic SDK. "
            "Auto-detects project language and provides language-specific guidance."
        ),
        prompt_fn=_api_dev_prompt,
        trigger="用户主动调用 /api-dev",
        when_to_use=(
            "When the user imports `anthropic` or `@anthropic-ai/sdk`, asks about Claude API, "
            "Anthropic SDK, or wants to build LLM-powered applications. "
            "Do NOT trigger for general programming questions."
        ),
        allowed_tools=["read_file", "list_directory", "web_fetch", "web_search"],
        argument_hint="[question or task description]",
        user_invocable=True,
    )

    # 2. lorem-ipsum: 长上下文测试填充文本生成
    manager.register_programmatic_skill(
        name="lorem-ipsum",
        description=(
            "Generate filler text for long context testing. "
            "Specify token count as argument (e.g., /lorem-ipsum 50000)."
        ),
        prompt_fn=_lorem_ipsum_prompt,
        trigger="用户主动调用 /lorem-ipsum",
        argument_hint="[token_count]",
        user_invocable=True,
    )

    logger.info("所有编程式内置 Skill 注册完成")
