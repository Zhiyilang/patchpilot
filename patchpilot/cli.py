"""PatchPilot 命令行入口。

  python -m patchpilot.cli examples/bad_code.py
  python -m patchpilot.cli path/to/code.py --html report.html
  python -m patchpilot.cli examples/bad_code.py --search      # 启用 Tavily 检索增强
  python -m patchpilot.cli examples/bad_code.py --no-llm      # 仅离线 Linter
"""

from __future__ import annotations

import argparse
import sys

from .agent import PatchPilot
from .receipts import html_receipt, text_receipt


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="patchpilot", description="Nebius + NVIDIA Nemotron 智能体代码审查")
    ap.add_argument("path", nargs="?", help="待审查的代码文件")
    ap.add_argument("--html", metavar="OUT", help="输出 HTML 报告")
    ap.add_argument("--search", action="store_true", help="启用 Tavily 检索增强")
    ap.add_argument("--no-llm", action="store_true", help="仅用离线 Linter（不调用 Nemotron）")
    args = ap.parse_args(argv)

    if not args.path:
        ap.error("请提供待审查的代码文件路径")

    with open(args.path, encoding="utf-8") as f:
        code = f.read()

    dp = PatchPilot()
    result = dp.review(code, use_llm=not args.no_llm, use_search=args.search)
    print(text_receipt(result))

    if args.html:
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(html_receipt(result))
        print(f"\nHTML 报告已写入：{args.html}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
