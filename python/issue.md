# VS Code 中 import 出现黄色波浪线（Import "xxx" could not be resolved）

## 现象

- 用 VS Code 打开项目后，Python 文件里除标准库以外的所有 import 都出现黄色波浪线，提示 `Import "xxx" could not be resolved`，包括 `deepagents`、`langchain_core` 等第三方包，以及项目自己的 `models`、`env_utils`。
- 刚打开 VS Code 时没有波浪线，等右下角状态栏显示出 Python 版本后才出现。
- 代码可以正常运行，只有编辑器报错。
- 打开仓库根目录或 `python/` 目录，表现相同。

## 环境

| 项 | 版本 |
|---|---|
| Python（`python/.venv`，uv 创建） | 3.13.12 |
| Pylance | 2026.4.1（pyright 1.1.414） |
| Python 扩展 | 2026.10.0 |
| 构建后端 | setuptools（`[build-system]`） |

## 背景知识

### 可编辑安装

- **普通安装**（`pip install .`）：把项目代码复制一份到 `.venv/lib/python3.13/site-packages/`，之后修改源码要重新安装才生效。
- **可编辑安装**（`pip install -e .`；`uv sync` 安装项目自身时默认也是这种）：不复制代码，只在 site-packages 里放一个“指路牌”，让 Python 到源码目录去找。源码修改后立即生效。

本项目通过可编辑安装，让任意目录下的脚本（例如 `m1/xxx.py`）都能 `from models import model`，不依赖当前工作目录。

### `.pth` 文件

`.pth` 是 Python 自带的机制。Python 启动时，标准库 `site` 模块会扫描 site-packages 中所有 `.pth` 文件，逐行处理：

- 一行是**路径**：追加到 `sys.path`。
- 一行以 **`import`** 开头：当作代码执行。

本项目的“指路牌”文件就在：

```
python/.venv/lib/python3.13/site-packages/
├── __editable__.lca_deepagents_python-0.1.0.pth
├── __editable___lca_deepagents_python_0_1_0_finder.py   （仅导入钩子方式才有）
└── lca_deepagents_python-0.1.0.dist-info/
```

### “指路牌”的两种实现

**1. 静态路径（compat 模式）**：`.pth` 里只有一行目录。

```
/Users/.../introduction-to-deep-agents/python
```

启动后整个 `python/` 目录进入 `sys.path`，按普通方式就能找到 `models.py`。它是纯文本，静态分析工具读一下就知道去哪找。代价是该目录下的所有模块都变得可导入。

**2. 导入钩子（setuptools v64+ 对平铺布局的默认方式）**：`.pth` 里是一行代码。

```
import __editable___lca_deepagents_python_0_1_0_finder; __editable___lca_deepagents_python_0_1_0_finder.install()
```

`install()` 往 `sys.meta_path` 插入一个自定义 finder。finder 内部有一张映射表：

```python
MAPPING = {'env_utils': '.../python/env_utils', 'models': '.../python/models'}
```

`import models` 时由它查表返回源码位置，表里没有的名字一律不管，因此只会暴露声明过的模块。代价是这张表只在运行时存在，静态分析工具读不到。

### `.pth` 是怎么生成的

1. `uv sync` 读取 `pyproject.toml`，项目自身需要以可编辑模式安装。
2. uv 按 PEP 660 调用构建后端（setuptools）的 `build_editable()` 钩子。
3. setuptools 生成一个“可编辑 wheel”，内含 `.pth`、finder（钩子方式时）和 dist-info。
4. uv 把这个 wheel 解包到 site-packages。

采用哪种实现由 setuptools 决定：src 布局通常用静态路径；平铺布局（模块直接放在项目根目录）为避免把整个目录暴露到 `sys.path`，会用导入钩子。本项目属于平铺布局，默认得到的是导入钩子。

### `py-modules`

setuptools 在 `pyproject.toml` 中的配置，用来声明要安装的**单文件顶层模块**：

```toml
[tool.setuptools]
py-modules = ["models", "env_utils"]
```

与之对应的是 `packages`，声明带 `__init__.py` 的目录包。大多数项目只发布一个包目录，钩子映射表里通常只有一项；本项目发布了两个单文件模块，所以映射表里有两项。

### Pylance 如何解析 import

Pylance 基于 pyright 做**静态分析**，不执行代码。查找 `import xxx` 的途径有：

1. 标准库 stub（Pylance 自带的 typeshed）。
2. 执行根目录（默认是 VS Code 打开的工作区根目录）。
3. `python.analysis.extraPaths` 中配置的路径。
4. 解释器的 site-packages，以及其中**静态路径型** `.pth` 指向的目录。钩子型 `.pth` 无法静态读懂。
5. 兜底：从当前文件所在目录开始**逐级向上**查找。`python/m1/xxx.py` 向上一级就到了 `python/`，能找到 `models.py`。所以不依赖 `.pth`，在任何工作区根目录下都能解析 `models`。

第三方包（`deepagents` 等）是普通安装，文件真实存在于 site-packages 中，走第 4 条即可，与可编辑安装无关。

### Pylance 实验功能 `python.analysis.enableEditableInstalls`

- **目的**：解决钩子型 `.pth` 无法被静态分析的问题。它在沙箱中（下载与本机 CPython 匹配的 WASI 构建）实际执行 `.pth` 里的钩子代码，算出每个可编辑包的源码位置，并把这些源码当作第一方代码来索引、类型检查，让它们参与自动导入、重命名和查找引用。
- **生效条件**：Python 3.13 及以上，并且能取得匹配的 WASI 构建。条件不满足时直接跳过，Pylance 退回普通解析。
- **默认值**：`true`。官方标注为实验性功能，可能导致 Pylance 停止工作。
- **作用域**：`"scope": "machine"`，**只认用户级设置**，写在工作区或文件夹的 `.vscode/settings.json` 中不生效。

## 根本原因

Pylance 2026.4.1 的 `enableEditableInstalls` 动态 `.pth` 解析存在缺陷。本项目同时满足以下条件，触发了这个缺陷：

- 解释器是 Python 3.13，满足该功能的启用条件；
- 项目用 setuptools 平铺布局 + `py-modules`，`uv sync` 默认生成**钩子型** `.pth`；
- 该功能默认开启。

缺陷的表现有两点：

1. 解析钩子时只提取出了映射表中的第一个模块（`Resolved packages: env_utils`），漏掉了 `models`。
2. 解析完成后，Pylance 只使用了 `.pth` 解析出的路径，丢掉了正常的搜索路径。日志中列出的搜索路径完全正确（包含 `python/` 和 site-packages），但实际导入全部失败，连 site-packages 里的第三方包和工作区根目录下的 `models` 也找不到，只有走自带 typeshed 的标准库能解析。

这和 [pylance-release#8184](https://github.com/microsoft/pylance-release/issues/8184) 是同类问题。维护者对该 issue 的说明是 *"we're not adding the sys paths, but only the ones returned by the pth file"*，修复已包含在 2026.3.102 中，但没有覆盖本项目的场景。2026.4.1 是当前最新正式版，之后的预发布版也没有相关修复，所以更新 Pylance 解决不了。

“刚打开时没有波浪线，状态栏出现 Python 版本后才出现”的原因是：解释器确定后 Pylance 才启动，随后执行了这段动态解析。

## 排查过程

1. **怀疑解释器没选对**：查看 VS Code 存储的解释器记录和 Python 扩展日志，两个工作区的活动解释器都是 `python/.venv/bin/python`（3.13.12）。解释器选择正常。
2. **用 pyright CLI 复现**：用与 Pylance 内核相同版本的 pyright 1.1.414，指定该 venv，分别从仓库根目录和 `python/` 检查，所有 import 都能解析。说明问题出在 Pylance 在 pyright 之上额外加的逻辑。
3. **读 Pylance 日志**：发现 `[Editable Installs]` 动态解析流程，以及 `Resolved packages: env_utils`，`models` 被漏掉。
4. **在 `python/.vscode/settings.json` 中关闭该功能**：日志中 `[Editable Installs]` 仍然运行，没有效果。原因是该设置为 `machine` 作用域，文件夹级设置被忽略。
5. **开启 Trace 日志**（`python.analysis.logLevel: "Trace"`）：搜索路径完全正确，但当前文件的 `langchain_core.tools`、`deepagents`、`models` 都是 `Could not import`，确认是 Pylance 内部解析失败，不是路径配置问题。
6. **实验 A：改用 compat 模式安装**（`uv pip install -e . --config-settings editable_mode=compat`），`.pth` 变成纯路径。重启语言服务后波浪线消失。之后执行 `uv sync`，又装回钩子方式，波浪线再次出现。确认问题与钩子型 `.pth` 相关。
7. **查 GitHub issue 与官方文档**：找到同类问题 #8184；官方文档对 setuptools 钩子型安装推荐的做法就是 compat 模式。
8. **在用户设置中关闭该功能**：波浪线消失，无论打开哪个目录都正常。第三方包走 site-packages 解析，`models` 走“逐级向上查找”解析。
9. **重新开启该功能，并在 `pyproject.toml` 中固定 compat 模式**：波浪线消失，`uv sync` 后也保持正常。

## 解决方案

### 方案一（采用）：在 `pyproject.toml` 中固定 compat 模式

```toml
[tool.uv]
config-settings = { editable_mode = "compat" }
```

添加后执行一次重新安装，让配置生效：

```bash
cd python
uv sync --reinstall-package lca-deepagents-python
```

之后检查 `.venv/lib/python3.13/site-packages/__editable__.lca_deepagents_python-0.1.0.pth`，内容应为一行源码目录路径。最后在 VS Code 中执行 `Python: Restart Language Server`。

优点：从源头避开钩子型 `.pth`，不依赖 Pylance 版本和设置，`uv sync` 后依然有效，对其他项目没有影响。
注意：`config-settings` 也会作用于其他需要从源码构建的依赖（例如 `forbiddenfruit`），对它们没有实际影响。

### 方案二：在**用户设置**中关闭实验功能

```json
"python.analysis.enableEditableInstalls": false
```

必须写在用户级 `settings.json` 中，写在工作区设置里无效。修改后执行 `Python: Restart Language Server`。

代价：这是全局设置，会影响所有项目。其他项目中如果有钩子方式可编辑安装、且不在文件上级目录里的包，Pylance 将无法解析，需要为那个项目配置 `extraPaths` 或改用 compat 模式。

## 参考

- [pylance-release#8184：`enableEditableInstalls` breaks relative imports in editable package](https://github.com/microsoft/pylance-release/issues/8184)
- [pylance-release#8225：动态 `.pth` 解析需要 Python 3.13+ 和匹配的 WASI 构建](https://github.com/microsoft/pylance-release/issues/8225)
- [Pylance 文档：How to Use Editable Installs with Pylance](https://github.com/microsoft/pylance-release/blob/main/docs/howto/editable-installs.md)
- [Pylance CHANGELOG](https://github.com/microsoft/pylance-release/blob/main/CHANGELOG.md)
- [PEP 660：Editable installs for pyproject.toml based builds](https://peps.python.org/pep-0660/)
