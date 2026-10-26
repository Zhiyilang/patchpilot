# PatchPilot — MatrixNEXT 2026 提交文档（创意赛道 · 流程自动驾驶）

> 提交时：本文件内容贴入"说明文档"链接（或直接附 GitHub 链接），视频按文末分镜录制（≤3 分钟）。
> 项目仓库：**https://gitee.com/ZhiYIlang/patchpilot**（当前版，2026-10-23 推送，MIT 公开；国内直连）
> 镜像：https://github.com/Zhiyilang/patchpilot（最后推送 2026-10-17，落后 6 天：缺 `BEIJING_OPENSOURCE_DOC.pdf`，5 个文件内容不同，2026-10-23 两侧归档比对实测）

## 一、它解决什么问题（问题）

代码审查是软件流程里最堵的一段：小团队没有专职 review 人，PR 排队几天；
好不容易排到，人工审查又被 bare except、硬编码密钥、可变默认参数这类
**机械可判的问题**占满注意力，真正需要人看的架构问题反而没时间看。

更广的看，这是所有"流程自动驾驶"赛道的共同痛点：**规则明确的部分没有
自动化，需要判断的部分没有腾出时间**。

## 二、方案：把代码审查流程做成自动驾驶

PatchPilot 是一个**代码审查智能体**。粘贴一段代码，它跑完整条闭环：

```
PERCEIVE 识别语言/行数 → LINT 离线 Linter → REASON LLM 深度审查（失败自动回落）
→ RETRIEVE 可选检索增强 → PLAN 合并去重 → EXPLAIN 结论 → RECEIPT 回执
```

### 三个设计决定

1. **双大脑，离线大脑永远在线。**
   第一大脑是**确定性离线 Linter**（12 条真实规则：裸 except、eval/exec 注入、
   硬编码密钥、被吞异常、`== None`、`== True/False`、`type()==`、可变默认参数、
   `import *`、调试 print、TODO/FIXME、超长行），零依赖、零密钥、永远可用。
   第二大脑是 **LLM 深度语义审查**，走任意 OpenAI 兼容端点
   （Nebius Token Factory / MOI Genesis / 本地模型）——**接不接、接哪家，
   都不影响产品可用**。这对"评委点开链接就要看到东西在跑"的评审场景是硬需求。
2. **不只报告，还给补丁。** 对可机械修复的问题（BARE_EXCEPT / EQ_NONE / EQ_BOOL）
   直接生成 before/after diff，人只需要确认。
3. **每条发现都可指认。** 行号 + 证据行原文，没有"AI 觉得这里不好"这种黑箱结论。

### 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 核心决策层 | Python 标准库，**零第三方依赖** | 审计性、可复现、任何机器能跑 |
| LLM 层 | OpenAI 兼容客户端（可插拔） | 不被任何一家模型绑定 |
| 检索层（可选） | Tavily | 补充最佳实践参考，不配则跳过 |
| Web 控制台 | 标准库 HTTP 服务（`server.py`，读 PORT） | 一键演示，无构建步骤 |
| 质量闸门 | `eval.py` 91 条断言 | 每次改动都证明产品没退 |

## 三、创新点（对照评审标准）

- **创新性**：把"确定性规则引擎 + LLM 判断"做成双大脑架构，LLM 是增强而非依赖；
  离线模式不是 demo 补丁，而是一等公民。
- **完成度**：91/91 断言、中英双语 README、CLI + Web 双入口、CI 三版本全绿。
- **技术深度**：自动补丁生成（AST 级改写）、证据引用回执、检索增强合并去重。
- **使用体验**：一条命令出报告；Web 控制台贴代码即出结果；无密钥开箱即用。

## 四、使用说明（评委复现）

```bash
git clone https://github.com/Zhiyilang/patchpilot
cd patchpilot
python -m patchpilot.cli examples/bad_code.py          # 离线审查（无需任何密钥）
python -m patchpilot.cli examples/bad_code.py --html report.html
python eval.py                                         # 91 条断言自证
python server.py                                       # Web 控制台 → http://localhost:8000
```

启用 LLM 深度审查（任一 OpenAI 兼容端点）：

```bash
export NEBIUS_API_KEY=<your-key>        # 或 MOI Genesis key
export NEBIUS_BASE=<openai-compatible-endpoint>
export NEBIUS_MODEL=<model-name>
python -m patchpilot.cli examples/bad_code.py
```

## 五、演示视频分镜（≤3 分钟，中文旁白）

| 时间 | 画面 | 旁白要点 |
|---|---|---|
| 0:00–0:25 | 终端 + PR 列表截图 | "代码审查排队几天，人工审查被 bare except 这类小事占满" |
| 0:25–0:55 | `python -m patchpilot.cli examples/bad_code.py`，报告逐条滚出 | "粘贴代码，秒出报告：每条发现带行号和证据行" |
| 0:55–1:35 | 高亮 before/after diff（BARE_EXCEPT / EQ_NONE 自动补丁） | "能机械修的直接给补丁，人只做确认" |
| 1:35–2:10 | 设置端点 + key 后再跑一次，展示语义级发现；拔掉 key 再跑，展示自动回落离线 Linter | "LLM 是第二大脑，可插拔；不接也能完整工作" |
| 2:10–2:40 | `python eval.py` → 91/91；浏览器打开 Web 控制台贴一段代码 | "91 条断言守着质量；Web 端同一套闭环" |
| 2:40–3:00 | 回执 HTML 高亮 + 仓库首页 | "流程自动驾驶：粘贴即审查，补丁已验证，结论可指认" |

录制工具：`_videotool` 产线已备（跑真命令 → 终端风帧 → x264），可由 AI 生成后用户上传。

## 六、备注

- 项目早于本赛事窗口创建（Nebius × NVIDIA Hackathon 同款载体）；窗口内的增量：
  MOI/Genesis 后端接入 + 中文提交物料 + 本分镜视频。
- 数据合规：创意赛道不涉及企业数据，无需数据合规声明（企业赛道才需要）。
