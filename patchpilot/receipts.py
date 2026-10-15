"""PatchPilot 回执渲染：文本 / HTML。用 f-string 拼接，规避 % 格式化 CSS 坑。"""

from __future__ import annotations

from . import i18n
from .research import tier_label

_SEV = {"HIGH": "🔴", "CAUTION": "🟡", "INFO": "🔵"}


def text_receipt(result: dict, lang: str = "zh") -> str:
    if not result.get("ok"):
        msg = result.get("error", "无法处理")
        if lang == "en":
            msg = i18n.t(lang, "unprocessable") + ": " + msg
        return f"PatchPilot\n{'=' * 40}\n{msg}\n"
    en = lang == "en"
    if en:
        title = i18n.t(lang, "title")
        brain_line = i18n.t(lang, "brain_line", brain=result["brain"],
                            language=result["language"], lines=result["lines"])
        score_line = i18n.t(lang, "score_line", score=result["score"],
                            band=result["band"])
        findings = result["findings"]
        highs = sum(1 for f in findings if f["severity"] == "HIGH")
        cautions = sum(1 for f in findings if f["severity"] == "CAUTION")
        infos = sum(1 for f in findings if f["severity"] == "INFO")
        summary = (i18n.t(lang, "summary_clean", lines=result["lines"],
                          language=result["language"]) if not findings else
                   i18n.t(lang, "summary_findings", lines=result["lines"],
                          language=result["language"], highs=highs,
                          cautions=cautions, infos=infos, band=result["band"]))
    else:
        title = "PatchPilot · 代码审查回执"
        brain_line = (f"大脑：{result['brain']}    语言：{result['language']}"
                      f"    行数：{result['lines']}")
        score_line = f"风险评分：{result['score']}/100    等级：{result['band']}"
        summary = result["summary"]
    out = [
        title,
        "=" * 48,
        brain_line,
        score_line,
        "-" * 48,
        summary,
    ]
    if result["findings"]:
        out.append("")
        for f in result["findings"]:
            emoji = _SEV.get(f["severity"], "•")
            loc = f"L{f['line']}" if f["line"] else "?"
            rule, message, suggestion = f["rule"], f["message"], f["suggestion"]
            if en:
                tr = i18n.rule_en(f["code"])
                if tr:
                    rule, message, suggestion = tr
            out.append(f"{emoji} [{f['severity']}] {rule}（{f['code']}）{loc} · {f['source']}"
                       if not en else
                       f"{emoji} [{f['severity']}] {rule} ({f['code']}) {loc} · {f['source']}")
            out.append(f"    {message}")
            out.append(f"    👉 {suggestion}")
            if f.get("evidence"):
                out.append(f"    📎 {f['evidence']}")
    if result["patches"]:
        out.append("")
        out.append(i18n.t(lang, "patches_header") if en else "补丁建议：")
        for p in result["patches"]:
            rationale = p["rationale"]
            if en:
                rationale = i18n.PATCH_EN.get(rationale, rationale)
            out.append(f"  L{p['line']} [{p['source']}] {rationale}")
            if p.get("before"):
                out.append(f"      - {p['before'].strip()}")
            out.append(f"      + {p['after'].strip()}")
    if result.get("references"):
        ev = result.get("evidence") or {}
        out.append("")
        out.append(i18n.t(lang, "evidence_header", mode=ev.get("mode", "-"))
                   if en else f"Tavily 证据（{ev.get('mode', '-')}）：")
        for r in result["references"]:
            mark = "✅" if r.get("quote_verified") else ("⚠️" if "quote_matched" in r else "·")
            out.append(f"  {mark} [{r['for']}] {r['title']}")
            if en:
                tier = i18n.UI_EN["tier"].get(r.get("tier", 0), str(r.get("tier", 0)))
            else:
                tier = tier_label(r.get("tier", 0))
            out.append(f"      {r['url']}  (credibility {tier}, score {r.get('score', '-')})")
        gate = ev.get("gate") or {}
        if gate:
            out.append(f"  🧭 " + (i18n.t(lang, "gate_line",
                                         considered=gate.get("considered", 0),
                                         admitted=gate.get("admitted", 0),
                                         calls=ev.get("calls", {}),
                                         credits=ev.get("credits", 0))
                                   if en else
                                   f"闸门：候选 {gate.get('considered', 0)} → 采纳 {gate.get('admitted', 0)}"
                                   f" · 端点 {ev.get('calls', {})} · credits {ev.get('credits', 0)}"))
    out.append("")
    out.append(_explain_text(result, en))
    out.append("=" * 48)
    return "\n".join(out)


def _explain_text(result: dict, en: bool) -> str:
    """Rebuild the explanation in the requested language from result fields."""
    findings = result["findings"]
    patches = result["patches"]
    references = result.get("references")
    ev = result.get("evidence") or {}
    nemotron_used = result.get("brain") == "nemotron"
    lines = []
    if en:
        highs = [f for f in findings if f["severity"] == "HIGH"]
        if highs:
            lines.append("⚠️ Fix the high-severity findings first:")
            for f in highs:
                loc = f"L{f['line']}" if f["line"] else "?"
                msg = f["message"]
                tr = i18n.rule_en(f["code"])
                if tr:
                    msg = tr[1]
                lines.append(f"  - [{f['code']}] {loc}: {msg}")
        else:
            lines.append("✅ No high-severity findings.")
        if patches:
            lines.append(i18n.UI_EN["explain_patches"].format(n=len(patches)))
        if nemotron_used:
            lines.append("🧠 " + i18n.UI_EN["explain_nemotron"])
        else:
            lines.append("ℹ️ " + i18n.UI_EN["explain_offline"])
        if references:
            verified = sum(1 for r in references if r.get("quote_verified"))
            lines.append("🔎 " + i18n.UI_EN["explain_tavily"].format(
                n=len(references), mode=ev.get("mode", "tavily"), verified=verified))
            if ev.get("degraded") and ev.get("reason"):
                lines.append(f"   ⚠️ {ev['reason']}")
        return "\n".join(lines)
    return result.get("explain", "")


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
        if r.get("quote_verified"):
            v = "<span class='ok'>✅ 已回正文核对</span>"
        elif "quote_matched" in r:
            v = f"<span class='warn'>⚠️ 核对未通过（{r.get('quote_matched')}/{len(r.get('quote_probes', []) or [0])}）</span>"
        else:
            v = ""
        fix = " <span class='src'>fixture</span>" if r.get("fixture") else ""
        refs_html += (f"<li>[{r['for']}] <a href='{r['url']}' target='_blank'>{r['title']}</a> "
                      f"<span class='src'>{r.get('domain', '')} · 可信度 {tier_label(r.get('tier', 0))} · "
                      f"score {r.get('score', '-')}</span> {v}{fix}</li>")
    ev = result.get("evidence") or {}
    gate = ev.get("gate") or {}
    stats = ""
    if gate:
        stats = (f"<div class='gate'>🧭 证据闸门：候选 {gate.get('considered', 0)} → 采纳 "
                 f"{gate.get('admitted', 0)} · 端点 {ev.get('calls', {})} · "
                 f"credits {ev.get('credits', 0)} · {ev.get('elapsed_s', 0)}s</div>")
    if ev.get("degraded") and ev.get("reason"):
        stats += f"<div class='warnline'>⚠️ {ev['reason']}</div>"
    ref_block = f"<h3>🔎 Tavily 证据（{ev.get('mode', '-')}）</h3>{stats}<ul>{refs_html}</ul>" \
        if (refs_html or gate) else ""

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
 .gate{{font-size:.8rem;color:#9aa0c3;background:#141833;padding:.4rem .7rem;border-radius:6px;margin:.4rem 0}}
 .warnline{{font-size:.82rem;color:#f0b429;background:#3a2c0d;padding:.4rem .7rem;border-radius:6px;margin:.4rem 0}}
 .ok{{color:#7ee787;font-size:.78rem}} .warn{{color:#f0b429;font-size:.78rem}}
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
