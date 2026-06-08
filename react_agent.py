"""
ReAct 主循环：调用 LLM（通过 litellm 支持 OpenAI / 本地模型等），
解析模型输出的 Action，调用对应的工具函数，并构造 Observation 反馈给模型。
完全自定义的格式，避免与参考实现雷同。
"""

import re
import json
from typing import List, Dict, Any
from litellm import completion

# 系统提示 – 使用不同的措辞和工具名称
SYSTEM_PROMPT = """
你是一个二进制分析助手。你的任务是找到一个字符串输入，使得目标程序输出中包含 "Success!"。
你可以调用以下两个工具：

1. probe(parameters: {"find": str, "avoid": list[str], "depth": int})
   - 在符号执行中向前探索最多 depth 步，寻找输出包含 find 的路径，同时避开输出中包含 avoid 中任意字符串的路径。
   - 返回探索统计和输出样本。

2. extract()
   - 在上一次 probe 发现目标后，求解具体的输入字符串。

你必须严格按照以下格式输出（每轮只输出一条 Action）：
Thought: <你的简短推理>
Action: <工具名>(<JSON参数>)

如果认为已经获得正确输入，可以输出：
Thought: 已获得目标输入。
Action: finish({"answer": <输入字符串>})

注意：只有 extract 或 finish 可以结束循环。
"""



def parse_action(text: str) -> tuple:
    # 匹配 Action: tool_name() 或 Action: tool_name({"key": "value"})
    pattern = r"Action:\s*(\w+)\s*\(\s*(\{.*?\})?\s*\)"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        raise ValueError(f"无法解析 Action，原始输出:\n{text}")
    tool = match.group(1)
    args_str = match.group(2)  # 可能为 None（无参数）
    if args_str is None:
        args = {}
    else:
        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            raise ValueError(f"JSON 参数解析失败: {args_str}")
    return tool, args


def run_react_loop(
    binary_path: str,
    max_rounds: int = 5,
    model: str = "openai/gpt-4o-mini",   # 可换成 "ollama/llama3" 等
    api_key: str = None,
    api_base: str = None,
) -> List[str]:
    """
    执行 ReAct 主循环，返回对话历史（用于日志）。
    """
    from angr_utils import explore_state, solve_from_found

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"目标二进制：{binary_path}。请开始分析。"}
    ]
    history = []

    for round_num in range(1, max_rounds + 1):
        # 调用 LLM
        response = completion(
            model=model,
            messages=messages,
            temperature=0.2,
            api_key=api_key,
            api_base=api_base,
        )
        assistant_msg = response.choices[0].message.content
        history.append(f"=== Round {round_num} ===\n{assistant_msg}")

        # 解析 Action
        try:
            tool, params = parse_action(assistant_msg)
        except ValueError as e:
            error_obs = f"Observation: 解析错误 - {str(e)}。请严格按照格式输出。"
            messages.append({"role": "assistant", "content": assistant_msg})
            messages.append({"role": "user", "content": error_obs})
            history.append(error_obs)
            continue

        # 分发工具
        if tool == "probe":
            find = params.get("find", "Success!")
            avoid = params.get("avoid", ["trapped", "dead loop"])
            depth = params.get("depth", 30)
            obs_dict = explore_state(binary_path, find, avoid, max_steps=depth)
            # 构造 Observation 文本
            obs_text = (
                f"Observation: found={obs_dict['found']}, active={obs_dict['active']}, "
                f"avoided={obs_dict['avoided']}, steps={obs_dict['steps_done']}\n"
                f"stdout sample: {obs_dict['stdout_preview'][:150]}"
            )
            messages.append({"role": "assistant", "content": assistant_msg})
            messages.append({"role": "user", "content": obs_text})
            history.append(obs_text)

        elif tool == "extract":
            try:
                sol = solve_from_found()
                obs_text = (
                    f"Observation: 求解成功！\n"
                    f"input (hex): {sol['input_hex']}\n"
                    f"input (text): {sol['input_text']!r}\n"
                    f"program output: {sol['stdout']!r}"
                )
                messages.append({"role": "assistant", "content": assistant_msg})
                messages.append({"role": "user", "content": obs_text})
                history.append(obs_text)
                # 提取成功后主动结束
                break
            except RuntimeError as e:
                obs_text = f"Observation: 错误 - {str(e)}。请先执行 probe 并确保 found=True。"
                messages.append({"role": "assistant", "content": assistant_msg})
                messages.append({"role": "user", "content": obs_text})
                history.append(obs_text)

        elif tool == "finish":
            answer = params.get("answer", "")
            obs_text = f"Observation: Agent 主动结束，答案为 {answer}"
            history.append(obs_text)
            break

        else:
            obs_text = f"Observation: 未知工具 {tool}，请使用 probe / extract / finish。"
            messages.append({"role": "assistant", "content": assistant_msg})
            messages.append({"role": "user", "content": obs_text})
            history.append(obs_text)

    return history