"""用 thinkific/src 下的最新课程源文件重新生成导师技能的 references。

源文件同时包含 Python 和 TypeScript 两个版本，这里只保留 Python 版本。

用法（在仓库根目录）：
    python3 scripts/sync_tutor_references.py
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REFS = REPO / ".agents/skills/lca-deepagents/references"
SRC = REPO / "thinkific/src"

OPEN = re.compile(r"<div\b")
CLOSE = re.compile(r"</div>")


def keep_python_only(text: str) -> str:
    """删除 TypeScript 块和语言切换按钮，去掉 Python 块的外层 div。"""
    out = []
    # mode 为 None 表示不在语言块内；"drop" 丢弃整个块；"unwrap" 保留内容、去掉外层标签
    mode = None
    depth = 0
    for line in text.splitlines(keepends=True):
        if mode is None:
            if 'data-lang="typescript"' in line or "data-page-lang-switch" in line:
                mode = "drop"
            elif 'data-lang="python"' in line:
                mode = "unwrap"
            else:
                out.append(line)
                continue
            # 语言块的开标签行本身不输出；单行闭合的块直接结束
            depth = len(OPEN.findall(line)) - len(CLOSE.findall(line))
            if depth <= 0:
                mode = None
            continue

        depth += len(OPEN.findall(line)) - len(CLOSE.findall(line))
        if depth <= 0:
            # 外层 div 的闭合行不输出
            mode = None
            continue
        if mode == "unwrap":
            out.append(line)
    return "".join(out)


EXCLUDED = {"m0.1-setup-typescript.md"}


def main() -> None:
    REFS.mkdir(parents=True, exist_ok=True)
    # 同步 thinkific/src 下所有课程源文件，跳过纯 TypeScript 课程
    for src in sorted(SRC.glob("*/*.md")):
        if src.name in EXCLUDED:
            continue
        target = REFS / src.name
        target.write_text(keep_python_only(src.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"已更新 {src.name}")


if __name__ == "__main__":
    main()
