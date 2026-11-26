# python/m1/m1.5_homework.py
"""M1.5 作业：打造你自己的自定义工具。

思路
实验里接入了一个自定义工具（read_sql），面向一个固定主题（Chinook
音乐数据库）。这份作业要你对一个你自己挑的主题做同样的事：选一个你真正
了解或感兴趣的东西（一款游戏、一项运动、一部剧、你最爱乐队的唱片目录、
本地冷知识，什么都行）。这里没有唯一正确的主题或人设，这正是重点所在。
两个同学做同一份作业，最后可能会做出完全不同的工具和 agent。

你需要填写的部分
  TODO 1：用 @tool 装饰器写一个你自己的自定义工具。随便挑个主题，存一份
    关于它的小型查询数据（用 dict 就行，不需要 API），再根据模型传入的
    参数返回其中一条。
  TODO 2：写一段系统提示词，给 agent 一个你自选的人设，并让它在回答前
    先调用你的工具。

运行
  cd python
  uv run ./m1/m1.5_homework.py
"""

import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

from langchain_core.tools import tool

from deepagents import create_deep_agent
from models import model


# ════════════════════════════════════════════════════════════════════════
# TODO 1：定义你自己的自定义工具。
#
# 要求：
#   - 保留 @tool 装饰器。
#   - 给它写一个像样的 docstring：用一句话说明，模型会读它来决定
#     什么时候调用这个工具。
#   - 至少接收一个参数，并返回一个字符串。
#   - 查询数据直接放在这个文件里就行（dict、list，或任何适合你主题的
#     结构）。不需要外部 API 或密钥。
#
# 示例结构（删掉它，写你自己的）：
#   @tool
#   def lookup_something(query: str) -> str:
#       """用一句话描述它返回什么、什么时候该调用它。"""
#       ...
# ════════════════════════════════════════════════════════════════════════

@tool
def your_custom_tool(query: str) -> str:
    """TODO 1：把这个 docstring 和函数体换成你自己的工具。"""
    raise NotImplementedError("TODO 1：见上方的注释块")


# ════════════════════════════════════════════════════════════════════════
# TODO 2：为你的 agent 写一段系统提示词。
#
# 给它一个人设（名字、语气、性格，想要什么都行），并让它在回答前
# 先调用 your_custom_tool（想改名也可以），就像实验里的 SYSTEM_PROMPT
# 把 agent 指向 read_sql 那样。
# ════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """TODO 2：把这里换成你自己的系统提示词。"""

# 防止在占位内容未填写时运行；填好的参考答案不需要这段检查，
# 因为里面已经没有占位文字了。
if "TODO 1" in your_custom_tool.description:
    raise NotImplementedError("TODO 1：见上方的注释块")
if "TODO 2" in SYSTEM_PROMPT:
    raise NotImplementedError("TODO 2：见上方的注释块")

agent = create_deep_agent(
    model=model,
    name="Homework_Agent",
    tools=[your_custom_tool],
    system_prompt=SYSTEM_PROMPT,
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "向你的 agent 提一个需要用到你的工具的问题。"}]}
)

print(result["messages"][-1].text)
