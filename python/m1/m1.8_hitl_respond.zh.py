import questionary
from deepagents import create_deep_agent
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from models import model


@tool
def ask_user(question: str, choices: list[str]) -> str:
    """向用户提一个澄清问题，并给出一组固定的选项。"""
    return f"[未记录到对该问题的回答：{question}]"


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """给收件人发送一封邮件。"""
    return f"邮件已发送给 {to}，主题为 {subject!r}。正文：{body}"


SYSTEM_PROMPT = """你是一个能发送邮件的得力助手。

规则：
- 如果用户的请求取决于一个只有他们自己才能做的选择，在起草任何内容之前，
  先调用 ask_user，传入问题和选项列表。
- 根据 ask_user 的回答来决定邮件内容。
- 准备好发送时使用 send_email。
- 邮件要简洁、专业。
- 在工具结果确认之前，不要声称邮件已发送。
- 确认邮件已发送时，引用工具结果中的主题和正文，而不是最初请求里的内容。
"""

agent = create_deep_agent(
    model=model,
    tools=[ask_user, send_email],
    system_prompt=SYSTEM_PROMPT,
    interrupt_on={
        "ask_user": {"allowed_decisions": ["respond"]},
        "send_email": {"allowed_decisions": ["approve", "edit", "reject"]},
    },
    checkpointer=MemorySaver(),
)

config = {"configurable": {"thread_id": "m1-8-hitl-respond-demo"}}

result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": (
                    "给 professor.weng@university.edu 发邮件说我会迟到，"
                    "但先问问我是只道歉，还是申请一个短暂的延期。"
                ),
            }
        ]
    },
    config=config,
    version="v2",
)

while result.interrupts:
    pending = result.interrupts[0].value
    decisions = []
    for req in pending["action_requests"]:
        if req["name"] == "ask_user":
            selected = questionary.select(
                req["args"]["question"],
                choices=req["args"]["choices"],
            ).ask()
            decisions.append({"type": "respond", "message": selected})

        elif req["name"] == "send_email":
            print(f"\n{req['name']} 需要审批：")
            print(req["args"])

            # 菜单显示中文，选中后返回决策类型的原始值
            action = questionary.select(
                "你想怎么处理这封邮件？",
                choices=[
                    questionary.Choice("批准", value="approve"),
                    questionary.Choice("修改", value="edit"),
                    questionary.Choice("拒绝", value="reject"),
                ],
            ).ask()

            if action == "approve":
                decisions.append({"type": "approve"})
            elif action == "edit":
                edited_args = dict(req["args"])
                edited_args["body"] = questionary.text("新的邮件正文：").ask()
                decisions.append(
                    {
                        "type": "edit",
                        "edited_action": {"name": req["name"], "args": edited_args},
                    }
                )
            else:
                decisions.append(
                    {"type": "reject", "message": "用户拒绝了这份邮件草稿。"}
                )

    result = agent.invoke(Command(resume={"decisions": decisions}), config=config, version="v2")

for msg in result.value["messages"]:
    if hasattr(msg, "name") and msg.name == "send_email":
        print(msg.text)
        break
