"""PatchPilot Web 控制台（零依赖，stdlib http.server）。

  GET  /          落地页
  GET  /app       审查工作台（粘贴代码 → 一键审查）
  POST /review    处理并渲染报告
  GET  /healthz   健康检查

读 PORT，绑 0.0.0.0。CSS 用独立常量（非 f-string）避开花括号陷阱。
"""

from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from .agent import PatchPilot
from .receipts import html_receipt

_CSS = """
:root{--bg:#0f1222;--card:#1a1e38;--ink:#e8eaf6;--muted:#9aa0c3;--acc:#76b900;--acc2:#7ee787;--line:#2a2f52}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink);line-height:1.6}
.wrap{max-width:900px;margin:0 auto;padding:2rem 1.2rem}
a{color:var(--acc2);text-decoration:none}
nav{display:flex;justify-content:space-between;align-items:center;padding:1rem 1.2rem;border-bottom:1px solid var(--line)}
nav .logo{font-weight:700}nav .logo span{color:var(--acc)}
.btn{display:inline-block;background:var(--acc);color:#0b1020;font-weight:600;padding:.6rem 1.1rem;border-radius:10px;border:0;cursor:pointer}
.btn.ghost{background:transparent;color:var(--acc);border:1px solid var(--acc)}
.hero{padding:2.6rem 0 1.6rem;text-align:center}
.hero h1{font-size:2rem;margin:.2rem 0}
.hero p{color:var(--muted);max-width:640px;margin:.6rem auto 1.4rem}
.pill{display:inline-block;background:var(--card);border:1px solid var(--line);color:var(--acc2);padding:.25rem .7rem;border-radius:999px;font-size:.8rem;margin-bottom:.8rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem;margin:1.4rem 0}
.feature{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:1.1rem}
.feature h3{margin:.2rem 0 .4rem;font-size:1.02rem}.feature p{color:var(--muted);font-size:.9rem;margin:0}
textarea{width:100%;min-height:260px;background:#0b0e1c;color:var(--ink);border:1px solid var(--line);border-radius:12px;padding:1rem;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.88rem}
.row{display:flex;gap:1rem;flex-wrap:wrap;align-items:center;margin:1rem 0}
label{color:var(--muted);font-size:.9rem}
.note{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:.8rem 1rem;color:var(--muted);font-size:.88rem;margin:1rem 0}
footer{color:var(--muted);font-size:.8rem;text-align:center;padding:2rem 0;border-top:1px solid var(--line);margin-top:2rem}
.result{margin-top:1.4rem}
"""


def _nav(active: str) -> str:
    def cls(k):
        return " style='color:var(--acc2)'" if k == active else ""
    return (f"<nav><div class='logo'>🩹 Patch<span>Pilot</span></div>"
            f"<div><a href='/'{cls('home')}>首页</a> &nbsp; "
            f"<a href='/app'{cls('app')}>审查工作台</a></div></nav>")


def _landing() -> str:
    return f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PatchPilot · Nebius + NVIDIA Nemotron 智能体代码审查</title>
<style>{_CSS}</style></head><body>
{_nav("home")}
<div class="wrap">
<div class="hero">
<div class="pill">⚡ Nebius Token Factory · 🧠 NVIDIA Nemotron · 🩹 自动修复建议</div>
<h1>粘贴代码，AI 审查员秒回报告</h1>
<p>PatchPilot 是一个跑在 <strong>Nebius Token Factory</strong> + <strong>NVIDIA Nemotron</strong> 上的智能体：
先用确定性离线 Linter 扫一遍，再由 Nemotron 深度审查 bug/安全/性能，给出可执行补丁。
无 API Key 也能用离线引擎完整演示。</p>
<a class="btn" href="/app">开始审查</a>
</div>
<div class="grid">
<div class="feature"><h3>🧠 双大脑</h3><p>离线 Linter（确定性兜底）+ Nemotron 深度审查；无 Key 自动回落，永不崩溃。</p></div>
<div class="feature"><h3>🛡️ 12 类检查</h3><p>裸 except、eval 注入、硬编码密钥、可变默认参数、== None、type()== …</p></div>
<div class="feature"><h3>🔧 自动补丁</h3><p>对可机械修复的问题直接给出 before/after diff，一键采纳。</p></div>
<div class="feature"><h3>🔎 可取证</h3><p>每条发现带证据行与行号；可选 Tavily 证据检索层，按域名分级 + 正文核对后才采信。</p></div>
</div>
<div class="note">🔑 配置 <code>NEBIUS_API_KEY</code> 即启用 NVIDIA Nemotron 深度审查（Nebius 注册送免费额度）；
可选 <code>TAVILY_API_KEY</code> 开启证据检索（search / extract / map / research 五端点）。</div>
</div>
<footer>PatchPilot · MIT · <a href="https://github.com/Zhiyilang/patchpilot">GitHub</a></footer>
</body></html>"""


def _app_page(prefill: str = "", result_html: str = "", banner: str = "",
              use_llm: bool = True, use_search: bool = False,
              offline_evidence: bool = False) -> str:
    llm_checked = " checked" if use_llm else ""
    search_checked = " checked" if use_search else ""
    off_checked = " checked" if offline_evidence else ""
    banner_html = f"<div class='note' style='border-color:var(--acc)'>{banner}</div>" if banner else ""
    return f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>审查工作台 · PatchPilot</title>
<style>{_CSS}</style></head><body>
{_nav("app")}
<div class="wrap">
<h1>审查工作台</h1>
<p style="color:var(--muted)">粘贴一段 Python 代码，一键审查。</p>
<form method="post" action="/review">
<textarea name="code" placeholder="在此粘贴 Python 代码…">{prefill}</textarea>
<div class="row">
<label><input type="checkbox" name="use_llm" value="1"{llm_checked}> 启用 Nemotron 深度审查</label>
<label><input type="checkbox" name="use_search" value="1"{search_checked}> Tavily 证据检索</label>
<label><input type="checkbox" name="offline_evidence" value="1"{off_checked}> 离线证据（fixture 演示）</label>
<button class="btn" type="submit">🔍 一键审查</button>
</div>
</form>
{banner_html}
<div class="result">{result_html}</div>
</div>
<footer>PatchPilot · MIT · <a href="/">返回首页</a></footer>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, html: str, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(_landing())
        elif path == "/app":
            self._send(_app_page())
        elif path == "/healthz":
            self._send('{"ok":true,"service":"patchpilot"}')
        else:
            self._send(_landing(), 404)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path != "/review":
            self._send(_landing(), 404)
            return
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        code = form.get("code", [""])[0]
        use_llm = form.get("use_llm", [""])[0] == "1"
        use_search = form.get("use_search", [""])[0] == "1"
        offline_evidence = form.get("offline_evidence", [""])[0] == "1"

        dp = PatchPilot(offline_evidence=offline_evidence)
        result = dp.review(code, use_llm=use_llm,
                           use_search=use_search or offline_evidence)
        if not result.get("ok"):
            self._send(_app_page(prefill=code, banner=result.get("error", "处理失败"),
                                 use_llm=use_llm, use_search=use_search,
                                 offline_evidence=offline_evidence))
            return
        receipt = html_receipt(result)
        self._send(_app_page(prefill=code, result_html=receipt, use_llm=use_llm,
                             use_search=use_search, offline_evidence=offline_evidence))


def serve(port: int | None = None) -> None:
    # Only fall back to the env/default when port is None. `port or ...`
    # treats an explicit 0 as "unset", which silently turns an ephemeral-port
    # request into the fixed default.
    if port is None:
        port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", int(port)), _Handler)
    print(f"PatchPilot 控制台已启动：http://0.0.0.0:{port}  (Ctrl+C 停止)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
