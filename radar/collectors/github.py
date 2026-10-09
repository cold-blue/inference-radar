from datetime import datetime, timedelta, timezone
import requests


API = "https://api.github.com"


def _headers(token):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(url, token, params=None):
    r = requests.get(
        url,
        headers=_headers(token),
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def collect_repo(repo, lookback_hours=48, max_items=30, token=None):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    items = []

    # Pull requests
    prs = _get(
        f"{API}/repos/{repo}/pulls",
        token,
        {"state": "all", "sort": "updated", "direction": "desc", "per_page": 30},
    )

    for pr in prs:
        updated = datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00"))
        if updated < cutoff:
            continue

        items.append({
            "source": "github",
            "source_id": f"pr:{repo}:{pr['number']}",
            "title": f"[PR] {repo}: {pr['title']}",
            "url": pr["html_url"],
            "content": (
                f"Repository: {repo}\n"
                f"PR #{pr['number']}\n"
                f"State: {pr['state']}\n"
                f"Draft: {pr.get('draft')}\n"
                f"Body:\n{pr.get('body') or ''}"
            ),
            "timestamp": pr["updated_at"],
        })

    # Releases
    releases = _get(
        f"{API}/repos/{repo}/releases",
        token,
        {"per_page": 20},
    )

    for release in releases:
        published = release.get("published_at") or release.get("created_at")
        if not published:
            continue

        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if dt < cutoff:
            continue

        items.append({
            "source": "github",
            "source_id": f"release:{repo}:{release['id']}",
            "title": f"[Release] {repo}: {release['name'] or release['tag_name']}",
            "url": release["html_url"],
            "content": release.get("body") or "",
            "timestamp": published,
        })

    items.sort(key=lambda x: x["timestamp"], reverse=True)
    return items[:max_items]


def collect_all(config, token=None):
    all_items = []

    gh = config["github"]

    for repo in gh["repositories"]:
        try:
            all_items.extend(
                collect_repo(
                    repo,
                    gh["lookback_hours"],
                    gh["max_items_per_repo"],
                    token,
                )
            )
        except Exception as e:
            print(f"[GitHub] failed: {repo}: {e}")

    return all_items
