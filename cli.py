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
    level=logging.INFO,
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
        help="LLM 模型 (默认: glm-4-plus, 可选: glm-4, gpt-4o, gpt-3.5-turbo)"
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
        print("请运行: export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)
    
    # 构建配置
    config = {
        "api_key": api_key,
        "model": args.model,
        "max_iterations": args.max_iterations,
        "permission_mode": args.mode
    }
    
    print(f"🚀 Claude Code Python MVP")
    print(f"   Model: {config['model']}")
    print(f"   Permission Mode: {config['permission_mode']}")
    print(f"   Max Iterations: {config['max_iterations']}")
    print()
    
    # 初始化 Agent Loop
    loop = AgentLoop(config)
    
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
    result = loop.run(user_input)
    print("="*60)
    
    if result:
        print(f"\n✅ 任务完成\n")
    else:
        print(f"\n⚠️  未获得响应\n")


if __name__ == "__main__":
    main()
