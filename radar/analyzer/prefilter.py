"""Zero-cost heuristic pre-filter.

Scores items by keyword hits from config `topics` before any LLM call.
Items below `analysis.prefilter.min_score` never reach the LLM; they are
marked as prefiltered in the analyses table so they are not re-examined.

arXiv items bypass the threshold by default (`prefilter.arxiv_bypass`):
they already passed curated arXiv queries, so the query itself is the
pre-filter. They are still scored, which ranks them among GitHub items.
"""

import re

# Obvious noise when present in the title (checked as substrings).
NEGATIVE_TITLE_KEYWORDS = [
    "[docs]", "docs:", "docs(", "doc:", "documentation", "typo",
    "[ci]", "ci:", "bump", "changelog", "readme", "formatting",
    "pre-commit", "lint", "spellcheck", "[test]", "test:", "tests:",
]

# Performance-signal words worth a bonus.
PERF_SIGNAL_WORDS = [
    "perf", "speedup", "faster", "latency", "throughput",
    "benchmark", "optimiz", "accelerat", "efficien",
]

# Collector prefixes like "[PR] vllm-project/vllm: " — stripped before
# scoring so repo names don't pollute title keyword hits.
_PREFIX_RE = re.compile(r"^\[(PR|Release)\]\s+[^:]+:\s*", re.IGNORECASE)


def prefilter_score(item, config):
    """Return a heuristic relevance score for an item (0 = obvious noise)."""
    raw_title = (item.get("title") or "").lower()
    title = _PREFIX_RE.sub("", raw_title)
    text = title + "\n" + (item.get("content") or "")[:2000].lower()

    for neg in NEGATIVE_TITLE_KEYWORDS:
        if neg in title:
            return 0.0

    score = 0.0

    for keywords in (config.get("topics") or {}).values():
        for kw in keywords:
            kw = str(kw).lower()
            if kw in text:
                # Title hits are a much stronger signal than body hits.
                score += 2.0 if kw in title else 1.0

    for word in PERF_SIGNAL_WORDS:
        if word in text:
            score += 1.0

    return score


def passes_prefilter(item, config):
    pf = (config.get("analysis") or {}).get("prefilter") or {}
    if not pf.get("enabled", True):
        return True
    if pf.get("arxiv_bypass", True) and item.get("source") == "arxiv":
        return True
    return prefilter_score(item, config) >= float(pf.get("min_score", 3.0))
