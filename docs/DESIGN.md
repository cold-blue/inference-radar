# Inference Radar 设计文档

> 版本：V0.1 · 更新日期：2026-10-09

## 1. 项目定位

Inference Radar 是一个**个人化的 LLM 推理加速领域情报雷达**：

每天自动从 GitHub / arXiv 等信息源采集最新动态，用 LLM 以"推理加速工程师"的视角筛选、评分、总结，产出一份"真正愿意看"的 Markdown 日报。

**设计原则**

- 不做大而全：第一版不做 Web UI、不做知识图谱、不做向量数据库
- 先跑通核心闭环：`自动发现 → 去重 → LLM 分析 → 个性化排序 → 日报`
- 原始数据与分析结果全部落盘（SQLite），可追溯、可重跑
- 信息源不是核心资产，**长期资产是结构化的个人技术数据库**

## 2. 整体架构

```text
                 ┌────────────────────────────────────────────┐
                 │                config.yaml                  │
                 │  watchlist / queries / topics / weights    │
                 └────────────────────────────────────────────┘
                                      │
 GitHub (PR/Release) ──┐               ▼
 arXiv (8 组查询)     ──┼─► Collect ─► ┌─────────┐ ─► Prefilter ─► Analyze ─► Rank ─► Report
 RSS (预留)           ──┘   去重       │ SQLite  │    关键词初筛    (LLM)     加权    (Markdown)
                                      │ items   │    (零 token)    并发
                                      │ analyses│
                                      └─────────┘
```

**六个阶段**

| 阶段 | 入口 | 说明 |
|------|------|------|
| Collect | `python -m radar collect` | 多源采集，`(source, source_id)` 去重入库 |
| Prefilter | （分析内完成） | 关键词启发式打分，零 token 剔除噪音 |
| Analyze | `python -m radar analyze` | 仅对通过初筛的高信号条目调用 LLM（并发） |
| Rank | （分析内完成） | LLM 评分 × 个人兴趣权重 → priority |
| Report | `python -m radar report` | 按 priority 分档生成 Markdown 日报 |
| Run | `python -m radar run` | 采集 → 分析 → 报告串行执行 |

## 3. 项目结构

```text
inference-radar/
├── config.yaml              # 全部业务配置（仓库、查询、主题、权重、阈值）
├── .env                     # API key / base_url / model / GitHub token
├── requirements.txt
├── radar/
│   ├── __main__.py          # python -m radar 入口
│   ├── cli.py               # CLI 子命令：init-db / collect / analyze / report / run
│   ├── config.py            # 加载 config.yaml + .env
│   ├── db.py                # SQLite 连接、建表、增删查
│   ├── pipeline.py          # 编排 collect → analyze → report
│   ├── report.py            # 生成 Markdown 日报
│   ├── collectors/
│   │   ├── github.py        # GitHub PR / Release 采集
│   │   ├── arxiv.py         # arXiv 论文采集
│   │   └── rss.py           # 预留：RSS / Blog 信息源
│   └── analyzer/
│       ├── llm.py           # OpenAI 兼容 API 调用
│       ├── prompts.py       # system prompt + user prompt
│       ├── prefilter.py     # 关键词启发式预过滤（零 token）
│       ├── classifier.py    # LLM 分析 + 打分编排
│       └── scorer.py        # 个人兴趣权重 + priority 计算
├── data/radar.db            # SQLite（原始条目 + 分析结果）
└── reports/YYYY-MM-DD.md    # 每日输出
```

## 4. 配置体系

### 4.1 config.yaml

| 配置块 | 内容 |
|--------|------|
| `github.repositories` | 11 个监控仓库：vllm、sglang、TensorRT-LLM、flashinfer、cutlass、triton、pytorch、nccl、ai-dynamo/dynamo、DeepEP、DeepGEMM |
| `github.lookback_hours` | 48 小时回看窗口 |
| `github.max_items_per_repo` | 每仓库每次最多 30 条 |
| `arxiv.queries` | 8 组查询：LLM inference / serving、KV cache、speculative decoding、MoE inference、GPU kernel、distributed inference、quantization |
| `arxiv.lookback_days` | 7 天窗口，每组查询最多 12 条 |
| `topics` | 9 个主题域的关键词表：runtime / attention / moe / speculative / distributed / kernel / compiler / quantization / hardware |
| `personal_interest` | 个人兴趣权重：pd_disaggregation / kv_cache / moe = 1.5，cuda_graph / kernel / inference_runtime = 1.4，speculative = 1.2，quantization = 1.1，generic_llm = 0.5 |
| `analysis.min_priority_to_report` / `max_items_in_report` | 报告阈值 5 分 / 最多 20 条 |
| `analysis.max_items_per_run` | 每轮 LLM 分析条数上限（预过滤后取 Top-N），默认 50 |
| `analysis.llm_workers` | LLM 并发请求数，默认 5 |
| `analysis.content_max_chars` | 送入 LLM 的 content 截断长度，默认 4000 |
| `analysis.prefilter` | 关键词预过滤：`enabled`、`min_score`（默认 3.0）、`arxiv_bypass`（arXiv 条目免初筛） |

### 4.2 .env

```bash
OPENAI_API_KEY=        # OpenAI 兼容 API key（必填）
OPENAI_BASE_URL=       # 兼容端点，如 https://api.deepseek.com（可选）
OPENAI_MODEL=          # 分析用模型，默认 gpt-5-mini
GITHUB_TOKEN=          # 提高 GitHub API 限流（可选，未配置为 60 次/小时）
```

> ⚠️ 注意：`OPENAI_BASE_URL` 若留空必须**整行删除或注释**，不能写成 `OPENAI_BASE_URL=`（空值）。
> OpenAI SDK 会直接读取该环境变量，空字符串会覆盖默认端点导致
> `Request URL is missing an 'http://' or 'https://' protocol` 错误。

## 5. 采集层（Collector）

统一输出字段：`source / source_id / title / url / content / timestamp`。

### 5.1 GitHub Collector（[github.py](radar/collectors/github.py)）

每个仓库 2 个 REST API 调用：

- **Pull Requests**：`GET /repos/{repo}/pulls?state=all&sort=updated&direction=desc`，按 `updated_at` 过滤 48h 窗口；content 含 PR 号、状态、draft 标记、正文
- **Releases**：`GET /repos/{repo}/releases`，按 `published_at` 过滤

`source_id` 形如 `pr:vllm-project/vllm:12345` / `release:{repo}:{id}`，天然幂等。

已知取舍：按 `updated_at` 排序抓取意味着"老 PR 有新评论"也会进入雷达（噪音），但保证了 merged/release 事件不会漏；精确 merged-PR 追踪列入演进路线。

### 5.2 arXiv Collector（[arxiv.py](radar/collectors/arxiv.py)）

- 使用 arXiv export API：`search_query=all:{query}&sortBy=submittedDate&sortOrder=descending`
- 逐查询抓取后按 `source_id`（arXiv id）跨查询去重
- content = 作者列表 + 摘要

### 5.3 RSS Collector

占位文件，预留给厂商博客 / 技术媒体，V0.2 接入。

### 5.4 去重

数据库层 `UNIQUE(source, source_id)` + `INSERT OR IGNORE`，采集端可重复跑，天然幂等。

## 6. 存储层（[db.py](radar/db.py)）

SQLite 单文件 `data/radar.db`，两张表：

### items —— 原始条目

| 列 | 说明 |
|----|------|
| `id` | 自增主键 |
| `source` | `github` / `arxiv` / ... |
| `source_id` | 源内唯一 ID，与 source 组成唯一约束 |
| `title` / `url` / `content` / `timestamp` | 原始内容 |
| `created_at` | 入库时间 |

### analyses —— LLM 分析结果（与 items 1:1）

| 列 | 说明 |
|----|------|
| `item_id` | 主键，外键 → items.id |
| `category` | LLM 分类：`product`（新产品/重大技术）/ `paper` / `pr` / `other`，驱动报告分板块 |
| `org` | 主导机构（公司/高校/社区），如 NVIDIA、MIT、vLLM 社区 |
| `venue` | 论文发表 venue（仅论文；未知为 arXiv preprint），用于顶会/获奖标记 |
| `topics` | LLM 判定的主题标签（逗号分隔） |
| `relevance` / `impact` / `novelty` | LLM 评分（1-10） |
| `personal_interest` | 个人兴趣权重（关键词命中 config） |
| `priority` | 最终优先级（0-10） |
| `summary` / `why_it_matters` / `technical_details` / `what_changed` / `implementation` | 结构化总结（简体中文） |
| `hardware` / `related_projects` | 涉及硬件 / 关联项目 |
| `worth_deep_dive` | 是否值得深读（0/1） |

设计要点：**原始数据与分析结果分离**。原始条目不可变，分析可重跑（`INSERT OR REPLACE` 覆盖）；换模型 / 改 prompt 后可清空 analyses 重新分析而不丢原始数据。新增列通过 `init_db` 内的轻量迁移（`PRAGMA table_info` + `ALTER TABLE`）自动补齐。

## 7. 分析层（Analyzer）

### 7.1 LLM Prompt 设计（[prompts.py](radar/analyzer/prompts.py)）

核心思想：**不是总结新闻，而是以推理加速工程师视角判断技术重要性**。

- 角色：expert LLM inference acceleration engineer
- 输出：严格 JSON（`response_format={"type": "json_object"}`），`temperature=0.1`
- **语言**：所有自然语言字段强制简体中文，专有名词（项目/硬件/技术/会议名）保留原文
- **分类**：`category`（product / paper / pr / other）驱动日报分板块；`org` 记录主导机构；论文填 `venue`，顶会/获奖置 `worth_deep_dive`
- 加分项：新推理技术、显著性能提升、运行时架构变化、新 kernel、新调度、新通信、新硬件、影响 vLLM/SGLang/TRT-LLM、生产相关、开源实现
- 减分项：普通 AI 新闻、无推理影响的模型发布、营销话术、小 bug 修复、仅文档变更
- user prompt 截断 content 至 `content_max_chars`（默认 4000）字符

### 7.2 打分与优先级（[scorer.py](radar/analyzer/scorer.py)）

LLM 给出三维评分：`relevance (R)`、`impact (I)`、`novelty (N)`。

个人兴趣系数 `U` 由**关键词匹配**得出：LLM 返回的 topics 命中 `config.personal_interest` 的 key 时取最大权重（默认 1.0，最高 1.5）。

最终优先级（代码实现公式）：

```text
priority = clip( 0.35×R + 0.25×I + 0.20×N + (U − 1.0) × 2.0, 0, 10 )
```

> 注：早期构想为 `0.35R + 0.25I + 0.20N + 0.20U` 的纯加权和，实现时改为
> "三维加权和 + 兴趣加性修正（最多 +1 分）"，避免兴趣项稀释技术评分的主导地位，
> 同时保证同技术水平下个人关注的主题（PD 分离 / KV Cache / MoE 等）稳定上浮。

效果：同一 relevance 下，个人兴趣高的主题 priority 更高 —— 日报逐渐"懂你"。

### 7.3 预过滤（[prefilter.py](radar/analyzer/prefilter.py)）

LLM 调用是唯一的成本与延迟来源，因此在其之前加一层**零 token 的启发式初筛**：

- **打分**：title + content 前 2000 字符，命中 `config.topics` 关键词计分（title 命中 ×2）；命中性能信号词（perf / speedup / latency / throughput / benchmark / optimiz…）加分；title 命中噪音词（docs / typo / CI / bump / changelog / test…）直接 0 分
- **阈值**：`prefilter.min_score`（默认 3.0）以下不进 LLM，写入 `topics=prefiltered, priority=0` 的分析记录——不进报告、不重审、可追溯
- **arXiv 豁免**：arXiv 条目已通过精选查询构造（查询本身即初筛），默认免于阈值过滤（`arxiv_bypass`），但仍参与打分排序
- **排序**：通过初筛的条目按启发式分数降序，每轮只取 Top `max_items_per_run`（默认 50）送入 LLM——高信号优先，token 预算可控
- 采集前缀（`[PR] repo:`）在打分前剥离，避免仓库名污染关键词命中

### 7.4 执行方式

- 每轮处理最多 500 条未分析条目：先全量初筛（免费），LLM 只分析 Top 50（可配）
- **并发分析**：`ThreadPoolExecutor`，`llm_workers`（默认 5）路并发；单条失败打印错误不中断批次
- SQLite 写侧 `PRAGMA busy_timeout` 容忍并发写入；每条分析独立落库，中断重跑无副作用
- content 截断至 `content_max_chars`（默认 4000）字符，控制单条 token 消耗

## 8. 报告层（[report.py](radar/report.py)）

日报**全中文**，取 `priority ≥ 5` 的条目（最多 30 条），按 LLM 分类组织为三个板块（板块内按 priority 降序）：

| 板块 | 内容 | 展示方式 |
|------|------|----------|
| 🚀 新产品 / 技术动态 | `category=product`：产品级发布、重大技术（多来自大公司/高校/主流社区），≤8 条 | 完整展开：发生了什么 / 为什么重要 / 技术细节 / 变化 / 实现 / 硬件 / 相关项目 |
| 📄 论文 | `category=paper`，≤12 条 | priority ≥6 中等展开（核心贡献 + 意义 + venue/机构）；其余一行简评；venue 命中顶会/获奖关键词加 ⭐ |
| 🔧 PR 动态 | `category=pr`，≤20 条 | **priority ≥8 的重要 feature 才完整展开**；其余进入「PR 速览」一行简评（标题链接 + 80 字内总结） |

老数据无 `category` 时按来源回退推断（arxiv→paper，Release→product，其余→pr）。输出 `reports/YYYY-MM-DD.md`，同日重跑覆盖。

## 9. 运行与部署

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# 编辑 .env

python -m radar run        # 一键跑全 pipeline
```

cron 每日 08:00：

```cron
0 8 * * * cd /path/to/inference-radar && .venv/bin/python -m radar run >> radar.log 2>&1
```

## 10. 试跑验证记录（2026-10-09）

| 项目 | 结果 |
|------|------|
| 采集 | 314 条：GitHub 252（11 仓库全覆盖）+ arXiv 62 |
| 预过滤 | 227 条待分析 → 39 条零成本剔除（docs/CI/test/build 等），50 条进入 LLM |
| LLM 分析 | 50 条 / 约 3 分钟（5 并发）；对照初版串行全量分析（100 条约 45 分钟），**速度提升 ~15×，LLM 调用减半，单条 token 降至 1/4** |
| 评分分布 | ≥8: 5 条 / 6-8: 48 条 / 5-6: 23 条 / <5: 61 条，区分度健康 |
| 日报 | `reports/2026-10-09.md`，Must Read 5 条（Rubin locality-domain、ROCm mono decode、DSV4 CP prefill、FlashInfer sparse attention 等） |
| 中文分板块日报 | 同日二版：prompt 中文化 + category/org/venue 分类，报告重组为「🚀 产品技术 / 📄 论文 / 🔧 PR」三板块，PR 默认一行简评、P≥7.5 才展开；仅重析报告窗口内 45 条，旧英文分析不动 |

试跑中发现并修复的问题：

1. `NVIDIA/ai-dynamo` 404 → 正确仓库为 `ai-dynamo/dynamo`（已修 config.yaml）
2. `.env` 中 `OPENAI_BASE_URL=`（空值）被 OpenAI SDK 读取并覆盖默认端点，报 `Request URL is missing protocol` → base_url 必须填真实值或整行删除
3. 初版全量串行分析过慢、token 浪费 → 引入预过滤 + 并发 + 截断（本次改进）

## 11. 已知限制（V0.1）

1. **GitHub 噪音**：按 `updated_at` 抓取，老 PR 新评论也会入库；无法区分 merged / closed / 仍在 review
2. **无 commit 级追踪**：重要 commit（非 PR）抓不到
3. **预过滤有误判风险**：关键词表维护质量直接影响召回（可通过降低 `min_score` 或关闭 `arxiv_bypass` 以外的豁免缓解；被误滤条目标记为 `prefiltered`，可清表重审）
4. **无跨源关联**：同一项工作的 paper / PR / release 各自成条，未关联
5. **无变化检测**：不能与昨日对比得出"项目显著变更"
6. **兴趣权重静态**：仅关键词匹配，不随阅读行为学习
7. **报告无 Runtime Updates 表格与 Research Ideas 板块**（原始构想中有，V0.1 未实现）

## 12. 演进路线

按价值排序：

1. **GitHub merged PR / commit 精确追踪**（Events API 或 GraphQL，去噪）
2. **RSS / 厂商博客 / 媒体信息源**（NVIDIA / PyTorch / vLLM blog 等）
3. **自动 Change Detection**：对比昨日与今日，生成"项目显著变更"摘要
4. **Paper → PR → Release → Benchmark 关联**
5. **Benchmark 数据库**：H100/B200 × batch × ISL/OSL × TP/EP → TTFT/TPOT，可查询
6. **个人研究主题追踪**：PD / KV Cache / MoE / CUDA Graph 的专项时间线
7. **Knowledge Graph + Research Dashboard**（长期）：分层 Model / Algorithm / Runtime / Kernel / Hardware / Benchmark，形成可查询的个人技术数据库

---

*本文档描述 V0.1 实现现状，演进路线为指导方向而非承诺。*
