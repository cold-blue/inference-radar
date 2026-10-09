from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import load_config, env
from .db import (
    init_db,
    insert_item,
    get_unanalyzed_items,
    save_analysis,
    get_report_items,
)
from .collectors.github import collect_all as collect_github
from .collectors.arxiv import collect_all as collect_arxiv
from .analyzer.classifier import analyze_and_score
from .analyzer.prefilter import prefilter_score, passes_prefilter
from .report import write_report


def collect():
    config = load_config()
    init_db()

    items = []

    items.extend(
        collect_github(
            config,
            token=env("GITHUB_TOKEN"),
        )
    )

    items.extend(
        collect_arxiv(config)
    )

    inserted = 0

    for item in items:
        if insert_item(item):
            inserted += 1

    return inserted


_PREFILTERED_RESULT = {
    "topics": ["prefiltered"],
    "summary": "Filtered out by keyword prefilter (no LLM call).",
}


def analyze():
    config = load_config()
    init_db()

    analysis_cfg = config.get("analysis") or {}
    max_items = int(analysis_cfg.get("max_items_per_run", 50))
    workers = int(analysis_cfg.get("llm_workers", 5))

    items = get_unanalyzed_items(limit=500)

    # Stage 1: zero-cost keyword prefilter. Noise is marked as analyzed
    # with priority 0 so it never reaches the LLM or the report.
    candidates = []
    skipped = 0
    for item in items:
        d = dict(item)
        if passes_prefilter(d, config):
            candidates.append((prefilter_score(d, config), d))
        else:
            save_analysis(item["id"], _PREFILTERED_RESULT)
            skipped += 1

    # Stage 2: highest-signal first, cap the number of LLM calls.
    candidates.sort(key=lambda x: x[0], reverse=True)
    batch = [d for _, d in candidates[:max_items]]

    print(
        f"[analyze] {len(items)} pending -> "
        f"{skipped} prefiltered, {len(batch)} to LLM"
    )

    count = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(analyze_and_score, item, config): item
            for item in batch
        }
        for fut in as_completed(futures):
            item = futures[fut]
            try:
                result = fut.result()
                save_analysis(item["id"], result)
                count += 1
                print(
                    f"[analyze] {item['title'][:70]} -> "
                    f"{result['priority']}/10"
                )
            except Exception as e:
                print(f"[analyze] failed: {item['title'][:70]}: {e}")

    return count


def report():
    config = load_config()

    rows = get_report_items(
        min_priority=config["analysis"]["min_priority_to_report"],
        limit=config["analysis"]["max_items_in_report"],
    )

    return write_report(rows)


def run_all():
    print("== Collect ==")
    print(f"New items: {collect()}")

    print("\n== Analyze ==")
    print(f"Analyzed: {analyze()}")

    print("\n== Report ==")
    path = report()

    print(f"Report: {path}")
