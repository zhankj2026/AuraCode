# 技能系统

技能（Skills）是按需激活的**领域知识包**。激活后，技能内容会注入到 AI 的系统提示词中，指导 AI 遵循特定领域的最佳实践。

技能采用**渐进式披露**设计：启动时只加载元数据（名称、描述），激活后才加载完整提示词，有效节省 Token。

---

## 内置技能

| 技能 | 说明 | 触发场景 |
|------|------|----------|
| `git-workflow` | Git 工作流规范（commit message 格式、分支策略）| 涉及 Git 操作时 |
| `python-standards` | Python 编码规范（PEP 8、类型注解、文档字符串）| Python 项目开发时 |
| `simplify` | 代码审查与简化（三路并行审查）| 执行 `/simplify` 命令时 |
| `verify` | 变更验证 | 执行 `/verify` 命令时 |
| `debug` | 调试诊断 | 执行 `/debug` 命令时 |
| `batch` | 大规模并行变更编排 | 执行 `/batch` 命令时 |
| `update-config` | 配置管理（Hooks/权限/环境变量）| 执行 `/update-config` 命令时 |

---

## 基本操作

### 查看技能

```
> /skills

可用技能 (共 7 个):

  📦 内置 (7 个):
    ⏸️ git-workflow
      描述: Git 工作流规范
      触发: 涉及 Git 操作时

    ⏸️ python-standards
      描述: Python 编码规范
      触发: Python 项目开发时
    ...
```

### 激活技能

```
> /activate git-workflow

✅ 技能 'git-workflow' 已激活
```

激活后，AI 在处理 Git 相关任务时会自动遵循技能中定义的最佳实践。

### 停用技能

```
> /deactivate git-workflow

✅ 技能 'git-workflow' 已停用
```

### 查看已激活技能

```
> /active

已激活技能 (1 个):
  ✅ git-workflow
```

---

## 自定义技能

支持三个层级的自定义技能，自动发现与加载：

### 层级

| 层级 | 路径 | 说明 |
|------|------|------|
| 内置 | `auracode/skills/` | 随 AuraCode 发布 |
| 项目级 | `.auracode/skills/` | 跟随仓库，团队共享 |
| 用户级 | `~/.auracode/skills/` | 个人全局，所有项目可用 |

### 目录结构

```
.auracode/skills/my-skill/
├── SKILL.md      # 技能元数据（YAML frontmatter）
└── prompt.md     # 完整提示词内容（激活时加载）
```

### SKILL.md 格式

```markdown
---
name: my-skill
description: 我的自定义技能
trigger: 当需要执行特定任务时
---

# My Skill

详细的技能指导内容...
```

### 示例：创建项目级技能

```bash
mkdir -p .auracode/skills/api-design
```

创建 `.auracode/skills/api-design/SKILL.md`：
```markdown
---
name: api-design
description: RESTful API 设计规范
trigger: 设计或修改 API 接口时
---
```

创建 `.auracode/skills/api-design/prompt.md`：
```markdown
# API 设计规范

## 命名规则
- 使用小写字母和连字符：`/users/{id}/orders`
- 避免动词，用 HTTP 方法表示操作

## 状态码
- 200: 成功
- 201: 创建成功
- 400: 请求参数错误
- 401: 未认证
- 403: 无权限
- 404: 资源不存在
- 500: 服务器错误
...
```

重启 AuraCode 后技能自动生效：

```
> /skills

可用技能 (共 8 个):

  📦 内置 (7 个):
    ...

  📁 项目级 (1 个):
    ⏸️ api-design
      描述: RESTful API 设计规范
      触发: 设计或修改 API 接口时
```

---

## 相关命令

| 命令 | 说明 |
|------|------|
| `/skills` | 列出所有可用技能 |
| `/activate <name>` | 激活技能 |
| `/deactivate <name>` | 停用技能 |
| `/active` | 查看已激活技能 |
