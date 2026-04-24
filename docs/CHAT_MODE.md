# 多轮对话模式文档

## 概述

cli.py 现在支持**多轮对话模式**，参考 Claude 命令行编程体验，提供持续的自然语言交互。

## 启动方式

```bash
# 直接启动（交互式）
python cli.py

# 带初始输入启动
python cli.py "帮我分析这个项目"

# 指定模型
python cli.py --model glm-4-plus
```

## 对话命令

在多轮对话中，可以使用以下命令：

### 基本命令

| 命令 | 功能 | 示例 |
|------|------|------|
| `/help` | 显示帮助 | `/help` |
| `/clear` | 清空对话历史 | `/clear` |
| `/status` | 显示系统状态 | `/status` |
| `/exit` | 退出对话 | `/exit` |
| `/quit` | 退出对话 | `/quit` |

### 技能管理命令

| 命令 | 功能 | 示例 |
|------|------|------|
| `/skills` | 列出所有技能 | `/skills` |
| `/skills list` | 列出所有技能 | `/skills list` |
| `/activate <name>` | 激活技能 | `/activate python-standards` |
| `/deactivate <name>` | 停用技能 | `/deactivate python-standards` |
| `/active` | 显示已激活的技能 | `/active` |

## 对话流程

### 启动界面

```
============================================================
🚀 Claude Code Python MVP - 多轮对话模式
============================================================
   Model: glm-4-plus
   Permission Mode: normal
   Max Iterations: 20

💡 提示:
   - 输入你的问题或指令
   - 输入 /help 查看可用命令
   - 输入 /clear 清空对话历史
   - 输入 /exit 或 /quit 退出
   - 按 Ctrl+C 退出

============================================================
```

### 对话示例

```
[0]> 帮我分析这个项目的结构

🔄 第 1 轮
------------------------------------------------------------
🤔 思考中... (使用 2 条消息历史)
💰 Token 使用: 输入=1234, 输出=567, 总计=1801

🤖 Assistant: 我来分析这个项目的结构...
[分析结果]

✅ 完成

💰 本轮 Token: 1801

[1]> 这个项目用了哪些设计模式？

🔄 第 2 轮
------------------------------------------------------------
🤔 思考中... (使用 5 条消息历史)
💰 Token 使用: 输入=2345, 输出=678, 总计=3023

🤖 Assistant: 这个项目使用了以下设计模式...
[分析结果]

✅ 完成

💰 本轮 Token: 3023

[2]> /activate python-standards
技能 'python-standards' 已激活

当前已激活的技能: python-standards

注意: 技能激活后将在下一次 LLM 调用时生效。

[2]> 现在重构 agent_loop.py，遵循 Python 编码规范

🔄 第 3 轮
------------------------------------------------------------
[对话继续...]

[3]> /status

============================================================
📊 当前状态
============================================================
插件: 1 个
钩子: 2 个
技能: 1/2 个激活
工具: 22 个
对话轮次: 3
使用 Token: 6847
============================================================

[3]> /exit


============================================================
📊 会话统计
============================================================
   对话轮次: 3
   总 Token: 6847
   会话时长: 45.2 秒
   平均 Token/轮: 2282
============================================================

✅ 感谢使用！再见！
```

## 核心功能

### 1. 上下文保持

- 所有对话轮次共享同一个 `AgentLoop` 实例
- 消息历史在对话中累积
- AI 可以引用之前的对话内容

### 2. 轮次跟踪

```python
self.round = 0  # 对话轮次计数器
self.total_tokens = 0  # 总 token 使用量
```

每轮对话后：
- 轮次计数器 +1
- 累加 token 使用量
- 显示本轮统计

### 3. 会话统计

退出时显示：
- 对话轮次
- 总 Token 使用
- 会话时长
- 平均 Token/轮

### 4. 特殊命令处理

在 `handle_command()` 中处理特殊命令：

```python
def handle_command(self, user_input: str) -> bool:
    """返回 True 表示继续对话，False 表示退出"""
    
    if user_input in ['/exit', '/quit']:
        return False  # 退出
    
    if user_input == '/clear':
        self.loop.messages = []  # 清空历史
        return True
    
    # ... 其他命令
```

## 使用场景

### 场景 1: 代码分析

```
[0]> 分析 core/agent_loop.py
[AI 分析...]

[1]> 它的设计模式是什么？
[AI 回答...]

[2]> 有什么可以改进的地方？
[AI 建议...]
```

### 场景 2: 代码重构

```
[0]> /activate python-standards
[激活技能]

[1]> 重构这个函数，遵循 PEP 8
[重构...]

[2]> 写一个单元测试
[测试代码...]
```

### 场景 3: 调试帮助

```
[0]> 这个测试失败了，帮我看看
[分析...]

[1]> 运行测试看看
[执行测试...]

[2]> 根据结果修复 bug
[修复代码...]
```

### 场景 4: 技能切换

```
[0]> /activate python-standards
[激活... ]

[1]> 编写 Python 代码
[AI 遵循规范...]

[2]> /deactivate python-standards
[停用...]

[3]> /activate git-workflow
[激活...]

[4]> 生成 Git 提交信息
[AI 遵循规范...]
```

## 技术实现

### ChatMode 类

```python
class ChatMode:
    """多轮对话模式处理器"""

    def __init__(self, loop: AgentLoop, config: dict):
        self.loop = loop
        self.config = config
        self.round = 0
        self.total_tokens = 0
        self.start_time = datetime.now()

    def run(self, initial_input: str = None):
        """运行多轮对话循环"""
        self.show_welcome()

        # 处理初始输入
        if initial_input:
            self.process_round(initial_input)

        # 对话循环
        while True:
            user_input = input(f"[{self.round}]> ").strip()

            # 处理特殊命令
            if not self.handle_command(user_input):
                break

            # 处理普通对话
            self.process_round(user_input)
```

### 命令与对话的区别

| 类型 | 输入格式 | 处理方式 | 输出 |
|------|----------|----------|------|
| **命令** | `/command` | `handle_command()` | 直接执行 |
| **对话** | 自然语言 | `process_round()` → `loop.run()` | AI 响应 |

### 上下文管理

```python
# AgentLoop 保持实例
loop = AgentLoop(config)

# 每轮对话都使用同一个 loop
# 消息历史在 loop.messages 中累积
for user_input in inputs:
    loop.run(user_input)  # messages 会累积
```

## 优势

### 1. 持续上下文
- AI 记住之前的对话
- 可以引用历史内容
- 更自然的交互

### 2. 灵活控制
- 随时激活/停用技能
- 清空历史重新开始
- 查看状态和统计

### 3. 效率提升
- 复用已加载的上下文
- 减少 token 重复加载
- 更快的响应速度

### 4. 类 Claude 体验
- 命令快捷方式
- 会话统计
- 友好的交互界面

## 对比：单轮 vs 多轮

| 特性 | 单轮对话 | 多轮对话 |
|------|----------|----------|
| 上下文 | 无 | 持续保持 |
| 技能管理 | 需重启 | 动态切换 |
| 统计信息 | 无 | 完整统计 |
| 用户体验 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

## 注意事项

1. **Token 累积**: 长对话会累积大量历史，可能影响性能
2. **内存使用**: 消息历史会占用内存
3. **建议使用 `/clear`**: 在切换话题时清空历史
4. **合理退出**: 使用 `/exit` 而不是 Ctrl+C 保存统计

## 文件变更

- `cli.py`: 重写对话模式，新增 `ChatMode` 类
- `tests/test_chat_mode.py`: 多轮对话测试

---

**相关文档**:
- [命令模式文档](COMMAND_MODE.md)
- [使用指南](USAGE_GUIDE.md)
- [README](../README.md)
