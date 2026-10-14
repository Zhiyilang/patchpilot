"""PatchPilot — 跑在 Nebius + NVIDIA Nemotron 上的智能体代码审查/自动修复应用。

模块：
  lint     离线 Linter（确定性兜底大脑，真实可用的 Python 静态检查）
  llm      Nebius Token Factory + NVIDIA Nemotron 深度审查 + 可选 Tavily 检索
  agent    PatchPilot.review() 智能体闭环
  receipts 文本 / HTML 回执
  web      stdlib Web 控制台（读 PORT）
  cli      命令行入口
"""

from .agent import PatchPilot
from .lint import OfflineLinter
from .llm import NemotronReviewer, TavilySearch, get_reviewer, get_search

__version__ = "1.0.0"
__all__ = ["PatchPilot", "OfflineLinter", "NemotronReviewer", "TavilySearch",
           "get_reviewer", "get_search"]
