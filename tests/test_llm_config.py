# -*- coding: utf-8 -*-
"""LLM 配置读写单测（bridge/server.py 的 _read_llm_config / _write_llm_config /
_live_llm_value / _live_default_model）。

这些函数让「前端改 LLM 配置」真正持久化到 config.yaml 并热更新，
且新建会话会从 config.yaml 回退读取（而非只靠环境变量）。

测试不触碰真实 config.yaml：用临时文件加载进全局 config_manager。
"""
import os
import sys
import tempfile
import textwrap

import pytest
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _setup(temp_dir: str, yaml_text: str):
    from config.manager import config_manager
    path = os.path.join(temp_dir, "config.yaml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(yaml_text)
    config_manager.load(path)
    return path


class _FakeServerConfig:
    default_model = "glm-4.7-flash"


@pytest.fixture
def srv(monkeypatch):
    from bridge import server as _srv
    with tempfile.TemporaryDirectory() as td:
        _setup(td, textwrap.dedent("""
        llm:
          provider: openai
          model: glm-4.7-flash
          base_url: https://open.bigmodel.cn/api/coding/paas/v4
          api_key: sk-secret-abc123
        """))
        _srv._server_config = _FakeServerConfig()
        yield _srv, td


def test_read_hides_api_key_plaintext(srv):
    _srv, _ = srv
    info = _srv._read_llm_config()
    assert info["provider"] == "openai"
    assert info["model"] == "glm-4.7-flash"
    assert info["base_url"] == "https://open.bigmodel.cn/api/coding/paas/v4"
    assert info["has_api_key"] is True
    # 明文密钥绝不能出现在响应里
    assert "sk-secret-abc123" not in str(info)


def test_write_persists_and_hot_reloads(srv):
    _srv, td = srv
    _srv._write_llm_config({"model": "new-model", "base_url": "https://x.test/v1"})
    # 落盘
    path = os.path.join(td, "config.yaml")
    with open(path, encoding="utf-8") as f:
        saved = yaml.safe_load(f)
    assert saved["llm"]["model"] == "new-model"
    assert saved["llm"]["base_url"] == "https://x.test/v1"
    # 内存热更新（新会话默认模型）
    assert _srv._server_config.default_model == "new-model"
    # 读回最新
    assert _srv._read_llm_config()["model"] == "new-model"


def test_write_skips_none_and_clears_empty_key(srv):
    _srv, td = srv
    # None 字段跳过；api_key 空串表示清空
    _srv._write_llm_config({"model": None, "api_key": ""})
    path = os.path.join(td, "config.yaml")
    with open(path, encoding="utf-8") as f:
        saved = yaml.safe_load(f)
    # model 未被 None 覆盖
    assert saved["llm"]["model"] == "glm-4.7-flash"
    # api_key 被清空
    assert saved["llm"].get("api_key", "") == ""


def test_live_fallback_reads_config_yaml(srv):
    _srv, _ = srv
    # _live_llm_value 从 config.yaml 读，建会话回退用
    assert _srv._live_llm_value("base_url") == "https://open.bigmodel.cn/api/coding/paas/v4"
    assert _srv._live_llm_value("model") == "glm-4.7-flash"
    # 缺失字段回退 None
    assert _srv._live_llm_value("not_exist") is None
    # 默认模型回退链：config.yaml -> _server_config.default_model
    assert _srv._live_default_model() == "glm-4.7-flash"
