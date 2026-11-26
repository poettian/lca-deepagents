from pathlib import Path
from uuid import uuid4

from deepagents import create_deep_agent
from deepagents.backends.langsmith import LangSmithSandbox
from langsmith.sandbox import SandboxClient

from models import model

DB_PATH = Path(__file__).resolve().parent / "chinook.db"

client = SandboxClient()
ls_sandbox = client.create_sandbox(name=f"lca-deepagents-lab-{uuid4().hex[:8]}")
print(f"沙箱：{ls_sandbox.name}  (id: {ls_sandbox.id})")

backend = LangSmithSandbox(sandbox=ls_sandbox)

# agent 运行前，把本地数据库上传进沙箱
with open(DB_PATH, "rb") as f:
    upload_results = backend.upload_files([("/chinook.db", f.read())])

# 上传失败不会抛异常，错误记录在每个结果的 error 字段里，需要自己检查
for upload_result in upload_results:
    if upload_result.error:
        raise RuntimeError(f"上传 {upload_result.path} 失败：{upload_result.error}")

# 沙箱里没有中文字体，所以要求图表内的文字用英文，回答用中文
agent = create_deep_agent(
    model=model,
    backend=backend,
    system_prompt=(
        "你是一名销售数据分析师，可以访问位于 /chinook.db 的 Chinook 音乐商店数据库。"
        "使用 sqlite3 和 matplotlib，通过图表来回答问题。"
        "这个沙箱的 Python 是外部托管的，安装包时要用 "
        "`pip install --break-system-packages <包名>`（例如 `pip install "
        "--break-system-packages matplotlib`）。sqlite3 是标准库，不要安装它。"
        "被要求生成图表时，先写一个 Python 脚本，再执行它，并确认输出文件已经生成。"
        "沙箱里没有中文字体，图表中的标题和标签一律用英文；给用户的回答用中文。"
    ),
)

try:
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "查询位于 /chinook.db 的 Chinook 数据库，统计各流派的总收入。"
                        "画一张简洁的环形图，展示每个流派占总销售收入的份额。"
                        "单个流派收入占比不到 3% 的，合并成一块 'Other'。"
                        "每一块都标注流派名和百分比。"
                        "使用区分度高的配色，中间留白色的圆孔，"
                        "确保标签之间、标签与标题之间都不重叠。"
                        "顶部留足边距，让标题完整显示。"
                        "把图表保存到 /genre_revenue.png。"
                    ),
                }
            ]
        }
    )
    print(result["messages"][-1].text)

    # 沙箱删除前，把图表读回本地
    png_bytes = ls_sandbox.read("/genre_revenue.png")
    out_path = Path(__file__).parent / "genre_revenue.png"
    out_path.write_bytes(png_bytes)
    print(f"图表已保存到 {out_path}")

finally:
    # 无论成功还是报错都删除沙箱，避免持续计费
    client.delete_sandbox(ls_sandbox.name)
