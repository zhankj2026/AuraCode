---
name: word-doc-generation
description: 生成排版型 Word 文档（诗集/报告/手册等有版式要求的 docx）的渲染器反馈闭环方法论
trigger: 当任务要求生成 Word/docx 文档且涉及排版、分页、每页内容约束、版式验收时激活
when_to_use: 生成 docx 时对版式有任何要求（每节一页、不溢出版心、避免段落跨页断裂等），或生成后需要验证排版是否达标
ecosystem: office
category: word-layout
keywords: word, docx, 文档, 排版, 分页, 页数, 版心, 页边距, python-docx, 文档网格, word_measure, 写入word, word文档, 生成word, word报告, 每页, 一页, 诗集, 页面布局
dependencies: word_measure, write_file, run_command
---

# Word 文档生成：渲染器反馈闭环

## 铁律：python-docx 没有分页引擎

分页发生在**渲染器**（Word/WPS）里，不在 python-docx 里。任何用字符数/行数估算页数的方案都必然偏差——实测案例：

| 坑 | 后果 |
|---|---|
| 中文 Word 默认 `docGrid` + `snapToGrid` 文档网格 | 实际行高比朴素估算大 **约 3 倍** |
| 汉字宽度按"每行 = 版心宽/字号"计算 | 行数高估近一倍（一个汉字占约 1 个字号单位，不是 0.5） |
| `doc.add_page_break()` | 会**额外插入一个空段落**；页面刚好排满时该空段落被挤到下页 → 产生空白页 |
| 先估算后生成再实测 | 估算与实测永远对不上 → 无限盲调循环（真实案例：78 轮请求 / 22 分钟） |

## 正确流程（四步闭环）

### 第 1 步：探版心（先测量，后生成）

```
word_measure(path=任意已有的同版式 docx, mode="pages")
```

拿到**真实**的 `usable_width_pt` / `usable_height_pt`。没有现成文件就先写一个只含 sectPr 的空 docx 再测。版心数据决定每页能放多少内容——一切排版决策从这里出发。

> **版心只探一次**：本步拿到的数值立即写进生成脚本注释（如 `# 版心 425.2×697.9pt，每页约 25 行`），后续所有轮次复用，**禁止每轮重探**——每轮重跑 `word_measure pages` 都是纯浪费（真实事故：同一常数被重探 6+ 次）。

如果目标环境禁用文档网格，在生成时就显式设置（一劳永逸消除 3 倍行高偏差）：

```python
from docx.oxml.ns import qn
sectPr = doc.sections[0]._sectPr
docGrid = sectPr.find(qn('w:docGrid'))
if docGrid is not None:
    docGrid.set(qn('w:type'), 'noGrid')   # 关闭文档网格
    # 段落级兜底: p.paragraph_format 的 snap_to_grid = False（python-docx 需 XML 设置）
```

### 第 2 步：生成（分页用 page_break_before）

**永远不要用 `doc.add_page_break()`**。用段落属性分页，不产生空段落：

```python
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

def page_break_before(paragraph):
    pPr = paragraph._p.get_or_add_pPr()
    el = OxmlElement('w:pageBreakBefore')
    pPr.append(el)

# 每节开头: 标题段设置 page_break_before，而不是在节尾 add_page_break
title = doc.add_heading('第三节 标题', level=1)
page_break_before(title)
```

### 第 3 步：实测验收（断言，禁止肉眼/估算判定）

```
word_measure(path="目标.docx", mode="outline")
```

拿到每段所在页码后，把版式需求转成**可程序化判定的断言**。

- 标题段页码 == 该节最后一段页码（节未跨页）
- 或明确允许跨页时：下一节标题页码 == 上一节末段页码 + 1

```
word_measure(path="目标.docx", mode="overflow")
```

检查哪些段落被分页从中间切断（如长赏析被切成两半且无"（续）"标记 → 违规）。

若 `outline`/`overflow` 暴露出**空白页或异常分页**，不要手写脚本拆 XML，直接改用诊断模式一次定位根因：

```
word_measure(path="目标.docx", mode="diagnose")
```

它会一次性回报「空白页页码（尾部/中间）+ pageBreakBefore 数量与位置 + 常见根因」，据此改脚本即可（详见下一节）。

### 第 4 步：失败回改（只改数据，不推翻框架）

实测不达标时，按优先级调整（每次只动一个变量，重新实测）：

1. **内容预算**：版心高度 ÷ 实测行高 = 每页实际容量；超预算的节启用"原文一页 + 注释赏析接次页"的拆分布局
2. **字号/行距档位**：预定义 2-3 档（宽松/标准/紧凑），整档切换，不要微调
3. **节拆分**：单节确实超一页 → 显式拆两节，次节加"（续）"标题

> **回改必须增量编辑**：改 `gen_xxx.py` 时用 `replace_in_file` 只动对应参数/片段，
> **不要整篇 `write_file` 重写**（实测事故里同一脚本被全量重写 6 次，每次数千 token，
> 纯属浪费）。典型例子——把"每首诗强制分页"改成"仅章节标题分页"以消除短诗留白，
> 只改 `page_break_before` 的调用条件这一处即可：
> ```python
> # 改前（每首诗都分页 → 短诗被推到新页留白，diagnose 会报尾部空白页）
> for poem in poems:
>     page_break_before(title_p)
> # 改后（仅首篇与章节标题分页，内容接排）
> for i, poem in enumerate(poems):
>     if i == 0 or poem.get("is_section_title"):
>         page_break_before(title_p)
> ```

## 收敛与停止条件（必须遵守）

渲染器反馈闭环的前提是「能停下来」。缺少停止条件会退化成无限回改循环——真实事故里一次杜甫诗集生成跑了 **20 轮 + 用户手动中断**，其中大半是重复探版心、整篇重写脚本、以及手写脚本拆 XML 追一个排版 bug。硬性约束：

1. **版心只探一次**：见第 1 步，数值写进脚本注释，后续轮次复用，禁止每轮重探。
2. **回改最多 2 轮**：第 3 步实测不达标 → 第 4 步回改 → 重新实测；仍不达标再回改 **1 次**（共 2 次）。第 3 次若仍不达标，**直接交付并附「残余问题说明」**，停止盲调。
3. **通过即停**：`outline`/`overflow` 断言全部通过、`word_measure` 不再报错，立即交付，**不再额外生成/测量**。
4. **异常分页用 `diagnose` 一键定位**：出现空白页/异常分页时，调用 `word_measure(mode="diagnose")` 一次拿到「空白页页码 + pageBreakBefore 数量与位置 + 根因」，据此改脚本；**严禁在对话里手写 `check_pages.py` 拆 XML**（那会徒增 5+ 轮）。
5. **增量编辑**：回改用 `replace_in_file` 改生成脚本里的对应参数/片段（字号档、行距、分页条件），**不要整篇 `gen_xxx.py` 全量重写**——每次全量重写都是数千 token 的浪费。

> 经验法则：从「写脚本生成」到「交付」整条链路**目标 6 轮以内**。超过 8 轮仍未收敛，先停下来审视根因（模型能力 / 版式目标是否自相矛盾），而不是继续迭代。

## 上下文管理（防压缩失忆）

排版调试会产生大量测量输出。为防止上下文压缩后丢失关键结论：

- 把版心数据、每节实测页码等**关键数字写进生成脚本的注释或一个 notes.md**，别只留在对话里
- 测量脚本调用 `word_measure` 工具而不是临时写 `.py` 再跑——工具输出经过 ToolEnhancer 管道，不会被当成待清理的临时文件

## 验收清单

- [ ] `word_measure pages`：总页数符合预期
- [ ] `word_measure outline`：所有断言通过（按规划跨页）
- [ ] `word_measure overflow`：无意外段落断裂（或断裂处已加"（续）"）
- [ ] 文档无连续空白页（空段落挤页的典型残留）
- [ ] 交付文件名与用户要求一致
- [ ] 版心只探了 1 次（数值已写进脚本注释，无重复 `word_measure pages`）
- [ ] 回改轮次 ≤ 2（超过即附残余问题说明交付，未无限盲调）
- [ ] 遇空白页/异常分页用 `diagnose` 一次定位，未手写脚本拆 XML

## PPT 说明

PPTX 不适用本方法论（无分页概念，画布绝对定位）。生成 PPTX 按幻灯片内容预算（参考 officedoc2html 的绝对定位模型）直接生成即可。
