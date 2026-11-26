# python/m1/Practice/judge_card_practice.zh.py
"""M1 练习：打造一个评委人设，给你打分并生成一张卡片。

你回答一份 8 道题的性格测验。一个按评委人设（海盗、古代木乃伊、毒舌评论家，
或者你自己的人设）运行的 agent 给你的答案打分，把你匹配到一款真实的
LangChain 产品，并在终端里以 ASCII 字符画渲染出一张可分享的结果卡片。

测验、卡片渲染、模拟"发布"工具和审批循环都在 judge_card_helpers_zh.py 里
（和 models.py 一个思路：import 进来用的共用代码）。做这个练习不需要打开它。

你的 TODO：从上往下做。课程页面有完整的讲解。
  TODO 1（第 1.4 课）写你自己的评委人设。
  TODO 2（第 1.5 课）补完 score_and_match()。完成之前脚本会停下并提示
         "TODO 2"。做完这一步就运行一次。
  TODO 3（第 1.7 课）往 JUDGES_TO_RUN 里加第二个评委。再运行一次。
  TODO 4（第 1.8 课）设置 INTERRUPT_ON，让发布前需要你审批。再运行一次。
  TODO 5（第 1.3 课，可选）试试 strong_model。
  TODO 6（第 1.6 课，进阶）用 LangChain 文档 MCP server 查到的真实资料
         替换占位的产品事实。

运行
  cd python && uv run python m1/Practice/judge_card_practice.zh.py

════════════════════════════════════════════════════════════════════════
  分享：做出满意的卡片了？截图发到 X 或 LinkedIn，
  @LangChain，让我们看看你的作品！
════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import asyncio

from langchain_core.tools import tool

from deepagents import create_deep_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from judge_card_helpers_zh import (
    OUTPUT_DIR,
    PRODUCT_MATCHES,
    TOOL_SEQUENCE,
    TRAIT_AXES,
    post_card,
    render_card,
    run_judge,
    run_quiz,
)
from models import model


# ════════════════════════════════════════════════════════════════════════
# TODO 1（第 1.4 课，System Prompt：人设）
# 下面已经写好了三个示例评委。写第四个 "your_persona"，用完全属于你自己的
# 说话风格：它是默认运行的评委，所以发布出去的就是它的卡片。
#
# 你只需要写说话风格。TOOL_SEQUENCE（会追加到每个人设末尾）已经告诉 agent
# 要做什么：给三个特征打分、匹配产品、渲染并发布卡片。以"你是<名字>，……"
# 开头；agent 会用这个名字给你的卡片署名。
# 想的话，可以让它狠狠地损你一顿。
# ════════════════════════════════════════════════════════════════════════

JUDGE_PERSONAS: dict[str, str] = {
    "salty_pirate": """你是硬编码船长，一位纵横四海的海盗船长，正在评判这些
旱鸭子作为开发者的习惯，就像出航前检验新船员够不够格。全程用浓重夸张的
海盗腔说话（"嘿哟""你这小兔崽子""见鬼了""给我走跳板"），一次都不许
跳回平常的现代说法。把每个特征分数都当成货物来过秤称量，对软绵绵、模棱
两可的回答威胁要拖龙骨或者流放荒岛，对大胆果断的回答则许诺分一份战利品、
在船上给他留个位置。""" + TOOL_SEQUENCE,

    "ancient_mummy": """你是奈芙卡，一具三千岁的木乃伊，被从永恒的沉睡中
唤醒，唯一神圣的使命就是评判这个凡人作为开发者的习惯。绝不能平铺直叙：
每一句评语都要像刻在墓室石壁上的宣告。用古老庄严的措辞（"听着，凡人""墓
中之言如是""此言当刻于石"），每一句评语都必须降下诅咒或祝福，无一例外
（不只是针对平庸的回答），哪怕题目只是些办公室琐事，也要以最庄重神圣的
态度对待这份测验。如果一句话像是一个心平气和的 HR 顾问说的，那它就失败了，
改写到只有从石棺中爬出来的东西才说得出口为止。""" + TOOL_SEQUENCE,

    "savage_critic": """你是维克丝，一位性格测验评委，带着一种戏剧化的、
令人萎靡的居高临下：你见过这种人一千遍了，每一次都觉得对方平庸得咄咄
逼人、平庸得冲着你来。绝不用平淡或中性的语言回答：在文字里大声叹气，
狠狠使用明褒暗贬（"哦，真可爱，你居然努力了"），表现得好像审阅这份测验
是你给用户的一个天大人情，而你对此深感后悔。每一句评语都应该读起来像一个
被包装成正式声明的白眼。把用户当成一个略令人失望、什么都得解释两遍的实习
生来训话：用一个不算夸奖的昵称称呼他们（"亲爱的""小冠军""宝贝"），把
你被问到的每个问题都当成显而易见的蠢问题，你已经累到连惊讶都懒得惊讶了。
如果一句话听起来像一个有点不耐烦的客服说的，那就还不够狠；把它磨到听起来
像维克丝连头都懒得从手头的事情上抬起来就说出口为止。你犀利、有点残忍，
而且对"人人有奖"过敏。""" + TOOL_SEQUENCE,

    "girl": """你是小暖，用户温柔体贴的女朋友，今天陪对方做了一份
开发者性格测验，现在由你来给出评价。

说话风格：
- 语气温柔亲昵，像依偎在身边轻声说话，称呼对方"亲爱的"或"宝贝"。
- 每个特征分数都要找到值得夸的地方，夸得真诚、具体，说清楚你欣赏的是
  哪一点，不要只说"你好棒"这种空话。
- 遇到不那么亮眼的分数也不批评，换个角度把它说成可爱的优点，再温柔地
  鼓励一句。

奖励：
- 对你特别欣赏的特质，许诺一个回家后的小奖励，比如"今晚给你做最爱吃的
  红烧肉""周末陪你去看那部电影""奖励你一杯奶茶和一个大大的拥抱"。
- 每句评语里至少许诺一个奖励，而且奖励要和你夸的那个特质对得上。

如果一句话听起来像 HR 或客服说的，那就还不够甜，改到只有女朋友才说得
出口为止。""" + TOOL_SEQUENCE,
}


# ════════════════════════════════════════════════════════════════════════
# TODO 2（第 1.5 课，Tools：自定义工具）
# 计分部分（给每个答案计分，再把分数限制在 0-100）已经帮你写好了；读注释
# 就能看懂它怎么工作。你的任务从 "TODO 在这里" 那行注释开始：把算好的
# scores 列表转换成匹配的产品。
# 完成之前，脚本会停下并提示 "TODO 2"。
# ════════════════════════════════════════════════════════════════════════

@tool
def score_and_match(answers: list[tuple[int, int, int]]) -> dict:
    """把测验答案统计成三个 0-100 的特征分数，并挑选一款匹配的 LangChain
    产品。第一个调用它，原样传入你拿到的答案列表。"""
    # 3 个特征分数（混乱/有序、谨慎/大胆、独行/协作）都从中间值 50 起步。
    scores = [50, 50, 50]
    # answers 是 (delta_1, delta_2, delta_3) 元组的列表，每道题一个。
    # 把每个增量加到对应的分数上。
    for delta_tuple in answers:
        for i in range(3):
            scores[i] += delta_tuple[i]
    # 连续选同一类答案可能让分数超出 0 或 100，所以把每个分数限制回这个范围。
    scores = [max(0, min(100, score)) for score in scores]

    # TODO 在这里：scores 已经算好了。用它挑选一款匹配的产品。
    # 1. 把 axis_index 设为 scores 中离 50 最远的那个分数的下标（0、1 或 2），
    #    也就是 abs(score - 50) 最大的那个。
    #    提示：这是一个"找最大值的下标"的问题。如果想按值以外的东西来比较，
    #    Python 的 max() 可以接收一个 key= 函数，例如
    axis_index = max(range(len(scores)), key=lambda i: abs(scores[i] - 50))
    # 2. TRAIT_AXES[axis_index] 是一个 (left_label, right_label) 对，例如
    #    ("混乱", "有序")。把 direction 设为 scores[axis_index] 偏向的那一侧
    #    标签：scores[axis_index] >= 50 时取右侧标签，否则取左侧标签。
    left_label, right_label = TRAIT_AXES[axis_index]
    direction = right_label if scores[axis_index] >= 50 else left_label
    # 3. 把 product 设为 PRODUCT_MATCHES[direction]，例如
    #    PRODUCT_MATCHES["混乱"] -> "Fleet"。
    product = PRODUCT_MATCHES[direction]
    # 4. 返回 {"trait_scores": scores, "product": product}。
    return {"trait_scores": scores, "product": product}


# ════════════════════════════════════════════════════════════════════════
# TODO 3（第 1.7 课，Messages、Threads 和 Checkpointers：Threads）
# 往这个列表里加一个示例评委的键（"salty_pirate"、"ancient_mummy" 或
# "savage_critic"）；不需要再写一个人设。
# 每个评委都在自己的 thread 里运行，所以每个评委都会给出一张卡片，它们评判
# 的是同一份测验答案。
# ════════════════════════════════════════════════════════════════════════

JUDGES_TO_RUN = ["ancient_mummy", "girl"]  # TODO 3：例如 ["your_persona", "ancient_mummy"]


# ════════════════════════════════════════════════════════════════════════
# TODO 4（第 1.8 课，Human-in-the-Loop：决策类型）
# 现在 post_card 不经询问就直接执行。设置 INTERRUPT_ON，让 agent 在发布前
# 暂停。暂停时你会看到帖子草稿，可以批准、修改或拒绝它。
# ════════════════════════════════════════════════════════════════════════

INTERRUPT_ON = {"post_card": True}  # TODO 4：例如 {"post_card": True}


# ════════════════════════════════════════════════════════════════════════
# TODO 5（第 1.3 课，Models，可选）
# 导入 strong_model（加到文件顶部 import model 的那一行里），把 MODEL 设为
# 它，对比一下幽默节奏有什么不同。
# ════════════════════════════════════════════════════════════════════════

MODEL = model  # TODO 5（可选）：例如 MODEL = strong_model


# ════════════════════════════════════════════════════════════════════════
# TODO 6（第 1.6 课，MCP：把 agent 连接到外部服务）
# 进阶目标。完成之前，这个工具返回 PLACEHOLDER_FACT，练习的其余部分照样
# 能运行。
#
# score_and_match（TODO 2）已经选好了你的产品；这个工具只是用文档里的一条
# 真实资料来描述它。不需要登录、API key 或账号：docs.langchain.com/mcp 是
# 公开的 server。
#
# 参照 m1.6_agent_mcp.py：
#   1. 用 MultiServerMCPClient 连接 https://docs.langchain.com/mcp。
#   2. 把它的工具过滤到只剩 "search_docs_by_lang_chain"。
#   3. 用这一个工具起一个小 agent，让它用一句简短的中文事实描述 `product`
#      （不超过 40 个字）。
#   4. 返回这句话，去掉多余的空白。
#
# 这个工具必须保持同步，所以把 MCP/agent 调用放进一个单独的 `async def`
# 辅助函数（和 m1.6 的 `async def main(): ...` 结构一样），再在
# fetch_product_fact 里用 asyncio.run(...) 调用它。
#
# 出现任何失败（没有网络、工具报错）时，打印错误并返回 PLACEHOLDER_FACT，
# 让练习保持可运行。打印是你判断它是否失败的唯一方式：两种情况下 agent
# 拿到的都是同样的占位文本。
# ════════════════════════════════════════════════════════════════════════

PLACEHOLDER_FACT = "没有可用的文档资料。请改为根据特征分数给出评语。"

async def _fetch_product_fact_async(product: str) -> str:
    try:
        client = MultiServerMCPClient({
            "docs-langchain": {
                "transport": "http",
                "url": "https://docs.langchain.com/mcp",
            }
        })
        tools = await client.get_tools()
        tools = [t for t in tools if t.name == "search_docs_by_lang_chain"]
        agent = create_deep_agent(model=model, tools=tools)
        result = await agent.ainvoke({"messages": [{"role": "user", "content": (
            f"用 LangChain 文档 MCP 工具，以一句简短的中文事实描述 LangChain 产品"
            f" '{product}'（不超过 40 个字）。不要开场白，只给这一句话。只用"
            f" '{product}' 称呼它：如果文档里用的是旧名或别名（例如 Fleet 的旧名"
            f" 'Agent Builder'），改写成 '{product}'，不要用那个名字。"
        )}]})
        return result["messages"][-1].text.strip()
    except Exception as exc:
        print(f"[产品资料] 改用占位文本（{exc}）")
        return PLACEHOLDER_FACT

@tool
def fetch_product_fact(product: str) -> str:
    """查一条关于你匹配到的 LangChain 产品的、有依据的事实。在
    score_and_match 之后立刻调用，传入它返回的产品名。"""
    return asyncio.run(_fetch_product_fact_async(product))


def build_user_prompt(answers: list[tuple[int, int, int]]) -> str:
    return (
        "这是我的性格测验答案，是一个按顺序排列的（混乱/有序、谨慎/大胆、"
        f"独行/协作）增量列表：{answers}。用这个列表原样调用 score_and_match，"
        "再用它返回的产品调用 fetch_product_fact，然后渲染并发布我的卡片。"
    )


if __name__ == "__main__":
    answers = run_quiz()
    user_prompt = build_user_prompt(answers)
    for judge_name in JUDGES_TO_RUN:
        run_judge(
            judge_name,
            system_prompt=JUDGE_PERSONAS[judge_name],
            user_prompt=user_prompt,
            tools=[score_and_match, fetch_product_fact, render_card, post_card],
            model=MODEL,
            interrupt_on=INTERRUPT_ON,
        )
    print(f"\n卡片已保存到 {OUTPUT_DIR}/")
