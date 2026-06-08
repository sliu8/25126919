import angr
import claripy
import logging
from pathlib import Path
from typing import List, Dict, Any

# 减少 angr 的冗长警告
logging.getLogger('angr').setLevel(logging.ERROR)
logging.getLogger('claripy').setLevel(logging.ERROR)

_last_simgr = None
_last_sym_stdin = None

def explore_state(
    binary_path: str,
    find_text: str,
    avoid_texts: List[str],
    max_steps: int = 10,          # 默认步数，可自行调整
    input_len: int = 9
) -> Dict[str, Any]:
    global _last_simgr, _last_sym_stdin
    print(f"[angr] 开始探索: {binary_path}, max_steps={max_steps}")

    # 关键优化：禁止加载外部库 + 用0填充未初始化内存
    proj = angr.Project(binary_path, auto_load_libs=False)
    sym_stdin = claripy.BVS("input", input_len * 8)

    init_state = proj.factory.full_init_state(
        args=[binary_path],
        stdin=sym_stdin,
        add_options={
            angr.options.ZERO_FILL_UNCONSTRAINED_MEMORY,
            angr.options.ZERO_FILL_UNCONSTRAINED_REGISTERS
        }
    )

    # 添加可打印字符约束（0x20-0x7E，排除换行和空字节）
    for byte in sym_stdin.chop(bits=8):
        init_state.solver.add(byte >= 0x20)
        init_state.solver.add(byte <= 0x7E)
        init_state.solver.add(byte != ord('\n'))
        init_state.solver.add(byte != ord('\x00'))

    simgr = proj.factory.simulation_manager(init_state)

    find_bytes = find_text.encode()
    avoid_bytes = [s.encode() for s in avoid_texts]

    def is_found(state):
        return find_bytes in state.posix.dumps(1)

    def is_avoid(state):
        return any(ab in state.posix.dumps(1) for ab in avoid_bytes)

    simgr.explore(find=is_found, avoid=is_avoid, step=max_steps)

    # 获取输出预览
    preview = ""
    if simgr.found:
        preview = simgr.found[0].posix.dumps(1)[:200].decode(errors='replace')
    elif simgr.active:
        preview = simgr.active[0].posix.dumps(1)[:200].decode(errors='replace')

    # 保存 found 状态供后续求解
    if simgr.found:
        _last_simgr = simgr
        _last_sym_stdin = sym_stdin

    result = {
        "found": len(simgr.found) > 0,
        "active": len(simgr.active),
        "avoided": len(simgr.avoid),
        "deadended": len(simgr.deadended),
        "errored": len(simgr.errored),
        "steps_done": max_steps,          # 修复：不再使用 simgr._step
        "stdout_preview": preview,
    }
    print(f"[angr] 探索完成: found={result['found']}, active={result['active']}")
    return result

def solve_from_found() -> Dict[str, Any]:
    global _last_simgr, _last_sym_stdin
    if _last_simgr is None or not _last_simgr.found:
        raise RuntimeError("没有可用的 found 状态，请先执行 explore_state 并确保 found=True")
    state = _last_simgr.found[0]
    concrete = state.solver.eval(_last_sym_stdin, cast_to=bytes)
    return {
        "input_hex": concrete.hex(),
        "input_text": concrete.decode(errors='replace'),
        "stdout": state.posix.dumps(1).decode(errors='replace'),
    }