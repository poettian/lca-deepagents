# python/m1/Practice/judge_card_helpers_zh.py
"""judge_card_practice.zh.py 的预置代码：测验、ASCII 卡片渲染、人设样式、
"发布"工具，以及 invoke/interrupt/resume 循环。

这里没有任何 TODO。想重新设计卡片样式的话可以读一下 render_card() 的
docstring，否则不需要打开这个文件。
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import questionary
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from deepagents import create_deep_agent

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 追加到 JUDGE_PERSONAS 中每个人设末尾的共用工具调用步骤，这样每个人设
# 字符串只需要定义说话风格，不用重复写流程。
TOOL_SEQUENCE = """
这是一次性的评判：你提问不会得到回复，拒绝或要求更多信息都不是可选项。
全程使用中文。
提到匹配的产品时，必须使用 score_and_match 返回的原样名称（例如 "Fleet"），
即使你记得它有旧名或别名（例如 "Agent Builder"），也绝不能使用。
评语和配文中不要使用破折号（——）连接句子，只用逗号、句号、冒号或分号。
下面这些步骤是严格的依赖链，不能并行：每一步都需要上一步的实际结果
（事实、trait_scores、render_card 的成功结果）才能执行。每一轮只调用其中
一个工具，等拿到结果后再调用下一个；即使你很确定下一次调用的参数是什么，
也绝不能在同一次回复里调用两个。
1. 用你拿到的测验答案列表调用 score_and_match，原样传入。
2. 用 score_and_match 返回的产品名调用 fetch_product_fact。
3. 根据 trait_scores 和刚拿到的事实，用你自己的腔调定一个"开发者类型"标题
   和一句话评语。评语开头直接点出匹配的产品（例如"你的本命产品是 Fleet"，
   或者用海盗腔说"你这小子配得上 Fleet"），然后用一个分句结合你查到的事实
   说明理由；不要把产品名埋在句末的从句里。
4. 调用 render_card，传入你的 builder_type、judge_name、verdict、
   trait_scores 和 product。
5. 渲染成功后，调用 post_card，附上一句配文。和评语不同，配文要用平实、
   口语化、通顺的现代中文，不要用人设的腔调，就像你自己真的要发出去一样。
   它应该读起来像一条真实的完成动态：你刚学完 LangChain Deep Agents 课程
   的模块 1，做完了这个练习，被评为某种 builder_type。明确直白地写出
   score_and_match 匹配到的产品（例如"分配到：Fleet"），再给出一个它为什么
   适合你的具体理由，不要编一句空泛的产品宣传语。例如："刚学完 LangChain
   Deep Agents 课程的模块 1，做了个评判开发习惯的小测验。我被评为务实的
   编排者，分配到 Fleet，自带审批流程的无代码 agent。感觉挺准。"
"""

RESET = "\033[0m"
BOLD = "\033[1m"
DEFAULT_COLOR = "\033[92m"  # 亮绿色（没有专属样式的人设，比如你自己的）

DEFAULT_MASCOT = "\n".join([
    " ___",
    "[o_o]",
    "/|_|\\",
    " | |",
])

# 测验评分用的 3 条固定性格维度。每个特征分数（0-100，由
# judge_card_practice.zh.py 中的 score_and_match 算出）表示你偏向*右侧*
# 标签的程度。
TRAIT_AXES = [("混乱", "有序"), ("谨慎", "大胆"), ("独行", "协作")]

# 8 道固定测验题。每个选项带一个（混乱/有序、谨慎/大胆、独行/协作）增量，
# 累加到每个维度从 50 起步的分数上。
QUIZ_QUESTIONS = [
    {
        "question": "早上 9 点，你有 3 条未读消息，还有一个今天必须交的大任务。",
        "choices": [
            ("立刻把三条都回了，大任务可以等等", (-2, 0, 2)),
            ("关掉通知，先专心做大任务", (2, 0, -2)),
            ("扫一眼，只回最急的那条，然后开干", (0, 1, 0)),
        ],
    },
    {
        "question": "你在别人写的代码里发现一个 bug，它不影响你手上的工作。",
        "choices": [
            ("手头的活先放下，马上修", (-1, 2, 0)),
            ("提个工单，回去继续干自己的事", (1, -1, 1)),
            ("留个评论，让原作者决定", (0, -2, 1)),
        ],
    },
    {
        "question": "项目计划毫无预兆地变了。",
        "choices": [
            ("太刺激了，来点即兴发挥。", (-2, 1, 0)),
            ("默默慌一下，然后从头重做计划。", (2, -1, 0)),
            ("先问问团队改了什么、为什么改，再做反应。", (0, 0, 2)),
        ],
    },
    {
        "question": "你怎么看待上线没有充分测试过的代码？",
        "choices": [
            ("直接上，出问题再往前修。", (-1, 2, 0)),
            ("绝对不行，我得有把握。", (1, -2, 0)),
            ("看是谁在盯这次发布。", (0, 0, 1)),
        ],
    },
    {
        "question": "选一种你理想的工作方式：",
        "choices": [
            ("一个人，戴上耳机，没有会议。", (0, 0, -2)),
            ("结对编程，跟人一起边想边说。", (0, 0, 2)),
            ("全组一起在白板前讨论。", (-1, 1, 2)),
        ],
    },
    {
        "question": "有人请你现在马上 review 他们的 PR。",
        "choices": [
            ("好，放下手上的事现在就看。", (0, -1, 2)),
            ("我先做完手头的任务，再去 review。", (1, 0, 0)),
            ("快速扫一遍，留几条评论，继续干活。", (-1, 0, 1)),
        ],
    },
    {
        "question": "CI 构建刚刚失败了，你的第一反应是？",
        "choices": [
            ("重跑一下，估计是偶发失败。", (-1, 1, 0)),
            ("先把完整日志读一遍，再动手。", (1, -1, 0)),
            ("找最后改过那个文件的人。", (0, 0, 2)),
        ],
    },
    {
        "question": "你怎么看待写文档？",
        "choices": [
            ("边做边写，未来的我会感谢我。", (1, -1, 0)),
            ("我总会写的，大概吧。", (-2, 1, -1)),
            ("只有很快有人要看时才写。", (0, 0, 1)),
        ],
    },
]

# 每个维度的每个倾向对应一款真实的 LangChain 产品，以 TRAIT_AXES 中的标签
# 为键。（完整产品线见 https://docs.langchain.com）由这张表决定你匹配到
# 哪款产品；TODO 6 的 MCP 调用只负责描述这张表已经选出的产品，不参与选择。
PRODUCT_MATCHES = {
    "混乱": "Fleet",
    "有序": "Evaluation",
    "谨慎": "Observability",
    "大胆": "Engine",
    "独行": "Sandboxes",
    "协作": "Deployment",
}


def display_width(text: str) -> int:
    """按终端显示宽度计算字符串长度，中文等全角字符占 2 列。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def pad_right(text: str, width: int) -> str:
    """按显示宽度在右侧补空格。"""
    return text + " " * max(width - display_width(text), 0)


def center_display(text: str, width: int) -> str:
    """按显示宽度居中。"""
    total = max(width - display_width(text), 0)
    left = total // 2
    return " " * left + text + " " * (total - left)


def wrap_display(text: str, width: int) -> list[str]:
    """按显示宽度折行：英文单词整体换行，中文可在任意字之间断开。"""
    tokens = re.findall(r"[^\s\u2e80-\u9fff\u3000-\u303f\uff00-\uffef]+|\s+|.", text)
    lines: list[str] = []
    current = ""
    for tok in tokens:
        if tok.isspace():
            # 空白只作为单词间的分隔，行首不保留
            if current and not current.endswith(" "):
                current += " "
            continue
        if current.strip() and display_width(current) + display_width(tok) > width:
            lines.append(current.rstrip())
            current = ""
        current += tok
    if current.strip():
        lines.append(current.rstrip())
    return lines or [""]


def strip_dashes(text: str) -> str:
    """把模型偶尔仍会写出的破折号替换成逗号。"""
    return re.sub(r"\s*—+\s*", "，", text)


def run_quiz() -> list[tuple[int, int, int]]:
    """用方向键选择的方式依次提出 8 道测验题，按顺序返回每个答案对应的
    （混乱/有序、谨慎/大胆、独行/协作）增量。"""
    answers = []
    for q in QUIZ_QUESTIONS:
        labels = [label for label, _ in q["choices"]]
        picked = questionary.select(q["question"], choices=labels).ask()
        deltas = next(deltas for label, deltas in q["choices"] if label == picked)
        answers.append(deltas)
    return answers


def render_result_card(
    builder_type: str,
    meters: list[tuple[str, str, int]],
    verdict: str,
    judge_name: str,
    mascot: str = DEFAULT_MASCOT,
    color: str = DEFAULT_COLOR,
) -> str:
    """在终端打印一张彩色 ASCII 结果卡片，并返回纯文本（不含 ANSI 颜色码），
    方便调用方同时保存到文件。

    meters：最多 3 个 (left_label, right_label, score_0_to_100) 元组，
    分数表示结果偏向*右侧*标签的程度。

    mascot/color：可选的人设专属样式（见 PERSONA_STYLES）。
    """
    margin = "  "
    width = max(display_width(builder_type) + 4, 24)
    title_top = margin + "┌" + "─" * width + "┐"
    title_mid = margin + "│" + center_display(builder_type.upper(), width) + "│"
    title_bot = margin + "└" + "─" * width + "┘"
    box_width = width + 2

    mascot_lines = mascot.split("\n")
    art_width = max(display_width(line) for line in mascot_lines)
    left_pad = margin + " " * max((box_width - art_width) // 2, 0)
    mascot_block = "\n".join(left_pad + line for line in mascot_lines)

    bar_width = 14
    label_width = max((display_width(left) for left, _, _ in meters[:3]), default=0)
    bar_lines = []
    for left, right, score in meters[:3]:
        score = max(0, min(100, score))
        filled = round(bar_width * score / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        bar_lines.append(f"  {pad_right(left, label_width)} [{bar}] {right}")

    sep_width = max((display_width(line) for line in bar_lines), default=2) - 2
    separator = "  " + "─" * sep_width
    bar_block = []
    for i, line in enumerate(bar_lines):
        bar_block.append(line)
        if i < len(bar_lines) - 1:
            bar_block.append(separator)

    wrapped = wrap_display(strip_dashes(verdict), width=44)
    wrapped[0] = f'"{wrapped[0]}'
    wrapped[-1] = f'{wrapped[-1]}"'
    verdict_lines = [f"  {line}" for line in wrapped]

    plain_lines = [
        "",
        mascot_block,
        "",
        title_top, title_mid, title_bot,
        "",
        *bar_block,
        "",
        *verdict_lines,
        "",
        f"  评委：{judge_name}",
    ]

    highlighted = {title_top, title_mid, title_bot, *bar_lines}
    for line in plain_lines:
        if line == mascot_block or line in highlighted:
            print(f"{color}{BOLD}{line}{RESET}")
        else:
            print(line)

    return "\n".join(plain_lines)


# 可选的人设专属样式，会传给 render_result_card。键是 judge_name（人设
# 对自己的称呼，例如 "奈芙卡"），因为 render_card 收到的是这个名字，而不是
# JUDGE_PERSONAS 字典的键。没有列在这里的人设使用默认外观（默认吉祥物、
# 绿色进度条）。想给自己的人设一个独特主题，可以加一项：
# PERSONA_STYLES["你的人设名字"] = {...}。
PERSONA_STYLES: dict[str, dict] = {
    "硬编码船长": {
        "mascot": "\n".join([
            "                  ______",
            '               .-"      "-.',
            "              /            \\",
            "  _          |              |          _",
            " ( \\         |,  .-.  .-.  ,|         / )",
            '  > "=._     | )(__/  \\__)( |     _.=" <',
            ' (_/"=._"=._ |/     /\\     \\| _.="_.="\\_)',
            '        "=._"(_     ^^     _)"_.="',
            '            "=\\__|IIIIII|__/="',
            '           _.="| \\IIIIII/ |"=._',
            ' _     _.="_.="\\          /"=._"=._     _',
            '( \\_.="_.="     `--------`     "=._"=._/ )',
            ' > _.="                            "=._ <',
            "(_/                                    \\_)",
        ]),
        "color": "\033[95m",  # 亮品红/紫色
    },
    "奈芙卡": {
        "mascot": "\n".join([
            "     .--.",
            "    | = o\\",
            "    \\= =_/",
            "     )= \\____",
            "    ; = _|__-\\",
            "    |= ----.\\",
            "    ('.==|",
            "   / \\=\\=\\",
            "_.'  /=/\\=\\_",
            "    /__) \\__)",
        ]),
        "color": "\033[93m",  # 亮黄色/金色
    },
    "维克丝": {
        "mascot": "\n".join([
            "  ///-\\\\\\",
            "  |-   ^|",
            "  |-   -|",
            "  |  ~ *scoff*",
            "   \\ O /",
            "    | |",
        ]),
        "color": "\033[91m",  # 亮红色
    },
}


PLATFORM = "X"
HANDLE = "@you"


POSTED_BANNER = [
    "                                    ░██                      ░██",
    "                                    ░██                      ░██",
    "░████████   ░███████   ░███████  ░████████  ░███████   ░████████",
    "░██    ░██ ░██    ░██ ░██           ░██    ░██    ░██ ░██    ░██",
    "░██    ░██ ░██    ░██  ░███████     ░██    ░█████████ ░██    ░██",
    "░███   ░██ ░██    ░██        ░██    ░██    ░██        ░██   ░███",
    "░██░█████   ░███████   ░███████      ░████  ░███████   ░█████░██",
    "░██",
    "░██",
]


def render_mock_post(caption: str, *, posted: bool) -> str:
    """打印一张 X 风格的模拟帖子卡片：要么是"草稿"预览（在 HITL 审批提示处、
    你做决定之前显示，内含配文），要么是"已发布"确认（post_card 真正执行
    后显示，用一个大号 posted 横幅代替重复的配文）。同时返回纯文本。"""
    caption = strip_dashes(caption)
    if posted:
        banner_width = max(len(line) for line in POSTED_BANNER)
        width = banner_width + 4
        left_pad = " " * ((width - banner_width) // 2)
        body = ["│" + left_pad + line.ljust(banner_width) + left_pad + "│" for line in POSTED_BANNER]
    else:
        width = 46
        wrapped = wrap_display(caption, width=width - 2)
        body = [
            *(pad_right(f"│ {line}", width + 1) + "│" for line in wrapped),
            "│" + "".ljust(width) + "│",
            "│" + pad_right("  ♡ 0    ↻ 0    ⤴ 分享", width) + "│",
        ]
    lines = [
        "┌" + "─" * width + "┐",
        "│" + pad_right(f" {HANDLE} 发布于 {PLATFORM}", width) + "│",
        "│" + "".ljust(width) + "│",
        *body,
        "└" + "─" * width + "┘",
        "  ● 已发布" if posted else "  ○ 草稿，等待你的审批",
    ]
    text = "\n".join(lines)
    print(text)
    return text


@tool
def render_card(
    builder_type: str,
    judge_name: str,
    verdict: str,
    trait_scores: list[int],
    product: str,
) -> str:
    """渲染并保存最终的结果卡片。只有在 score_and_match 给出了 trait_scores
    和匹配产品，并且你已经定好 builder_type 标题和一句话评语之后，才能调用。"""
    meters = [(left, right, score) for (left, right), score in zip(TRAIT_AXES, trait_scores)]
    style = PERSONA_STYLES.get(judge_name, {})
    card_text = render_result_card(builder_type, meters, verdict, judge_name, **style)
    # 文件名保留中文，只把其他符号替换成下划线
    safe_type = re.sub(r"[^\w]+", "_", builder_type.lower()).strip("_")
    safe_judge = re.sub(r"[^\w]+", "_", judge_name.lower()).strip("_")
    out_path = OUTPUT_DIR / f"{safe_judge}_{safe_type}.txt"
    out_path.write_text(f"{card_text}\n\n  匹配产品：{product}\n", encoding="utf-8")
    return f"卡片已在上方打印，并保存到 {out_path}。匹配的 LangChain 产品：{product}。"


@tool
def post_card(caption: str) -> str:
    """把最终的结果卡片作为模拟帖子发布到 X。不会有任何内容离开这个终端。
    只有在 render_card 生成卡片之后才能调用。"""
    render_mock_post(caption, posted=True)
    print(
        "\n  * 提醒：这只是模拟发布，没有任何内容离开终端。"
        "想真正发出去的话，截图你的卡片，发到 X 或 LinkedIn 并 @LangChain！"
    )
    return f"已发布，配文：{caption!r}"


def _invoke_checked(agent, agent_input, config):
    """执行一次 agent.invoke()，把未完成 TODO 抛出的 NotImplementedError
    转成一条简短易读的提示，而不是一长串 LangGraph/工具调用的报错堆栈。"""
    try:
        return agent.invoke(agent_input, config=config, version="v2")
    except NotImplementedError as e:
        print(f"\n已停止：{e}")
        print("上面的错误来自某次工具调用（不是别处崩溃）：完成对应的 TODO 后再重新运行。")
        sys.exit(1)


def run_judge(
    judge_name: str,
    *,
    system_prompt: str,
    user_prompt: str,
    tools: list,
    model,
    interrupt_on: dict | None = None,
    thread_prefix: str = "m1-practice",
) -> None:
    """为一个评委人设创建 agent，运行评判，并依次处理所有人工审批提示，
    直到结束。"""
    agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        interrupt_on=interrupt_on,
        checkpointer=MemorySaver(),
    )
    config = {"configurable": {"thread_id": f"{thread_prefix}-{judge_name}"}}

    result = _invoke_checked(
        agent, {"messages": [{"role": "user", "content": user_prompt}]}, config
    )

    while result.interrupts:
        pending = result.interrupts[0].value
        decisions = []
        for req in pending["action_requests"]:
            print(f"\n[{judge_name}] {req['name']} 需要审批：")
            if req["name"] == "post_card":
                render_mock_post(req["args"].get("caption", ""), posted=False)
            else:
                for key, value in req["args"].items():
                    if isinstance(value, str):
                        wrapped = wrap_display(value, width=44)
                        indent = " " * (len(key) + 4)
                        print(f"  {key}: {wrapped[0]}")
                        for line in wrapped[1:]:
                            print(f"{indent}{line}")
                    else:
                        print(f"  {key}: {value}")
            # 中英文输入都接受
            while True:
                choice = input("批准、修改还是拒绝？(批准/修改/拒绝)：").strip().lower()
                if choice in ("批准", "approve", "accept", "yes", "y"):
                    decisions.append({"type": "approve"})
                    break
                elif choice in ("修改", "edit", "e"):
                    edited_args = dict(req["args"])
                    edited_args["caption"] = input("新的配文：")
                    decisions.append({"type": "edit", "edited_action": {"name": req["name"], "args": edited_args}})
                    break
                elif choice in ("拒绝", "reject", "r", "no", "n"):
                    decisions.append({"type": "reject", "message": "用户在发布前拒绝了这张卡片。"})
                    break
                else:
                    print("  请输入 批准、修改 或 拒绝。")
        result = _invoke_checked(agent, Command(resume={"decisions": decisions}), config)
