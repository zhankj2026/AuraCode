#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
officedoc2html.py — docx/pptx → HTML 预览转换（纯 Python stdlib，零三方依赖）

原理：docx/pptx 都是 OOXML（ZIP + XML）。用 zipfile 解包、ElementTree 解析：
- docx: word/document.xml 的 <w:p>（段落）→ <p>/<h1..h3>（按样式名），
        <w:t> 拼文本，内嵌图片（word/media/*）转 base64 <img>。
- pptx: ppt/slides/slide*.xml 每页 → 一个 16:9 卡片；文本框文本按
        <a:p> 段落聚合；内嵌图片转 base64 <img>。按页码数字排序。

用法: python officedoc2html.py <file.docx|file.pptx>
输出: HTML 打到 stdout（IPC 捕获）；错误打到 stderr，退出码非 0。
限制: 只读文本+图片，不还原复杂排版（表格转简化文本网格）；旧 .doc/.ppt
      二进制格式不支持（提示另存为 .docx/.pptx）。
"""
import base64
import io
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
PR = '{http://schemas.openxmlformats.org/package/2006/relationships}'

CSS = """
<style>
body{font-family:'Microsoft YaHei',system-ui,sans-serif;margin:0;padding:24px;background:#f5f6f8;color:#1f2329;}
.doc{max-width:820px;margin:0 auto;background:#fff;padding:48px 56px;box-shadow:0 2px 12px rgba(0,0,0,.08);border-radius:8px;}
h1{font-size:1.7em;border-bottom:2px solid #e8eaed;padding-bottom:8px;}
h2{font-size:1.35em;margin-top:1.4em;}
h3{font-size:1.15em;margin-top:1.2em;}
p{line-height:1.75;margin:.6em 0;white-space:pre-wrap;}
img{max-width:100%;border-radius:4px;}
.slide{max-width:960px;margin:16px auto;background:#fff;aspect-ratio:16/9;box-shadow:0 2px 10px rgba(0,0,0,.10);border-radius:8px;padding:40px 48px;overflow:auto;position:relative;}
.slide .no{position:absolute;top:12px;right:16px;color:#9aa0a6;font-size:12px;}
.slide h2{margin-top:0;}
.footer{max-width:960px;margin:8px auto;color:#9aa0a6;font-size:12px;text-align:center;}
</style>
"""


def esc(s: str) -> str:
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def media_b64(zf: zipfile.ZipFile, name: str) -> str:
    try:
        data = zf.read(name)
        ext = name.rsplit('.', 1)[-1].lower()
        mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                'gif': 'image/gif', 'webp': 'image/webp', 'bmp': 'image/bmp',
                'emf': 'image/emf', 'wmf': 'image/wmf'}.get(ext, 'application/octet-stream')
        return f'data:{mime};base64,{base64.b64encode(data).decode()}'
    except KeyError:
        return ''


# ── DOCX ──────────────────────────────────────────────────────

def docx_paragraphs(zf):
    """产出 (style, text, images) 列表。images 为该段落内嵌图片 media 路径。"""
    doc = ET.fromstring(zf.read('word/document.xml'))
    rels = {}
    if 'word/_rels/document.xml.rels' in zf.namelist():
        relroot = ET.fromstring(zf.read('word/_rels/document.xml.rels'))
        for rel in relroot.iter(f'{PR}Relationship'):
            rels[rel.get('Id')] = rel.get('Target', '')
    out = []
    for p in doc.iter(f'{W}p'):
        style = ''
        ppr = p.find(f'{W}pPr')
        if ppr is not None:
            ps = ppr.find(f'{W}pStyle')
            if ps is not None:
                style = ps.get(f'{W}val', '') or ''
        texts = []
        images = []
        for node in p.iter():
            tag = node.tag
            if tag == f'{W}t':
                texts.append(node.text or '')
            elif tag == f'{A}blip':
                rid = node.get(f'{R}embed') or ''
                target = rels.get(rid, '')
                if target:
                    images.append('word/' + target.lstrip('/') if not target.startswith('word/') else target)
        out.append((style, ''.join(texts), images))
    return out


def docx_table_text(row_el) -> str:
    """表格行 → 简化文本（| 分隔）。"""
    cells = []
    for tc in row_el.iter(f'{W}tc'):
        cell_text = ''.join(t.text or '' for t in tc.iter(f'{W}t'))
        cells.append(cell_text.strip())
    return '| ' + ' | '.join(cells) + ' |'


def convert_docx(path: str) -> str:
    with zipfile.ZipFile(path) as zf:
        parts = []
        for style, text, images in docx_paragraphs(zf):
            style_l = (style or '').lower()
            if style_l.startswith('heading1') or style_l == 'title':
                parts.append(f'<h1>{esc(text)}</h1>')
            elif style_l.startswith('heading2'):
                parts.append(f'<h2>{esc(text)}</h2>')
            elif style_l.startswith('heading3') or 'heading' in style_l:
                parts.append(f'<h3>{esc(text)}</h3>')
            elif text or images:
                img_html = ''.join(
                    f'<img src="{media_b64(zf, m)}" alt="img"/>' for m in images
                )
                parts.append(f'<p>{esc(text)}{img_html}</p>')
        body = '\n'.join(parts) or '<p>(空文档)</p>'
    return f'<!DOCTYPE html><html><head><meta charset="utf-8">{CSS}</head><body><div class="doc">{body}</div></body></html>'


# ── PPTX ──────────────────────────────────────────────────────

def slide_sort_key(name: str):
    m = re.search(r'slide(\d+)\.xml$', name)
    return int(m.group(1)) if m else 9999


def convert_pptx(path: str) -> str:
    with zipfile.ZipFile(path) as zf:
        slide_names = [n for n in zf.namelist()
                       if re.match(r'ppt/slides/slide\d+\.xml$', n)]
        slide_names.sort(key=slide_sort_key)
        if not slide_names:
            return f'<!DOCTYPE html><html><head><meta charset="utf-8">{CSS}</head><body><div class="doc"><p>(无幻灯片)</p></div></body></html>'

        # 每个 slide 的 rels：图片 rid → media 路径
        def slide_rels(slide_xml_name: str) -> dict:
            base = slide_xml_name.replace('ppt/slides/', '')
            rel_name = f'ppt/slides/_rels/{base}.rels'
            rels = {}
            if rel_name in zf.namelist():
                root = ET.fromstring(zf.read(rel_name))
                for rel in root.iter(f'{PR}Relationship'):
                    rid, target = rel.get('Id'), rel.get('Target', '')
                    if target.startswith('../'):
                        target = target[3:]  # ../media/x.png → media/x.png
                    rels[rid] = 'ppt/' + target
            return rels

        slides_html = []
        for idx, sname in enumerate(slide_names, 1):
            root = ET.fromstring(zf.read(sname))
            rels = slide_rels(sname)
            paras = []
            images = []
            first_text_done = False
            for node in root.iter():
                if node.tag == f'{A}p':
                    text = ''.join(t.text or '' for t in node.iter(f'{A}t'))
                    if text.strip():
                        # 段首文本（一般是大标题）放大
                        if not first_text_done:
                            paras.append(f'<h2>{esc(text)}</h2>')
                            first_text_done = True
                        else:
                            paras.append(f'<p>{esc(text)}</p>')
                elif node.tag == f'{A}blip':
                    rid = node.get(f'{R}embed') or ''
                    mpath = rels.get(rid, '')
                    if mpath:
                        images.append(mpath)
            img_html = ''.join(
                f'<img src="{media_b64(zf, m)}" alt="img"/>' for m in images
            )
            inner = '\n'.join(paras) + img_html
            slides_html.append(
                f'<div class="slide"><span class="no">{idx} / {len(slide_names)}</span>{inner}</div>'
            )
        body = '\n'.join(slides_html)
        foot = f'<div class="footer">共 {len(slide_names)} 页 · 文本+图片预览（简化排版）</div>'
    return f'<!DOCTYPE html><html><head><meta charset="utf-8">{CSS}</head><body>{body}{foot}</body></html>'


def main():
    if len(sys.argv) < 2:
        print('usage: officedoc2html.py <file.docx|file.pptx>', file=sys.stderr)
        sys.exit(2)
    path = sys.argv[1]
    low = path.lower()
    try:
        if low.endswith('.docx'):
            sys.stdout.buffer.write(convert_docx(path).encode('utf-8'))
        elif low.endswith('.pptx'):
            sys.stdout.buffer.write(convert_pptx(path).encode('utf-8'))
        else:
            print('不支持的格式（仅 .docx/.pptx；旧版 .doc/.ppt 请先另存为新格式）',
                  file=sys.stderr)
            sys.exit(2)
    except zipfile.BadZipFile:
        print('文件不是有效的 OOXML（docx/pptx）格式', file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f'转换失败: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
