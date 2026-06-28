#!/usr/bin/env python3
"""
将 docs/*.md 转换为 website/docs/*.html
实现 Markdown 文档与 Website 的自动关联
"""
import os
import re
from pathlib import Path

def markdown_to_html(md_content, title="AuraCode 文档"):
    """简单的 Markdown 转 HTML"""
    # 提取标题（第一个 # 标题）
    title_match = re.search(r'^# (.+)$', md_content, re.MULTILINE)
    if title_match:
        title = title_match.group(1)
    
    # 转换 Markdown 为 HTML（简化版）
    html_content = md_content
    
    # 转换标题
    html_content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
    
    # 转换链接
    html_content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html_content)
    
    # 转换代码块
    html_content = re.sub(r'```(\w+)?\n(.*?)```', r'<pre><code class="language-\1">\2</code></pre>', html_content, flags=re.DOTALL)
    
    # 转换行内代码
    html_content = re.sub(r'`([^`]+)`', r'<code>\1</code>', html_content)
    
    # 转换粗体和斜体
    html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
    html_content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html_content)
    
    # 转换表格（简化）
    html_content = re.sub(r'\|(.+)\|', r'<div class="md-table-row">|\1|</div>', html_content)
    
    # 转换段落（双换行）
    paragraphs = html_content.split('\n\n')
    html_content = '\n\n'.join([
        f'<p>{p}</p>' if not p.startswith('<h') and not p.startswith('<pre') and not p.startswith('<div') else p
        for p in paragraphs
    ])
    
    return title, html_content

def generate_html_page(title, content, doc_path=""):
    """生成完整的 HTML 页面"""
    # 生成面包屑导航
    breadcrumb = '<span>📂 <a href="../index.html">首页</a></span>'
    if doc_path:
        parts = doc_path.split('/')
        breadcrumb += ''.join([f'<span class="sep">/</span><span>{p}</span>' for p in parts])
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - AuraCode</title>
    <link rel="stylesheet" href="../css/style.css">
    <link rel="stylesheet" href="../css/docs.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .md-content {{ line-height: 1.8; }}
        .md-content h1 {{ font-size: 2rem; margin-bottom: 1rem; }}
        .md-content h2 {{ font-size: 1.5rem; margin: 2rem 0 1rem; }}
        .md-content h3 {{ font-size: 1.25rem; margin: 1.5rem 0 0.75rem; }}
        .md-content p {{ margin: 1rem 0; }}
        .md-content pre {{ background: var(--bg); padding: 1rem; border-radius: 0.5rem; overflow-x: auto; margin: 1rem 0; }}
        .md-content code {{ background: var(--bg); padding: 0.2rem 0.4rem; border-radius: 0.25rem; font-size: 0.9em; }}
        .md-content pre code {{ background: none; padding: 0; }}
        .md-content table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
        .md-content th, .md-content td {{ padding: 0.75rem; border: 1px solid var(--border-color); text-align: left; }}
        .md-content th {{ background: var(--s1); }}
        .md-content ul, .md-content ol {{ margin: 1rem 0; padding-left: 2rem; }}
        .md-content li {{ margin: 0.5rem 0; }}
        .md-content a {{ color: var(--acc); text-decoration: none; }}
        .md-content a:hover {{ text-decoration: underline; }}
        .md-content strong {{ font-weight: 600; }}
        .md-content hr {{ border: none; border-top: 1px solid var(--border-color); margin: 2rem 0; }}
    </style>
</head>
<body>
    <!-- 导航栏 -->
    <nav class="navbar">
        <div class="container">
            <div class="nav-brand">
                <i class="fas fa-code"></i>
                <span>AuraCode</span>
            </div>
            <ul class="nav-menu">
                <li><a href="../index.html">首页</a></li>
                <li><a href="../index.html#features">功能</a></li>
                <li><a href="../index.html#docs">文档</a></li>
                <li><a href="../index.html#quickstart">快速开始</a></li>
            </ul>
        </div>
    </nav>

    <!-- 文档内容 -->
    <div class="docs-container">
        <aside class="docs-sidebar">
            <div class="sidebar-section">
                <h3>入门指南</h3>
                <ul>
                    <li><a href="quickstart.html">快速开始</a></li>
                </ul>
            </div>
            <div class="sidebar-section">
                <h3>用户指南</h3>
                <ul>
                    <li><a href="user-guide/chat.html">对话交互</a></li>
                    <li><a href="user-guide/commands.html">命令参考</a></li>
                    <li><a href="user-guide/tools.html">工具系统</a></li>
                    <li><a href="user-guide/skills.html">技能系统</a></li>
                    <li><a href="user-guide/memory.html">记忆系统</a></li>
                    <li><a href="user-guide/permissions.html">权限管理</a></li>
                    <li><a href="user-guide/mcp.html">MCP 协议</a></li>
                </ul>
            </div>
            <div class="sidebar-section">
                <h3>高级功能</h3>
                <ul>
                    <li><a href="advanced/bridge.html">Bridge 远程控制</a></li>
                    <li><a href="advanced/hooks.html">钩子系统</a></li>
                    <li><a href="advanced/plugins.html">插件系统</a></li>
                    <li><a href="advanced/error-recovery.html">错误恢复</a></li>
                </ul>
            </div>
            <div class="sidebar-section">
                <h3>开发</h3>
                <ul>
                    <li><a href="development/architecture.html">架构总览</a></li>
                </ul>
            </div>
        </aside>

        <main class="docs-content">
            <div class="docs-header">
                <h1>{title}</h1>
            </div>
            <div class="md-content">
                {content}
            </div>

            <div class="docs-navigation">
                <a href="../index.html" class="nav-btn prev">
                    <i class="fas fa-arrow-left"></i>
                    返回首页
                </a>
            </div>
        </main>
    </div>

    <!-- 页脚 -->
    <footer class="footer">
        <div class="container">
            <div class="footer-bottom">
                <p>&copy; 2026 AuraCode. MIT License.</p>
            </div>
        </div>
    </footer>

    <script src="../js/main.js"></script>
    <script src="../js/docs.js"></script>
</body>
</html>"""

def convert_docs():
    """转换所有 Markdown 文档"""
    docs_dir = Path('docs')
    website_docs_dir = Path('website/docs')
    
    # 创建目标目录
    website_docs_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建子目录
    (website_docs_dir / 'user-guide').mkdir(exist_ok=True)
    (website_docs_dir / 'advanced').mkdir(exist_ok=True)
    (website_docs_dir / 'development').mkdir(exist_ok=True)
    
    converted = 0
    
    # 转换所有 .md 文件
    for md_file in docs_dir.rglob('*.md'):
        # 跳过 index.md
        if md_file.name == 'index.md':
            continue
        
        # 读取 Markdown
        with open(md_file, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        # 转换为 HTML
        title, html_content = markdown_to_html(md_content)
        
        # 生成完整页面
        relative_path = md_file.relative_to(docs_dir)
        full_html = generate_html_page(title, html_content, str(relative_path))
        
        # 写入 HTML
        html_file = website_docs_dir / relative_path.with_suffix('.html')
        html_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(full_html)
        
        print(f'✓ {md_file} → {html_file}')
        converted += 1
    
    print(f'\n总计: 转换 {converted} 个文档')

if __name__ == '__main__':
    convert_docs()
