# python/m1/Practice/judge_card_practice_filled.zh.py
"""judge_card_practice.zh.py 的个人参考副本，填好了 TODO 1 到 4 以及进阶的
TODO 6，可以端到端运行，看看完成后的练习是什么样子。"""

from __future__ import annotations

import asyncio

from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient

from deepagents import create_deep_agent
from judge_card_helpers_zh import (
    OUTPUT_DIR,
    TRAIT_AXES,
    PRODUCT_MATCHES,
    TOOL_SEQUENCE,
    post_card,
    render_card,
    run_judge,
    run_quiz,
)
from models import model

# TODO 1 已填：三个自带的人设，加上 "your_persona"（这里是像素：和另外
# 三个完全相反的气质）。
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

    "your_persona": """你是像素，一位性格测验评委，不管用户怎么回答，你都对
他们的一切感到无休止的、甚至有点可疑的欣喜。你欢呼，你用感叹号，你把每个
特征分数都当成超能力（"看看你，大胆 92 分，太不可思议了！"），哪怕是最
谨慎、最独行、最有序的回答，你也能把它说成一段激动人心的成长史。""" + TOOL_SEQUENCE,
}


# TODO 2 已填
@tool
def score_and_match(answers: list[tuple[int, int, int]]) -> dict:
    """把测验答案统计成三个 0-100 的特征分数，并挑选一款匹配的 LangChain
    产品。第一个调用它，原样传入你拿到的答案列表。"""
    scores = [50, 50, 50]
    for delta in answers:
        for i in range(3):
            scores[i] += delta[i]
    scores = [max(0, min(100, score)) for score in scores]
    axis_index = max(range(3), key=lambda i: abs(scores[i] - 50))
    left, right = TRAIT_AXES[axis_index]
    direction = right if scores[axis_index] >= 50 else left
    product = PRODUCT_MATCHES[direction]
    return {"trait_scores": scores, "product": product}


# TODO 3 已填：运行全部四个人设（三个自带的 + your_persona）
JUDGES_TO_RUN = ["your_persona", "ancient_mummy", "salty_pirate", "savage_critic"]

# TODO 4 已填
INTERRUPT_ON = {"post_card": True}

# TODO 5（可选）保持默认模型
MODEL = model


# 文档 server 连不上时返回这个。不需要登录或 API key：
# docs.langchain.com/mcp 是公开的 server。
PLACEHOLDER_FACT = "没有可用的文档资料。请改为根据特征分数给出评语。"


async def _fetch_product_fact_async(product: str) -> str:
    try:
        client = MultiServerMCPClient({
            "docs-langchain": {"transport": "http", "url": "https://docs.langchain.com/mcp"},
        })
        tools = await client.get_tools()
        tools = [t for t in tools if t.name == "search_docs_by_lang_chain"]
        fact_agent = create_deep_agent(model=model, tools=tools)
        result = await fact_agent.ainvoke({"messages": [{"role": "user", "content": (
            f"用 LangChain 文档 MCP 工具，以一句简短的中文事实描述 LangChain 产品"
            f" '{product}'（不超过 40 个字）。不要开场白，只给这一句话。只用"
            f" '{product}' 称呼它：如果文档里用的是旧名或别名（例如 Fleet 的旧名"
            f" 'Agent Builder'），改写成 '{product}'，不要用那个名字。"
        )}]})
        return result["messages"][-1].text.strip()
    except Exception as exc:
        print(f"[产品资料] 改用占位文本（{exc}）")
        return PLACEHOLDER_FACT


# TODO 6 已填（进阶目标）
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
            thread_prefix="m1-practice-filled",
        )
    print(f"\n卡片已保存到 {OUTPUT_DIR}/")
