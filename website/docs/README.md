# 文档系统说明

## 📊 文档架构

AuraCode 采用**单一数据源 + 自动转换**的文档架构：

```
docs/ (Markdown 源文件)
  ↓ build_docs.py 自动转换
website/docs/ (HTML 网站文档)
  ↓ 被引用
website/index.html (官网首页)
```

## 🔄 工作流程

### 1. 编写文档（维护 Markdown）

在 `docs/` 目录下编写或更新 Markdown 文档：

```
docs/
├── quick-start.md              # 快速开始
├── user-guide/                 # 用户指南
│   ├── chat.md                # 对话交互
│   ├── commands.md            # 命令参考
│   ├── tools.md               # 工具系统
│   ├── skills.md              # 技能系统
│   ├── memory.md              # 记忆系统
│   ├── permissions.md         # 权限管理
│   └── mcp.md                 # MCP 协议
├── advanced/                   # 高级功能
│   ├── bridge.md              # Bridge 远程控制
│   ├── hooks.md               # 钩子系统
│   ├── plugins.md             # 插件系统
│   └── error-recovery.md      # 错误恢复
└── development/                # 开发文档
    └── architecture.md        # 架构总览
```

### 2. 转换为 HTML

运行转换脚本：

```bash
python build_docs.py
```

这会将所有 `docs/*.md` 转换为 `website/docs/*.html`，并自动添加：
- 导航栏
- 侧边栏
- 面包屑
- 页脚

### 3. 首页链接自动生效

`website/index.html` 中的文档卡片已配置好链接，转换完成后立即可访问。

## 📁 目录结构

```
website/
├── index.html                      # 官网首页
├── css/                            # 样式文件
│   ├── style.css
│   └── docs.css
├── js/                             # 脚本文件
│   ├── main.js
│   └── docs.js
└── docs/                           # 生成的 HTML 文档
    ├── quick-start.html
    ├── quickstart.html             # 旧版（保留兼容）
    ├── test_bridge.html            # Bridge 测试页面
    ├── user-guide/                 # 用户指南
    │   ├── chat.html
    │   ├── commands.html
    │   ├── tools.html
    │   ├── skills.html
    │   ├── memory.html
    │   ├── permissions.html
    │   └── mcp.html
    ├── advanced/                   # 高级功能
    │   ├── bridge.html
    │   ├── hooks.html
    │   ├── plugins.html
    │   └── error-recovery.html
    └── development/                # 开发文档
        └── architecture.html
```

## 🎯 文档关联图

```
┌─────────────────────────────────────────┐
│         website/index.html              │
│   (官网首页 - 8个文档卡片)              │
└─────────────┬───────────────────────────┘
              │ 链接
              ↓
┌─────────────────────────────────────────┐
│      website/docs/*.html                │
│   (自动生成的 HTML 文档)                │
│   - 带导航栏                            │
│   - 带侧边栏                            │
│   - 带面包屑                            │
└─────────────┬───────────────────────────┘
              │ 由 build_docs.py 生成
              ↓
┌─────────────────────────────────────────┐
│         docs/*.md                       │
│   (Markdown 源文件 - 单一数据源)        │
│   - 易于维护                            │
│   - Git 友好                            │
│   - 可读性强                            │
└─────────────────────────────────────────┘
```

## 📝 添加新文档

### 步骤 1: 创建 Markdown 文件

在 `docs/` 相应目录创建 `.md` 文件：

```bash
# 例如：添加用户指南文档
echo "# 新主题\n\n内容..." > docs/user-guide/new-topic.md
```

### 步骤 2: 运行转换

```bash
python build_docs.py
```

### 步骤 3: 在首页添加链接（可选）

编辑 `website/index.html`，在文档区域添加新卡片：

```html
<div class="doc-card">
    <div class="doc-icon">
        <i class="fas fa-icon-name"></i>
    </div>
    <h3>新主题</h3>
    <p>描述信息</p>
    <a href="docs/user-guide/new-topic.html" class="doc-link">查看文档 →</a>
</div>
```

### 步骤 4: 提交

```bash
git add docs/ website/
git commit -m "docs: 添加新主题文档"
```

## 🔧 build_docs.py 功能

转换脚本 `build_docs.py` 提供：

1. **自动目录结构创建**
   - `website/docs/user-guide/`
   - `website/docs/advanced/`
   - `website/docs/development/`

2. **Markdown 转 HTML**
   - 标题转换 (`#` → `<h1>`)
   - 链接转换 (`[text](url)` → `<a>`)
   - 代码块转换 (```` → `<pre><code>`)
   - 表格转换
   - 粗体/斜体转换

3. **页面模板生成**
   - 统一导航栏
   - 完整侧边栏（包含所有文档链接）
   - 面包屑导航
   - 页脚版权信息

4. **样式注入**
   - Markdown 内容专用样式
   - 代码高亮
   - 表格样式
   - 响应式布局

## 💡 最佳实践

### ✅ 推荐

1. **始终在 `docs/` 中编辑**
   - 不要直接编辑 `website/docs/*.html`
   - 保持 Markdown 为单一数据源

2. **每次更新后运行转换**
   ```bash
   python build_docs.py
   ```

3. **使用相对链接**
   ```markdown
   # 正确
   [命令参考](user-guide/commands.md)
   
   # 错误（绝对路径）
   [命令参考](/docs/user-guide/commands.md)
   ```

4. **保持文档结构清晰**
   - `user-guide/` - 面向用户
   - `advanced/` - 面向高级用户
   - `development/` - 面向开发者

### ❌ 避免

1. 不要手动修改生成的 HTML
2. 不要在 `website/docs/` 中创建 `.md` 文件
3. 不要忘记运行 `build_docs.py` 就提交代码

## 🚀 部署

### 本地预览

```bash
cd website
python -m http.server 8000
# 访问 http://localhost:8000
```

### GitHub Pages

1. 确保 `website/` 目录在仓库中
2. 在仓库设置中启用 GitHub Pages
3. 选择 `main` 分支和 `/opencode/website` 目录

### 静态托管

可直接部署 `website/` 目录到任何静态托管服务：
- Vercel
- Netlify
- Cloudflare Pages
- 任何 Web 服务器

## 📊 统计

- **Markdown 源文件**: 13 个
- **生成 HTML 文件**: 15 个（含 quickstart.html 兼容版）
- **文档分类**: 3 大类（用户指南/高级功能/开发）
- **转换脚本**: 1 个 (`build_docs.py`)

---

**文档系统已完全整合，Markdown 与 Website 自动关联！** 🎉
