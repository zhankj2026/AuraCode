# Claude Code Python MVP - 编程能力增强计划

**当前状态**: 基础工具链已完成,具备文件读写和命令执行能力  
**目标**: 增强为真正的 AI 编程助手,具备完整的软件开发能力  
**时间**: 2026-04-05

---

## 📊 当前能力评估

### ✅ 已实现
- 文件读取/写入
- 命令执行
- 目录浏览
- 基础权限管理
- Agent Loop 循环

### ❌ 核心缺陷
1. **无代码理解能力** - 不能分析代码结构、依赖关系
2. **无搜索能力** - 无法在代码库中搜索/定位
3. **无版本控制** - 不能管理 Git 操作
4. **无批量操作** - 每次只能处理单个文件
5. **无项目管理** - 不理解项目结构和构建流程
6. **无错误恢复** - 工具失败后无法自我修复

---

## 🎯 增强路线图

### Phase 1: 代码理解能力 (优先级: 🔴 最高)

**目标**: 让 AI 能理解和分析代码

#### 1.1 代码搜索工具
```python
# 新增工具
- grep: 搜索文件内容(正则表达式)
- find: 查找文件(按名称/类型)
- code_search: 语义搜索代码片段
```

**实现方案**:
```python
def grep_handler(pattern: str, path: str = ".", file_pattern: str = "*.py") -> str:
    """增强版 grep - 支持文件过滤"""
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", "--include=" + file_pattern, pattern, path],
        capture_output=True, text=True
    )
    return result.stdout

# 注册
register_tool("grep", {
    "description": "搜索代码内容(支持正则和文件过滤)",
    "parameters": {...},
    "handler": grep_handler
})
```

**预期效果**:
```
用户: "找到所有处理用户认证的函数"
AI: 使用 grep 搜索 "auth|login|authentication"
AI: 找到 15 个匹配,分析后给出建议
```

#### 1.2 代码分析工具
```python
# 新增工具
- analyze_file: 分析单个文件结构(函数/类/导入)
- get_file_tree: 生成项目文件树
- detect_patterns: 检测设计模式
```

**实现示例**:
```python
def analyze_file_handler(path: str) -> str:
    """分析文件结构"""
    import ast
    
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    
    tree = ast.parse(source)
    
    analysis = {
        "classes": [],
        "functions": [],
        "imports": []
    }
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            analysis["classes"].append(node.name)
        elif isinstance(node, ast.FunctionDef):
            analysis["functions"].append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                analysis["imports"].append(alias.name)
    
    return json.dumps(analysis, indent=2, ensure_ascii=False)
```

**预期效果**:
```
用户: "分析 main.py 的结构"
AI: 返回:
{
  "classes": ["AgentLoop", "ToolRegistry"],
  "functions": ["main", "run", "execute"],
  "imports": ["os", "sys", "openai"]
}
```

---

### Phase 2: 版本控制集成 (优先级: 🔴 最高)

**目标**: 集成 Git,支持完整的开发工作流

#### 2.1 Git 工具集
```python
# 新增工具
- git_status: 查看仓库状态
- git_diff: 查看文件差异
- git_commit: 提交更改
- git_branch: 分支管理
- git_log: 查看提交历史
- git_stash: 暂存更改
```

**实现示例**:
```python
def git_status_handler() -> str:
    """查看 Git 仓库状态"""
    result = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True, text=True, cwd="."
    )
    
    if result.returncode != 0:
        return "错误: 当前目录不是 Git 仓库"
    
    return result.stdout if result.stdout else "工作区干净"

def git_diff_handler(path: str = None) -> str:
    """查看文件差异"""
    cmd = ["git", "diff"]
    if path:
        cmd.append(path)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.stdout else "无差异"
```

**预期效果**:
```
用户: "查看当前修改了哪些文件"
AI: 使用 git_status 工具
AI: 显示:
 M core/agent_loop.py
 M tools/registry.py
?? new_feature.py

用户: "提交这些更改"
AI: 使用 git_add, git_commit 工具
AI: 成功提交 abc1234: "添加新功能"
```

---

### Phase 3: 批量操作能力 (优先级: 🟡 高)

**目标**: 支持多文件操作和重构

#### 3.1 批量文件操作
```python
# 新增工具
- batch_read: 批量读取多个文件
- batch_write: 批量修改多个文件
- find_and_replace: 查找替换(多文件)
- refactor: 代码重构辅助
```

**实现示例**:
```python
def batch_read_handler(paths: List[str]) -> str:
    """批量读取文件"""
    results = {}
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                results[path] = f.read()
        except Exception as e:
            results[path] = f"错误: {str(e)}"
    
    return json.dumps(results, ensure_ascii=False)

def find_and_replace_handler(
    pattern: str, 
    replacement: str, 
    file_pattern: str = "*.py",
    dry_run: bool = True
) -> str:
    """查找替换(支持预览)"""
    import glob
    
    files = glob.glob(file_pattern, recursive=True)
    changes = []
    
    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        if pattern in content:
            new_content = content.replace(pattern, replacement)
            changes.append({
                "file": filepath,
                "occurrences": content.count(pattern)
            })
            
            if not dry_run:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
    
    return f"找到 {len(changes)} 个文件包含匹配内容\n" + json.dumps(changes, indent=2)
```

**预期效果**:
```
用户: "将所有文件中的 'old_function' 改为 'new_function'"
AI: 使用 find_and_replace (dry_run=True)
AI: 找到 12 个文件包含 23 处匹配,是否执行?

用户: "执行"
AI: 使用 find_and_replace (dry_run=False)
AI: 成功修改 12 个文件
```

---

### Phase 4: 项目管理能力 (优先级: 🟡 高)

**目标**: 理解和管理项目结构

#### 4.1 项目感知工具
```python
# 新增工具
- build_project: 执行构建命令
- run_tests: 运行测试套件
- analyze_dependencies: 分析依赖关系
- generate_docs: 生成文档
- detect_issues: 检测代码问题
```

**实现示例**:
```python
def detect_tech_stack_advanced(project_root: str) -> Dict:
    """增强版技术栈检测"""
    indicators = {
        "requirements.txt": {"type": "python", "package_manager": "pip"},
        "package.json": {"type": "nodejs", "package_manager": "npm"},
        "go.mod": {"type": "go", "package_manager": "go mod"},
        "pom.xml": {"type": "java", "package_manager": "maven"},
        "Cargo.toml": {"type": "rust", "package_manager": "cargo"},
    }
    
    detected = []
    for filename, info in indicators.items():
        if os.path.exists(os.path.join(project_root, filename)):
            detected.append(info)
    
    return detected

def run_tests_handler(test_command: str = None) -> str:
    """运行测试"""
    # 自动检测测试命令
    if not test_command:
        if os.path.exists("pytest.ini"):
            test_command = "pytest"
        elif os.path.exists("package.json"):
            test_command = "npm test"
        else:
            return "未找到测试配置"
    
    result = subprocess.run(
        test_command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=120
    )
    
    output = result.stdout
    if result.stderr:
        output += "\n" + result.stderr
    
    return output
```

**预期效果**:
```
用户: "运行测试"
AI: 检测到 pytest 配置
AI: 执行 pytest
AI: 测试通过: 45/45, 耗时 2.3s

用户: "构建项目"
AI: 检测到 Node.js 项目
AI: 执行 npm run build
AI: 构建成功,输出到 dist/ 目录
```

---

### Phase 5: 智能辅助功能 (优先级: 🟢 中)

**目标**: 提供更智能的编程辅助

#### 5.1 智能工具
```python
# 新增工具
- suggest_fix: 分析错误并建议修复
- explain_code: 解释代码逻辑
- generate_tests: 生成单元测试
- review_code: 代码审查
- optimize_code: 性能优化建议
```

**实现方案**:
这些工具主要依赖 LLM 的智能,实现相对简单:

```python
def suggest_fix_handler(error_message: str, context: str) -> str:
    """分析错误并建议修复"""
    # 这个工具主要由 LLM 处理,不需要复杂实现
    # 只需返回错误信息给 LLM,让它分析
    return f"错误信息:\n{error_message}\n\n上下文:\n{context}"
```

**预期效果**:
```
用户: "这段代码有什么问题?"
AI: 使用 analyze_file 分析结构
AI: 使用 review_code 审查代码
AI: 发现 3 个问题:
    1. 缺少错误处理
    2. 变量命名不清晰
    3. 可以优化性能
AI: 给出具体修复建议
```

---

### Phase 6: 持久化和上下文 (优先级: 🟢 中)

**目标**: 记住历史操作和项目状态

#### 6.1 会话管理
```python
# 新增模块
- session_manager: 管理对话历史
- project_memory: 记住项目信息
- task_tracker: 跟踪任务进度
```

**实现示例**:
```python
class ProjectMemory:
    """项目记忆管理器"""
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.memory_file = os.path.join(project_root, ".claude_memory.json")
        self.memory = self._load_memory()
    
    def _load_memory(self) -> Dict:
        if os.path.exists(self.memory_file):
            with open(self.memory_file, "r") as f:
                return json.load(f)
        return {"tech_stack": {}, "key_files": [], "notes": []}
    
    def save_note(self, note: str):
        """保存笔记"""
        self.memory["notes"].append({
            "content": note,
            "timestamp": datetime.now().isoformat()
        })
        self._save_memory()
    
    def _save_memory(self):
        with open(self.memory_file, "w") as f:
            json.dump(self.memory, f, indent=2)
```

**预期效果**:
```
用户: "记住这个项目的技术栈是 Python + FastAPI"
AI: 已保存到项目记忆

用户: (下次对话) "这个项目用什么技术栈?"
AI: 从记忆中读取: Python + FastAPI
```

---

## 📈 实施优先级

### 第一批 (立即实施)
1. ✅ grep 工具 - 代码搜索
2. ✅ git_status/git_diff - 版本控制
3. ✅ analyze_file - 代码分析

### 第二批 (本周实施)
4. find 工具 - 文件查找
5. git_commit/git_branch - Git 操作
6. batch_read - 批量读取
7. find_and_replace - 查找替换

### 第三批 (下周实施)
8. build_project - 项目构建
9. run_tests - 测试运行
10. generate_docs - 文档生成
11. session_manager - 会话管理

### 第四批 (后续增强)
12. suggest_fix - 错误修复建议
13. generate_tests - 测试生成
14. review_code - 代码审查
15. project_memory - 项目记忆

---

## 💡 快速实施指南

### 最小增强方案 (3个工具,30分钟)

只需添加 3 个工具,立即提升编程能力:

```python
# 1. 创建 tools/builtin/grep.py
import subprocess
from tools.registry import register_tool

def grep_handler(pattern: str, path: str = ".") -> str:
    result = subprocess.run(
        ["grep", "-rn", pattern, path],
        capture_output=True, text=True
    )
    return result.stdout if result.stdout else "未找到匹配"

register_tool("grep", {
    "description": "递归搜索文件内容",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "搜索模式"},
            "path": {"type": "string", "description": "搜索路径", "default": "."}
        },
        "required": ["pattern"]
    },
    "handler": grep_handler
})

# 2. 创建 tools/builtin/git_status.py
import subprocess
from tools.registry import register_tool

def git_status_handler() -> str:
    result = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return "错误: 不是 Git 仓库"
    return result.stdout if result.stdout else "工作区干净"

register_tool("git_status", {
    "description": "查看 Git 仓库状态",
    "parameters": {"type": "object", "properties": {}},
    "handler": git_status_handler
})

# 3. 创建 tools/builtin/analyze_file.py
import ast
from tools.registry import register_tool

def analyze_file_handler(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    
    tree = ast.parse(source)
    analysis = {"classes": [], "functions": [], "imports": []}
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            analysis["classes"].append(node.name)
        elif isinstance(node, ast.FunctionDef):
            analysis["functions"].append(node.name)
    
    return json.dumps(analysis, indent=2)

register_tool("analyze_file", {
    "description": "分析 Python 文件结构",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"}
        },
        "required": ["path"]
    },
    "handler": analyze_file_handler
})

# 4. 在 tools/builtin/__init__.py 中导入
from . import grep
from . import git_status
from . import analyze_file
```

**效果提升**:
```
之前: "读取 main.py" → AI 看到代码但无法搜索其他文件
现在: "找到所有处理用户的函数" → AI 用 grep 搜索整个项目
```

---

## 🎯 成功指标

### 量化指标

| 指标 | 当前 | Phase 1后 | Phase 3后 | 目标 |
|------|------|-----------|-----------|------|
| 工具数量 | 4 | 7 | 11 | 15+ |
| 代码理解 | ❌ 无 | ✅ 基础 | ✅ 完整 | ✅ 深度 |
| 版本控制 | ❌ 无 | ✅ 基础 | ✅ 完整 | ✅ 智能 |
| 批量操作 | ❌ 无 | ❌ 无 | ✅ 支持 | ✅ 智能 |
| 项目管理 | ❌ 无 | ❌ 无 | ⚠️ 部分 | ✅ 完整 |

### 能力矩阵

| 任务类型 | 当前能力 | 增强后能力 |
|---------|---------|-----------|
| 读取单个文件 | ✅ | ✅ |
| 修改单个文件 | ✅ | ✅ |
| **搜索代码** | ❌ | ✅ grep/find |
| **分析代码结构** | ❌ | ✅ analyze_file |
| **Git 操作** | ❌ | ✅ git_* 工具 |
| **批量修改** | ❌ | ✅ batch_* 工具 |
| **运行测试** | ❌ | ✅ run_tests |
| **构建项目** | ❌ | ✅ build_project |
| **代码审查** | ❌ | ✅ review_code |
| **错误修复** | ❌ | ✅ suggest_fix |

---

## 📚 参考资源

### Claude Code 源码对照

| Python MVP 工具 | Claude Code 源码位置 | 说明 |
|----------------|---------------------|------|
| grep | `src/utils/searchUtils.ts` | 搜索功能 |
| git_* | `src/utils/gitUtils.ts` | Git 操作 |
| analyze_file | `src/utils/fileUtils.ts` | 文件分析 |
| batch_* | `src/tools/batchTools.ts` | 批量操作 |

### 学习资源

- OpenAI Function Calling: https://platform.openai.com/docs/guides/function-calling
- GLM Tool 调用: https://open.bigmodel.cn/dev/api#tool-call
- AST 模块文档: https://docs.python.org/3/library/ast.html
- Git 命令参考: https://git-scm.com/docs

---

## 🚀 立即行动

### 10分钟快速增强

```bash
cd opencode

# 创建 grep 工具
cat > tools/builtin/grep.py << 'EOF'
import subprocess
from tools.registry import register_tool

def grep_handler(pattern: str, path: str = ".") -> str:
    result = subprocess.run(
        ["grep", "-rn", pattern, path],
        capture_output=True, text=True
    )
    return result.stdout if result.stdout else "未找到匹配"

register_tool("grep", {
    "description": "递归搜索文件内容",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "搜索模式"},
            "path": {"type": "string", "description": "搜索路径", "default": "."}
        },
        "required": ["pattern"]
    },
    "handler": grep_handler
})
EOF

# 更新 __init__.py
echo "from . import grep" >> tools/builtin/__init__.py

# 测试
python cli.py --model glm-4-plus "搜索项目中所有包含 'class' 的行"
```

---

**总结**: 通过添加代码搜索、版本控制、批量操作等工具,可以将当前的"基础文件操作工具"增强为"真正的 AI 编程助手"。建议按优先级逐步实施,每添加一个工具都能立即提升编程能力。
