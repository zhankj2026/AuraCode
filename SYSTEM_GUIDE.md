# Claude Code Python MVP - 系统介绍与使用指南

## 项目概述

Claude Code Python MVP 是一个基于 Claude Code 架构设计的 Python 实现，提供了生产级 AI 编程助手的核心功能。系统采用 TAOR（Think-Act-Observe-Repeat）智能体循环，通过丰富的工具系统和扩展能力，能够帮助用户完成各种复杂的编程任务。

## 核心功能

### 1. TAOR 智能体循环
- **Think（思考）**: 系统通过 LLM 分析用户需求，制定执行计划
- **Act（行动）**: 调用适当的工具执行具体操作
- **Observe（观察）**: 收集工具执行结果，分析当前状态
- **Repeat（重复）**: 根据结果继续下一步，直到任务完成

### 2. 工具系统（22+ 内置工具）

#### 文件操作工具
- `read_file`: 读取文件内容
- `write_file`: 写入文件
- `list_directory`: 列出目录内容

#### 搜索分析工具
- `grep`: 搜索文件内容
- `find`: 查找文件
- `analyze_file`: 分析代码文件

#### 代码编辑工具
- `replace_in_file`: 替换文件内容
- `undo_edit`: 撤销编辑

#### 质量检查工具
- `lint`: 代码检查
- `run_tests`: 运行测试

#### 命令执行工具
- `run_command`: 执行 Shell 命令

#### 智能体工具
- `spawn_subagent`: 创建并行子任务
- `plan_agent`: 规划任务

#### 技能管理工具
- `activate_skill`: 激活技能
- `list_skills`: 列出可用技能

#### 记忆管理工具
- `save_memory`: 保存记忆
- `load_memory`: 加载记忆
- `search_memories`: 搜索记忆

### 3. 权限管理系统

系统提供四级权限控制：

1. **normal（普通模式）**: 默认模式，需要用户确认大多数操作
2. **auto（自动模式）**: 自动允许大多数安全操作
3. **plan（计划模式）**: 用于规划阶段的权限控制
4. **bypass（绕过模式）**: 绕过大部分权限检查（谨慎使用）

### 4. 插件系统

动态加载插件，扩展系统功能：

```python
from plugins.base import ToolPlugin

class MyPlugin(ToolPlugin):
    @property
    def name(self):
        return "my-plugin"

    def get_tools(self):
        return [...]  # 插件提供的工具

    def get_hooks(self):
        return [...]  # 插件提供的钩子
```

### 5. 钩子系统

在工具执行的不同阶段插入自定义逻辑：

- **PreToolUse**: 工具执行前
- **PostToolUse**: 工具执行后
- **PostToolUseFailure**: 工具失败时

```python
hook_manager.register_hook("PreToolUse", my_hook)
```

### 6. 技能系统（渐进式披露）

按需注入领域知识，避免信息过载：

- **python-standards**: Python 编码规范
- **git-workflow**: Git 工作流规范
- **更多自定义技能...**

技能采用两阶段加载：
1. 元数据始终显示（轻量）
2. 激活后加载完整内容（重量）

### 7. Subagent 系统

并行执行多个任务，提高效率：

```python
# 创建并行任务
spawn_subagent(task="分析代码结构")
spawn_subagent(task="生成测试用例")

# 获取结果
join_subagent(agent_id="...")
```

### 8. 记忆系统

仿 Claude Code 设计，支持 4 种记忆类型：

- **user**: 用户角色、偏好、知识背景
- **feedback**: 用户反馈指导（有效/无效方法）
- **project**: 项目目标、截止日期、状态
- **reference**: 外部系统参考（Bug 追踪、文档等）

### 9. 命令系统（12+ 内置命令）

#### 系统命令
- `help`: 显示帮助信息
- `status`: 查看系统状态

#### 技能管理命令
- `skills`: 列出可用技能
- `activate`: 激活技能
- `deactivate`: 停用技能

#### 工具命令
- `plugins`: 列出已加载插件
- `hooks`: 列出已注册钩子

#### 分析命令
- `analyze`: 分析代码
- `test`: 运行测试
- `lint`: 代码检查

## 架构设计

### 核心模块

```
opencode/
├── cli.py                 # CLI 入口（双模式）
├── core/                  # 核心实现
│   ├── agent_loop.py     # TAOR 循环引擎
│   ├── context.py        # 项目上下文加载
│   ├── message.py        # 消息处理
│   ├── subagent.py       # Subagent 管理
│   └── memory.py         # 记忆系统
├── tools/                 # 工具系统
│   ├── registry.py       # 工具注册表
│   └── builtin/          # 内置工具（22+）
├── commands/              # 命令系统
│   ├── registry.py       # 命令注册表
│   ├── base.py           # 命令基类
│   └── builtin/          # 内置命令（12+）
├── permissions/           # 权限管理
│   └── manager.py        # 权限管理器
├── plugins/               # 插件系统
│   ├── base.py           # 插件基类
│   └── loader.py         # 插件加载器
├── hooks/                 # 钩子系统
│   └── manager.py        # 钩子管理器
├── skills/                # 技能系统
│   ├── context.py        # 技能上下文
│   ├── loader.py         # 技能管理器
│   ├── python-standards/ # Python 编码规范
│   └── git-workflow/     # Git 工作流
└── tests/                 # 测试文件
    └── demos/            # 演示文件
```

### 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                      用户界面层                          │
│  ┌──────────────┐              ┌──────────────┐         │
│  │  对话模式    │              │  命令模式    │         │
│  │  (ChatMode)  │              │ (CommandMode)│         │
│  └──────────────┘              └──────────────┘         │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                   Agent Loop (TAOR)                      │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐        │
│  │ Think  │→ │  Act   │→ │Observe │→ │ Repeat │        │
│  └────────┘  └────────┘  └────────┘  └────────┘        │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                    扩展系统层                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ 插件系统 │  │ 钩子系统 │  │ 技能系统 │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                    工具执行层                            │
│  ┌──────────────────────────────────────────┐          │
│  │  工具注册表 (TOOL_REGISTRY)              │          │
│  │  - 文件操作    - 搜索分析               │          │
│  │  - 代码编辑    - 质量检查               │          │
│  │  - 命令执行    - 智能体管理             │          │
│  └──────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                    支撑服务层                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ 权限管理器   │  │ 记忆管理器   │  │ Subagent     │ │
│  │              │  │              │  │ 管理器       │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## 系统提示词结构

系统采用分层提示词设计（6层）：

1. **基础角色定义**: 定义 AI 的角色和工作原则
2. **记忆系统**: 用户信息、反馈、项目上下文
3. **项目上下文**: CLAUDE.md 文件内容
4. **技能系统**: 可用技能（元数据）+ 已激活技能（完整内容）
5. **工具说明**: 所有可用工具的描述
6. **安全规则**: 操作安全和权限控制规则

## 使用示例：生成扫雷游戏

下面演示如何使用系统在 demo 目录中生成一个扫雷游戏。

### 步骤1：启动系统

```bash
# 设置 API Key（智谱 GLM）
export OPENAI_API_KEY="your-zhipu-api-key"
export OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"

# 启动对话模式
python cli.py
```

### 步骤2：与系统对话

```
[0]> 在 demo 目录中创建一个扫雷游戏
```

### 步骤3：系统执行过程

系统会自动执行以下步骤：

1. **Think（思考）**: 分析扫雷游戏的需求
   - 需要 HTML 界面
   - 需要 JavaScript 逻辑
   - 需要 CSS 样式

2. **Act（行动）**: 使用工具创建文件
   - 创建 `demo/minesweeper.html`
   - 创建 `demo/minesweeper.css`
   - 创建 `demo/minesweeper.js`

3. **Observe（观察）**: 检查文件是否创建成功

4. **Repeat（重复）**: 继续完善功能

### 步骤4：生成的文件

#### demo/minesweeper.html

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>扫雷游戏</title>
    <link rel="stylesheet" href="minesweeper.css">
</head>
<body>
    <div class="container">
        <h1>扫雷游戏</h1>
        <div class="info">
            <span>剩余地雷: <strong id="mines-count">10</strong></span>
            <span>时间: <strong id="timer">0</strong> 秒</span>
        </div>
        <div class="board" id="board"></div>
        <div class="controls">
            <button onclick="initGame()">重新开始</button>
        </div>
    </div>
    <script src="minesweeper.js"></script>
</body>
</html>
```

#### demo/minesweeper.css

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: Arial, sans-serif;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.container {
    background: white;
    padding: 2rem;
    border-radius: 10px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

h1 {
    text-align: center;
    color: #333;
    margin-bottom: 1rem;
}

.info {
    display: flex;
    justify-content: space-around;
    margin-bottom: 1rem;
    font-size: 1.1rem;
}

.board {
    display: grid;
    grid-template-columns: repeat(10, 30px);
    gap: 2px;
    margin-bottom: 1rem;
}

.cell {
    width: 30px;
    height: 30px;
    background: #ccc;
    border: 1px solid #999;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    cursor: pointer;
    user-select: none;
}

.cell:hover {
    background: #bbb;
}

.cell.revealed {
    background: #eee;
    cursor: default;
}

.cell.mine {
    background: #ff6b6b;
}

.cell.flagged {
    background: #ffd93d;
}

.controls {
    text-align: center;
}

button {
    padding: 0.5rem 2rem;
    font-size: 1rem;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
}

button:hover {
    background: #5568d3;
}
```

#### demo/minesweeper.js

```javascript
const ROWS = 10;
const COLS = 10;
const MINES = 10;

let board = [];
let minesLocations = [];
let minesCount = MINES;
let timer = 0;
let timerInterval;
let gameOver = false;

function initGame() {
    // 重置状态
    board = [];
    minesLocations = [];
    minesCount = MINES;
    timer = 0;
    gameOver = false;
    
    // 更新显示
    document.getElementById('mines-count').textContent = minesCount;
    document.getElementById('timer').textContent = timer;
    
    // 清除定时器
    if (timerInterval) {
        clearInterval(timerInterval);
    }
    
    // 创建棋盘
    createBoard();
    
    // 放置地雷
    placeMines();
    
    // 计算数字
    calculateNumbers();
    
    // 渲染棋盘
    renderBoard();
}

function createBoard() {
    const boardElement = document.getElementById('board');
    boardElement.innerHTML = '';
    
    for (let i = 0; i < ROWS * COLS; i++) {
        board.push({
            mine: false,
            revealed: false,
            flagged: false,
            neighborMines: 0
        });
    }
}

function placeMines() {
    let minesPlaced = 0;
    
    while (minesPlaced < MINES) {
        const randomIndex = Math.floor(Math.random() * (ROWS * COLS));
        
        if (!board[randomIndex].mine) {
            board[randomIndex].mine = true;
            minesLocations.push(randomIndex);
            minesPlaced++;
        }
    }
}

function calculateNumbers() {
    for (let i = 0; i < ROWS * COLS; i++) {
        if (board[i].mine) continue;
        
        const neighbors = getNeighbors(i);
        let count = 0;
        
        neighbors.forEach(index => {
            if (board[index].mine) count++;
        });
        
        board[i].neighborMines = count;
    }
}

function getNeighbors(index) {
    const neighbors = [];
    const row = Math.floor(index / COLS);
    const col = index % COLS;
    
    for (let i = -1; i <= 1; i++) {
        for (let j = -1; j <= 1; j++) {
            if (i === 0 && j === 0) continue;
            
            const newRow = row + i;
            const newCol = col + j;
            
            if (newRow >= 0 && newRow < ROWS && newCol >= 0 && newCol < COLS) {
                neighbors.push(newRow * COLS + newCol);
            }
        }
    }
    
    return neighbors;
}

function renderBoard() {
    const boardElement = document.getElementById('board');
    boardElement.innerHTML = '';
    
    board.forEach((cell, index) => {
        const cellElement = document.createElement('div');
        cellElement.classList.add('cell');
        cellElement.dataset.index = index;
        
        cellElement.addEventListener('click', handleClick);
        cellElement.addEventListener('contextmenu', handleRightClick);
        
        boardElement.appendChild(cellElement);
    });
}

function handleClick(e) {
    if (gameOver) return;
    
    const index = parseInt(e.target.dataset.index);
    
    if (board[index].flagged || board[index].revealed) return;
    
    // 开始计时
    if (!timerInterval) {
        timerInterval = setInterval(() => {
            timer++;
            document.getElementById('timer').textContent = timer;
        }, 1000);
    }
    
    revealCell(index);
}

function handleRightClick(e) {
    e.preventDefault();
    
    if (gameOver) return;
    
    const index = parseInt(e.target.dataset.index);
    
    if (board[index].revealed) return;
    
    const cellElement = e.target;
    
    if (board[index].flagged) {
        board[index].flagged = false;
        cellElement.classList.remove('flagged');
        minesCount++;
    } else {
        board[index].flagged = true;
        cellElement.classList.add('flagged');
        minesCount--;
    }
    
    document.getElementById('mines-count').textContent = minesCount;
}

function revealCell(index) {
    if (index < 0 || index >= board.length) return;
    if (board[index].revealed || board[index].flagged) return;
    
    const cellElement = document.querySelector(`[data-index="${index}"]`);
    board[index].revealed = true;
    cellElement.classList.add('revealed');
    
    if (board[index].mine) {
        cellElement.classList.add('mine');
        cellElement.textContent = '💣';
        endGame(false);
        return;
    }
    
    if (board[index].neighborMines > 0) {
        cellElement.textContent = board[index].neighborMines;
        cellElement.style.color = getNumberColor(board[index].neighborMines);
    } else {
        // 递归打开相邻格子
        const neighbors = getNeighbors(index);
        neighbors.forEach(neighborIndex => {
            revealCell(neighborIndex);
        });
    }
    
    // 检查胜利
    checkWin();
}

function getNumberColor(num) {
    const colors = [
        '',        // 0
        '#0000ff', // 1 - 蓝色
        '#008000', // 2 - 绿色
        '#ff0000', // 3 - 红色
        '#000080', // 4 - 深蓝色
        '#800000', // 5 - 深红色
        '#008080', // 6 - 青色
        '#000000', // 7 - 黑色
        '#808080'  // 8 - 灰色
    ];
    return colors[num];
}

function checkWin() {
    let revealedCount = 0;
    
    board.forEach(cell => {
        if (cell.revealed) revealedCount++;
    });
    
    if (revealedCount === ROWS * COLS - MINES) {
        endGame(true);
    }
}

function endGame(won) {
    gameOver = true;
    
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
    
    if (won) {
        setTimeout(() => {
            alert('恭喜你赢了！用时: ' + timer + ' 秒');
        }, 100);
    } else {
        // 显示所有地雷
        minesLocations.forEach(index => {
            const cellElement = document.querySelector(`[data-index="${index}"]`);
            cellElement.classList.add('revealed', 'mine');
            cellElement.textContent = '💣';
        });
        
        setTimeout(() => {
            alert('游戏结束！你踩到了地雷。');
        }, 100);
    }
}

// 初始化游戏
initGame();
```

### 步骤5：运行游戏

在浏览器中打开 `demo/minesweeper.html` 即可开始游戏。

## 高级用法

### 自定义技能

创建自定义技能目录结构：

```
skills/
└── my-skill/
    ├── skill.md        # 技能元数据
    └── content.md      # 技能完整内容
```

### 自定义插件

```python
from plugins.base import ToolPlugin

class MyPlugin(ToolPlugin):
    @property
    def name(self):
        return "my-plugin"
    
    @property
    def version(self):
        return "1.0.0"
    
    @property
    def description(self):
        return "我的自定义插件"
    
    def get_tools(self):
        return [
            {
                "name": "my_tool",
                "description": "我的工具",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                },
                "handler": lambda: "结果",
                "permission_level": "read"
            }
        ]
```

### 配置文件

系统支持通过配置文件自定义行为：

```python
config = {
    # LLM 配置
    "api_key": "...",
    "base_url": "...",
    "model": "glm-4-plus",
    
    # Agent 配置
    "max_iterations": 20,
    "permission_mode": "normal",
    
    # 扩展系统
    "enable_plugins": True,
    "enable_hooks": True,
    "enable_skills": True,
    "enable_memory": True,
    "active_skills": [],
    
    # 记忆系统
    "memory_dir": ".claude/memory",
}
```

## 支持的 LLM

### 智谱 GLM（推荐）
```bash
export OPENAI_API_KEY="your-zhipu-api-key"
export OPENAI_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
```

可用模型：
- `glm-4-plus` - 最强性能（推荐）
- `glm-4` - 标准版
- `glm-4-air` - 快速响应
- `glm-4-flash` - 超快速度
- `glm-4.7` - 最新版

### OpenAI
```bash
export OPENAI_API_KEY="sk-your-api-key"
```

## 总结

Claude Code Python MVP 是一个功能强大的 AI 编程助手，通过 TAOR 循环、丰富的工具系统和灵活的扩展机制，能够帮助用户高效完成各种编程任务。系统的模块化设计和插件架构使其易于扩展和定制。

无论是简单的代码生成任务（如扫雷游戏），还是复杂的项目重构，系统都能提供智能化的辅助，大大提高开发效率。
