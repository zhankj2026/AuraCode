#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
officedoc2html.py — docx/pptx → HTML 预览转换（纯 Python stdlib，零三方依赖）

原理：docx/pptx 都是 OOXML（ZIP + XML）。用 zipfile 解包、ElementTree 解析。

pptx 采用「绝对定位画布」忠实还原（v3）：
- 幻灯片尺寸取自 ppt/presentation.xml 的 sldSz（EMU→px @96dpi）
- 每个 <p:sp>/<p:pic> 按 xfrm 坐标/尺寸绝对定位，z 序按文档序
- prstGeom：rect / roundRect / ellipse / triangle 等映射 CSS 形状
- 填充/描边：solidFill 直取；gradFill → linear/radial-gradient（含 tint/
  shade/lumMod 修饰）；schemeClr 查 theme1.xml clrScheme
- 文本：rPr 的 sz(百分之一磅→px)/b/i/u/颜色/字体 + pPr 的 algn 对齐 +
  bodyPr 的 anchor 垂直锚点；buChar/buAutoNum 项目符号
- 背景：slide > slideLayout > slideMaster 三级继承（纯色/渐变/图片）
- 组合形状 grpSp：off/chOff/ext/chExt 仿射缩放展开
- 图片：blip r:embed → rels → media/* 转 base64 内联
- 自适应缩放：内联脚本把 1280×720 等原始画布等比缩放到预览区宽度

docx（v2 富文本）：
- run 级 rPr：颜色/字号(半磅)/加粗/斜体/下划线/删除线/高亮/字体/上下标
- 段落级 pPr：对齐/缩进/段距/项目符号；pStyle → h1-h6（读 styles.xml，
  style 的 rPr 颜色字号一并继承）
- 表格 w:tbl：列宽(dxa)/跨列/跨行/单元格底纹
- 页面版式 sectPr：pgSz/pgMar → 正文宽度与页边距
- 内嵌图片（blip → base64 内联）

用法: python officedoc2html.py <file.docx|file.pptx>
输出: HTML → stdout；错误 → stderr，退出码非 0。
限制: 不支持旋转/图表/艺术字/SmartArt；旧 .doc/.ppt 二进制格式不支持。
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
body{font-family:'Microsoft YaHei','Microsoft YaHei UI','PingFang SC','Hiragino Sans GB','Heiti SC','SimHei','Source Han Sans SC','Noto Sans CJK SC','WenQuanYi Micro Hei',system-ui,-apple-system,sans-serif;margin:0;padding:20px;background:#e8eaed;color:#1f2329;}
.doc{max-width:820px;margin:0 auto;background:#fff;padding:48px 56px;box-shadow:0 2px 12px rgba(0,0,0,.08);border-radius:8px;box-sizing:border-box;}
.doc h1{font-size:1.7em;border-bottom:2px solid #e8eaed;padding-bottom:8px;}
.doc h2{font-size:1.35em;margin-top:1.4em;}
.doc h3{font-size:1.15em;margin-top:1.2em;}
.doc p{line-height:1.75;margin:.6em 0;}
.doc img{max-width:100%;border-radius:4px;}
.doc table{border-collapse:collapse;margin:1em 0;width:100%;}
.doc td,.doc th{border:1px solid #b8bcc4;padding:6px 10px;vertical-align:top;}
.doc a{color:#2563eb;}
.slide-scroll{overflow:auto;padding:4px 0;}
.slide-wrap{position:relative;margin:16px auto;overflow:hidden;border-radius:6px;box-shadow:0 2px 14px rgba(0,0,0,.18);}
.slide{position:relative;background:#fff;transform-origin:top left;}
.slide .sp{position:absolute;box-sizing:border-box;overflow:hidden;display:flex;}
.slide .sp p{margin:0;}
.slide .no{position:absolute;top:8px;right:12px;color:rgba(0,0,0,.28);font-size:12px;z-index:99;}
.footer{max-width:1280px;margin:8px auto;color:#9aa0a6;font-size:12px;text-align:center;}
</style>
"""

# 自适应缩放脚本：把每页原始尺寸（如 1280×720）等比缩放到预览区宽度。
# HTML 完全由本脚本生成，内容可信；无 sandbox 时执行，有 sandbox 时退化为可滚动原尺寸。
FIT_JS = """
<script>
(function(){
  function fit(){
    var scroll=document.querySelector('.slide-scroll');
    if(!scroll)return;
    var avail=scroll.clientWidth-8;
    document.querySelectorAll('.slide-wrap').forEach(function(w){
      var s=w.querySelector('.slide');
      if(!s)return;
      var sw=parseFloat(w.getAttribute('data-w')||s.getAttribute('data-w')||s.style.width)||0;
      var sh=parseFloat(w.getAttribute('data-h')||s.getAttribute('data-h')||s.style.height)||0;
      if(!sw||!sh)return;
      var k=Math.min(1,avail/sw);
      s.style.transform='scale('+k+')';
      w.style.width=(sw*k)+'px';
      w.style.height=(sh*k)+'px';
    });
  }
  window.addEventListener('resize',fit);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',fit);
  else fit();
})();
</script>
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


# ═════════════════════════ 颜色解析（solid / 渐变通用） ═════════════════════════

def _apply_lum(hex6: str, lum_mod: float, lum_off: float) -> str:
    """lumMod/lumOff 明度调整：HSL 的 L' = L*lumMod + lumOff/100000。
    近似实现：RGB 线性缩放 + 偏移（视觉足够接近）。"""
    r = int(hex6[0:2], 16); g = int(hex6[2:4], 16); b = int(hex6[4:6], 16)
    off = lum_off * 255.0
    r = max(0, min(255, int(r * lum_mod + off)))
    g = max(0, min(255, int(g * lum_mod + off)))
    b = max(0, min(255, int(b * lum_mod + off)))
    return f'#{r:02X}{g:02X}{b:02X}'


def _apply_tint_shade(hex6: str, tint: float = None, shade: float = None) -> str:
    """tint：向白色混合；shade：向黑色混合（val 为万分比）。"""
    r = int(hex6[0:2], 16); g = int(hex6[2:4], 16); b = int(hex6[4:6], 16)
    if tint is not None:
        f = tint / 100000.0
        r = int(r + (255 - r) * f); g = int(g + (255 - g) * f); b = int(b + (255 - b) * f)
    if shade is not None:
        f = shade / 100000.0
        r = int(r * f); g = int(g * f); b = int(b * f)
    r = max(0, min(255, r)); g = max(0, min(255, g)); b = max(0, min(255, b))
    return f'#{r:02X}{g:02X}{b:02X}'


def color_el_css(el, theme: dict):
    """颜色元素（srgbClr/sysClr/schemeClr/prstClr）→ '#RRGGBB'（含子修饰）。"""
    if el is None:
        return None
    tag = el.tag.split('}')[-1]
    if tag == 'srgbClr':
        base = el.get('val') or ''
    elif tag == 'sysClr':
        base = el.get('lastClr') or '000000'
    elif tag == 'schemeClr':
        base = theme.get(el.get('val', '') or '', '#000000')
        base = (base or '#000000').lstrip('#')
    else:
        return None
    if not re.match(r'^[0-9A-Fa-f]{6}$', base):
        return None
    lum_mod, lum_off, tint, shade = 1.0, 0.0, None, None
    for mod in el:
        mtag = mod.tag.split('}')[-1]
        try:
            v = int(mod.get('val', '0'))
        except (TypeError, ValueError):
            continue
        if mtag == 'lumMod':
            lum_mod = v / 100000.0
        elif mtag == 'lumOff':
            lum_off = v / 100000.0
        elif mtag == 'tint':
            tint = v
        elif mtag == 'shade':
            shade = v
    out = '#' + base
    if lum_mod != 1.0 or lum_off != 0.0:
        out = _apply_lum(base, lum_mod, lum_off)
    if tint is not None:
        out = _apply_tint_shade(out.lstrip('#'), tint=tint)
    if shade is not None:
        out = _apply_tint_shade(out.lstrip('#'), shade=shade)
    return out


def color_of(parent_el, theme: dict):
    """取 solidFill 子元素颜色（srgbClr / schemeClr 含修饰变体）。"""
    if parent_el is None:
        return None
    sf = parent_el.find(f'{A}solidFill')
    if sf is None:
        return None
    for c in sf:
        col = color_el_css(c, theme)
        if col:
            return col
    return None


def grad_fill_css(fill_el, theme: dict) -> str:
    """a:gradFill → CSS linear-gradient / radial-gradient。"""
    if fill_el is None:
        return ''
    gs_lst = fill_el.find(f'{A}gsLst')
    if gs_lst is None:
        return ''
    stops = []
    for gs in gs_lst.findall(f'{A}gs'):
        try:
            pos = int(gs.get('pos', '0')) / 1000.0  # 万分比 → 百分比
        except (TypeError, ValueError):
            pos = 0.0
        col = None
        for c in gs:
            col = color_el_css(c, theme)
            if col:
                break
        if col:
            stops.append(f'{col} {max(0.0, min(100.0, pos)):.1f}%')
    if not stops:
        return ''
    if len(stops) == 1:
        return f'background:{stops[0].split()[0]};'
    lin = fill_el.find(f'{A}lin')
    if lin is not None and lin.get('ang') is not None:
        try:
            ang = int(lin.get('ang')) / 60000.0  # 1/60000 度
        except (TypeError, ValueError):
            ang = 0.0
        # OOXML 角度 0°=向东（左→右），顺时针；CSS 0°=向北（下→上），顺时针
        css_ang = (ang + 90.0) % 360.0
        return f'background:linear-gradient({css_ang:.0f}deg,{",".join(stops)});'
    path = fill_el.find(f'{A}path')
    if path is not None:
        ptype = path.get('path', '') or ''
        if ptype == 'circle':
            fr = path.find(f'{A}fillToRect')
            l = t = 50.0
            if fr is not None:
                try:
                    l = int(fr.get('l', '50000')) / 1000.0
                    t = int(fr.get('t', '50000')) / 1000.0
                except (TypeError, ValueError):
                    pass
            return f'background:radial-gradient(circle at {l:.0f}% {t:.0f}%,{",".join(stops)});'
        if ptype == 'rect':
            return f'background:linear-gradient(to bottom,{",".join(stops)});'
        return f'background:radial-gradient(circle,{",".join(stops)});'
    return f'background:linear-gradient(to right,{",".join(stops)});'


def fill_css_of(parent_el, theme: dict) -> str:
    """按子元素顺序找 gradFill/solidFill/noFill → 完整 background CSS；无填充返回 ''。"""
    if parent_el is None:
        return ''
    for child in parent_el:
        tag = child.tag.split('}')[-1]
        if tag == 'gradFill':
            css = grad_fill_css(child, theme)
            if css:
                return css
        elif tag == 'solidFill':
            for c in child:
                col = color_el_css(c, theme)
                if col:
                    return f'background:{col};'
        elif tag == 'noFill':
            return 'background:transparent;'
    return ''


# ═════════════════════════ DOCX v2（富文本 + 表格 + 页面版式） ═════════════════════════

_W_ENUM = 'auto'


def _twips2px(v) -> float:
    try:
        return int(v) / 15.0  # twips(1/20pt) → px（×4/3/20）
    except (TypeError, ValueError):
        return 0.0


def docx_styles(zf) -> dict:
    """styles.xml → {styleId: {'name':…, 'color':…, 'sz':半磅, 'b':bool, 'i':bool}}
    仅取段落样式（heading/标题 映射与 run 属性继承用）。"""
    out = {}
    if 'word/styles.xml' not in zf.namelist():
        return out
    try:
        root = ET.fromstring(zf.read('word/styles.xml'))
    except ET.ParseError:
        return out
    for st in root.findall(f'{W}style'):
        sid = st.get(f'{W}styleId', '') or ''
        if not sid:
            continue
        info = {'name': '', 'color': None, 'sz': 0, 'b': False, 'i': False}
        nm = st.find(f'{W}name')
        if nm is not None:
            info['name'] = (nm.get(f'{W}val', '') or '').lower()
        rpr = st.find(f'{W}rPr')
        if rpr is not None:
            col = rpr.find(f'{W}color')
            if col is not None and (col.get(f'{W}val') or '') not in ('', 'auto'):
                info['color'] = '#' + col.get(f'{W}val')
            sz = rpr.find(f'{W}sz')
            if sz is not None:
                try:
                    info['sz'] = int(sz.get(f'{W}val', '0'))
                except (TypeError, ValueError):
                    pass
            info['b'] = rpr.find(f'{W}b') is not None
            info['i'] = rpr.find(f'{W}i') is not None
        out[sid] = info
    return out


def _heading_level(style_id: str, styles: dict) -> int:
    """styleId → 标题级别（1-6），非标题返回 0。"""
    info = styles.get(style_id) or {}
    name = info.get('name', '')
    m = re.match(r'^(?:heading|标题)\s*([1-6])$', name)
    if m:
        return int(m.group(1))
    m = re.match(r'^(\d)', style_id or '')
    if (style_id or '').lower().startswith('heading') and m:
        return int(m.group(1))
    if name == 'title' or (style_id or '').lower() == 'title':
        return 1
    return 0


def _docx_run_html(r, styles_def: dict) -> str:
    """w:r → 富文本 span（颜色/字号/粗斜/下划线/删除线/高亮/字体/上下标）。"""
    texts = []
    for node in r:
        if node.tag == f'{W}t':
            texts.append(esc(node.text or ''))
        elif node.tag == f'{W}tab':
            texts.append('&emsp;&emsp;')
        elif node.tag == f'{W}br':
            texts.append('<br/>')
    text = ''.join(texts)
    if not text:
        return ''
    rpr = r.find(f'{W}rPr')
    style = []
    font = ''
    if rpr is not None:
        col = rpr.find(f'{W}color')
        if col is not None and (col.get(f'{W}val') or '') not in ('', 'auto'):
            v = col.get(f'{W}val')
            style.append(f'color:#{v}')
        sz = rpr.find(f'{W}sz')
        if sz is not None:
            try:
                half_pts = int(sz.get(f'{W}val', '0'))
                if half_pts:
                    style.append(f'font-size:{half_pts / 2 * PT2PX:.1f}px')
            except (TypeError, ValueError):
                pass
        if rpr.find(f'{W}b') is not None:
            style.append('font-weight:700')
        if rpr.find(f'{W}i') is not None:
            style.append('font-style:italic')
        u = rpr.find(f'{W}u')
        if u is not None and (u.get(f'{W}val', 'single') or 'single') != 'none':
            style.append('text-decoration:underline')
        if rpr.find(f'{W}strike') is not None:
            style.append('text-decoration:line-through')
        hl = rpr.find(f'{W}highlight')
        if hl is not None and hl.get(f'{W}val', '') not in ('', 'none'):
            _HL = {'yellow': '#ffff00', 'green': '#00ff00', 'cyan': '#00ffff',
                   'magenta': '#ff00ff', 'blue': '#0000ff', 'red': '#ff0000',
                   'darkBlue': '#000080', 'darkYellow': '#808000',
                   'darkGreen': '#008000', 'darkMagenta': '#800080', 'darkRed': '#800000'}
            style.append(f'background:{_HL.get(hl.get(f"{W}val"), "#ffff00")}')
        shd = rpr.find(f'{W}shd')
        if shd is not None:
            fill = shd.get(f'{W}fill', '')
            if fill and fill not in ('auto', 'FFFFFF', 'ffffff'):
                style.append(f'background:#{fill}')
        rfonts = rpr.find(f'{W}rFonts')
        if rfonts is not None:
            font = (rfonts.get(f'{W}ascii') or rfonts.get(f'{W}hAnsi') or
                    rfonts.get(f'{W}eastAsia') or '')
        va = rpr.find(f'{W}vertAlign')
        if va is not None:
            v = va.get(f'{W}val', '')
            if v == 'superscript':
                style.append('font-size:0.7em;vertical-align:super')
            elif v == 'subscript':
                style.append('font-size:0.7em;vertical-align:sub')
    if not style and not font:
        return text
    attrs = ''
    if font:
        attrs += f' data-ff="{esc(font)}"'
    s = f'style="{";".join(style)}"' if style else ''
    cls = ' class="ff"' if font else ''
    return f'<span{cls}{attrs} {s}>{text}</span>'


def _docx_para_html(p, styles: dict, styles_def_unused=None, in_cell=False) -> str:
    """w:p → <p>（或表格内不带 margin 的 <p>）。含对齐/缩进/段距/符号/超链接。"""
    ppr = p.find(f'{W}pPr')
    pstyle_id = ''
    align = ''
    indent = ''
    spacing = ''
    bullet = False
    if ppr is not None:
        ps = ppr.find(f'{W}pStyle')
        if ps is not None:
            pstyle_id = ps.get(f'{W}val', '') or ''
        jc = ppr.find(f'{W}jc')
        if jc is not None:
            align = {'center': 'center', 'right': 'right',
                     'both': 'justify', 'distribute': 'justify'}.get(jc.get(f'{W}val', ''), '')
        ind = ppr.find(f'{W}ind')
        if ind is not None:
            fl = ind.get(f'{W}firstLine') or ind.get(f'{W}firstLineChars')
            left = ind.get(f'{W}left') or ind.get(f'{W}start') or ind.get(f'{W}hanging')
            if fl:
                indent += f'text-indent:{_twips2px(fl):.0f}px;'
            elif left:
                indent += f'margin-left:{_twips2px(left):.0f}px;'
        spc = ppr.find(f'{W}spacing')
        if spc is not None:
            before = spc.get(f'{W}before')
            after = spc.get(f'{W}after')
            if before:
                spacing += f'margin-top:{_twips2px(before):.0f}px;'
            if after:
                spacing += f'margin-bottom:{_twips2px(after):.0f}px;'
        bullet = ppr.find(f'{W}numPr') is not None
    # run 序列（含 hyperlink 内 run）
    runs = []
    for child in p:
        if child.tag == f'{W}r':
            h = _docx_run_html(child, styles)
            if h:
                runs.append(h)
        elif child.tag == f'{W}hyperlink':
            inner = []
            for hr in child.findall(f'{W}r'):
                h = _docx_run_html(hr, styles)
                if h:
                    inner.append(h)
            if inner:
                runs.append(f'<a>{"".join(inner)}</a>')
    # 标题映射：heading → hN，并继承 style rPr 颜色/字号/粗斜
    lvl = _heading_level(pstyle_id, styles)
    if lvl and (runs or not in_cell):
        info = styles.get(pstyle_id, {})
        hstyle = []
        if info.get('color'):
            hstyle.append(f'color:{info["color"]}')
        if info.get('sz'):
            hstyle.append(f'font-size:{info["sz"] / 2 * PT2PX:.1f}px')
        hs = f' style="{";".join(hstyle)}"' if hstyle else ''
        return f'<h{lvl}{hs}>{"".join(runs)}</h{lvl}>'
    if not runs:
        return '<p style="height:.8em"></p>' if not in_cell else ''
    style = []
    if align:
        style.append(f'text-align:{align}')
    if indent:
        style.append(indent.rstrip(';'))
    if spacing:
        style.append(spacing.rstrip(';'))
    if in_cell:
        style.append('margin:.2em 0')
    prefix = '<span style="margin-right:6px">•</span> ' if bullet else ''
    s = f'style="{";".join(style)}"' if style else ''
    return f'<p {s}>{prefix}{"".join(runs)}</p>'


def _docx_tbl_html(tbl, styles: dict) -> str:
    """w:tbl → <table>（列宽 dxa、gridSpan 跨列、vMerge 跨行近似、底纹）。"""
    # 网格总宽
    grid = tbl.find(f'{W}tblGrid')
    widths = []
    if grid is not None:
        for gc in grid.findall(f'{W}gridCol'):
            widths.append(_twips2px(gc.get(f'{W}w', '0')))
    total = sum(widths)
    rows_html = []
    for tr in tbl.findall(f'{W}tr'):
        cells_html = []
        col_pos = 0  # 当前单元格对应 gridCol 起始列（gridSpan 跨列累加）
        for tc in tr.findall(f'{W}tc'):
            tcpr = tc.find(f'{W}tcPr')
            cstyle = []
            span = 1
            if tcpr is not None:
                gs = tcpr.find(f'{W}gridSpan')
                if gs is not None:
                    try:
                        span = int(gs.get(f'{W}val', '1'))
                    except (TypeError, ValueError):
                        span = 1
                tcw = tcpr.find(f'{W}tcW')
                if tcw is not None and tcw.get(f'{W}type') == 'dxa':
                    px = _twips2px(tcw.get(f'{W}w', '0'))
                    if px > 0:
                        cstyle.append(f'width:{px:.0f}px')
                shd = tcpr.find(f'{W}shd')
                if shd is not None:
                    fill = shd.get(f'{W}fill', '')
                    if fill and fill not in ('auto', 'FFFFFF', 'ffffff'):
                        cstyle.append(f'background:#{fill}')
                if tcpr.find(f'{W}vMerge') is not None:
                    vm = tcpr.find(f'{W}vMerge')
                    if (vm.get(f'{W}val', 'continue') or 'continue') == 'restart':
                        cstyle.append('border-top:none')
                    else:
                        col_pos += span
                        cells_html.append('<td style="border:none;padding:0 10px"></td>')
                        continue
            if not cstyle or not any(s.startswith('width') for s in cstyle):
                # 无显式列宽 → 用 gridCol 宽度（跨列求和）；table-layout:fixed
                # 下缺宽度会被浏览器均分，不等列网格会错
                gw = sum(widths[col_pos:col_pos + span]) if widths and col_pos < len(widths) else 0
                if gw > 0:
                    cstyle.insert(0, f'width:{gw:.0f}px')
            col_pos += span
            paras = [_docx_para_html(p, styles, in_cell=True)
                     for p in tc.findall(f'{W}p')]
            cs = f' style="{";".join(cstyle)}"' if cstyle else ''
            span_attr = f' colspan="{span}"' if span > 1 else ''
            cells_html.append(f'<td{span_attr}{cs}>{"".join(paras) or "&nbsp;"}</td>')
        rows_html.append(f'<tr>{"".join(cells_html)}</tr>')
    tstyle = f' style="width:{total:.0f}px;table-layout:fixed;"' if total > 0 else ''
    return f'<table{tstyle}>{"".join(rows_html)}</table>'


def _docx_media_in_runs(el, rels, zf, out: list):
    """递归收集元素内 blip 引用的图片（w:drawing/w:pict → a:blip）。"""
    for blip in el.iter(f'{A}blip'):
        rid = blip.get(f'{R}embed') or ''
        target = rels.get(rid)
        if target:
            out.append(target)


def convert_docx(path: str) -> str:
    with zipfile.ZipFile(path) as zf:
        styles = docx_styles(zf)
        rels = {}
        if 'word/_rels/document.xml.rels' in zf.namelist():
            relroot = ET.fromstring(zf.read('word/_rels/document.xml.rels'))
            for rel in relroot.iter(f'{PR}Relationship'):
                target = rel.get('Target', '') or ''
                if target and not target.startswith('#'):
                    if not target.startswith('word/'):
                        target = 'word/' + target.lstrip('/')
                    rels[rel.get('Id')] = target
        doc = ET.fromstring(zf.read('word/document.xml'))
        body = doc.find(f'{W}body')
        parts = []
        page_w = 0.0
        pad = ''
        if body is not None:
            for child in body:
                if child.tag == f'{W}p':
                    # 段内图片（w:drawing/w:pict → blip）
                    imgs = []
                    _docx_media_in_runs(child, rels, zf, imgs)
                    img_html = ''.join(
                        f'<img src="{media_b64(zf, m)}" alt="img"/>'
                        for m in imgs if media_b64(zf, m))
                    ph = _docx_para_html(child, styles)
                    if img_html:
                        if ph.startswith('<p '):
                            ph = ph.replace('>', '>' + img_html, 1)
                        elif ph.startswith('<p>'):
                            ph = ph.replace('>', '>' + img_html, 1)
                        else:  # 标题段
                            ph = img_html + ph
                    parts.append(ph)
                elif child.tag == f'{W}tbl':
                    parts.append(_docx_tbl_html(child, styles))
                elif child.tag == f'{W}sectPr':
                    # 页面版式：pgSz/pgMar → 容器宽度与页边距
                    pgsz = child.find(f'{W}pgSz')
                    pgmar = child.find(f'{W}pgMar')
                    if pgsz is not None:
                        w_tw = int(pgsz.get(f'{W}w', '0') or 0)
                        ml = int(pgmar.get(f'{W}left', '0') or 0) if pgmar is not None else 0
                        mr = int(pgmar.get(f'{W}right', '0') or 0) if pgmar is not None else 0
                        mt = int(pgmar.get(f'{W}top', '0') or 0) if pgmar is not None else 0
                        mb = int(pgmar.get(f'{W}bottom', '0') or 0) if pgmar is not None else 0
                        if w_tw:
                            page_w = (w_tw - ml - mr) / 15.0
                            pad = (f'padding:{mt / 15:.0f}px {mr / 15:.0f}px '
                                   f'{mb / 15:.0f}px {ml / 15:.0f}px;')
        # sectPr 也可出现在段内（节属性），上面只兜 body 级；无则用默认 A4 纵向近似
        body_html = '\n'.join(parts) or '<p>(空文档)</p>'
        doc_style = ''
        if page_w:
            doc_style = f' style="width:{page_w:.0f}px;max-width:none;{pad}"'
        elif pad:
            doc_style = f' style="{pad}"'
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8">{CSS}</head>'
            f'<body><div class="doc"{doc_style}>{body_html}</div></body></html>')


# ═════════════════════════ PPTX v3（绝对定位画布 + 渐变 + 自适应缩放） ═════════════════════════

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
    # Office 系统色别名归一（clrScheme 中可能为 window/windowText 等词而非 hex）
    _SYS = {'window': '#FFFFFF', 'windowText': '#000000',
            'windowFrame': '#D4D0C8', 'menu': '#FFFFFF', 'menuText': '#000000',
            'menuBar': '#FFFFFF', 'activeBorder': '#D4D0C8', 'inactiveBorder': '#D4D0C8'}
    for k, v in list(out.items()):
        if v and not (len(v) == 7 and all(c in '0123456789ABCDEFabcdef' for c in v[1:])):
            out[k] = _SYS.get(v[1:] if v.startswith('#') else v, v)
    # 主题别名
    out['tx1'] = out.get('dk1')
    out['bg1'] = out.get('lt1')
    out['tx2'] = out.get('dk2', '#44546A')
    out['bg2'] = out.get('lt2', '#E7E6E6')
    return out


def _resolve_rel_target(part_dir: str, target: str) -> str:
    """将 .rels 中的 Target 解析为归档内绝对路径。
    target 相对「part 所在目录」（即 _rels 的上级目录），需正确折叠 '../'。
    例：part_dir='ppt/slides', target='../media/image7.png' → 'ppt/media/image7.png'。"""
    if not target:
        return ''
    if target.startswith('/'):
        return target.lstrip('/')
    path = part_dir.rstrip('/') + '/' + target
    stack = []
    for seg in path.split('/'):
        if seg == '' or seg == '.':
            continue
        if seg == '..':
            if stack:
                stack.pop()
        else:
            stack.append(seg)
    return '/'.join(stack)


def parse_rels(zf, rel_name: str) -> dict:
    """{'rId1': ('slideLayout', 'ppt/slideLayouts/slideLayout1.xml')} 按 type 后缀分类。
    Target 已解析为归档内绝对路径。"""
    out = {}
    if rel_name not in zf.namelist():
        return out
    # part 所在目录 = .rels 路径去掉 '/_rels/...' 后缀
    part_dir = rel_name.rsplit('/_rels/', 1)[0]
    root = ET.fromstring(zf.read(rel_name))
    for rel in root.iter(f'{PR}Relationship'):
        rtype = (rel.get('Type') or '').rsplit('/', 1)[-1]
        target = rel.get('Target') or ''
        out[rel.get('Id')] = (rtype, _resolve_rel_target(part_dir, target))
    return out


def style_fill_of(sp, theme: dict):
    """shapeStyle 主题填充：fillRef idx>1 时用 accent 色的 lumMod 变体近似。
    spPr 无显式填充时兜底（否则形状变透明——v2 已知「颜色不对」根因之一）。"""
    style = sp.find(f'{P}style')
    if style is None:
        return None
    fr = style.find(f'{A}fillRef')
    if fr is None:
        return None
    try:
        idx = int(fr.get('idx', '1'))
    except (TypeError, ValueError):
        idx = 1
    if idx < 1:
        return None
    sf = fr.find(f'{A}schemeClr')
    if sf is None:
        return None
    return color_el_css(sf, theme)


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
    if prst in ('diamond',):
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


def run_html(r, theme, scale: float = 1.0) -> str:
    """a:r → 带 span 样式的 HTML（scale 为 normAutofit 缩字系数）"""
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
            style.append(f'font-size:{sz / 100 * PT2PX * scale:.1f}px')
        elif scale != 1.0:
            style.append(f'font-size:{18 * scale:.1f}px')
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
        if not sz and scale == 1.0:
            style.append('font-size:18px')
    else:
        style.append('font-size:18px' if scale == 1.0 else f'font-size:{18 * scale:.1f}px')
    s = f'style="{";".join(style)}"' if style else ''
    ff = f' data-ff="{esc(font)}"' if font else ''
    cls = ' class="ff"' if font else ''
    return f'<span{cls}{ff} {s}>{text}</span>'


def para_html(p, theme, scale: float = 1.0) -> str:
    """a:p → <p style=align>，含项目符号/段前段后距近似"""
    pPr = p.find(f'{A}pPr')
    align = 'left'
    indent_bullet = False
    num_bullet = False
    line_pct = None
    spc_bef = 0.0
    spc_aft = 0.0
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
                line_pct = int(lnSpc.get('val')) / 1000
            except (TypeError, ValueError):
                pass
        # 段前/段后距：spcPts（百分之一磅）→ px
        for tag, store in (('spcBef', 'bef'), ('spcAft', 'aft')):
            el = pPr.find(f'{A}{tag}/{A}spcPts')
            if el is not None and el.get('val'):
                try:
                    v = int(el.get('val')) / 100 * PT2PX
                    if store == 'bef':
                        spc_bef = v
                    else:
                        spc_aft = v
                except (TypeError, ValueError):
                    pass
    return _para_runs(p, theme, align, indent_bullet, num_bullet,
                      line_pct, spc_bef, spc_aft, scale)


def _para_runs(p, theme, align, bullet, num, line_pct, spc_bef=0.0, spc_aft=0.0,
               scale: float = 1.0):
    runs = [run_html(r, theme, scale) for r in p.findall(f'{A}r')]
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
    # PowerPoint 段落无 UA 外边距——显式归零，否则浏览器默认 margin:1em 0
    # 会把每个文本框的文字整体往下顶（中文 16px），主副标题重叠的根因。
    style.append('margin:0')
    if ml != '0':
        style.append(f'margin-left:{ml}')
    if spc_bef:
        style.append(f'padding-top:{spc_bef:.1f}px')
    if spc_aft:
        style.append(f'padding-bottom:{spc_aft:.1f}px')
    if line_pct:
        # 无单位倍数（按自身字号算），百分比按 <p> 继承字号算是错的
        style.append(f'line-height:{line_pct / 100:.2f}')
    if not runs and not brs:
        return f'<p style="height:.6em;margin:0"></p>'
    return f'<p style="{";".join(style)}">{prefix}{content}</p>'


def txBody_html(txBody, theme, scale: float = 1.0) -> str:
    if txBody is None:
        return ''
    paras = ''.join(para_html(p, theme, scale) for p in txBody.findall(f'{A}p'))
    return f'<div class="tx" style="width:100%">{paras}</div>'


def body_pad_css(txBody) -> str:
    """bodyPr 内边距：显式 lIns/rIns/tIns/bIns（EMU→px），缺省用 PowerPoint 默认。"""
    if txBody is None:
        return 'padding:4.8px 7.2px;'
    bp = txBody.find(f'{A}bodyPr')
    if bp is None:
        return 'padding:4.8px 7.2px;'
    try:
        l = int(bp.get('lIns', 91440)) / EMU_PER_PX
        r = int(bp.get('rIns', 91440)) / EMU_PER_PX
        t = int(bp.get('tIns', 45720)) / EMU_PER_PX
        b = int(bp.get('bIns', 45720)) / EMU_PER_PX
    except (TypeError, ValueError):
        return 'padding:4.8px 7.2px;'
    return f'padding:{t:.1f}px {r:.1f}px {b:.1f}px {l:.1f}px;'


def autofit_scale(txBody) -> float:
    """normAutofit fontScale（千分比）→ 缩放系数。PowerPoint 溢出缩字近似。"""
    if txBody is None:
        return 1.0
    bp = txBody.find(f'{A}bodyPr')
    if bp is None:
        return 1.0
    na = bp.find(f'{A}normAutofit')
    if na is not None and na.get('fontScale'):
        try:
            return int(na.get('fontScale')) / 100000.0
        except (TypeError, ValueError):
            return 1.0
    return 1.0


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


def _rels_name_for(part: str) -> str:
    """'ppt/slides/slide1.xml' → 'ppt/slides/_rels/slide1.xml.rels'"""
    d, f = part.rsplit('/', 1)
    return f'{d}/_rels/{f}.rels'


def ph_of(sp):
    """(type, idx) 或 None。占位符标识，用于跨 slide/layout/master 继承。"""
    ph = sp.find(f'{P}nvSpPr/{P}nvPr/{P}ph')
    if ph is None:
        return None
    return (ph.get('type', 'body') or 'body', ph.get('idx', '') or '')


def ph_xfrm_table(zf, part: str, depth=0) -> dict:
    """收集 layout（及其 master）占位符坐标 {(type,idx): box}。
    本级覆盖上级（layout 定位优先于 master）。"""
    table = {}
    if depth > 2 or part not in zf.namelist():
        return table
    # 先递归上级（低优先）
    try:
        rels = parse_rels(zf, _rels_name_for(part))
    except ET.ParseError:
        rels = {}
    for rid, (rtype, target) in rels.items():
        if rtype == 'slideMaster' and target:
            t2 = target if target.startswith('ppt/') else 'ppt/' + target
            table.update(ph_xfrm_table(zf, t2, depth + 1))
    # 本级覆盖
    try:
        root = ET.fromstring(zf.read(part))
    except ET.ParseError:
        return table
    spTree = root.find(f'{P}cSld/{P}spTree')
    if spTree is None:
        return table
    for sp in spTree.iter(f'{P}sp'):
        ph = ph_of(sp)
        if ph is None:
            continue
        box = xfrm_of(sp.find(f'{P}spPr'))
        if box:
            table[ph] = box
    return table


def render_shape(el, tf: Transform, theme, rels, zf, ph_table=None) -> str:
    spPr = el.find(f'{P}spPr')
    box = xfrm_of(spPr)
    if box is None:
        # 占位符无坐标 → 继承版式/母版同 (type,idx) 坐标；仍无 → 跳过
        ph = ph_of(el)
        if ph and ph_table and ph in ph_table:
            box = ph_table[ph]
    if box is None:
        box = (0, 0, 0, 0)
    x, y, cx, cy = tf.apply(*box)
    if cx <= 0 or cy <= 0:
        return ''  # 零尺寸形状跳过
    px = x / EMU_PER_PX; py = y / EMU_PER_PX
    pw = cx / EMU_PER_PX; ph = cy / EMU_PER_PX

    # 填充：显式 gradFill/solidFill/noFill（v3 支持渐变）→ shapeStyle 兜底 → 透明
    fill = fill_css_of(spPr, theme)
    if not fill:
        sf = style_fill_of(el, theme)
        fill = f'background:{sf};' if sf else 'background:transparent;'

    g = spPr.find(f'{A}prstGeom') if spPr is not None else None
    prst = (g.get('prst', 'rect') if g is not None else 'rect')
    is_line = prst in ('line', 'straightConnector1', 'straightConnector',
                       'bentConnector', 'bentConnector3', 'curvedConnector3')
    if is_line:
        # 线条：细高（或细宽）矩形 + 填充当颜色
        line_col = (fill.split(':', 1)[1].rstrip(';') if fill.startswith('background:#')
                    else '#33475b')
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
    # PowerPoint 默认文本内边距：lIns/rIns=91440EMU(7.2px)、tIns/bIns=45720EMU(4.8px)
    pad = body_pad_css(txBody)
    style = pos + fill + geom_css(spPr) + line_css(spPr, theme) + pad
    tx = txBody_html(txBody, theme, autofit_scale(txBody))
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
    mpath = target.lstrip('/')  # parse_rels 已剥 '../'，此处为归档内相对路径
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
    """slide → layout → master 三级背景查找（纯色/渐变/图片）。
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
                # v3：gradFill/solidFill/noFill 统一入口（渐变背景——
                # 深色渐变底+浅色字的 PPT 此前全被渲染成白底导致文字“消失”）
                css = fill_css_of(bgPr, theme)
                if css:
                    return css
                blip = bgPr.find(f'{A}blipFill/{A}blip')
                if blip is not None:
                    rid = blip.get(f'{R}embed') or ''
                    target = rels.get(rid, ('', ''))[1] if rid in rels else ''
                    if target:
                        mpath = target.lstrip('/')
                        b64 = media_b64(zf, mpath)
                        if b64:
                            return f'background:url({b64}) center/cover no-repeat;'
            # 背景引用：<p:bgRef><a:schemeClr val="bg1"/> → 主题色
            bgRef = bg.find(f'{P}bgRef')
            if bgRef is not None:
                sch = bgRef.find(f'{A}schemeClr')
                if sch is not None:
                    col = color_el_css(sch, theme)
                    if col:
                        return f'background:{col};'
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

        # 幻灯片顺序按 presentation.xml 的 sldIdLst（文件名序号不总可靠）
        pres_rels = parse_rels(zf, 'ppt/_rels/presentation.xml.rels')
        sld_ids = pres.find(f'{P}sldIdLst')
        slide_names = []
        if sld_ids is not None:
            for sld in sld_ids.findall(f'{P}sldId'):
                rid = sld.get(f'{R}id') or ''
                target = pres_rels.get(rid, ('', ''))[1]
                if target:
                    slide_names.append(target.lstrip('/'))
        if not slide_names:  # 兜底：按文件名序号
            slide_names = [n for n in zf.namelist()
                           if re.match(r'ppt/slides/slide\d+\.xml$', n)]
            slide_names.sort(key=lambda n: int(re.search(r'slide(\d+)\.xml$', n).group(1)))
        if not slide_names:
            return f'<!DOCTYPE html><html><head><meta charset="utf-8">{CSS}</head><body><div class="doc"><p>(无幻灯片)</p></div></body></html>'

        slides_html = []
        for idx, sname in enumerate(slide_names, 1):
            rel_name = _rels_name_for(sname)
            rels = parse_rels(zf, rel_name)
            bg = bg_css_of(zf, theme, [(sname, rels)])

            # 本页 layout（及其 master）的占位符坐标表——slide 中
            # 无 xfrm 的占位符（标题/正文框）从这里继承坐标，否则整块丢失
            ph_table = {}
            for rid, (rtype, target) in rels.items():
                if rtype == 'slideLayout' and target:
                    layout_part = target if target.startswith('ppt/') else 'ppt/' + target
                    ph_table = ph_xfrm_table(zf, layout_part)
                    break

            root = ET.fromstring(zf.read(sname))
            spTree = root.find(f'{P}cSld/{P}spTree')
            shapes: list = []
            if spTree is not None:
                walk_tree(spTree, IDENT, shapes)
            inner = ''.join(
                render_shape(el, tf, theme, rels, zf, ph_table) if kind == 'sp'
                else render_pic(el, tf, rels, zf)
                for kind, el, tf in shapes
            )
            no = (f'<span class="no">{idx} / {len(slide_names)}</span>'
                  if idx > 1 or len(slide_names) > 1 else '')
            # data-w/data-h 供自适应缩放脚本读取；wrap 高宽由脚本按比例设置。
            # 无 JS 环境（脚本被禁）退化为原始尺寸滚动查看，不会裁切内容。
            slides_html.append(
                f'<div class="slide-wrap" style="width:{Wpx:.0f}px;height:{Hpx:.0f}px;">'
                f'<div class="slide" style="width:{Wpx:.0f}px;height:{Hpx:.0f}px;{bg}">{no}{inner}</div>'
                f'</div>'
            )

        body = '<div class="slide-scroll">' + '\n'.join(slides_html) + '</div>'
        foot = (f'<div class="footer">共 {len(slide_names)} 页 · '
                f'{Wpx:.0f}×{Hpx:.0f}px 绝对定位还原（文本/形状/图片/渐变背景）</div>')
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8">{CSS}</head>'
            f'<body>{body}{foot}{FIT_JS}</body></html>')


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
