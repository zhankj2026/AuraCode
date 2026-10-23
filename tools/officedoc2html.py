#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
officedoc2html.py — docx/pptx → HTML 预览转换（纯 Python stdlib，零三方依赖）

原理：docx/pptx 都是 OOXML（ZIP + XML）。用 zipfile 解包、ElementTree 解析。

pptx 采用「绝对定位画布」忠实还原（v2，替代初版段落流方案）：
- 幻灯片尺寸取自 ppt/presentation.xml 的 sldSz（EMU→px @96dpi）
- 每个 <p:sp>/<p:pic> 按 xfrm 坐标/尺寸绝对定位，z 序按文档序
- prstGeom：rect / roundRect / ellipse / triangle 等映射 CSS 形状
- 填充/描边：srgbClr 直取，schemeClr 查 theme1.xml clrScheme（lumMod 忽略）
- 文本：rPr 的 sz(百分之一磅→px)/b/i/u/颜色/字体 + pPr 的 algn 对齐 +
  bodyPr 的 anchor 垂直锚点；buChar/buAutoNum 项目符号
- 背景：slide > slideLayout > slideMaster 三级继承（纯色/图片）
- 组合形状 grpSp：off/chOff/ext/chExt 仿射缩放展开
- 图片：blip r:embed → rels → media/* 转 base64 内联

docx：段落流 + pStyle 映射 h1-h3 + 内嵌图片（保持 v1 行为）。

用法: python officedoc2html.py <file.docx|file.pptx>
输出: HTML → stdout；错误 → stderr，退出码非 0。
限制: 不支持旋转/渐变/图表/艺术字/SmartArt；旧 .doc/.ppt 二进制格式不支持。
"""
import base64
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
PR = '{http://schemas.openxmlformats.org/package/2006/relationships}'

EMU_PER_PX = 9525.0  # 96dpi
PT2PX = 4.0 / 3.0

CSS = """
<style>
body{font-family:'Microsoft YaHei',system-ui,sans-serif;margin:0;padding:20px;background:#e8eaed;color:#1f2329;}
.doc{max-width:820px;margin:0 auto;background:#fff;padding:48px 56px;box-shadow:0 2px 12px rgba(0,0,0,.08);border-radius:8px;}
.doc h1{font-size:1.7em;border-bottom:2px solid #e8eaed;padding-bottom:8px;}
.doc h2{font-size:1.35em;margin-top:1.4em;}
.doc h3{font-size:1.15em;margin-top:1.2em;}
.doc p{line-height:1.75;margin:.6em 0;white-space:pre-wrap;}
.doc img{max-width:100%;border-radius:4px;}
.slide-scroll{overflow:auto;padding:4px 0;}
.slide{position:relative;margin:16px auto;background:#fff;box-shadow:0 2px 14px rgba(0,0,0,.18);border-radius:6px;overflow:hidden;}
.slide .sp{position:absolute;box-sizing:border-box;overflow:hidden;display:flex;}
.slide .no{position:absolute;top:8px;right:12px;color:rgba(0,0,0,.28);font-size:12px;z-index:99;}
.footer{max-width:1280px;margin:8px auto;color:#9aa0a6;font-size:12px;text-align:center;}
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
                'emf': 'image/emf', 'wmf': 'image/wmf',
                'tiff': 'image/tiff', 'png ': 'image/png'}.get(ext, 'application/octet-stream')
        return f'data:{mime};base64,{base64.b64encode(data).decode()}'
    except KeyError:
        return ''


# ═════════════════════════ DOCX（v1 保持） ═════════════════════════

def docx_paragraphs(zf):
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
            if node.tag == f'{W}t':
                texts.append(node.text or '')
            elif node.tag == f'{A}blip':
                rid = node.get(f'{R}embed') or ''
                target = rels.get(rid, '')
                if target:
                    m = target if target.startswith('word/') else 'word/' + target.lstrip('/')
                    images.append(m)
        out.append((style, ''.join(texts), images))
    return out


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


# ═════════════════════════ PPTX v2（绝对定位画布） ═════════════════════════

def theme_colors(zf) -> dict:
    """theme1.xml clrScheme → {dk1: '#RRGGBB', accent1: ...}"""
    out = {}
    for name in zf.namelist():
        if re.match(r'ppt/theme/theme\d+\.xml$', name):
            try:
                root = ET.fromstring(zf.read(name))
            except ET.ParseError:
                continue
            scheme = root.find(f'{A}themeElements/{A}clrScheme')
            if scheme is None:
                continue
            for child in scheme:
                key = child.tag.split('}')[-1]
                for c in child:
                    val = c.get('val') or c.get('lastClr')
                    if val:
                        out.setdefault(key, '#' + val)
            break
    out.setdefault('dk1', '#000000')
    out.setdefault('lt1', '#FFFFFF')
    # 主题别名
    out['tx1'] = out.get('dk1')
    out['bg1'] = out.get('lt1')
    out['tx2'] = out.get('dk2', '#44546A')
    out['bg2'] = out.get('lt2', '#E7E6E6')
    return out


def parse_rels(zf, rel_name: str) -> dict:
    """{'rId1': ('slideLayout', 'slideLayouts/slideLayout1.xml')} 按 type 后缀分类"""
    out = {}
    if rel_name not in zf.namelist():
        return out
    root = ET.fromstring(zf.read(rel_name))
    for rel in root.iter(f'{PR}Relationship'):
        rtype = (rel.get('Type') or '').rsplit('/', 1)[-1]
        target = rel.get('Target') or ''
        if target.startswith('../'):
            target = target[3:]
        elif target.startswith('/'):
            target = target.lstrip('/')
        out[rel.get('Id')] = (rtype, target)
    return out


def color_of(parent_el, theme: dict):
    """取 solidFill 子元素颜色（srgbClr / schemeClr）。parent_el 是 rPr/ln/bgPr/spPr。"""
    if parent_el is None:
        return None
    sf = parent_el.find(f'{A}solidFill')
    if sf is None:
        return None
    srgb = sf.find(f'{A}srgbClr')
    if srgb is not None and srgb.get('val'):
        return '#' + srgb.get('val')
    sch = sf.find(f'{A}schemeClr')
    if sch is not None:
        return theme.get(sch.get('val', ''))
    return None


def xfrm_of(spPr):
    x = spPr.find(f'{A}xfrm') if spPr is not None else None
    if x is None:
        return None
    off = x.find(f'{A}off')
    ext = x.find(f'{A}ext')
    if off is None or ext is None:
        return None
    try:
        return (int(off.get('x', 0)), int(off.get('y', 0)),
                int(ext.get('cx', 0)), int(ext.get('cy', 0)))
    except (TypeError, ValueError):
        return None


def geom_css(spPr) -> str:
    g = spPr.find(f'{A}prstGeom') if spPr is not None else None
    prst = (g.get('prst', 'rect') if g is not None else 'rect') or 'rect'
    if prst in ('roundRect', 'round1Rect', 'round2SameRect', 'round2DiagRect'):
        return 'border-radius:14px;'
    if prst in ('ellipse', 'ellipseRgn'):
        return 'border-radius:50%;'
    if prst in ('triangle', 'rtTriangle'):
        return 'clip-path:polygon(0 100%,50% 0,100% 100%);'
    if prst in ('diamond'):
        return 'clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%);'
    if prst in ('parallelogram',):
        return 'clip-path:polygon(12% 0,100% 0,88% 100%,0 100%);'
    if prst in ('chevron',):
        return 'clip-path:polygon(0 0,86% 0,100% 50%,86% 100%,0 100%);'
    if prst in ('line', 'straightConnector1', 'straightConnector'):
        return 'border-radius:0;'
    return ''


def line_css(spPr, theme) -> str:
    ln = spPr.find(f'{A}ln') if spPr is not None else None
    if ln is None:
        return ''
    try:
        w = int(ln.get('w', 12700))
    except (TypeError, ValueError):
        w = 12700
    col = color_of(ln, theme)
    if col:
        return f'border:{max(1, w / EMU_PER_PX):.2f}px solid {col};'
    if ln.find(f'{A}noFill') is not None:
        return ''
    return f'border:{max(1, w / EMU_PER_PX):.2f}px solid #d0d3d9;'


def run_html(r, theme) -> str:
    """a:r → 带 span 样式的 HTML"""
    t_el = r.find(f'{A}t')
    text = esc(t_el.text or '') if t_el is not None else ''
    rPr = r.find(f'{A}rPr')
    style = []
    font = ''
    if rPr is not None:
        try:
            sz = int(rPr.get('sz', 0))
        except (TypeError, ValueError):
            sz = 0
        if sz:
            style.append(f'font-size:{sz / 100 * PT2PX:.1f}px')
        if rPr.get('b') == '1':
            style.append('font-weight:700')
        if rPr.get('i') == '1':
            style.append('font-style:italic')
        if rPr.get('u') == 'sng':
            style.append('text-decoration:underline')
        col = color_of(rPr, theme)
        if col:
            style.append(f'color:{col}')
        latin = rPr.find(f'{A}latin')
        if latin is not None and latin.get('typeface'):
            font = latin.get('typeface')
        # 默认字号兜底：标题占位等无显式 sz 时用 18px
        if not sz:
            style.append('font-size:18px')
    else:
        style.append('font-size:18px')
    s = f'style="{";".join(style)}"' if style else ''
    ff = f' data-ff="{esc(font)}"' if font else ''
    cls = ' class="ff"' if font else ''
    return f'<span{cls}{ff} {s}>{text}</span>'


def para_html(p, theme) -> str:
    """a:p → <p style=align>，含项目符号近似"""
    pPr = p.find(f'{A}pPr')
    align = 'left'
    indent_bullet = False
    num_bullet = False
    if pPr is not None:
        algn = pPr.get('algn', '')
        align = {'l': 'left', 'ctr': 'center', 'r': 'right', 'just': 'justify'}.get(algn, 'left')
        if pPr.find(f'{A}buChar') is not None:
            indent_bullet = True
        elif pPr.find(f'{A}buAutoNum') is not None:
            num_bullet = True
        lnSpc = pPr.find(f'{A}lnSpc/{A}spcPct')
        if lnSpc is not None and lnSpc.get('val'):
            try:
                pct = int(lnSpc.get('val')) / 1000
                return _para_runs(p, theme, align, indent_bullet, num_bullet, pct)
            except (TypeError, ValueError):
                pass
    return _para_runs(p, theme, align, indent_bullet, num_bullet, None)


def _para_runs(p, theme, align, bullet, num, line_pct):
    runs = [run_html(r, theme) for r in p.findall(f'{A}r')]
    # br 换行
    brs = p.findall(f'{A}br')
    content = ('<br/>'.join(runs) if not brs else
               ''.join(runs) + '<br/>' * len(brs))
    prefix = ''
    ml = '0'
    if bullet:
        prefix = '<span style="margin-right:6px">•</span>'
        ml = '18px'
    elif num:
        prefix = '<span style="margin-right:6px">◦</span>'
        ml = '18px'
    style = [f'text-align:{align}']
    if ml != '0':
        style.append(f'margin-left:{ml}')
    if line_pct:
        style.append(f'line-height:{line_pct:.0f}%')
    if not runs and not brs:
        return f'<p style="height:.6em"></p>'
    return f'<p style="{";".join(style)}">{prefix}{content}</p>'


def txBody_html(txBody, theme) -> str:
    if txBody is None:
        return ''
    paras = ''.join(para_html(p, theme) for p in txBody.findall(f'{A}p'))
    return f'<div class="tx" style="width:100%">{paras}</div>'


def body_anchor_css(txBody) -> str:
    if txBody is None:
        return 'align-items:flex-start;'
    anchor = txBody.get('anchor', 't')
    return {'t': 'align-items:flex-start;', 'ctr': 'align-items:center;',
            'b': 'align-items:flex-end;'}.get(anchor, 'align-items:flex-start;')


class Transform:
    """组合形状坐标系变换：child EMU → 绝对 EMU（仿射）"""
    def __init__(self):
        self.ox = self.oy = self.chox = self.choy = 0
        self.sx = self.sy = 1.0

    def child(self):
        t = Transform()
        return t

    def apply(self, x, y, cx, cy):
        return (self.ox + (x - self.chox) * self.sx,
                self.oy + (y - self.choy) * self.sy,
                cx * self.sx, cy * self.sy)


IDENT = Transform()


def make_group_transform(grpSpPr) -> Transform:
    t = Transform()
    x = grpSpPr.find(f'{A}xfrm') if grpSpPr is not None else None
    if x is None:
        return t
    off = x.find(f'{A}off'); ext = x.find(f'{A}ext')
    ch_off = x.find(f'{A}chOff'); ch_ext = x.find(f'{A}chExt')
    try:
        t.ox = int(off.get('x', 0)); t.oy = int(off.get('y', 0))
        ecx = int(ext.get('cx', 1)); ecy = int(ext.get('cy', 1))
        t.chox = int(ch_off.get('x', 0)); t.choy = int(ch_off.get('y', 0))
        chcx = int(ch_ext.get('cx', 1) or 1); chcy = int(ch_ext.get('cy', 1) or 1)
        t.sx = ecx / chcx if chcx else 1.0
        t.sy = ecy / chcy if chcy else 1.0
    except (TypeError, ValueError, AttributeError):
        pass
    return t


def render_shape(el, tf: Transform, theme, rels, zf) -> str:
    spPr = el.find(f'{P}spPr')
    box = xfrm_of(spPr)
    if box is None:
        # 无坐标（如占位在 spTree 根）→ 退化成占满整页
        box = (0, 0, 0, 0)
    x, y, cx, cy = tf.apply(*box)
    if cx <= 0 or cy <= 0:
        return ''  # 零尺寸形状跳过
    px = x / EMU_PER_PX; py = y / EMU_PER_PX
    pw = cx / EMU_PER_PX; ph = cy / EMU_PER_PX

    fill = color_of(spPr, theme)
    has_nofill = spPr is not None and spPr.find(f'{A}noFill') is not None
    bg_css = f'background:{fill};' if fill else (
        'background:transparent;' if has_nofill else 'background:transparent;')

    g = spPr.find(f'{A}prstGeom') if spPr is not None else None
    prst = (g.get('prst', 'rect') if g is not None else 'rect')
    is_line = prst in ('line', 'straightConnector1', 'straightConnector',
                       'bentConnector', 'bentConnector3', 'curvedConnector3')
    if is_line:
        # 线条：细高（或细宽）矩形 + 填充当颜色
        line_col = fill or '#33475b'
        if pw >= ph:  # 水平线
            style = (f'left:{px:.1f}px;top:{py + ph / 2 - 1:.1f}px;'
                     f'width:{pw:.1f}px;height:2.2px;background:{line_col};')
        else:
            style = (f'left:{px + pw / 2 - 1:.1f}px;top:{py:.1f}px;'
                     f'width:2.2px;height:{ph:.1f}px;background:{line_col};')
        return f'<div class="sp" style="position:absolute;{style}"></div>'

    txBody = el.find(f'{P}txBody')
    anchor = body_anchor_css(txBody)
    pos = (f'left:{px:.1f}px;top:{py:.1f}px;width:{pw:.1f}px;height:{ph:.1f}px;')
    style = pos + bg_css + geom_css(spPr) + line_css(spPr, theme)
    tx = txBody_html(txBody, theme)
    return f'<div class="sp" style="{style}{anchor}">{tx}</div>'


def render_pic(el, tf: Transform, rels, zf) -> str:
    spPr = el.find(f'{P}spPr')
    box = xfrm_of(spPr)
    if box is None:
        return ''
    x, y, cx, cy = tf.apply(*box)
    blip = el.find(f'{P}blipFill/{A}blip')
    if blip is None:
        return ''
    rid = blip.get(f'{R}embed') or ''
    target = dict(rels).get(rid, ('', ''))[1] if rid in rels else ''
    if not target:
        return ''
    mpath = target if target.startswith('ppt/') else 'ppt/' + target
    b64 = media_b64(zf, mpath)
    if not b64:
        return ''
    px = x / EMU_PER_PX; py = y / EMU_PER_PX
    pw = cx / EMU_PER_PX; ph = cy / EMU_PER_PX
    return (f'<img src="{b64}" style="position:absolute;left:{px:.1f}px;'
            f'top:{py:.1f}px;width:{pw:.1f}px;height:{ph:.1f}px;object-fit:fill;"/>')


def walk_tree(parent, tf: Transform, out: list):
    for el in parent:
        if el.tag == f'{P}sp':
            out.append(('sp', el, tf))
        elif el.tag == f'{P}pic':
            out.append(('pic', el, tf))
        elif el.tag == f'{P}grpSp':
            gtf = make_group_transform(el.find(f'{P}grpSpPr'))
            walk_tree(el, gtf, out)


def bg_css_of(zf, theme, slide_rels, depth=0) -> str:
    """slide → layout → master 三级背景查找（纯色/图片）。
    slide_rels: [(part_name, rels_dict), ...]"""
    if depth > 2:
        return ''
    for part, rels in slide_rels:
        if part not in zf.namelist():
            continue
        root = ET.fromstring(zf.read(part))
        cSld = root.find(f'{P}cSld')
        if cSld is None:
            continue
        bg = cSld.find(f'{P}bg')
        if bg is not None:
            bgPr = bg.find(f'{P}bgPr')
            if bgPr is not None:
                col = color_of(bgPr, theme)
                if col:
                    return f'background:{col};'
                blip = bgPr.find(f'{A}blipFill/{A}blip')
                if blip is not None:
                    rid = blip.get(f'{R}embed') or ''
                    target = rels.get(rid, ('', ''))[1] if rid in rels else ''
                    if target:
                        mpath = target if target.startswith('ppt/') else 'ppt/' + target
                        b64 = media_b64(zf, mpath)
                        if b64:
                            return f'background:url({b64}) center/cover no-repeat;'
        # 本级无背景 → 沿 rels 找 layout / master 链
        for rid, (rtype, target) in rels.items():
            if rtype in ('slideLayout', 'slideMaster') and target:
                nxt = target if target.startswith('ppt/') else 'ppt/' + target
                if 'slides/' in nxt:
                    nxt_rel = nxt.replace('slides/', 'slides/_rels/') + '.rels'
                elif 'slideLayouts/' in nxt:
                    nxt_rel = nxt.replace('slideLayouts/', 'slideLayouts/_rels/') + '.rels'
                else:
                    nxt_rel = nxt.replace('slideMasters/', 'slideMasters/_rels/') + '.rels'
                nxt_rels = parse_rels(zf, nxt_rel) if nxt_rel in zf.namelist() else {}
                css = bg_css_of(zf, theme, [(nxt, nxt_rels)], depth + 1)
                if css:
                    return css
    return ''


def convert_pptx(path: str) -> str:
    with zipfile.ZipFile(path) as zf:
        theme = theme_colors(zf)

        # 幻灯片尺寸
        pres = ET.fromstring(zf.read('ppt/presentation.xml'))
        sldsz = pres.find(f'{P}sldSz')
        try:
            slide_cx = int(sldsz.get('cx', 12192000))
            slide_cy = int(sldsz.get('cy', 6858000))
        except (TypeError, ValueError, AttributeError):
            slide_cx, slide_cy = 12192000, 6858000
        Wpx = slide_cx / EMU_PER_PX
        Hpx = slide_cy / EMU_PER_PX

        slide_names = [n for n in zf.namelist()
                       if re.match(r'ppt/slides/slide\d+\.xml$', n)]
        slide_names.sort(key=lambda n: int(re.search(r'slide(\d+)\.xml$', n).group(1)))
        if not slide_names:
            return f'<!DOCTYPE html><html><head><meta charset="utf-8">{CSS}</head><body><div class="doc"><p>(无幻灯片)</p></div></body></html>'

        slides_html = []
        for idx, sname in enumerate(slide_names, 1):
            rel_name = sname.replace('ppt/slides/', 'ppt/slides/_rels/') + '.rels'
            rels = parse_rels(zf, rel_name)
            bg = bg_css_of(zf, theme, [(sname, rels)])

            root = ET.fromstring(zf.read(sname))
            spTree = root.find(f'{P}cSld/{P}spTree')
            shapes: list = []
            if spTree is not None:
                walk_tree(spTree, IDENT, shapes)
            inner = ''.join(
                render_shape(el, tf, theme, rels, zf) if kind == 'sp'
                else render_pic(el, tf, rels, zf)
                for kind, el, tf in shapes
            )
            no = (f'<span class="no">{idx} / {len(slide_names)}</span>'
                  if idx > 1 or len(slide_names) > 1 else '')
            slides_html.append(
                f'<div class="slide" style="width:{Wpx:.0f}px;height:{Hpx:.0f}px;{bg}">{no}{inner}</div>'
            )

        body = '<div class="slide-scroll">' + '\n'.join(slides_html) + '</div>'
        foot = (f'<div class="footer">共 {len(slide_names)} 页 · '
                f'{Wpx:.0f}×{Hpx:.0f}px 绝对定位还原（文本/形状/图片/背景）</div>')
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
