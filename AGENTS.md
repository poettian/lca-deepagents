# AGENTS.md

## 仓库来源

- `origin`：个人 fork，`https://github.com/poettian/lca-deepagents.git`
- `upstream`：课程官方仓库，`https://github.com/langchain-ai/lca-deepagents.git`

课程内容以 `upstream/main` 为准，同步方式：

```bash
git fetch upstream
git merge upstream/main
```

本地有未提交改动且和上游改动的文件重叠时，先 `git stash`，合并后再 `git stash pop`。

`python/models.py` 的默认模型是本地自定义配置（OpenRouter 上的 GPT-6 Luna），合并冲突时保留本地默认模型，其余部分以上游为准。

## 回答课程外的问题

学生追问课程内容没有覆盖的实现细节（如 state 结构、system message 的拼装方式、middleware 的加载时机）时，必须先阅读已安装的源码核实，再作答。不凭推测或记忆回答，避免误导。

源码位置（Python 版本号以 `python/.venv/lib/` 下实际目录为准）：

- `python/.venv/lib/python3.13/site-packages/deepagents/`：Deep Agents，middleware 在 `middleware/`，backend 在 `backends/`
- `python/.venv/lib/python3.13/site-packages/langchain/agents/`：`create_agent`、`AgentState`、`ModelRequest` 等底层类型
- `python/.venv/lib/python3.13/site-packages/langgraph/`：checkpointer、store、graph 运行时

## 导师技能 lca-deepagents

`.agents/skills/lca-deepagents/` 是课程导师技能，`.claude/skills/lca-deepagents` 是指向它的软链接。两者都在 `.gitignore` 中，不受 git 管理。

技能由 skills 工具从 `langchain-ai/lca-tutors` 安装（见 `skills-lock.json`）。这个来源仓库里的 `references/` 更新滞后于课程仓库，因此本地的 `references/` 由课程源文件 `thinkific/src/` 生成，内容比来源仓库新。

用 skills 工具更新或重新安装这个技能时，`references/` 会被来源仓库的版本覆盖，需要重新生成。

### 生成 references

每次合并 `upstream/main` 之后，或者重新安装导师技能之后，在仓库根目录执行：

```bash
python3 scripts/sync_tutor_references.py
```

脚本会同步 `thinkific/src/<模块>/<课程>.md` 到 `.agents/skills/lca-deepagents/references/<课程>.md`（跳过 `m0.1-setup-typescript.md`），只保留 Python 版本内容。
