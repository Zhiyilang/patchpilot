"""PatchPilot 回执渲染：文本 / HTML。用 f-string 拼接，规避 % 格式化 CSS 坑。"""

from __future__ import annotations

_SEV = {"HIGH": "🔴", "CAUTION": "🟡", "INFO": "🔵"}


def text_receipt(result: dict) -> str:
    if not result.get("ok"):
        return f"PatchPilot\n{'=' * 40}\n{result.get('error', '无法处理')}\n"
    out = [
        "PatchPilot · 代码审查回执",
        "=" * 48,
        f"大脑：{result['brain']}    语言：{result['language']}    行数：{result['lines']}",
        f"风险评分：{result['score']}/100    等级：{result['band']}",
        "-" * 48,
        result["summary"],
    ]
    if result["findings"]:
        out.append("")
        for f in result["findings"]:
            emoji = _SEV.get(f["severity"], "•")
            loc = f"L{f['line']}" if f["line"] else "?"
            out.append(f"{emoji} [{f['severity']}] {f['rule']}（{f['code']}）{loc} · {f['source']}")
            out.append(f"    {f['message']}")
            out.append(f"    👉 {f['suggestion']}")
            if f.get("evidence"):
                out.append(f"    📎 {f['evidence']}")
    if result["patches"]:
        out.append("")
        out.append("补丁建议：")
        for p in result["patches"]:
            out.append(f"  L{p['line']} [{p['source']}] {p['rationale']}")
            if p.get("before"):
                out.append(f"      - {p['before'].strip()}")
            out.append(f"      + {p['after'].strip()}")
    if result.get("references"):
        out.append("")
        out.append("最佳实践参考：")
        for r in result["references"]:
            out.append(f"  - [{r['for']}] {r['title']} — {r['url']}")
    out.append("")
    out.append(result["explain"])
    out.append("=" * 48)
    return "\n".join(out)


def html_receipt(result: dict) -> str:
    if not result.get("ok"):
        return (f"<html><body style=\"font-family:sans-serif;padding:2rem\">"
                f"<h2>PatchPilot</h2><p>{result.get('error', '')}</p></body></html>")
    band_color = {"HIGH": "#dc2626", "MEDIUM": "#d97706", "LOW": "#16a34a"}.get(result["band"], "#333")
    rows = ""
    for f in result["findings"]:
        color = {"HIGH": "#dc2626", "CAUTION": "#d97706", "INFO": "#2563eb"}.get(f["severity"], "#333")
        loc = f"L{f['line']}" if f["line"] else "?"
        ev = f"<div class='ev'>📎 {f['evidence']}</div>" if f.get("evidence") else ""
        rows += (f"<div class='f' style='border-left-color:{color}'>"
                 f"<div class='fh'><span class='sev' style='background:{color}'>{f['severity']}</span>"
                 f"<strong>{f['rule']}</strong> <span class='code'>{f['code']}</span> "
                 f"<span class='loc'>{loc}</span> <span class='src'>{f['source']}</span></div>"
                 f"<div class='msg'>{f['message']}</div><div class='sug'>👉 {f['suggestion']}</div>{ev}</div>")
    if not rows:
        rows = "<p class='clean'>✅ 未发现明显问题。</p>"

    patches_html = ""
    for p in result["patches"]:
        b = f"<div class='diff del'>- {p['before'].strip()}</div>" if p.get("before") else ""
        patches_html += (f"<div class='patch'><div class='ploc'>L{p['line']} "
                         f"<span class='src'>{p['source']}</span> — {p['rationale']}</div>"
                         f"{b}<div class='diff add'>+ {p['after'].strip()}</div></div>")
    patch_block = f"<h3>🔧 补丁建议</h3>{patches_html}" if patches_html else ""

    refs_html = ""
    for r in result.get("references", []):
        refs_html += f"<li>[{r['for']}] <a href='{r['url']}' target='_blank'>{r['title']}</a></li>"
    ref_block = f"<h3>🔎 最佳实践参考（Tavily）</h3><ul>{refs_html}</ul>" if refs_html else ""

    return f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PatchPilot 代码审查报告</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0f1222;color:#e8eaf6;margin:0;padding:2rem}}
 .card{{max-width:820px;margin:0 auto;background:#1a1e38;border-radius:14px;box-shadow:0 6px 24px rgba(0,0,0,.4);padding:1.6rem 1.8rem}}
 h1{{font-size:1.35rem;margin:0 0 .2rem}} .meta{{color:#9aa0c3;font-size:.85rem;margin-bottom:1rem}}
 .score{{display:flex;align-items:center;gap:1rem;margin:1rem 0}}
 .badge{{color:#fff;padding:.3rem .8rem;border-radius:999px;font-weight:600;background:{band_color}}}
 .summary{{background:#141833;padding:.7rem 1rem;border-radius:8px;margin:.6rem 0 1rem}}
 .f{{border-left:4px solid #ccc;padding:.6rem .9rem;margin:.6rem 0;background:#141833;border-radius:0 8px 8px 0}}
 .fh{{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}} .sev{{color:#fff;font-size:.72rem;padding:.1rem .5rem;border-radius:6px}}
 .code{{font-family:monospace;color:#9aa0c3;font-size:.8rem}} .loc{{font-family:monospace;color:#6ea8fe;font-size:.85rem}}
 .src{{font-size:.72rem;background:#2a2f52;padding:.05rem .45rem;border-radius:6px;color:#b9c0e0}}
 .msg{{margin:.35rem 0}} .sug{{color:#7ee787;font-size:.9rem}} .ev{{color:#9aa0c3;font-size:.8rem;font-family:monospace;margin-top:.3rem}}
 .clean{{color:#16a34a;font-weight:600}}
 .patch{{background:#141833;border-radius:8px;padding:.6rem .9rem;margin:.5rem 0;font-family:monospace;font-size:.85rem}}
 .ploc{{color:#9aa0c3;font-family:sans-serif;margin-bottom:.3rem}}
 .diff{{white-space:pre-wrap}} .del{{color:#ff7b72}} .add{{color:#7ee787}}
 ul{{line-height:1.7}} a{{color:#6ea8fe}}
 .explain{{white-space:pre-wrap;background:#0f2a4a;border:1px solid #2b4a7a;padding:.8rem 1rem;border-radius:8px;margin-top:1rem}}
</style></head><body>
<div class='card'>
<h1>🩹 PatchPilot 代码审查报告</h1>
<div class='meta'>大脑：{result['brain']} · Nemotron：{'启用' if result['nemotron_used'] else '离线'} · {result['language']} · {result['lines']} 行</div>
<div class='score'><span class='badge'>{result['band']}</span><span>风险评分 <strong>{result['score']}</strong>/100</span></div>
<div class='summary'>{result['summary']}</div>
{rows}
{patch_block}
{ref_block}
<div class='explain'>{result['explain']}</div>
</div></body></html>"""
