#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
word_measure — 用真实 Word/WPS 渲染引擎测量 docx 排版（页数/段落页位/溢出）

背景：python-docx 没有分页引擎——分页发生在渲染器（Word/WPS）里。用字符数
估算行高/页数必然偏离（docGrid 文档网格、snapToGrid、字体度量都是坑，
实测偏差可达 3 倍）。生成排版型 docx 的正确方法论是「渲染器反馈闭环」：
先实测版心容量 → 生成 → 再实测断言验收。

测量通道（三级降级）：
1. Word COM（Word.Application）——真实分页，最准
2. WPS COM（KWPS.Application）——国产环境备选
3. python-docx 字符估算——无 COM 环境兜底，结果显式标注"估算值"

三种模式（+ 诊断模式）：
- pages:    总页数 + 版心尺寸（探版心用）
- outline:  每段落的文本摘要 + 所在页码（断言"标题与正文同页"等用）
- overflow: 跨页段落检测（哪些段落被分页从中间切开）
- diagnose: 排版异常一键定位——空白页（尾部/中间）+ pageBreakBefore 数量与位置。
            出现空白页/异常分页时优先用此模式，不要在对话里手写脚本拆 XML。

用法（agent 视角）:
  word_measure(path="报告.docx", mode="pages")
  word_measure(path="报告.docx", mode="outline", max_paragraphs=80)
  word_measure(path="报告.docx", mode="overflow")
  word_measure(path="报告.docx", mode="diagnose")   # 空白页/多余分页一键定位

COM 安全设计：
- 全程 try/finally 保证 doc.Close + app.Quit（上次日志事故正是 agent
  手写脚本崩在 COM 清理上）
- gencache 失败自动降 EnsureDispatch（防 makepy 缓存损坏）
- pywin32 缺失时返回安装指引而非崩溃
"""

import logging
import os
import platform

from tools.registry import register_tool

logger = logging.getLogger(__name__)

# wdStatisticPages = 2（ComputeStatistics 参数）
WD_STAT_PAGES = 2
# wdActiveEndPageNumber = 3（Range.Information 参数）— 段落所在页
WD_PAGE = 3
# wdHorizontalPositionRelativeToPage = 5（用于检测段落是否溢出）
WD_HORZ_POS = 5

MAX_PARAGRAPH_TEXT = 60  # outline 模式每段摘要截断长度


def _com_available() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        import win32com.client  # noqa: F401
        return True
    except ImportError:
        return False


def _try_dispatch(app, use_gencache: bool = True):
    """按 gencache→Ensure 顺序 dispatch；gencache 缓存损坏时自动降级。"""
    import win32com.client as win32
    if use_gencache:
        try:
            return win32.gencache.EnsureDispatch(app)
        except Exception:
            logger.warning(f"gencache dispatch {app} 失败，降级 EnsureDispatch")
    return win32.Dispatch(app)


def _measure_with_com(path: str, mode: str, max_paragraphs: int, progids):
    """Word/WPS COM 测量。progids 是按优先级排列的 ProgID 列表。"""
    import pythoncom

    pythoncom.CoInitialize()
    app = None
    doc = None
    try:
        last_err = None
        for progid in progids:
            try:
                app = _try_dispatch(progid)
                break
            except Exception as e:  # ProgID 不存在/未安装
                last_err = e
                app = None
        if app is None:
            return None, f"COM 启动失败: {last_err}"

        app.Visible = False
        try:
            app.DisplayAlerts = 0
        except Exception:
            pass

        doc = app.Documents.Open(os.path.abspath(path), ReadOnly=True)
        try:
            doc.Repaginate()
        except Exception:
            pass  # WPS 某些版本无此方法，Open 后已是最终分页

        total = doc.ComputeStatistics(WD_STAT_PAGES)

        if mode == "pages":
            ps = doc.PageSetup
            # Word COM 的 PageSetup 尺寸单位就是磅(pt)，直接用（曾误除 20）
            usable_w = ps.PageWidth - ps.LeftMargin - ps.RightMargin
            usable_h = ps.PageHeight - ps.TopMargin - ps.BottomMargin
            return {
                "total_pages": total,
                "usable_width_pt": round(usable_w, 1),
                "usable_height_pt": round(usable_h, 1),
                "engine": progid,
            }, None

        if mode == "outline":
            paras = doc.Paragraphs
            n = paras.Count
            limit = min(n, max_paragraphs) if max_paragraphs > 0 else n
            lines = []
            for i in range(1, limit + 1):
                p = paras(i)
                txt = p.Range.Text.replace("\r", "").replace("\x07", "").strip()
                try:
                    page = p.Range.Information(WD_PAGE)
                except Exception:
                    page = -1
                lines.append(f"p{i:>3} 页{page:>3} | {txt[:MAX_PARAGRAPH_TEXT]}")
            tail = f"\n(仅显示前 {limit}/{n} 段，max_paragraphs 调大看更多)" if limit < n else ""
            return {
                "total_pages": total,
                "paragraph_count": n,
                "outline": "\n".join(lines) + tail,
                "engine": progid,
            }, None

        if mode == "overflow":
            paras = doc.Paragraphs
            n = paras.Count
            crossing = []
            for i in range(1, n + 1):
                p = paras(i)
                txt = p.Range.Text.replace("\r", "").replace("\x07", "").strip()
                # 空段自身常横跨分页符（add_page_break 的残留），无内容不算"被切断"
                if not txt:
                    continue
                try:
                    # 段首/段尾页码不同 ⇒ 段落被分页切断
                    rng = p.Range
                    start_pg = rng.Information(WD_PAGE)
                    end_rng = rng.Duplicate
                    end_rng.Collapse(0)  # 0 = wdCollapseEnd
                    end_pg = end_rng.Information(WD_PAGE)
                    if end_pg != start_pg:
                        crossing.append(
                            f"p{i:>3} 页{start_pg}→{end_pg} | {txt[:MAX_PARAGRAPH_TEXT]}"
                        )
                except Exception:
                    continue
            return {
                "total_pages": total,
                "paragraph_count": n,
                "crossing_paragraphs": crossing if crossing else [],
                "summary": (f"共 {len(crossing)} 个段落被分页切断"
                            if crossing else "无段落被分页切断 ✅"),
                "engine": progid,
            }, None

        if mode == "diagnose":
            paras = doc.Paragraphs
            n = paras.Count
            page_break_paras = []
            page_has_text = {}
            for i in range(1, n + 1):
                p = paras(i)
                txt = p.Range.Text.replace("\r", "").replace("\x07", "").strip()
                try:
                    pbreak = bool(p.Range.ParagraphFormat.PageBreakBefore)
                except Exception:
                    pbreak = False
                if pbreak:
                    page_break_paras.append(i)
                try:
                    pg = p.Range.Information(WD_PAGE)
                except Exception:
                    pg = -1
                if txt and pg > 0:
                    page_has_text[pg] = True
            blank_pages = [pg for pg in range(1, total + 1)
                           if not page_has_text.get(pg, False)]
            text_pages = sorted(page_has_text.keys())
            max_text_page = max(text_pages) if text_pages else 0
            trailing_blank = [pg for pg in blank_pages if pg > max_text_page]
            internal_blank = [pg for pg in blank_pages if pg <= max_text_page]
            reasons = []
            if trailing_blank:
                reasons.append(
                    f"尾部空白页 {len(trailing_blank)} 个（页 {trailing_blank[0]}–{trailing_blank[-1]}）")
            if internal_blank:
                reasons.append(f"中间空白页 {len(internal_blank)} 个（页 {internal_blank}）")
            if page_break_paras:
                shown = page_break_paras[:10]
                more = "..." if len(page_break_paras) > 10 else ""
                reasons.append(
                    f"{len(page_break_paras)} 个段落设了 pageBreakBefore（索引 {shown}{more}）")
            if trailing_blank and page_break_paras:
                reasons.append(
                    "常见根因：每节/每首诗都强制 pageBreakBefore，内容短时被推到新页留白；"
                    "或正文末段之后多出一个多余分页")
            if not reasons:
                reasons.append("未发现空白页或多余分页 ✅")
            return {
                "total_pages": total,
                "paragraph_count": n,
                "page_break_before_count": len(page_break_paras),
                "page_break_before_paras": page_break_paras,
                "blank_pages": blank_pages,
                "trailing_blank_pages": trailing_blank,
                "summary": "；".join(reasons),
                "engine": progid,
            }, None

        return None, f"未知模式: {mode}"

    finally:
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:
            pass
        try:
            if app is not None:
                app.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()


def _estimate_with_python_docx(path: str, mode: str, max_paragraphs: int):
    """无 COM 环境的估算兜底。显式标注估算属性，防止 agent 当实测值用。"""
    try:
        from docx import Document
    except ImportError:
        return None, ("python-docx 未安装（pip install python-docx），"
                      "且无 Word/WPS COM 可用，无法测量")

    doc = Document(path)
    paras = doc.paragraphs

    # A4 默认版心估算：21cm 页宽 - 3.18cm×2 边距 ≈ 14.6cm ≈ 414pt
    # 五号(10.5pt)字号下每行 ≈ 39 汉字，行高 1.5 倍 ≈ 15.75pt
    USABLE_H_PT = 697.0  # 29.7cm - 2.54×2cm ≈ 24.6cm ≈ 697pt
    LINE_H_PT = 15.75
    CHARS_PER_LINE = 39

    if mode == "pages":
        return {
            "total_pages": "估算不可用（需 COM）",
            "note": ("⚠️ 无 Word/WPS COM，估算模式不支持页数测量。"
                     "pages/outline/overflow 模式均需真实渲染器。"),
            "engine": "estimate",
        }, None

    if mode == "outline":
        lines = []
        limit = min(len(paras), max_paragraphs) if max_paragraphs > 0 else len(paras)
        for i, p in enumerate(paras[:limit], 1):
            lines.append(f"p{i:>3} 页 ? | {p.text[:MAX_PARAGRAPH_TEXT]}（页码需 COM）")
        return {
            "paragraph_count": len(paras),
            "outline": "\n".join(lines),
            "note": "⚠️ 估算模式无页码信息",
            "engine": "estimate",
        }, None

    if mode == "overflow":
        long_paras = []
        for i, p in enumerate(paras, 1):
            est_lines = max(1, -(-len(p.text) // CHARS_PER_LINE))
            if est_lines * LINE_H_PT > USABLE_H_PT * 0.85:
                long_paras.append(
                    f"p{i:>3} 估算{est_lines}行 | {p.text[:MAX_PARAGRAPH_TEXT]}"
                )
        return {
            "paragraph_count": len(paras),
            "crossing_paragraphs": long_paras,
            "summary": (f"估算 {len(long_paras)} 个超长段落可能跨页（⚠️ 估算值，非实测）"
                        if long_paras else "估算无超长段落（⚠️ 估算值，非实测）"),
            "engine": "estimate",
        }, None

    if mode == "diagnose":
        try:
            from docx.oxml.ns import qn
        except ImportError:
            return None, "python-docx 未安装，无法统计 pageBreakBefore"
        pb_paras = []
        for idx, p in enumerate(doc.paragraphs, 1):
            if p._p.find('.//' + qn('w:pageBreakBefore')) is not None:
                pb_paras.append(idx)
        return {
            "paragraph_count": len(doc.paragraphs),
            "page_break_before_count": len(pb_paras),
            "page_break_before_paras": pb_paras,
            "note": ("⚠️ 估算模式无分页引擎，无法检测空白页；"
                     "仅统计 pageBreakBefore 数量（真实空白页需 Word/WPS COM）"),
            "engine": "estimate",
        }, None

    return None, f"未知模式: {mode}"


def word_measure_handler(path: str, mode: str = "pages",
                         max_paragraphs: int = 100) -> str:
    """
    用真实 Word/WPS 渲染引擎测量 docx 的分页与排版。

    Args:
        path: docx 文件路径
        mode: pages | outline | overflow
        max_paragraphs: outline 模式最多列出的段落数（0=全部）

    Returns:
        文本报告（JSON 风格字段 + outline 明细）
    """
    if not path or not str(path).strip():
        return "错误: path 不能为空"
    abs_path = os.path.abspath(path)
    if not os.path.isfile(abs_path):
        return f"错误: 文件不存在 {abs_path}"
    if not abs_path.lower().endswith(".docx"):
        return f"错误: 仅支持 .docx（旧 .doc 请先转存新格式）: {abs_path}"
    if mode not in ("pages", "outline", "overflow", "diagnose"):
        return f"错误: mode 仅支持 pages/outline/overflow/diagnose，收到 {mode!r}"

    # ① Word COM → ② WPS COM → ③ 估算
    if _com_available():
        for progids in (["Word.Application"], ["KWPS.Application"]):
            result, err = _measure_with_com(abs_path, mode, max_paragraphs, progids)
            if result is not None:
                return _format(result)
            logger.warning(f"{progids[0]} 测量失败: {err}")
        # COM 都失败 → 落到估算
    else:
        logger.info("pywin32 不可用，使用估算模式")

    result, err = _estimate_with_python_docx(abs_path, mode, max_paragraphs)
    if result is None:
        return f"错误: {err}\n提示: Windows 安装 pywin32 后可用真实渲染器测量（pip install pywin32）"
    return _format(result)


def _format(r: dict) -> str:
    lines = [f"测量引擎: {r.get('engine', '?')}"]
    if "total_pages" in r:
        lines.append(f"总页数: {r['total_pages']}")
    if "paragraph_count" in r:
        lines.append(f"段落总数: {r['paragraph_count']}")
    if "usable_width_pt" in r:
        lines.append(f"版心宽度: {r['usable_width_pt']} pt")
        lines.append(f"版心高度: {r['usable_height_pt']} pt")
    if "summary" in r:
        lines.append(f"结论: {r['summary']}")
    if "page_break_before_count" in r:
        lines.append(f"pageBreakBefore 数量: {r['page_break_before_count']}")
        pb = r.get("page_break_before_paras", [])
        if pb:
            lines.append(f"  位置(段落索引): {pb}")
    if "blank_pages" in r:
        lines.append(f"空白页: {r['blank_pages'] if r['blank_pages'] else '无'}")
        tb = r.get("trailing_blank_pages", [])
        if tb:
            lines.append(f"  其中尾部空白页: {tb}")
    if "note" in r:
        lines.append(r["note"])
    if "outline" in r:
        lines.append("")
        lines.append("段落页位:")
        lines.append(r["outline"])
    if r.get("crossing_paragraphs"):
        lines.append("")
        lines.append("跨页/超长段落:")
        lines.extend("  " + c for c in r["crossing_paragraphs"][:30])
        if len(r["crossing_paragraphs"]) > 30:
            lines.append(f"  ...共 {len(r['crossing_paragraphs'])} 个")
    return "\n".join(lines)


register_tool("word_measure", {
    "description": (
        "用真实 Word/WPS 渲染引擎测量 .docx 的分页与排版（只读，不修改文件）。\n"
        "生成排版型 Word 文档时，禁止用字符数估算分页——python-docx 没有分页引擎，"
        "docGrid/snapToGrid/字体度量都会让估算偏差达 3 倍。正确流程：\n"
        "1. mode=pages 先探版心（真实可用宽高）\n"
        "2. 生成文档\n"
        "3. mode=outline 断言验收（如每首诗标题与正文同页）\n"
        "4. mode=overflow 检查段落被分页切断的情况\n"
        "5. mode=diagnose 排版异常一键定位（空白页页码 + pageBreakBefore 数量与位置），"
        "出现空白页/异常分页时优先用它而非手写脚本拆 XML\n"
        "无 Word/WPS 环境时自动降级估算并显式标注。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "docx 文件路径"},
            "mode": {
                "type": "string",
                "enum": ["pages", "outline", "overflow", "diagnose"],
                "description": "pages=总页数+版心尺寸; outline=逐段页位; overflow=跨页段落检测; diagnose=空白页+pageBreakBefore 一键定位",
            },
            "max_paragraphs": {
                "type": "integer",
                "description": "outline 模式最多列出的段落数，0=全部（默认 100）",
            },
        },
        "required": ["path"],
    },
    "handler": word_measure_handler,
    "permission_level": "read",
})
