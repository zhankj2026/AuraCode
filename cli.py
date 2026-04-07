#!/usr/bin/env python3
"""
Claude Code Python MVP - CLI 入口

简单的命令行接口,支持基本的参数解析和 Agent Loop 执行。
"""

import argparse
import os
import sys
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from core.agent_loop import AgentLoop

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,  # 改为 DEBUG 级别,显示所有日志
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    parser = argparse.ArgumentParser(
        description="Claude Code Python MVP - AI 编程助手"
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="用户指令"
    )
    parser.add_argument(
        "--mode",
        choices=["normal", "auto", "plan", "bypass"],
        default="normal",
        help="权限模式 (默认: normal)"
    )
    parser.add_argument(
        "--model",
        default="glm-4-plus",
        help="LLM 模型 (默认: glm-4-plus, 可选: glm-4, glm-4-air, gpt-4o)"
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="API Base URL (默认从环境变量 OPENAI_BASE_URL 读取)"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=20,
        help="最大迭代次数 (默认: 20)"
    )
    
    args = parser.parse_args()
    
    # 检查 API 密钥
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("❌ 错误: 未设置 OPENAI_API_KEY 环境变量")
        print("\n配置方法:")
        print("  智谱 GLM:")
        print("    Windows: $env:OPENAI_API_KEY=\"your-key\"")
        print("    Windows: $env:OPENAI_BASE_URL=\"https://open.bigmodel.cn/api/paas/v4\"")
        print("    Linux/Mac: export OPENAI_API_KEY=\"your-key\"")
        print("    Linux/Mac: export OPENAI_BASE_URL=\"https://open.bigmodel.cn/api/paas/v4\"")
        print("\n  OpenAI:")
        print("    Windows: $env:OPENAI_API_KEY=\"sk-your-key\"")
        print("    Linux/Mac: export OPENAI_API_KEY=\"sk-your-key\"")
        print("\n获取 GLM API Key: https://open.bigmodel.cn/")
        sys.exit(1)
    
    # 构建配置
    config = {
        "api_key": api_key,
        "base_url": args.base_url or os.environ.get("OPENAI_BASE_URL"),
        "model": args.model,
        "max_iterations": args.max_iterations,
        "permission_mode": args.mode
    }
    
    # 显示配置信息
    print(f"🚀 Claude Code Python MVP")
    print(f"   Model: {config['model']}")
    print(f"   Base URL: {config['base_url'] or 'https://api.openai.com/v1'}")
    print(f"   Permission Mode: {config['permission_mode']}")
    print(f"   Max Iterations: {config['max_iterations']}")
    print()
    
    # 初始化 Agent Loop
    try:
        loop = AgentLoop(config)
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        sys.exit(1)
    
    # 获取用户输入
    if args.prompt:
        user_input = " ".join(args.prompt)
    else:
        user_input = input("> ")
    
    if not user_input.strip():
        print("⚠️  请输入指令")
        sys.exit(1)
    
    # 执行
    print("\n" + "="*60)
    try:
        result = loop.run(user_input)
        print("="*60)
        
        if result:
            print(f"\n✅ 任务完成\n")
        else:
            print(f"\n⚠️  未获得响应\n")
    except Exception as e:
        print("="*60)
        print(f"\n❌ 执行失败: {e}")
        print(f"\n可能原因:")
        print(f"  1. 模型名称错误: {config['model']}")
        print(f"  2. API Key 无效或过期")
        print(f"  3. Base URL 配置错误: {config['base_url']}")
        print(f"  4. 网络连接问题")
        print(f"\n建议:")
        print(f"  - 检查 GLM 模型列表: https://open.bigmodel.cn/dev/api")
        print(f"  - 使用 glm-4-plus 或 glm-4-air 试试")
        print(f"  - 确认 OPENAI_BASE_URL 设置为: https://open.bigmodel.cn/api/paas/v4")
        sys.exit(1)


if __name__ == "__main__":
    main()
