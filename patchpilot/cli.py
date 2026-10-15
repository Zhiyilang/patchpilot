"""PatchPilot 命令行入口。

  python -m patchpilot.cli examples/bad_code.py
  python -m patchpilot.cli path/to/code.py --html report.html
  python -m patchpilot.cli examples/bad_code.py --search            # Tavily 证据检索
  python -m patchpilot.cli examples/bad_code.py --offline-evidence  # 断网演示
  python -m patchpilot.cli examples/bad_code.py --evidence-json ev.json
  python -m patchpilot.cli --map-site docs.python.org               # 直接调 /map
  python -m patchpilot.cli --research "python eval injection CWE"   # 直接调 /research
  python -m patchpilot.cli examples/bad_code.py --no-llm            # 仅离线 Linter
"""

from __future__ import annotations

import argparse
import json
import sys

from .agent import PatchPilot
from .receipts import html_receipt, text_receipt
from .research import ResearchLayer, TavilyClient, TavilyError


def _standalone(args) -> int:
    """不审查代码，直接演示某个 Tavily 端点（便于视频录制与调试）。"""
    layer = ResearchLayer.from_env()
    if layer.client is None:
        print("[SKIP] 未设置 TAVILY_API_KEY，无法调用该端点。")
        return 1
    client: TavilyClient = layer.client
    try:
        if args.map_site:
            payload = client.map(args.map_site, max_depth=1, limit=20)
            urls = payload.get("results", []) or payload.get("urls", [])
            print(f"/map {args.map_site} -> {len(urls)} urls")
            for u in urls[:10]:
                print("  -", u if isinstance(u, str) else u.get("url"))
        elif args.research:
            payload = client.research(args.research)
            print(json.dumps(payload, ensure_ascii=False, indent=2)[:2000])
        elif args.usage:
            print(json.dumps(client.usage(), ensure_ascii=False, indent=2)[:2000])
    except TavilyError as exc:
        print(f"[FAIL] {exc}")
        return 1
    print(f"\ncalls={client.calls} credits={client.credits}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="patchpilot",
                                 description="Nebius + NVIDIA Nemotron 智能体代码审查")
    ap.add_argument("path", nargs="?", help="待审查的代码文件")
    ap.add_argument("--html", metavar="OUT", help="输出 HTML 报告")
    ap.add_argument("--search", action="store_true", help="启用 Tavily 证据检索层")
    ap.add_argument("--offline-evidence", action="store_true",
                    help="用内置 fixture 代替真实检索（断网演示）")
    ap.add_argument("--evidence-json", metavar="OUT", help="导出证据包 JSON")
    ap.add_argument("--no-llm", action="store_true", help="仅用离线 Linter（不调用 Nemotron）")
    # 端点直通（演示/调试用）
    ap.add_argument("--map-site", metavar="URL", help="直接调用 Tavily /map")
    ap.add_argument("--research", metavar="QUERY", help="直接调用 Tavily /research")
    ap.add_argument("--usage", action="store_true", help="直接调用 Tavily /usage")
    args = ap.parse_args(argv)

    if args.map_site or args.research or args.usage:
        return _standalone(args)

    if not args.path:
        ap.error("请提供待审查的代码文件路径")

    with open(args.path, encoding="utf-8") as f:
        code = f.read()

    dp = PatchPilot(offline_evidence=args.offline_evidence)
    result = dp.review(code, use_llm=not args.no_llm,
                       use_search=args.search or args.offline_evidence)
    print(text_receipt(result))

    if args.evidence_json:
        with open(args.evidence_json, "w", encoding="utf-8") as f:
            json.dump(result.get("evidence", {}), f, ensure_ascii=False, indent=2)
        print(f"\n证据包已写入：{args.evidence_json}")

    if args.html:
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(html_receipt(result))
        print(f"\nHTML 报告已写入：{args.html}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
