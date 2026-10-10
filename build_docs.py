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
样式统一引用 css/style.css + css/docs.css（与 index.html 设计语言一致）
"""
import re
from pathlib import Path

# 文档清单：(目录, 文件名不含扩展名, 侧边栏标签)
# 顺序即上一篇/下一篇导航顺序
DOCS = [
    ("", "quick-start", "快速开始"),
    ("user-guide", "chat", "对话交互"),
    ("user-guide", "commands", "命令参考"),
    ("user-guide", "tools", "工具系统"),
    ("user-guide", "skills", "技能系统"),
    ("user-guide", "memory", "记忆系统"),
    ("user-guide", "permissions", "权限管理"),
    ("user-guide", "mcp", "MCP 协议集成"),
    ("user-guide", "loop-scheduling", "定时任务调度"),
    ("user-guide", "batch-workflow", "动态工作流"),
    ("user-guide", "workflow-generator", "WorkflowScriptGenerator"),
    ("advanced", "bridge", "Bridge 远程控制"),
    ("advanced", "hooks", "钩子系统"),
    ("advanced", "plugins", "插件系统"),
    ("advanced", "error-recovery", "错误恢复"),
    ("development", "architecture", "架构总览"),
    ("development", "agent-architecture-guide", "Agent 架构指南"),
    ("development", "bridge-streaming-analysis", "Bridge 流式分析"),
]

SIDEBAR_GROUPS = [
    ("入门指南", ["quick-start"]),
    ("用户指南", ["chat", "commands", "tools", "skills", "memory",
                "permissions", "mcp", "loop-scheduling", "batch-workflow",
                "workflow-generator"]),
    ("高级功能", ["bridge", "hooks", "plugins", "error-recovery"]),
    ("开发", ["architecture", "agent-architecture-guide",
             "bridge-streaming-analysis"]),
]

GITHUB_URL = "https://github.com/zhankj2026/AuraCode"
GITEE_URL = "https://gitee.com/creating2018/auracode"


def escape_html(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def slugify(text):
    """生成锚点 id：保留中文/字母/数字/连字符"""
    text = re.sub(r'[^\w一-鿿-]+', '', text.replace(' ', '-'))
    return text.strip('-') or 'section'


# ---------------- Markdown → HTML ----------------

def convert_inline(text):
    """行内元素转换：行内代码 → 链接 → 粗体 → 斜体"""
    stash = []

    def stash_code(m):
        stash.append(f'<code class="inline-code">{escape_html(m.group(1))}</code>')
        return f'\x03{len(stash) - 1}\x03'

    text = re.sub(r'`([^`]+)`', stash_code, text)

    def convert_link(m):
        href = m.group(2)
        # 文档间相对链接 .md → .html（含 .md#锚点 形式）
        href = re.sub(r'\.md(#|$)', r'.html\1', href)
        return f'<a href="{href}" class="md-link">{m.group(1)}</a>'

    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', convert_link, text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong class="md-strong">\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em class="md-em">\1</em>', text)
    return _restore_codes(text, stash)


def _restore_codes(text, stash):
    return re.sub(r'\x03(\d+)\x03', lambda m: stash[int(m.group(1))], text)


def code_block_html(lang, code):
    lang = lang or 'text'
    return (
        f'<div class="code-block">\n'
        f'<div class="code-header">\n'
        f'<span>{escape_html(lang)}</span>\n'
        f'<button class="copy-btn"><i class="fas fa-copy"></i></button>\n'
        f'</div>\n'
        f'<pre><code>{escape_html(code)}</code></pre>\n'
        f'</div>'
    )


def quote_box_html(lines):
    """引用块 → 提示框，按开头符号分流"""
    text = '<br>'.join(convert_inline(l) for l in lines)
    first = lines[0]
    if first.startswith(('⚠', '❗', '❕')) or '注意' in first[:6]:
        cls, icon = 'warning', 'fa-exclamation-triangle'
    elif first.startswith('✅') or first.startswith('✔'):
        cls, icon = 'success', 'fa-check-circle'
    elif first.startswith('❌'):
        cls, icon = 'error', 'fa-times-circle'
    else:
        cls, icon = 'info', 'fa-info-circle'
    return f'<div class="{cls}-box"><i class="fas {icon}"></i><div><p>{text}</p></div></div>'


def table_html(rows):
    """rows: 已按 | 分割的单元格列表的列表，第 0 行为表头"""
    headers = rows[0]
    html = ['<table class="md-table">', '<thead><tr>',
            ''.join(f'<th>{convert_inline(h)}</th>' for h in headers),
            '</tr></thead>', '<tbody>']
    for row in rows[1:]:
        html.append('<tr>' + ''.join(f'<td>{convert_inline(c)}</td>' for c in row) + '</tr>')
    html += ['</tbody>', '</table>']
    return '\n'.join(html)


def _split_cells(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def markdown_to_html(md_content):
    """Markdown 转 HTML，返回 (title, description, body_html, sections)

    sections: [(slug, h2标题), ...] 供侧边栏"本页目录"使用
    """
    title = "AuraCode 文档"
    m = re.search(r'^# (.+)$', md_content, re.MULTILINE)
    if m:
        title = m.group(1).strip()

    description = ""
    for line in md_content.split('\n'):
        s = line.strip()
        if (s and not s.startswith(('#', '```', '>', '-', '*', '|', '---'))
                and not description):
            description = s
            break

    lines = md_content.split('\n')
    out = []            # 输出行缓冲
    sections = []       # h2 小节列表
    para = []           # 段落缓冲
    code = None         # 代码块缓冲 (lang, [lines])
    quote = []          # 引用块缓冲
    list_buf = []       # 列表缓冲
    list_tag = None     # 'ul' | 'ol'
    table_rows = None   # 表格缓冲

    def flush_para():
        if para:
            out.append(f'<p class="md-paragraph">{convert_inline(" ".join(para))}</p>')
            para.clear()

    def flush_list():
        nonlocal list_buf, list_tag
        if list_buf:
            out.append(f'<{list_tag} class="md-list">\n' +
                       '\n'.join(f'<li>{convert_inline(i)}</li>' for i in list_buf) +
                       f'\n</{list_tag}>')
            list_buf, list_tag = [], None

    def flush_quote():
        if quote:
            out.append(quote_box_html(quote))
            quote.clear()

    def flush_table():
        nonlocal table_rows
        if table_rows:
            out.append(table_html(table_rows))
            table_rows = None

    def flush_all():
        flush_para(); flush_list(); flush_quote(); flush_table()

    in_section = False
    for line in lines:
        stripped = line.strip()

        # --- 代码块 ---
        if stripped.startswith('```'):
            if code is not None:
                flush_all()
                out.append(code_block_html(code[0], '\n'.join(code[1])))
                code = None
            else:
                flush_all()
                code = (stripped[3:].strip(), [])
            continue
        if code is not None:
            code[1].append(line)
            continue

        # --- 空行 ---
        if not stripped:
            flush_para(); flush_list(); flush_quote(); flush_table()
            continue

        # --- 标题 ---
        m = re.match(r'^(#{1,6}) (.+)$', stripped)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            flush_all()
            if level == 1:
                continue  # 页面标题已在 docs-header 中呈现
            if level == 2:
                if in_section:
                    out.append('</section>')
                in_section = True
                slug = slugify(text)
                sections.append((slug, text))
                out.append(f'<section id="{slug}" class="doc-section">')
                out.append(f'<h2>{convert_inline(text)}</h2>')
            else:
                out.append(f'<h3>{convert_inline(text)}</h3>')
            continue

        # --- 分隔线 ---
        if re.match(r'^-{3,}$', stripped):
            flush_all()
            out.append('<hr class="md-hr">')
            continue

        # --- 引用块 ---
        if stripped.startswith('>'):
            flush_para(); flush_list(); flush_table()
            quote.append(stripped.lstrip('> ').rstrip())
            continue
        else:
            flush_quote()

        # --- 表格 ---
        if stripped.startswith('|'):
            flush_para(); flush_list()
            if re.match(r'^[\s|:-]+$', stripped):
                continue  # 分隔线行，跳过
            if table_rows is None:
                table_rows = []
            table_rows.append(_split_cells(stripped))
            continue
        else:
            flush_table()

        # --- 列表 ---
        m = re.match(r'^[-*] (.+)$', stripped)
        m2 = re.match(r'^\d+[.、] (.+)$', stripped)
        if m or m2:
            flush_para()
            tag = 'ul' if m else 'ol'
            if list_buf and list_tag != tag:
                flush_list()
            list_tag = tag
            list_buf.append((m or m2).group(1).strip())
            continue
        else:
            flush_list()

        # --- 普通段落 ---
        para.append(stripped)

    flush_all()
    if code is not None:  # 未闭合的代码块
        out.append(code_block_html(code[0], '\n'.join(code[1])))
    if in_section:
        out.append('</section>')

    return title, description, '\n'.join(out), sections


# ---------------- 页面模板 ----------------

CATEGORY_CN = {"user-guide": "用户指南", "advanced": "高级功能", "development": "开发"}


def generate_html_page(title, description, content, sections, doc_path):
    """生成完整 HTML 页面（样式与 index.html 一致）"""
    parts = doc_path.split('/')
    current_dir = parts[0] if len(parts) > 1 else ""
    prefix = '../' * len(parts)  # 指向 website/ 根

    def make_link(category, stem):
        """生成指向其他文档的相对链接"""
        if current_dir == "":
            return f"{category}/{stem}.html" if category else f"{stem}.html"
        if current_dir == category:
            return f"{stem}.html"
        return f"../{category}/{stem}.html" if category else f"../{stem}.html"

    # --- 侧边栏：本页目录 + 全量文档导航 ---
    doc_map = {stem: (cat, label) for cat, stem, label in DOCS}
    current_stem = parts[-1].replace('.html', '')

    toc_html = ''
    if sections:
        toc_html = ('<div class="sidebar-section"><h3>本页目录</h3><ul>' +
                    ''.join(f'<li><a href="#{slug}">{convert_inline(text)}</a></li>'
                            for slug, text in sections) +
                    '</ul></div>')

    nav_html = ''
    for group_label, stems in SIDEBAR_GROUPS:
        items = []
        for stem in stems:
            cat, label = doc_map[stem]
            active = ' class="active"' if stem == current_stem and cat == current_dir else ''
            items.append(f'<li><a href="{make_link(cat, stem)}"{active}>{label}</a></li>')
        nav_html += (f'<div class="sidebar-section"><h3>{group_label}</h3>'
                     f'<ul>{"".join(items)}</ul></div>')

    sidebar_html = f'<aside class="docs-sidebar">{toc_html}{nav_html}</aside>'

    # --- 面包屑 ---
    crumb = (f'<a href="{prefix}index.html" class="breadcrumb-link">'
             f'<i class="fas fa-home"></i> 首页</a>'
             f'<span class="breadcrumb-sep">/</span>'
             f'<span class="breadcrumb-item">文档</span>')
    if current_dir:
        crumb += (f'<span class="breadcrumb-sep">/</span>'
                  f'<span class="breadcrumb-item">{CATEGORY_CN.get(current_dir, current_dir)}</span>')
    crumb += (f'<span class="breadcrumb-sep">/</span>'
              f'<span class="breadcrumb-item">{title}</span>')

    # --- 上一篇 / 下一篇 ---
    ordered = [stem for _, stems in SIDEBAR_GROUPS for stem in stems]
    idx = ordered.index(current_stem) if current_stem in ordered else -1
    prev_html = next_html = ''
    if idx > 0:
        p_stem = ordered[idx - 1]
        prev_html = (f'<a href="{make_link(doc_map[p_stem][0], p_stem)}" class="nav-btn prev">'
                     f'<i class="fas fa-arrow-left"></i> {doc_map[p_stem][1]}</a>')
    else:
        prev_html = (f'<a href="{prefix}index.html" class="nav-btn prev">'
                     f'<i class="fas fa-arrow-left"></i> 返回首页</a>')
    if 0 <= idx < len(ordered) - 1:
        n_stem = ordered[idx + 1]
        next_html = (f'<a href="{make_link(doc_map[n_stem][0], n_stem)}" class="nav-btn next">'
                     f'{doc_map[n_stem][1]} <i class="fas fa-arrow-right"></i></a>')

    subtitle = f'<p>{convert_inline(description)}</p>' if description else ''

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - AuraCode</title>
    <link rel="stylesheet" href="{prefix}css/style.css">
    <link rel="stylesheet" href="{prefix}css/docs.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <!-- 导航栏（与 index.html 一致） -->
    <nav class="navbar">
        <div class="container">
            <div class="nav-brand">
                <i class="fas fa-code"></i>
                <span>AuraCode</span>
            </div>
            <ul class="nav-menu">
                <li><a href="{prefix}index.html">首页</a></li>
                <li><a href="{prefix}index.html#features">功能</a></li>
                <li><a href="{prefix}index.html#docs">文档</a></li>
                <li><a href="{prefix}index.html#quickstart">快速开始</a></li>
                <li><a href="{GITHUB_URL}" target="_blank" class="nav-btn">
                    <i class="fab fa-github"></i> GitHub
                </a></li>
                <li><a href="{GITEE_URL}" target="_blank" class="nav-btn">
                    <i class="fab fa-github"></i> gitee
                </a></li>
            </ul>
            <div class="hamburger">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    </nav>

    <!-- 文档内容 -->
    <div class="docs-container">
        {sidebar_html}

        <main class="docs-content">
            <div class="docs-header">
                <div class="breadcrumb">{crumb}</div>
                <h1>{title}</h1>
                {subtitle}
            </div>
            <div class="md-content">
                {content}
            </div>

            <div class="docs-navigation">
                {prev_html}
                {next_html}
            </div>
        </main>
    </div>

    <!-- 页脚（与 index.html 一致） -->
    <footer class="footer">
        <div class="container">
            <div class="footer-content">
                <div class="footer-brand">
                    <div class="nav-brand">
                        <i class="fas fa-code"></i>
                        <span>AuraCode</span>
                    </div>
                    <p>生产级 AI 编程助手，赋能开发者高效编程</p>
                </div>
                <div class="footer-links">
                    <div class="footer-column">
                        <h4>产品</h4>
                        <ul>
                            <li><a href="{prefix}index.html#features">功能</a></li>
                            <li><a href="{prefix}index.html#docs">文档</a></li>
                            <li><a href="{prefix}index.html#quickstart">快速开始</a></li>
                        </ul>
                    </div>
                    <div class="footer-column">
                        <h4>资源</h4>
                        <ul>
                            <li><a href="{make_link('', 'quick-start')}">快速开始</a></li>
                            <li><a href="{make_link('user-guide', 'commands')}">命令参考</a></li>
                            <li><a href="{make_link('advanced', 'bridge')}">Bridge 远程控制</a></li>
                        </ul>
                    </div>
                    <div class="footer-column">
                        <h4>社区</h4>
                        <ul>
                            <li><a href="{GITHUB_URL}" target="_blank">GitHub</a></li>
                            <li><a href="{GITEE_URL}" target="_blank">gitee</a></li>
                        </ul>
                    </div>
                </div>
            </div>
            <div class="footer-bottom">
                <p>&copy; 2026 AuraCode. MIT License.</p>
            </div>
        </div>
    </footer>

    <script src="{prefix}js/main.js"></script>
    <script src="{prefix}js/docs.js"></script>
</body>
</html>"""


# ---------------- 主流程 ----------------

def convert_docs():
    """按 DOCS 清单转换所有 Markdown 文档"""
    docs_dir = Path('docs')
    website_docs_dir = Path('website/docs')

    converted = 0
    for category, stem, label in DOCS:
        md_file = docs_dir / category / f'{stem}.md'
        if not md_file.exists():
            print(f'⚠ 跳过（源文件不存在）: {md_file}')
            continue

        html_content = md_file.read_text(encoding='utf-8')
        title, description, body, sections = markdown_to_html(html_content)
        rel_html = f'{category}/{stem}.html' if category else f'{stem}.html'
        full_html = generate_html_page(title, description, body, sections, rel_html)

        html_file = website_docs_dir / rel_html
        html_file.parent.mkdir(parents=True, exist_ok=True)
        html_file.write_text(full_html, encoding='utf-8')
        print(f'✓ {md_file} → {html_file}')
        converted += 1

        # quickstart.html 兼容副本（index.html 卡片链接指向它，同级目录相对路径一致）
        if stem == 'quick-start':
            (website_docs_dir / 'quickstart.html').write_text(full_html, encoding='utf-8')
            print(f'✓ {md_file} → {website_docs_dir / "quickstart.html"} (兼容副本)')
            converted += 1

    print(f'\n总计: 生成 {converted} 个 HTML 文件')


if __name__ == '__main__':
    convert_docs()
