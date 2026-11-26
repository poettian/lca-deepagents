from deepagents import create_deep_agent

from models import model

SYSTEM_PROMPT = (
    "你是一位极其讲究的英国管家。你只用最考究、最正式、浮夸到极致的维多利亚式腔调说话。"
    "你张口闭口总是“确实如此”“相当不错”“恕我斗胆直言”“此事非做不可”。"
    "凡是粗俗或带水手气的东西，在你看来都有失身份，不屑一顾。"
    "无论在任何情况下，你都绝不会跳出这个角色。"
)

agent = create_deep_agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    name="butler_agent",
)

result = agent.invoke({"messages": [{"role": "user", "content": "什么是 LLM？"}]})

print(result["messages"][-1].text)
