# PatchPilot 🩹 — 跑在 Nebius + NVIDIA Nemotron 上的智能体代码审查

**粘贴代码，AI 审查员秒回报告。** PatchPilot 是为 **Nebius × NVIDIA Global AI Hackathon**
打造的智能体代码审查/自动修复工具：在 **Nebius Token Factory** 上用 **NVIDIA Nemotron**
跑完整的多步智能体闭环；无 API Key 时自动回落到确定性离线 Linter，开箱即可完整演示。

- ⚡ **跑在 Nebius Token Factory + NVIDIA Nemotron**（`nvidia/nemotron-3-super-120b-a12b`）做深度语义审查
- 🛡️ **双大脑**：离线 Linter（12 条真实规则，永远可用）+ Nemotron 深度审查；无 Key 也完整可用
- 🔧 **自动补丁**：对可机械修复的问题给出 before/after diff
- 🔎 **可解释**：每条发现带行号 + 证据行；可选 **Tavily** 检索补充最佳实践参考
- 🧪 **自测**：`python eval.py` → **37/37 断言全过**，零依赖

## 快速开始

```bash
python -m patchpilot.cli examples/bad_code.py        # 离线模式审查示例烂代码
python -m patchpilot.cli examples/bad_code.py --html report.html
python eval.py                                        # 离线自测（37 断言）
python server.py                                      # Web 控制台 → http://localhost:8000
```

## 启用 NVIDIA Nemotron 深度审查

```bash
export NEBIUS_API_KEY=...            # Nebius 注册送免费额度
export NEBIUS_BASE=https://api.tokenfactory.nebius.com/v1/
export NEBIUS_MODEL=nvidia/nemotron-3-super-120b-a12b
python -m patchpilot.cli examples/bad_code.py
```

可选 Tavily 检索增强：`export TAVILY_API_KEY=...` 后加 `--search`。

## 智能体闭环

```
PERCEIVE 识别语言/行数 → LINT 离线Linter → REASON Nemotron深度审查（失败自动回落）
→ RETRIEVE 可选Tavily检索 → PLAN 合并去重 → EXPLAIN 结论 → RECEIPT 回执
```

## 离线 Linter 覆盖（12 类）

裸 except、eval/exec 注入、硬编码密钥、被吞异常、== None、== True/False、type()==、
可变默认参数、import *、调试 print、TODO/FIXME、超长行。其中 BARE_EXCEPT / EQ_NONE / EQ_BOOL
会自动生成补丁。

## 配置

| 环境变量 | 用途 | 不配时 |
|---|---|---|
| `NEBIUS_API_KEY` | 启用 Nemotron 深度审查 | 仅离线 Linter（功能完整） |
| `NEBIUS_BASE` / `NEBIUS_MODEL` | Nebius 端点 / NVIDIA 模型 | 默认 hackathon 端点 + Nemotron |
| `TAVILY_API_KEY` | 检索增强 | 跳过 |
| `PORT` | Web 端口 | `8000` |

## License

MIT © Zhiyilang — 见 [`LICENSE`](LICENSE)。详见 [`DESIGN.md`](DESIGN.md)。
