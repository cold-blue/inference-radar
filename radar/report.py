from datetime import datetime
from pathlib import Path

from .config import ROOT

# 顶会/奖项关键词，命中则在论文标题前加 ⭐
TOP_VENUE_KEYWORDS = (
    "sosp", "osdi", "asplos", "isca", "micro", "hpca", "sigmod", "vldb",
    "eurosys", "mlsys", "neurips", "icml", "iclr", "pldi", "atc",
    "best paper", "award", "获奖",
)

# 各板块条数上限
MAX_PRODUCTS = 8
MAX_PAPERS = 12
MAX_PRS = 20

# PR 展开阈值：达到该 priority 的重要 feature 才展开，其余简评
PR_EXPAND_PRIORITY = 7.5
# 论文展开阈值
PAPER_EXPAND_PRIORITY = 6.0


def _bullets(value):
    if not value:
        return "无"
    if isinstance(value, str):
        return value
    return ", ".join(value)


def _field(r, name, default=""):
    try:
        v = r[name]
    except (KeyError, IndexError):
        return default
    return v if v is not None else default


def _category(r):
    """LLM 分类优先；老数据按来源回退推断。"""
    cat = _field(r, "category")
    if cat:
        return cat
    if r["source"] == "arxiv":
        return "paper"
    if (r["title"] or "").startswith("[Release]"):
        return "product"
    return "pr"


def _is_top_venue(r):
    venue = _field(r, "venue").lower()
    return any(k in venue for k in TOP_VENUE_KEYWORDS)


def _expanded_block(idx, r):
    """完整展开块：新产品/技术、重要 PR 使用。"""
    return [
        f"### {idx}. {r['title']}",
        "",
        f"**Priority:** {r['priority']}/10 | **机构:** {_field(r, 'org') or '—'}",
        "",
        f"**Topics:** `{r['topics']}`",
        "",
        f"**链接:** {r['url']}",
        "",
        f"**发生了什么:** {_field(r, 'summary')}",
        "",
        f"**为什么重要:** {_field(r, 'why_it_matters')}",
        "",
        f"**技术细节:** {_field(r, 'technical_details')}",
        "",
        f"**变化:** {_field(r, 'what_changed')}",
        "",
        f"**实现:** {_field(r, 'implementation')}",
        "",
        f"**硬件:** {_bullets(_field(r, 'hardware'))} | **相关项目:** {_bullets(_field(r, 'related_projects'))}",
        "",
    ]


def _paper_block(idx, r):
    """论文中等块：贡献 + 意义，顶会/获奖加 ⭐。"""
    star = "⭐ " if _is_top_venue(r) else ""
    venue = _field(r, "venue") or "arXiv preprint"
    return [
        f"### {idx}. {star}{r['title']}",
        "",
        f"**Priority:** {r['priority']}/10 | **Venue:** {venue} | **机构:** {_field(r, 'org') or '—'}",
        "",
        f"**链接:** {r['url']}",
        "",
        f"**核心贡献:** {_field(r, 'summary')} {_field(r, 'technical_details')}",
        "",
        f"**为什么重要:** {_field(r, 'why_it_matters')}",
        "",
    ]


def _one_liner(r):
    """简评一行：标题 + 链接 + 一句话总结。"""
    return f"- [{r['title']}]({r['url']}) — {_field(r, 'summary')} *(P {r['priority']})*"


def generate_report(rows):
    today = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"# LLM Inference Radar — {today}",
        "",
        "> 面向 LLM 推理加速工程师的个人技术雷达日报。",
        "",
        "---",
        "",
    ]

    products, papers, prs = [], [], []
    for r in rows:
        cat = _category(r)
        if cat == "product":
            products.append(r)
        elif cat == "paper":
            papers.append(r)
        else:
            prs.append(r)

    # rows 已按 priority 降序；各板块截断到上限
    products = products[:MAX_PRODUCTS]
    papers = papers[:MAX_PAPERS]
    prs = prs[:MAX_PRS]

    # ---- 板块一：新产品 / 技术动态 ----
    lines += ["# 🚀 新产品 / 技术动态", ""]
    if not products:
        lines += ["今日无产品级动态。", ""]
    for i, r in enumerate(products, 1):
        lines += _expanded_block(i, r)

    # ---- 板块二：论文 ----
    lines += ["---", "", "# 📄 论文", ""]
    if not papers:
        lines += ["今日无值得关注的论文。", ""]
    expanded_papers = [r for r in papers if r["priority"] >= PAPER_EXPAND_PRIORITY]
    brief_papers = [r for r in papers if r["priority"] < PAPER_EXPAND_PRIORITY]
    for i, r in enumerate(expanded_papers, 1):
        lines += _paper_block(i, r)
    if brief_papers:
        lines += ["**其他论文速览**", ""]
        for r in brief_papers:
            lines.append(_one_liner(r))
        lines.append("")

    # ---- 板块三：PR 动态 ----
    lines += ["---", "", "# 🔧 PR 动态", ""]
    if not prs:
        lines += ["今日无值得关注的 PR。", ""]
    expanded_prs = [r for r in prs if r["priority"] >= PR_EXPAND_PRIORITY]
    brief_prs = [r for r in prs if r["priority"] < PR_EXPAND_PRIORITY]
    if expanded_prs:
        lines += ["## 重点 Feature", ""]
        for i, r in enumerate(expanded_prs, 1):
            lines += _expanded_block(i, r)
    if brief_prs:
        lines += ["## PR 速览", ""]
        for r in brief_prs:
            lines.append(_one_liner(r))
        lines.append("")

    return "\n".join(lines)


def write_report(rows):
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)

    path = reports / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    path.write_text(generate_report(rows), encoding="utf-8")

    return path
