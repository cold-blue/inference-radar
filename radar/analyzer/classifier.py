from .llm import analyze_item
from .scorer import keyword_personal_interest, calculate_priority


def analyze_and_score(item, config):
    max_chars = int((config.get("analysis") or {}).get("content_max_chars", 4000))
    result = analyze_item(item, max_chars)

    personal_interest = keyword_personal_interest(
        result,
        config,
    )

    result["personal_interest"] = personal_interest
    result["priority"] = calculate_priority(
        result,
        personal_interest,
    )

    return result
