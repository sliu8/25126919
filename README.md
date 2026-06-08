# angr ReAct Agent 报告


# 环境与依赖

 项目     | 版本/说明                              |
| ------ | ---------------------------------- |
| 操作系统   | Windows 11                         |
| 编译器    | gcc (MinGW)                        |
| Python | 3.13                               |
| angr   | ≥ 9.2                              |
| openai | ≥ 1.0                              |
| LLM    | Deepseek（通过 OpenAI 兼容 API 调用） |
# 项目结构文件
angr/                               # 项目根目录
├── crackme.c                       # 目标程序源码（C语言），包含密码验证逻辑
├── crackme                         # Linux 下编译的可执行文件（忽略）
├── crackme.exe                     # Windows 下编译的可执行文件
├── angr_utils.py                   # angr 工具封装：提供 explore_state（探索）和 solve_from_found（求解）
├── react_agent.py                  # ReAct 主循环：LLM 调用、动作解析、工具派发
├── run_experiment.py               # 运行入口：解析命令行参数、设置环境变量、执行 Agent
├── requirement.txt                 # Python 依赖列表（angr, litellm, openai）
├── react_log.txt                   # 运行日志（自动生成，包含完整的 Thought/Action/Observation）
├── .gitignore                      # Git 忽略规则（排除 __pycache__、日志、可执行文件等）
├── README.md                       # 项目说明文档（可选）
└── __pycache__/                    # Python 字节码缓存目录（自动生成，已忽略）

# 交互
=== Round 1 ===
Thought: 首先，我需要使用 probe 工具来探索目标程序，寻找输出包含 "Success!" 的路径。由于没有初始输入，我会从程序入口开始探索，设置 find 为 "Success!"，avoid 为空，depth 先设为 100 步。

Action: probe({"find": "Success!", "avoid": [], "depth": 100})

Observation: found=True, active=4, avoided=0, steps=100
stdout sample: Enter password: Success! Flag is found.


=== Round 2 ===
Thought: probe 找到了目标路径，输出包含 "Success!"。现在我可以使用 extract 工具来求解具体的输入字符串。

Action: extract()

Observation: 求解成功！
input (hex): 415a63453f3f3f3f3f
input (text): 'AZcE?????'
program output: 'Enter password: Success! Flag is found.\n'

# 思考题
在本实验中，LLM主要承担**高层决策与任务编排**的角色。它并不直接执行符号执行，而是作为智能体的“大脑”，根据angr工具返回的观察（如探索统计、输出样本）进行推理，自主决定调用`probe`或`extract`工具以及设置参数（如探索深度、避免字符串）。通过ReAct范式的“Thought→Action→Observation”循环，LLM将自然语言理解与符号执行有机结合，实现了对逆向分析任务的智能引导。

LLM借助语义与常识缓解纯符号执行的搜索空间困难，主要体现在**语义剪枝与动态策略调整**。它能理解程序输出中的自然语言信息（如`"Wrong password!"`或`"trapped"`），从而将相关字符串作为避免条件传递给angr，主动剪除无意义的路径分支，避免状态爆炸。同时，LLM可根据中间观察（如活跃状态数、输出预览）自适应调整探索深度或放宽约束，使符号执行能够聚焦于可能成功的目标区域，而非盲目遍历所有路径。

