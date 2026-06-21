---
name: git-workflow
description: Git 工作流和提交规范
trigger: 当执行 Git 操作或提交代码时激活
when_to_use: 当执行 Git 提交、分支管理、合并或创建 PR 时主动激活
---

# Git 工作流规范

## 分支策略

### 主要分支
- `main` - 生产环境代码,受保护
- `develop` - 开发环境,集成测试
- `feature/*` - 功能分支
- `bugfix/*` - 修复分支
- `hotfix/*` - 紧急修复分支

### 分支命名
```
feature/user-authentication
bugfix/fix-login-error
hotfix/security-patch
```

## 提交规范

### 提交消息格式
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 类型
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式(不影响代码运行)
- `refactor`: 重构
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具相关

### 示例

```bash
# ✅ 好的提交消息
feat(auth): 添加用户登录功能

实现 JWT 认证,支持 token 刷新

Closes #123

fix(api): 修复空指针异常

当用户数据为空时返回 404 而非 500

docs(readme): 更新安装说明

添加 Windows 和 macOS 的安装步骤
```

## 工作流

### 功能开发
```bash
# 1. 从 develop 创建功能分支
git checkout develop
git pull origin develop
git checkout -b feature/new-feature

# 2. 开发并提交
git add .
git commit -m "feat: 实现新功能"

# 3. 推送到远程
git push origin feature/new-feature

# 4. 创建 Pull Request 合并到 develop
```

### 紧急修复
```bash
# 1. 从 main 创建 hotfix 分支
git checkout main
git pull origin main
git checkout -b hotfix/critical-bug

# 2. 修复并提交
git commit -m "fix: 修复关键 bug"

# 3. 合并到 main 和 develop
git checkout main
git merge hotfix/critical-bug
git push origin main

git checkout develop
git merge hotfix/critical-bug
git push origin develop
```

## 最佳实践

### 提交前检查
1. 运行测试: `pytest`
2. 代码格式化: `black .`
3. 静态检查: `ruff check .`
4. 查看变更: `git diff --cached`

### 提交原则
- 频繁提交,每次提交完成一个逻辑单元
- 提交前确保代码可编译/测试通过
- 提交消息清晰描述"为什么"而非"做了什么"
- 使用现在时态: "添加功能" 而非 "添加了功能"

### 避免的提交
```bash
# ❌ 不要提交
- 调试代码 (print, console.log)
- 临时文件 (*.tmp, *.bak)
- 敏感信息 (密码, API Key)
- node_modules, __pycache__, .env
```

### .gitignore 示例
```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/

# 环境
.env
.env.local

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

## Git 命令速查

### 常用命令
```bash
# 查看状态
git status
git log --oneline -10

# 撤销
git reset --soft HEAD~1  # 撤销提交,保留变更
git checkout -- <file>   # 撤销文件修改

# 储藏
git stash                # 储藏变更
git stash pop            # 恢复储藏

# 清理
git clean -fd            # 删除未跟踪文件
```

### 查看历史
```bash
# 图形化日志
git log --graph --oneline --all

# 查看某文件的修改历史
git log -p <file>

# 查找包含某字符串的提交
git log --grep="keyword"
```

## 协作规范

### Code Review
- 每个 PR 至少 1 人审核
- 审核通过后才能合并
- 小步提交,便于 review
- 及时回复 review 意见

### 冲突解决
```bash
# 1. 更新主分支
git checkout develop
git pull origin develop

# 2. 合并到功能分支
git checkout feature/my-feature
git merge develop

# 3. 解决冲突后提交
git add .
git commit -m "merge: 解决与 develop 的冲突"
```
