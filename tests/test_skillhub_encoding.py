# -*- coding: utf-8 -*-
"""SkillHub CLI 子进程编码回归测试。

背景（真机 bug，2026-10-20）：
  Windows 下 Python 子进程 stdout 为管道时默认用本地代码页（GBK）输出。
  skillhub CLI print 含 emoji（U+1F469）的 JSON 直接 UnicodeEncodeError
  （搜索报错）；输出中文则被 bridge 按 utf-8 解码成乱码（◆◆◆）。
  两个症状同一根因：bridge/server.py:_run_skillhub 未强制子进程 UTF-8。

修复：
  1) 子进程 env 注入 PYTHONIOENCODING=utf-8 + PYTHONUTF8=1（治本）；
  2) 父进程捕获原始字节，utf-8 -> gbk -> replace 依次解码（防御，
     兜住不认这两个环境变量的 exe）。

本测试镜像 _run_skillhub 的调用方式（剥离代理 env + 编码注入 + 字节解码），
三场景：修复前复现崩溃 / 修复后干净 / gbk 回退兜底。
"""
import json
import os
import subprocess
import sys
import tempfile

PY = sys.executable

CHILD_UTF8 = (
    "# -*- coding: utf-8 -*-\n"
    "import json\n"
    'payload = {"results": [{"name": "PDF \\U0001f469\\u200d\\u2695\\ufe0f \\u63d0\\u53d6\\u5668",\n'
    '                        "description": "\\u4ece PDF \\u4e2d\\u63d0\\u53d6\\u6587\\u672c \\U0001f4c4"}]}\n'
    "print(json.dumps(payload, ensure_ascii=False))\n"
)

CHILD_GBK = (
    "# -*- coding: utf-8 -*-\n"
    "import json, sys\n"
    'payload = {"results": [{"name": "PDF \\u63d0\\u53d6\\u5668",\n'
    '                        "description": "\\u4ece PDF \\u4e2d\\u63d0\\u53d6\\u6587\\u672c"}]}\n'
    "# 模拟不认 PYTHONIOENCODING 的旧 exe：坚持用本地代码页 GBK 写管道\n"
    'sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("gbk"))\n'
)

EXPECT_EMOJI_NAME = "PDF \U0001f469\u200d\u2695\ufe0f 提取器"


def decode_pipe(data: bytes) -> str:
    """与 bridge/server.py:_decode_pipe 保持一致。"""
    for enc in ("utf-8", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def strip_encode_env(env: dict) -> dict:
    return {k: v for k, v in env.items()
            if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}


def run_child(script: str, env: dict, tmpdir: str) -> subprocess.CompletedProcess:
    path = os.path.join(tmpdir, "_child.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(script)
    try:
        return subprocess.run([PY, path], capture_output=True,
                              timeout=30, env=env)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def test_gbk_pipe_crashes_on_emoji_without_utf8_env():
    """场景 A（修复前提）：无编码环境变量时 emoji 应崩——保证 bug 真实存在。"""
    with tempfile.TemporaryDirectory() as td:
        r = run_child(CHILD_UTF8, strip_encode_env(dict(os.environ)), td)
    crashed = (r.returncode != 0
               or b"UnicodeEncodeError" in r.stderr)
    assert crashed, (
        "子进程未复现 GBK 崩溃（本机代码页可能不是 GBK），"
        f"rc={r.returncode} stderr={r.stderr[:200]!r}"
    )


def test_utf8_env_fix():
    """场景 B（治本）：注入 PYTHONIOENCODING/PYTHONUTF8 后 emoji+中文干净往返。"""
    env = strip_encode_env(dict(os.environ))
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    with tempfile.TemporaryDirectory() as td:
        r = run_child(CHILD_UTF8, env, td)
    assert r.returncode == 0, f"子进程失败: {r.stderr[:300]!r}"
    data = json.loads(decode_pipe(r.stdout))
    item = data["results"][0]
    assert item["name"] == EXPECT_EMOJI_NAME, f"名称不一致: {item['name']!r}"
    assert "\U0001f4c4" in item["description"], "描述中的 emoji 丢失"


def test_gbk_fallback_defense():
    """场景 C（防御）：子进程坚持 GBK 输出时，父进程 gbk 回退能正确还原。"""
    env = strip_encode_env(dict(os.environ))
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    with tempfile.TemporaryDirectory() as td:
        r = run_child(CHILD_GBK, env, td)
    assert r.returncode == 0, f"子进程失败: {r.stderr[:300]!r}"
    data = json.loads(decode_pipe(r.stdout))
    assert data["results"][0]["name"] == "PDF 提取器", \
        f"gbk 回退还原失败: {data['results'][0]['name']!r}"
