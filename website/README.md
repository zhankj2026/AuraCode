# AuraCode 官方网站

这是 AuraCode AI 编程助手的官方网站，提供产品介绍、功能展示和详细文档。

## 📁 项目结构

```
website/
├── index.html              # 首页
├── css/
│   ├── style.css          # 主样式文件
│   └── docs.css           # 文档页面样式
├── js/
│   ├── main.js            # 主脚本
│   └── docs.js            # 文档页面脚本
├── docs/
│   ├── README.md          # 文档说明
│   ├── quick-start.html   # 快速开始文档
│   ├── quickstart.html    # 快速开始（旧版）
│   ├── test_bridge.html   # Bridge PC 端测试页
│   ├── test_bridge_mobile.html  # Bridge 移动端测试页
│   ├── user-guide/        # 用户指南
│   │   ├── chat.html      # 对话交互
│   │   ├── commands.html  # 命令参考
│   │   ├── tools.html     # 工具系统
│   │   ├── skills.html    # 技能系统
│   │   ├── memory.html    # 记忆系统
│   │   ├── permissions.html # 权限管理
│   │   └── mcp.html       # MCP 协议
│   ├── advanced/          # 高级功能
│   │   ├── bridge.html    # Bridge 远程控制
│   │   ├── hooks.html     # 钩子系统
│   │   ├── plugins.html   # 插件系统
│   │   └── error-recovery.html # 错误恢复
│   └── development/       # 开发文档
│       ├── architecture.html # 架构总览
│       └── agent-architecture-guide.html # 智能体架构指南
└── README.md              # 本文件
```

## 🚀 快速开始

### 方式 1: 直接打开

直接用浏览器打开 `index.html` 文件即可查看网站。

### 方式 2: 使用本地服务器（推荐）

使用 Python 启动本地服务器：

```bash
# Python 3
python -m http.server 8000

# Python 2
python -m SimpleHTTPServer 8000
```

然后访问：http://localhost:8000

### 方式 3: 使用 Node.js

安装 http-server：

```bash
npm install -g http-server
http-server -p 8000
```

然后访问：http://localhost:8000

## 📄 页面说明

### 首页 (index.html)

- **导航栏**：固定顶部，支持移动端响应式菜单
- **Hero 区域**：产品介绍、统计数字、终端演示
- **功能展示**：9 个核心功能卡片（56 工具/54 命令/9 技能等）
- **文档区域**：13 个文档入口（用户指南/高级功能/开发文档）
- **快速开始**：3 步安装指南
- **LLM 支持**：支持的模型列表（智谱 AI/OpenAI/其他）
- **页脚**：链接和版权信息

### 文档页面

#### 快速开始 (docs/quick-start.html)

- **侧边栏**：文档导航
- **内容区域**：详细的安装和配置说明
- **代码块**：支持一键复制
- **信息框**：提示、警告、成功等不同类型

#### 用户指南 (docs/user-guide/)

- **chat.html**：对话交互指南
- **commands.html**：54 条命令完整参考
- **tools.html**：56 个内置工具分类介绍
- **skills.html**：9 项领域技能激活与自定义
- **memory.html**：跨会话持久化记忆系统
- **permissions.html**：四级权限模式与规则配置
- **mcp.html**：MCP 协议集成指南

#### 高级功能 (docs/advanced/)

- **bridge.html**：Bridge 远程控制（REST + WebSocket）
- **hooks.html**：配置驱动的事件钩子系统
- **plugins.html**：插件生命周期管理
- **error-recovery.html**：6 层纵深防御体系

#### 开发文档 (docs/development/)

- **architecture.html**：项目结构与模块关系
- **agent-architecture-guide.html**：智能体架构指南（TAOR 循环）

#### Bridge 测试页面

- **test_bridge.html**：PC 端 Bridge 测试界面（支持事件级 + Token 级流式）
- **test_bridge_mobile.html**：移动端 Bridge 测试界面（响应式设计）

## 🎨 设计特点

- **深色主题**：现代化的深色设计
- **响应式布局**：支持桌面、平板、手机
- **平滑动画**：元素进入视口动画
- **交互效果**：悬停、点击等交互反馈
- **渐变色彩**：紫色渐变主题色
- **代码高亮**：简单的语法高亮

## 🔧 自定义配置

### 修改主题色

在 `css/style.css` 中修改 CSS 变量：

```css
:root {
    --primary-color: #6366f1;
    --primary-dark: #4f46e5;
    --secondary-color: #8b5cf6;
    /* ... 其他变量 */
}
```

### 修改内容

- **首页内容**：编辑 `index.html`
- **文档内容**：编辑 `docs/quickstart.html` 或创建新的文档页面
- **样式**：编辑 `css/style.css` 或 `css/docs.css`
- **交互**：编辑 `js/main.js` 或 `js/docs.js`

### 添加新文档页面

1. 在 `docs/` 目录下创建新的 HTML 文件
2. 复制 `quickstart.html` 的结构
3. 修改内容和侧边栏链接
4. 在首页的文档区域添加链接

## 📱 响应式断点

- **桌面**：> 1024px
- **平板**：768px - 1024px
- **手机**：< 768px

## 🌐 浏览器支持

- Chrome (推荐)
- Firefox
- Safari
- Edge

## 📦 依赖

- Font Awesome 6.4.0 (CDN)
- 无其他依赖

## 🚀 部署

### GitHub Pages

1. 将 `website` 目录推送到 GitHub
2. 在仓库设置中启用 GitHub Pages
3. 选择 `main` 分支作为源

### Vercel

1. 安装 Vercel CLI：`npm i -g vercel`
2. 运行：`vercel`
3. 按照提示完成部署

### Netlify

1. 登录 Netlify
2. 拖拽 `website` 目录到部署区域
3. 完成部署

## 📝 待办事项

- [x] 添加用户指南文档（7 个页面）
- [x] 添加高级功能文档（4 个页面）
- [x] 添加开发文档（2 个页面）
- [x] 添加 Bridge 测试页面（PC + 移动端）
- [x] 支持 Token 级流式输出（打字机效果）
- [ ] 添加搜索功能
- [ ] 添加暗色/亮色主题切换
- [ ] 添加多语言支持
- [ ] 添加博客功能
- [ ] 添加评论系统

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题，请通过以下方式联系：

- GitHub Issues
- Discussions

---

**AuraCode** - AI 编程助手，让编程更高效！