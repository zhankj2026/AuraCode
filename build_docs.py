#!/usr/bin/env python3
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 zhankj
#
# This source code is licensed under the [ Apache-2.0] license.
# For the full license text, please refer to the LICENSE file in the root directory.
#
# Author: zhankj <creating2018@aliyun.com>
# Project Homepage: http://www.auracode.top
#

"""
将 docs/*.md 转换为 website/docs/*.html
实现 Markdown 文档与 Website 的自动关联
"""
import os
import re
from pathlib import Path

def markdown_to_html(md_content, title="AuraCode 文档"):
    """Markdown 转 HTML（改进版）"""
    # 提取标题（第一个 # 标题）
    title_match = re.search(r'^# (.+)$', md_content, re.MULTILINE)
    if title_match:
        title = title_match.group(1)
    
    # 转换 Markdown 为 HTML
    html_content = md_content
    
    # 1. 转换代码块（优先处理，避免内部内容被误转换）
    def convert_code_block(match):
        lang = match.group(1) or ''
        code = match.group(2)
        return f'<pre class="code-block"><code class="language-{lang}">{code}</code></pre>'
    html_content = re.sub(r'```(\w*)?\n(.*?)```', convert_code_block, html_content, flags=re.DOTALL)
    
    # 2. 转换表格
    def convert_table(match):
        table_text = match.group(0)
        lines = table_text.strip().split('\n')
        if len(lines) < 2:
            return table_text
        
        # 移除分隔线
        rows = [line for line in lines if not re.match(r'^[\s\|:-]+$', line)]
        if len(rows) < 2:
            return table_text
        
        html = '<table class="md-table">\n'
        # 表头
        headers = [cell.strip() for cell in rows[0].split('|') if cell.strip()]
        html += '<thead><tr>' + ''.join([f'<th>{h}</th>' for h in headers]) + '</tr></thead>\n'
        # 表体
        html += '<tbody>\n'
        for row in rows[1:]:
            cells = [cell.strip() for cell in row.split('|') if cell.strip()]
            if cells:
                html += '<tr>' + ''.join([f'<td>{c}</td>' for c in cells]) + '</tr>\n'
        html += '</tbody></table>'
        return html
    
    html_content = re.sub(r'(\|[^\n]+\|\n)+', convert_table, html_content)
    
    # 3. 转换标题
    html_content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
    
    # 4. 转换引用块
    html_content = re.sub(r'^> (.+)$', r'<blockquote class="md-quote">\1</blockquote>', html_content, flags=re.MULTILINE)
    
    # 5. 转换列表
    html_content = re.sub(r'^[-*] (.+)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'(<li>.*</li>\n?)+', lambda m: f'<ul class="md-list">\n{m.group(0)}</ul>\n', html_content)
    
    # 6. 转换链接
    html_content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" class="md-link">\1</a>', html_content)
    
    # 7. 转换行内代码
    html_content = re.sub(r'`([^`]+)`', r'<code class="inline-code">\1</code>', html_content)
    
    # 8. 转换粗体和斜体
    html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong class="md-strong">\1</strong>', html_content)
    html_content = re.sub(r'\*(.+?)\*', r'<em class="md-em">\1</em>', html_content)
    
    # 9. 转换分隔线
    html_content = re.sub(r'^---+$', r'<hr class="md-hr">', html_content, flags=re.MULTILINE)
    
    # 10. 转换段落（双换行）
    paragraphs = html_content.split('\n\n')
    html_content = '\n\n'.join([
        f'<p class="md-paragraph">{p}</p>' if not p.startswith('<') else p
        for p in paragraphs
    ])
    
    return title, html_content

def generate_html_page(title, content, doc_path=""):
    """生成完整的 HTML 页面（美化版）"""
    # 生成面包屑导航
    breadcrumb = '<a href="../index.html" class="breadcrumb-link"><i class="fas fa-home"></i> 首页</a>'
    if doc_path:
        parts = doc_path.split('/')
        breadcrumb += ''.join([f'<span class="breadcrumb-sep">/</span><span class="breadcrumb-item">{p.replace(".html", "")}</span>' for p in parts])
    
    # 根据文档所在目录生成正确的侧边栏相对路径
    if doc_path:
        # 统一路径分隔符（Windows 使用 \，Linux/Mac 使用 /）
        normalized_path = doc_path.replace('\\', '/')
        parts = normalized_path.split('/')
        current_dir = parts[0] if len(parts) > 1 else ""  # 当前文档所在目录
        depth = len(parts) - 1  # 目录深度
    else:
        current_dir = ""
        depth = 0
    
    # 生成侧边栏链接（根据当前目录动态调整）
    def make_link(category, filename):
        """生成正确的相对路径"""
        if current_dir == "":
            # 根目录文档
            return f"{category}/{filename}" if category else filename
        elif current_dir == category:
            # 同目录文档
            return filename
        else:
            # 不同目录
            return f"../{category}/{filename}" if category else f"../{filename}"
    
    sidebar_html = f"""
        <aside class="docs-sidebar">
            <div class="sidebar-section">
                <h3>入门指南</h3>
                <ul>
                    <li><a href="{make_link('', 'quick-start.html')}">快速开始</a></li>
                </ul>
            </div>
            <div class="sidebar-section">
                <h3>用户指南</h3>
                <ul>
                    <li><a href="{make_link('user-guide', 'chat.html')}">对话交互</a></li>
                    <li><a href="{make_link('user-guide', 'commands.html')}">命令参考</a></li>
                    <li><a href="{make_link('user-guide', 'tools.html')}">工具系统</a></li>
                    <li><a href="{make_link('user-guide', 'skills.html')}">技能系统</a></li>
                    <li><a href="{make_link('user-guide', 'memory.html')}">记忆系统</a></li>
                    <li><a href="{make_link('user-guide', 'permissions.html')}">权限管理</a></li>
                    <li><a href="{make_link('user-guide', 'mcp.html')}">MCP 协议</a></li>
                </ul>
            </div>
            <div class="sidebar-section">
                <h3>高级功能</h3>
                <ul>
                    <li><a href="{make_link('advanced', 'bridge.html')}">Bridge 远程控制</a></li>
                    <li><a href="{make_link('advanced', 'hooks.html')}">钩子系统</a></li>
                    <li><a href="{make_link('advanced', 'plugins.html')}">插件系统</a></li>
                    <li><a href="{make_link('advanced', 'error-recovery.html')}">错误恢复</a></li>
                </ul>
            </div>
            <div class="sidebar-section">
                <h3>开发</h3>
                <ul>
                    <li><a href="{make_link('development', 'architecture.html')}">架构总览</a></li>
                </ul>
            </div>
        </aside>
    """
    
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
        /* Markdown 内容样式 */
        .md-content {{ 
            line-height: 1.8;
            color: var(--text-primary);
        }}
        
        /* 标题样式 */
        .md-content h1 {{ 
            font-size: 2.25rem;
            font-weight: 800;
            margin: 2rem 0 1.5rem;
            padding-bottom: 0.75rem;
            border-bottom: 2px solid var(--border-color);
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .md-content h2 {{ 
            font-size: 1.75rem;
            font-weight: 700;
            margin: 2.5rem 0 1rem;
            padding-left: 1rem;
            border-left: 4px solid var(--primary-color);
        }}
        .md-content h3 {{ 
            font-size: 1.35rem;
            font-weight: 600;
            margin: 2rem 0 0.75rem;
            color: var(--primary-color);
        }}
        
        /* 段落样式 */
        .md-paragraph {{
            margin: 1.25rem 0;
            line-height: 1.8;
        }}
        
        /* 代码块样式 */
        .code-block {{
            background: var(--darker-bg);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            padding: 1.25rem;
            margin: 1.5rem 0;
            overflow-x: auto;
            position: relative;
        }}
        .code-block::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
            border-radius: 0.75rem 0.75rem 0 0;
        }}
        .code-block code {{
            font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
            font-size: 0.9rem;
            line-height: 1.6;
            color: var(--text-primary);
        }}
        .inline-code {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 0.2rem 0.5rem;
            border-radius: 0.35rem;
            font-family: 'Cascadia Code', 'Fira Code', monospace;
            font-size: 0.85em;
            color: var(--primary-color);
        }}
        
        /* 表格样式 */
        .md-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            margin: 1.5rem 0;
            border-radius: 0.75rem;
            overflow: hidden;
            border: 1px solid var(--border-color);
        }}
        .md-table thead {{
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
        }}
        .md-table th {{
            padding: 1rem;
            text-align: left;
            font-weight: 600;
            color: white;
        }}
        .md-table td {{
            padding: 0.875rem 1rem;
            border-top: 1px solid var(--border-color);
            background: var(--card-bg);
        }}
        .md-table tbody tr:hover td {{
            background: rgba(99, 102, 241, 0.05);
        }}
        
        /* 引用块样式 */
        .md-quote {{
            border-left: 4px solid var(--primary-color);
            background: rgba(99, 102, 241, 0.05);
            padding: 1rem 1.25rem;
            margin: 1.5rem 0;
            border-radius: 0 0.5rem 0.5rem 0;
            font-style: italic;
            color: var(--text-secondary);
        }}
        
        /* 列表样式 */
        .md-list {{
            margin: 1.25rem 0;
            padding-left: 2rem;
        }}
        .md-list li {{
            margin: 0.75rem 0;
            line-height: 1.7;
            position: relative;
        }}
        .md-list li::marker {{
            color: var(--primary-color);
        }}
        
        /* 链接样式 */
        .md-link {{
            color: var(--primary-color);
            text-decoration: none;
            font-weight: 500;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }}
        .md-link:hover {{
            color: var(--secondary-color);
            border-bottom-color: var(--secondary-color);
        }}
        
        /* 粗体和斜体 */
        .md-strong {{
            font-weight: 700;
            color: var(--text-primary);
        }}
        .md-em {{
            font-style: italic;
            color: var(--text-secondary);
        }}
        
        /* 分隔线 */
        .md-hr {{
            border: none;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--border-color), transparent);
            margin: 2.5rem 0;
        }}
        
        /* 面包屑导航 */
        .breadcrumb-link {{
            color: var(--primary-color);
            text-decoration: none;
            font-weight: 500;
        }}
        .breadcrumb-link:hover {{
            text-decoration: underline;
        }}
        .breadcrumb-sep {{
            color: var(--text-secondary);
            margin: 0 0.5rem;
        }}
        .breadcrumb-item {{
            color: var(--text-secondary);
            text-transform: capitalize;
        }}
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
        {sidebar_html}

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
