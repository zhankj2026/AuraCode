#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 OpenAI 客户端初始化
"""
import os
import sys
import time

print("DEBUG: Starting test...", flush=True)

# 测试 1: 环境变量
print("\n=== Test 1: Environment Variables ===", flush=True)
api_key = os.environ.get("OPENAI_API_KEY")
base_url = os.environ.get("OPENAI_BASE_URL")
print(f"API Key: {'SET' if api_key else 'NOT SET'}", flush=True)
print(f"Base URL: {base_url or 'NOT SET'}", flush=True)

# 测试 2: 导入 OpenAI
print("\n=== Test 2: Import OpenAI ===", flush=True)
start = time.time()
try:
    from openai import OpenAI
    print(f"✅ OpenAI imported in {time.time() - start:.2f}s", flush=True)
except Exception as e:
    print(f"❌ Import failed: {e}", flush=True)
    sys.exit(1)

# 测试 3: 创建客户端
print("\n=== Test 3: Create Client ===", flush=True)
if not api_key:
    print("❌ API Key not set", flush=True)
    sys.exit(1)

config_base_url = "https://open.bigmodel.cn/api/paas/v4/"
base_url = base_url or config_base_url
print(f"Using base_url: {base_url}", flush=True)
print(f"Using timeout: 300s", flush=True)

start = time.time()
try:
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=300.0,
        max_retries=0,
    )
    print(f"✅ Client created in {time.time() - start:.2f}s", flush=True)
except Exception as e:
    print(f"❌ Client creation failed: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 4: 简单 API 调用（列出模型）
print("\n=== Test 4: Test API Connection ===", flush=True)
start = time.time()
try:
    # 尝试列出模型（超时 10 秒）
    import httpx
    with httpx.Client(timeout=10.0) as http_client:
        response = http_client.get(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        if response.status_code == 200:
            print(f"✅ API connection OK in {time.time() - start:.2f}s", flush=True)
        else:
            print(f"⚠️ API returned {response.status_code}", flush=True)
except Exception as e:
    print(f"⚠️ API test failed: {e}", flush=True)

print("\n✅ All tests passed!", flush=True)
