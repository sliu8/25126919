#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from react_agent import run_react_loop

def main():
    if len(sys.argv) < 2:
        print("用法: python run_experiment.py <crackme二进制路径> [--model model_name] [--api-base URL]")
        sys.exit(1)

    binary = sys.argv[1]
    if not Path(binary).exists():
        print(f"错误: 二进制文件 {binary} 不存在")
        sys.exit(1)

    model = "deepseek/deepseek-chat"   # 默认改为 DeepSeek 模型
    api_base = None

    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        if idx + 1 < len(sys.argv):
            model = sys.argv[idx+1]
    if "--api-base" in sys.argv:
        idx = sys.argv.index("--api-base")
        if idx + 1 < len(sys.argv):
            api_base = sys.argv[idx+1]

    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("错误: 未设置 API 密钥。请设置环境变量 DEEPSEEK_API_KEY 或 OPENAI_API_KEY")
        sys.exit(1)

    if api_base is None and "deepseek" in model.lower():
        api_base = "https://api.deepseek.com/v1"

    print(f"[*] 目标: {binary}")
    print(f"[*] 使用模型: {model}")
    print(f"[*] API Base: {api_base}")
    print("[*] 开始 ReAct 循环...\n")

    history = run_react_loop(
        binary_path=binary,
        max_rounds=6,
        model=model,
        api_key=api_key,
        api_base=api_base,
    )

    log_file = "react_log.txt"
    with open(log_file, "w", encoding="utf-8") as f:
        for line in history:
            f.write(line + "\n\n")
    print(f"\n[+] 对话日志已保存到 {log_file}")

if __name__ == "__main__":
    main()