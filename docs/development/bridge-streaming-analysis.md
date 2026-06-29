# Bridge 流式协议技术分析

> **分析日期**: 2026-06-28  
> **状态**: 关键发现已确认  
> **影响**: 决定前端"流式输出"的能力边界

---

## 一、核心发现

### 1.1 AgentLoop 确实实现了 Token 级流式

**代码位置**: `core/agent_loop.py:1242`

```python
def _call_llm_streaming(self, messages, tools=None):
    """流式调用 LLM"""
    response = self.client.chat.completions.create(
        model=self.model,
        messages=messages,
        tools=tools,
        stream=True  # ← 启用流式
    )
    
    for delta in response:
        if delta.content:
            print(delta.content, flush=True)  # ← 按 token 流式输出到 stdout
            # ... 累积 tool_calls
```

**结论**: ✅ AgentLoop 的 LLM 调用确实是按 token 流式输出的。

---

## 二、关键瓶颈：Bridge 缓冲了 stdout

### 2.1 Bridge Session 的 stdout 缓冲机制

**代码位置**: `bridge/session.py`

```python
class BridgeSession:
    def __init__(self):
        self._stdout_buffer = []  # ← 缓冲 stdout
    
    def run(self):
        """运行 TAOR 循环"""
        # 重定向 stdout
        old_stdout = sys.stdout
        sys.stdout = TextIOWrapper(BufferedWriter(self._stdout_buffer))
        
        try:
            # 执行 AgentLoop
            result = self.agent_loop.run(messages)
        finally:
            # 恢复 stdout
            sys.stdout = old_stdout
            
            # ← 关键：回合结束后才发出 output 事件
            self.emit('output', {
                'text': ''.join(self._stdout_buffer)  # 整个回合的文本一次性发出
            })
```

**问题**: 
- AgentLoop 的 `print(delta.content, flush=True)` 写入的是被 Bridge 重定向的 stdout
- Bridge 将这些输出缓冲到 `_stdout_buffer`
- 仅在 **回合结束后** (session.py:700) 才作为单个 `output` 事件发出

### 2.2 流式能力现状

| 层级 | 能力 | 实现方式 | 实时性 |
|------|------|---------|--------|
| **事件级流式** | ✅ 已实现 | WebSocket 实时推送 | 实时 |
| **Token 级流式** | ❌ 未实现 | stdout 缓冲，回合后发送 | 延迟 |

**当前实时事件**（TAOR 循环运行期间实时触发）：

```javascript
// 这些事件是实时的 ✅
turn_start          → 轮次开始
tool_execute        → 工具执行开始
tool_complete       → 工具执行完成
llm_call            → LLM 请求记录
assistant_message   → AI 回复（完整消息）
context_compacted   → 上下文压缩
fallback_activated  → 备用模型激活
aborted             → 中断
result              → 轮次结果

// 这个事件是延迟的 ⚠️
output              → stdout 缓冲（回合结束后一次性发出）
```

---

## 三、真正的"流式输出"能做到什么程度

### 3.1 当前能力：事件级流式

**前端表现**：

```
[14:32:01] 🤔 思考中... (轮次 1)          ← turn_start (实时)
[14:32:03] ⚙️ 执行: read_file             ← tool_execute (实时)
[14:32:03] ✅ read_file 完成              ← tool_complete (实时)
[14:32:05] 🤔 思考中... (轮次 2)          ← turn_start (实时)
[14:32:08] 💬 AI 回复内容...              ← assistant_message (实时)
[14:32:10] ┌─ ✅ 结果: success ──         ← result (实时)
[14:32:10] 📝 [stdout 缓冲内容]           ← output (延迟，回合结束后)
```

**用户体验**：
- ✅ 可以看到工具执行的实时进度
- ✅ 可以看到轮次的开始和结束
- ✅ 可以看到 AI 的完整回复
- ❌ **看不到** token 逐个输出的打字机效果

### 3.2 目标能力：Token 级流式

**期望表现**：

```
[14:32:08] 💬 AI 开始回复:
           这个项目的架构设计...           ← token 1-10 (实时)
           采用了 TAOR 循环...            ← token 11-20 (实时)
           核心引擎包括...                ← token 21-30 (实时)
           四层扩展体系...                ← token 31-40 (实时)
```

**技术挑战**：
- 需要修改 Bridge Session 的 stdout 处理逻辑
- 需要在 AgentLoop 流式输出时实时 emit 事件
- 需要定义新的事件类型（如 `text_chunk`）

---

## 四、优化方案（规划中）

### 4.1 方案 A：修改 Bridge 实时捕获 stdout

**思路**：在 AgentLoop 输出时实时捕获并转发

```python
class RealtimeStdoutCapture:
    """实时 stdout 捕获器"""
    
    def __init__(self, emit_callback):
        self.emit = emit_callback
        self.buffer = []
    
    def write(self, text):
        self.buffer.append(text)
        # 实时发出 text_chunk 事件
        self.emit('text_chunk', {'content': text})
    
    def flush(self):
        pass

# 在 BridgeSession.run() 中使用
capture = RealtimeStdoutCapture(self.emit)
sys.stdout = capture
```

**优点**：
- 最小改动，只需修改 Bridge 层
- AgentLoop 代码无需改动

**缺点**：
- stdout 重定向可能影响其他输出
- 需要处理并发问题

### 4.2 方案 B：AgentLoop 直接 emit 事件

**思路**：AgentLoop 流式输出时直接调用 emit

```python
class AgentLoop:
    def __init__(self, config, emit_callback=None):
        self.emit = emit_callback  # ← 新增回调
    
    def _call_llm_streaming(self, messages):
        for delta in response:
            if delta.content:
                print(delta.content, flush=True)
                
                # 实时发出事件
                if self.emit:
                    self.emit('text_chunk', {
                        'content': delta.content,
                        'turn': self.turn_count
                    })
```

**优点**：
- 更清晰的事件流
- 不依赖 stdout 重定向

**缺点**：
- 需要修改 AgentLoop 接口
- 需要处理 Bridge 和 CLI 模式的差异

### 4.3 方案 C：混合方案（推荐）

**思路**：结合 A 和 B 的优点

```python
# 1. AgentLoop 支持可选的 emit 回调
class AgentLoop:
    def __init__(self, config, event_bus=None):
        self.event_bus = event_bus
    
    def _emit_text_chunk(self, content):
        """发出文本块事件"""
        if self.event_bus:
            self.event_bus.emit('text_chunk', {
                'content': content,
                'turn': self.turn_count
            })
    
    def _call_llm_streaming(self, messages):
        for delta in response:
            if delta.content:
                print(delta.content, flush=True)
                self._emit_text_chunk(delta.content)

# 2. Bridge 传入 event_bus
session = BridgeSession()
agent_loop = AgentLoop(config, event_bus=session.event_bus)

# 3. CLI 模式不传入 event_bus（保持原有行为）
agent_loop = AgentLoop(config)  # 使用 stdout
```

**优点**：
- 向后兼容（CLI 模式不受影响）
- Bridge 模式获得实时流式能力
- 清晰的职责分离

---

## 五、前端适配

### 5.1 当前前端实现

```javascript
// test_bridge.html / test_bridge_mobile.html
function handle(event) {
    switch(event.type) {
        case 'output':
            // ⚠️ 这是延迟的（整个回合的 stdout）
            tln('sys', event.data.text);
            break;
        
        case 'assistant_message':
            // ✅ 这是实时的（完整消息）
            tln('ai', event.data.content);
            break;
    }
}
```

### 5.2 未来前端实现（Token 级流式）

```javascript
let currentMessage = null;

function handle(event) {
    switch(event.type) {
        case 'text_chunk':
            // ✅ 实时追加 token
            if (!currentMessage) {
                currentMessage = createMessageElement('ai');
            }
            currentMessage.append(event.data.content);
            scrollToBottom();
            break;
        
        case 'assistant_message':
            // 完整消息（fallback）
            if (currentMessage) {
                currentMessage.update(event.data.content);
            }
            currentMessage = null;
            break;
    }
}
```

---

## 六、优先级评估

| 优化项 | 优先级 | 工作量 | 影响范围 |
|--------|--------|--------|---------|
| 事件级流式完善 | ✅ 高 | 小 | Bridge 前端 |
| Token 级流式（方案 C） | 🟡 中 | 中 | AgentLoop + Bridge + 前端 |
| 打字机效果优化 | 🟡 中 | 小 | 前端 |
| 流式中断支持 | 🟢 低 | 中 | AgentLoop + Bridge |

---

## 七、总结

### 7.1 当前状态

✅ **已实现**：
- AgentLoop 的 LLM 调用确实是 token 级流式
- Bridge 的事件级流式传输（tool/turn/result 实时推送）
- 前端实时渲染事件 + 运行中指示器

⚠️ **限制**：
- stdout 被 Bridge 缓冲，token 级流式未传到前端
- 用户看到的是事件级流式，而非打字机效果

### 7.2 下一步

📋 **规划**：
1. 实现方案 C（混合方案）
2. 定义 `text_chunk` 事件协议
3. 修改 AgentLoop 支持 event_bus
4. 修改 Bridge 实时转发 token
5. 更新前端支持打字机效果

### 7.3 技术债务

```
TODO:
- [ ] AgentLoop 添加 event_bus 参数
- [ ] 定义 text_chunk 事件格式
- [ ] BridgeSession 实现实时 stdout 捕获
- [ ] 前端适配 text_chunk 事件
- [ ] 性能测试（高频事件推送）
- [ ] 文档更新
```

---

**文档版本**: 1.0  
**最后更新**: 2026-06-28  
**维护者**: AuraCode 核心开发团队
