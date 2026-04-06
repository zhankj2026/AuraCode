# 上下文管理与配置系统

## 1. 上下文管理概述

### 1.1 为什么需要上下文管理?

LLM 本身是无状态的,每次调用都是独立的。为了让 AI 理解你的项目,我们需要提供:

- 📋 **项目约定** - 编码规范、架构模式
- 🛠️ **技术栈信息** - 语言、框架、工具链
- 📝 **历史记忆** - 之前的对话和决策
- 🎯 **当前任务** - 待解决的问题和目标

Claude Code 通过 **CLAUDE.md** 文件和多层级上下文加载机制实现这一点。

### 1.2 Claude Code 的上下文层级

```
优先级从高到低:
┌─────────────────────────────────────┐
│ 1. 企业级配置 (Enterprise)           │ ← 组织统一规范
├─────────────────────────────────────┤
│ 2. 用户级配置 (~/.claude/CLAUDE.md) │ ← 个人偏好
├─────────────────────────────────────┤
│ 3. 项目级配置 (.claude/CLAUDE.md)    │ ← 项目特定约定
├─────────────────────────────────────┤
│ 4. 子目录级配置 (src/.claude/...)   │ ← 模块级规范
└─────────────────────────────────────┘
```

**MVP 策略:** 我们只实现项目级配置(第 3 层),后续可扩展其他层级。

---

## 2. CLAUDE.md 加载机制

### 2.1 核心实现

```python
# core/context.py
import os
from typing import Optional, List


def load_project_context(project_root: str = ".") -> str:
    """
    加载项目上下文(CLAUDE.md + 技术栈检测)
    
    Args:
        project_root: 项目根目录路径
        
    Returns:
        格式化的上下文字符串,如果无上下文则返回空字符串
    """
    context_parts = []
    
    # 1. 加载 CLAUDE.md
    claude_md_content = load_claude_md(project_root)
    if claude_md_content:
        context_parts.append(f"## 项目约定\n\n{claude_md_content}")
    
    # 2. 检测技术栈
    tech_stack = detect_tech_stack(project_root)
    if tech_stack:
        context_parts.append(f"## 技术栈\n\n{tech_stack}")
    
    # 3. 检测项目结构
    project_structure = detect_project_structure(project_root)
    if project_structure:
        context_parts.append(f"## 项目结构\n\n{project_structure}")
    
    # 合并所有部分
    if context_parts:
        return "\n\n".join(context_parts)
    
    return ""


def load_claude_md(project_root: str) -> Optional[str]:
    """
    加载 CLAUDE.md 文件
    
    搜索路径:
    1. {project_root}/.claude/CLAUDE.md
    2. {project_root}/CLAUDE.md (备选)
    
    Args:
        project_root: 项目根目录
        
    Returns:
        文件内容,如果不存在则返回 None
    """
    # 优先搜索 .claude/ 目录
    claude_dir_path = os.path.join(project_root, ".claude", "CLAUDE.md")
    if os.path.exists(claude_dir_path):
        try:
            with open(claude_dir_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception as e:
            print(f"⚠️  读取 CLAUDE.md 失败: {e}")
    
    # 备选: 根目录下的 CLAUDE.md
    root_path = os.path.join(project_root, "CLAUDE.md")
    if os.path.exists(root_path):
        try:
            with open(root_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception as e:
            print(f"⚠️  读取 CLAUDE.md 失败: {e}")
    
    return None


def detect_tech_stack(project_root: str) -> Optional[str]:
    """
    自动检测项目技术栈
    
    通过检测标志性文件判断项目类型:
    - requirements.txt / setup.py → Python
    - package.json → Node.js/JavaScript
    - go.mod → Go
    - pom.xml / build.gradle → Java
    - Cargo.toml → Rust
    - Gemfile → Ruby
    - composer.json → PHP
    
    Args:
        project_root: 项目根目录
        
    Returns:
        技术栈描述字符串,如果无法检测则返回 None
    """
    indicators = {
        # Python
        "requirements.txt": "Python 项目 (使用 pip 管理依赖)",
        "setup.py": "Python 项目 (使用 setuptools)",
        "pyproject.toml": "Python 项目 (使用 Poetry 或 PEP 517)",
        "Pipfile": "Python 项目 (使用 Pipenv)",
        
        # JavaScript/TypeScript
        "package.json": "Node.js/JavaScript 项目",
        "tsconfig.json": "TypeScript 项目",
        "next.config.js": "Next.js 项目",
        "nuxt.config.js": "Nuxt.js 项目",
        
        # Go
        "go.mod": "Go 项目",
        
        # Java
        "pom.xml": "Java/Maven 项目",
        "build.gradle": "Java/Gradle 项目",
        
        # Rust
        "Cargo.toml": "Rust 项目",
        
        # Ruby
        "Gemfile": "Ruby 项目",
        
        # PHP
        "composer.json": "PHP 项目",
        
        # .NET
        "*.csproj": ".NET/C# 项目",
        
        # Docker
        "Dockerfile": "使用 Docker 容器化",
        "docker-compose.yml": "使用 Docker Compose",
    }
    
    detected = []
    
    for filename, description in indicators.items():
        # 处理通配符
        if "*" in filename:
            import glob
            pattern = os.path.join(project_root, filename)
            if glob.glob(pattern):
                detected.append(f"- {description}")
        else:
            filepath = os.path.join(project_root, filename)
            if os.path.exists(filepath):
                detected.append(f"- {description}")
    
    return "\n".join(detected) if detected else None


def detect_project_structure(project_root: str) -> Optional[str]:
    """
    检测项目结构(顶层目录)
    
    Args:
        project_root: 项目根目录
        
    Returns:
        项目结构描述
    """
    try:
        items = os.listdir(project_root)
        
        # 过滤隐藏文件和常见忽略项
        ignore_prefixes = [".", "__", "node_modules", "venv", ".git"]
        visible_items = [
            item for item in items 
            if not any(item.startswith(p) for p in ignore_prefixes)
        ]
        
        # 分类
        dirs = []
        files = []
        
        for item in visible_items:
            full_path = os.path.join(project_root, item)
            if os.path.isdir(full_path):
                dirs.append(item + "/")
            else:
                files.append(item)
        
        # 只显示重要的目录和文件
        important_dirs = [d for d in dirs if d in [
            "src/", "lib/", "app/", "tests/", "docs/", 
            "config/", "scripts/", "tools/"
        ]]
        
        important_files = [f for f in files if f in [
            "README.md", "LICENSE", "Makefile", "CHANGELOG.md"
        ]]
        
        output_parts = []
        
        if important_dirs:
            output_parts.append("主要目录:")
            for d in sorted(important_dirs):
                output_parts.append(f"  - {d}")
        
        if important_files:
            output_parts.append("\n重要文件:")
            for f in sorted(important_files):
                output_parts.append(f"  - {f}")
        
        return "\n".join(output_parts) if output_parts else None
    
    except Exception:
        return None
```

### 2.2 使用示例

```python
# 在 Agent Loop 中加载上下文
from core.context import load_project_context

class AgentLoop:
    def _build_system_prompt(self) -> str:
        parts = []
        
        # 基础角色
        parts.append("你是一个 AI 编程助手...")
        
        # 项目上下文
        project_context = load_project_context(".")
        if project_context:
            parts.append(project_context)
        # 输出示例:
        # ## 项目约定
        # 
        # ## 项目架构
        # - 使用 FastAPI 构建 REST API
        # - PostgreSQL 作为主数据库
        # 
        # ## 技术栈
        # 
        # - Python 项目 (使用 pip 管理依赖)
        # - 使用 Docker 容器化
        
        # 工具说明
        parts.append("可用工具:...")
        
        return "\n\n".join(parts)
```

---

## 3. CLAUDE.md 最佳实践

### 3.1 标准模板

```markdown
# .claude/CLAUDE.md

## 项目概述

简要描述项目的目标和主要功能。

**项目名称:** My Project  
**版本:** 1.0.0  
**主要功能:** 
- 功能 1
- 功能 2

## 项目架构

### 技术栈

- **后端:** FastAPI (Python 3.10+)
- **数据库:** PostgreSQL 14
- **缓存:** Redis 7
- **消息队列:** RabbitMQ
- **部署:** Docker + Kubernetes

### 目录结构

```
my_project/
├── app/              # 应用代码
│   ├── api/         # API 路由
│   ├── models/      # 数据模型
│   ├── services/    # 业务逻辑
│   └── utils/       # 工具函数
├── tests/           # 测试代码
├── docs/            # 文档
└── config/          # 配置文件
```

### 关键设计决策

1. **异步优先**: 所有 I/O 操作使用 async/await
2. **依赖注入**: 使用 FastAPI 的 Depends 机制
3. **错误处理**: 统一使用 HTTPException
4. **日志记录**: 使用 structlog 结构化日志

## 编码规范

### Python 风格

- 遵循 PEP 8
- 使用类型注解(强制)
- 函数必须有 docstring
- 最大行长度: 88 字符(black 默认)

### 命名约定

- 变量/函数: `snake_case`
- 类名: `PascalCase`
- 常量: `UPPER_CASE`
- 私有方法: `_leading_underscore`

### 示例代码

```python
from typing import List
from fastapi import APIRouter, Depends

router = APIRouter()

@router.get("/users", response_model=List[UserSchema])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    获取用户列表
    
    Args:
        skip: 跳过的记录数
        limit: 返回的最大记录数
        db: 数据库会话
        
    Returns:
        用户列表
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return users
```

## 测试要求

- 使用 pytest 框架
- 单元测试覆盖率 ≥ 80%
- 每个新功能必须包含测试
- 运行测试: `pytest tests/ -v --cov=app`

## Git 工作流

- 分支策略: Git Flow
- 提交信息: Conventional Commits
- PR 要求: 至少 1 个 reviewer,所有测试通过

## 部署流程

1. 构建 Docker 镜像: `docker build -t myapp .`
2. 推送到仓库: `docker push registry/myapp:latest`
3. 更新 Kubernetes: `kubectl apply -f k8s/`

## 常见问题

### Q: 如何添加新的 API 端点?

A: 
1. 在 `app/api/` 创建路由文件
2. 定义 Pydantic schema
3. 实现业务逻辑
4. 添加单元测试
5. 更新 API 文档

### Q: 数据库迁移怎么做?

A:
1. 修改 `app/models/` 中的模型
2. 生成迁移: `alembic revision --autogenerate -m "描述"`
3. 检查迁移文件
4. 执行迁移: `alembic upgrade head`
```

### 3.2 精简版模板(小型项目)

```markdown
# .claude/CLAUDE.md

## 技术栈

- Python 3.10+
- Flask
- SQLite

## 编码规范

- 使用类型注解
- 函数必须有 docstring
- 遵循 PEP 8

## 项目结构

```
project/
├── app.py          # 主应用
├── models.py       # 数据模型
├── routes.py       # 路由
└── tests/          # 测试
```

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 运行开发服务器
python app.py

# 运行测试
pytest tests/
```
```

---

## 4. YAML 配置系统

### 4.1 默认配置

```yaml
# config/defaults.yaml

# LLM 配置
llm:
  provider: openai  # openai, anthropic, azure, local
  model: gpt-4o
  base_url: https://api.openai.com/v1
  api_key: null  # 从环境变量读取
  max_tokens: 4096
  temperature: 0.2
  top_p: 1.0
  frequency_penalty: 0.0
  presence_penalty: 0.0

# 权限配置
permissions:
  mode: normal  # normal, auto, plan, bypass
  allow_rules:
    - "run_command:ls"
    - "run_command:git status"
    - "run_command:git log"
    - "read_file:*"
  deny_rules:
    - "run_command:rm -rf"
    - "run_command:sudo"
    - "run_command:shutdown"
    - "run_command:reboot"

# Agent 配置
agent:
  max_iterations: 20
  context_window: 200000  # token 限制
  auto_compact_threshold: 0.95  # 95% 时触发压缩
  retry_max_attempts: 3
  retry_backoff_factor: 2  # 指数退避因子

# 上下文配置
context:
  load_claude_md: true
  max_files_read: 10  # 单次最多读取的文件数
  max_output_lines: 500  # 工具输出最大行数
  tech_stack_detection: true  # 自动检测技术栈

# 日志配置
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: null  # 日志文件路径,null 表示只输出到控制台

# UI 配置
ui:
  show_token_usage: true  # 显示 token 使用情况
  show_tool_calls: true  # 显示工具调用
  color_output: true  # 彩色输出
```

### 4.2 配置加载器实现

```python
# config/loader.py
import os
import yaml
from typing import Dict, Any, Optional
from copy import deepcopy


DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "defaults.yaml")


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载并合并配置
    
    优先级(从高到低):
    1. 命令行参数(由 CLI 处理)
    2. 环境变量
    3. 用户配置文件(config.yaml)
    4. 默认配置(defaults.yaml)
    
    Args:
        config_path: 用户配置文件路径,默认为当前目录的 config.yaml
        
    Returns:
        合并后的配置字典
    """
    # 1. 加载默认配置
    config = load_defaults()
    
    # 2. 加载用户配置文件
    user_config_path = config_path or "config.yaml"
    if os.path.exists(user_config_path):
        user_config = load_yaml_file(user_config_path)
        config = deep_merge(config, user_config)
    
    # 3. 环境变量覆盖
    config = apply_env_overrides(config)
    
    return config


def load_defaults() -> Dict[str, Any]:
    """加载默认配置"""
    return load_yaml_file(DEFAULT_CONFIG_PATH)


def load_yaml_file(file_path: str) -> Dict[str, Any]:
    """
    加载 YAML 文件
    
    Args:
        file_path: YAML 文件路径
        
    Returns:
        解析后的字典
        
    Raises:
        FileNotFoundError: 文件不存在
        yaml.YAMLError: YAML 格式错误
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if data else {}
    except FileNotFoundError:
        raise FileNotFoundError(f"配置文件不存在: {file_path}")
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"YAML 格式错误 ({file_path}): {e}")


def deep_merge(base: Dict, override: Dict) -> Dict:
    """
    深度合并两个字典
    
    Args:
        base: 基础字典
        override: 覆盖字典
        
    Returns:
        合并后的新字典
    """
    result = deepcopy(base)
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # 递归合并嵌套字典
            result[key] = deep_merge(result[key], value)
        else:
            # 直接覆盖
            result[key] = deepcopy(value)
    
    return result


def apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    应用环境变量覆盖
    
    支持的环境变量:
    - OPENAI_API_KEY → llm.api_key
    - ANTHROPIC_API_KEY → llm.api_key (如果 provider 是 anthropic)
    - MODEL → llm.model
    - PERMISSION_MODE → permissions.mode
    - MAX_ITERATIONS → agent.max_iterations
    - LOG_LEVEL → logging.level
    
    Args:
        config: 当前配置
        
    Returns:
        应用环境变量后的配置
    """
    # LLM API Key
    if os.environ.get("OPENAI_API_KEY"):
        config["llm"]["api_key"] = os.environ["OPENAI_API_KEY"]
    elif os.environ.get("ANTHROPIC_API_KEY"):
        config["llm"]["api_key"] = os.environ["ANTHROPIC_API_KEY"]
    
    # 模型名称
    if os.environ.get("MODEL"):
        config["llm"]["model"] = os.environ["MODEL"]
    
    # 权限模式
    if os.environ.get("PERMISSION_MODE"):
        config["permissions"]["mode"] = os.environ["PERMISSION_MODE"]
    
    # 最大迭代次数
    if os.environ.get("MAX_ITERATIONS"):
        try:
            config["agent"]["max_iterations"] = int(os.environ["MAX_ITERATIONS"])
        except ValueError:
            print(f"⚠️  无效的 MAX_ITERATIONS: {os.environ['MAX_ITERATIONS']}")
    
    # 日志级别
    if os.environ.get("LOG_LEVEL"):
        config["logging"]["level"] = os.environ["LOG_LEVEL"].upper()
    
    return config


def validate_config(config: Dict[str, Any]) -> List[str]:
    """
    验证配置的有效性
    
    Args:
        config: 待验证的配置
        
    Returns:
        错误消息列表,为空表示配置有效
    """
    errors = []
    
    # 验证 LLM 配置
    if not config.get("llm", {}).get("api_key"):
        errors.append("缺少 LLM API 密钥,请设置 OPENAI_API_KEY 环境变量或在配置文件中指定")
    
    valid_providers = ["openai", "anthropic", "azure", "local"]
    if config.get("llm", {}).get("provider") not in valid_providers:
        errors.append(f"无效的 LLM provider,必须是 {valid_providers}")
    
    # 验证权限模式
    valid_modes = ["normal", "auto", "plan", "bypass"]
    if config.get("permissions", {}).get("mode") not in valid_modes:
        errors.append(f"无效的权限模式,必须是 {valid_modes}")
    
    # 验证最大迭代次数
    max_iter = config.get("agent", {}).get("max_iterations", 0)
    if not isinstance(max_iter, int) or max_iter < 1:
        errors.append("max_iterations 必须是正整数")
    
    # 验证温度值
    temperature = config.get("llm", {}).get("temperature", 0)
    if not (0 <= temperature <= 2):
        errors.append("temperature 必须在 0-2 之间")
    
    return errors
```

### 4.3 使用示例

```python
# cli.py
from config.loader import load_config, validate_config

def main():
    # 加载配置
    config = load_config()
    
    # 验证配置
    errors = validate_config(config)
    if errors:
        print("❌ 配置错误:")
        for error in errors:
            print(f"  - {error}")
        exit(1)
    
    # 使用配置
    print(f"✅ 配置加载成功")
    print(f"   Model: {config['llm']['model']}")
    print(f"   Permission Mode: {config['permissions']['mode']}")
    print(f"   Max Iterations: {config['agent']['max_iterations']}")
    
    # 初始化 Agent Loop
    from core.agent_loop import AgentLoop
    loop = AgentLoop(config)
    
    # ... 运行 ...
```

---

## 5. 环境变量优先级

### 5.1 完整优先级链

```
命令行参数 > 环境变量 > config.yaml > defaults.yaml
```

### 5.2 示例场景

**场景 1:** 开发环境使用 GPT-4,生产环境使用 GPT-3.5

```bash
# 开发环境
export MODEL=gpt-4
python cli.py "优化这段代码"

# 生产环境
export MODEL=gpt-3.5-turbo
python cli.py "修复这个 bug"
```

**场景 2:** 临时切换权限模式

```bash
# 临时使用 bypass 模式(不修改配置文件)
export PERMISSION_MODE=bypass
python cli.py "批量重命名文件"
```

**场景 3:** CI/CD 环境配置

```yaml
# .github/workflows/ci.yml
jobs:
  test:
    runs-on: ubuntu-latest
    env:
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      PERMISSION_MODE: bypass
      MAX_ITERATIONS: 10
    steps:
      - run: python cli.py "运行测试并修复失败用例"
```

---

## 6. 上下文管理高级主题

### 6.1 多项目上下文隔离

当你在多个项目间切换时,每个项目应有独立的上下文:

```bash
# 项目 A
cd /path/to/project-a
python cli.py "分析项目结构"  # 加载 project-a/.claude/CLAUDE.md

# 项目 B
cd /path/to/project-b
python cli.py "添加新功能"  # 加载 project-b/.claude/CLAUDE.md
```

### 6.2 动态上下文注入

除了静态的 CLAUDE.md,还可以在运行时动态注入上下文:

```python
class AgentLoop:
    def _build_system_prompt(self) -> str:
        parts = []
        
        # 1. 静态上下文(CLAUDE.md)
        parts.append(load_project_context())
        
        # 2. 动态上下文: 当前 Git 分支
        git_branch = get_current_git_branch()
        if git_branch:
            parts.append(f"当前 Git 分支: {git_branch}")
        
        # 3. 动态上下文: 最近修改的文件
        recent_files = get_recently_modified_files(limit=5)
        if recent_files:
            parts.append(f"最近修改的文件:\n" + "\n".join(recent_files))
        
        # 4. 动态上下文: 环境变量
        env_vars = {k: v for k, v in os.environ.items() if k.startswith("APP_")}
        if env_vars:
            parts.append(f"应用环境变量:\n{json.dumps(env_vars, indent=2)}")
        
        return "\n\n".join(parts)


def get_current_git_branch() -> Optional[str]:
    """获取当前 Git 分支"""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_recently_modified_files(limit: int = 5) -> List[str]:
    """获取最近修改的文件"""
    try:
        result = subprocess.run(
            ["git", "log", "--name-only", "-n", str(limit), "--pretty=format:"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            files = [f for f in result.stdout.splitlines() if f]
            return list(dict.fromkeys(files))[:limit]  # 去重
    except Exception:
        pass
    return []
```

### 6.3 上下文缓存优化

对于大型项目,频繁读取 CLAUDE.md 和检测技术栈可能较慢。可以引入缓存:

```python
from functools import lru_cache
import hashlib


@lru_cache(maxsize=128)
def load_project_context_cached(project_root: str) -> str:
    """
    带缓存的上下文加载
    
    缓存键: 项目路径 + CLAUDE.md 的 MD5
    """
    return load_project_context(project_root)


def get_context_cache_key(project_root: str) -> str:
    """生成上下文缓存键"""
    claude_md_path = os.path.join(project_root, ".claude", "CLAUDE.md")
    
    if os.path.exists(claude_md_path):
        with open(claude_md_path, "rb") as f:
            md5 = hashlib.md5(f.read()).hexdigest()
    else:
        md5 = "no-claude-md"
    
    return f"{project_root}:{md5}"
```

---

## 7. 单元测试示例

### 7.1 测试上下文加载

```python
# tests/test_context.py
import pytest
import tempfile
import os
from core.context import load_project_context, load_claude_md, detect_tech_stack


def test_load_claude_md():
    """测试 CLAUDE.md 加载"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建 .claude/CLAUDE.md
        claude_dir = os.path.join(tmpdir, ".claude")
        os.makedirs(claude_dir)
        
        claude_md_path = os.path.join(claude_dir, "CLAUDE.md")
        with open(claude_md_path, "w") as f:
            f.write("## 测试项目\n这是测试内容")
        
        content = load_claude_md(tmpdir)
        assert content == "## 测试项目\n这是测试内容"


def test_load_claude_md_not_exists():
    """测试 CLAUDE.md 不存在的情况"""
    with tempfile.TemporaryDirectory() as tmpdir:
        content = load_claude_md(tmpdir)
        assert content is None


def test_detect_tech_stack_python():
    """测试 Python 项目检测"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建 requirements.txt
        with open(os.path.join(tmpdir, "requirements.txt"), "w") as f:
            f.write("flask==2.0.1")
        
        tech_stack = detect_tech_stack(tmpdir)
        assert "Python 项目" in tech_stack


def test_detect_tech_stack_nodejs():
    """测试 Node.js 项目检测"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建 package.json
        with open(os.path.join(tmpdir, "package.json"), "w") as f:
            f.write('{"name": "test"}')
        
        tech_stack = detect_tech_stack(tmpdir)
        assert "Node.js" in tech_stack


def test_load_project_context_complete():
    """测试完整的上下文加载"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建 CLAUDE.md
        claude_dir = os.path.join(tmpdir, ".claude")
        os.makedirs(claude_dir)
        with open(os.path.join(claude_dir, "CLAUDE.md"), "w") as f:
            f.write("## 约定\n使用 TypeScript")
        
        # 创建 package.json
        with open(os.path.join(tmpdir, "package.json"), "w") as f:
            f.write('{}')
        
        context = load_project_context(tmpdir)
        assert "约定" in context
        assert "TypeScript" in context
        assert "Node.js" in context
```

### 7.2 测试配置加载

```python
# tests/test_config.py
import pytest
import tempfile
import os
import yaml
from config.loader import load_config, validate_config, deep_merge


def test_load_default_config():
    """测试加载默认配置"""
    config = load_config()
    
    assert "llm" in config
    assert "permissions" in config
    assert "agent" in config


def test_load_user_config():
    """测试加载用户配置"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建用户配置文件
        config_path = os.path.join(tmpdir, "config.yaml")
        user_config = {
            "llm": {
                "model": "gpt-3.5-turbo"
            },
            "agent": {
                "max_iterations": 10
            }
        }
        
        with open(config_path, "w") as f:
            yaml.dump(user_config, f)
        
        # 加载配置
        config = load_config(config_path)
        
        # 验证用户配置覆盖了默认值
        assert config["llm"]["model"] == "gpt-3.5-turbo"
        assert config["agent"]["max_iterations"] == 10
        
        # 验证未覆盖的配置保持默认值
        assert "temperature" in config["llm"]


def test_deep_merge():
    """测试深度合并"""
    base = {
        "a": 1,
        "b": {
            "c": 2,
            "d": 3
        }
    }
    
    override = {
        "b": {
            "c": 20,
            "e": 4
        },
        "f": 5
    }
    
    result = deep_merge(base, override)
    
    assert result["a"] == 1  # 保持不变
    assert result["b"]["c"] == 20  # 被覆盖
    assert result["b"]["d"] == 3  # 保持不变
    assert result["b"]["e"] == 4  # 新增
    assert result["f"] == 5  # 新增


def test_validate_config_valid():
    """测试有效配置验证"""
    config = {
        "llm": {
            "api_key": "test-key",
            "provider": "openai",
            "model": "gpt-4",
            "temperature": 0.5
        },
        "permissions": {
            "mode": "normal"
        },
        "agent": {
            "max_iterations": 20
        }
    }
    
    errors = validate_config(config)
    assert len(errors) == 0


def test_validate_config_invalid():
    """测试无效配置验证"""
    config = {
        "llm": {
            "provider": "invalid-provider",
            "temperature": 3.0  # 超出范围
        },
        "permissions": {
            "mode": "invalid-mode"
        },
        "agent": {
            "max_iterations": -1  # 负数
        }
    }
    
    errors = validate_config(config)
    assert len(errors) > 0
```

---

## 8. 常见问题

### Q1: CLAUDE.md 应该放在哪里?

**A:** 推荐放在 `.claude/CLAUDE.md`,备选方案是项目根目录的 `CLAUDE.md`。

```
my_project/
├── .claude/
│   └── CLAUDE.md  ← 推荐位置
├── src/
└── README.md
```

### Q2: 如何让不同子目录有不同的约定?

**A:** 在每个子目录创建独立的 `.claude/CLAUDE.md`:

```
my_project/
├── .claude/CLAUDE.md          # 全局约定
├── frontend/.claude/CLAUDE.md # React 规范
└── backend/.claude/CLAUDE.md  # FastAPI 规范
```

### Q3: 配置文件的优先级如何工作?

**A:** 

```yaml
# defaults.yaml
llm:
  model: gpt-4
  temperature: 0.2

# config.yaml (用户配置)
llm:
  model: gpt-3.5-turbo  # 覆盖 model

# 最终结果
llm:
  model: gpt-3.5-turbo  # 来自 config.yaml
  temperature: 0.2      # 来自 defaults.yaml
```

### Q4: 如何在 CI/CD 中使用不同的配置?

**A:** 使用环境变量:

```bash
# GitHub Actions
export PERMISSION_MODE=bypass
export MAX_ITERATIONS=10
export MODEL=gpt-3.5-turbo

python cli.py "执行任务"
```

---

**文档版本:** v1.0  
**最后更新:** 2026-04-05  
**相关文档:** 
- [文档 1: 架构总览](./01-architecture-overview.md)
- [文档 2: Agent Loop 核心实现](./02-agent-loop-implementation.md)
- [文档 3: 工具系统与权限管理](./03-tools-and-permissions.md)
