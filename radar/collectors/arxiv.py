from datetime import datetime, timedelta, timezone
import urllib.parse
import requests
import feedparser


def search_arxiv(query, max_results=12, lookback_days=7):
    encoded = urllib.parse.quote(query)

    url = (
        "https://export.arxiv.org/api/query?"
        f"search_query=all:{encoded}"
        f"&start=0"
        f"&max_results={max_results}"
        f"&sortBy=submittedDate"
        f"&sortOrder=descending"
    )

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    feed = feedparser.parse(response.text)
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    results = []

    for entry in feed.entries:
        published = entry.get("published")
        if not published:
            continue

        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if dt < cutoff:
            continue

        abstract = " ".join(entry.get("summary", "").split())

        results.append({
            "source": "arxiv",
            "source_id": entry.get("id", entry.link),
            "title": entry.title.replace("\n", " ").strip(),
            "url": entry.link,
            "content": (
                f"Authors: {', '.join(a.name for a in entry.get('authors', []))}\n"
                f"Abstract:\n{abstract}"
            ),
            "timestamp": published,
        })

    return results


def collect_all(config):
    results = []
    cfg = config["arxiv"]

    for query in cfg["queries"]:
        try:
            results.extend(
                search_arxiv(
                    query,
                    cfg["max_results_per_query"],
                    cfg["lookback_days"],
                )
            )
        except Exception as e:
            print(f"[arXiv] failed: {query}: {e}")

    # De-duplicate by source_id
    unique = {}
    for item in results:
        unique[item["source_id"]] = item

    return list(unique.values())
