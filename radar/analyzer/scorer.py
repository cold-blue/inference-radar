def keyword_personal_interest(result, config):
    weights = config.get("personal_interest", {})

    topics = [
        str(x).lower()
        for x in result.get("topics", [])
    ]

    score = 1.0

    for topic in topics:
        for key, weight in weights.items():
            if key.lower() in topic:
                score = max(score, float(weight))

    return score


def calculate_priority(result, personal_interest):
    r = float(result.get("relevance", 0))
    i = float(result.get("impact", 0))
    n = float(result.get("novelty", 0))

    base = (
        0.35 * r +
        0.25 * i +
        0.20 * n
    )

    # Convert personal-interest multiplier into a modest additive bonus.
    bonus = (personal_interest - 1.0) * 2.0

    return round(max(0.0, min(10.0, base + bonus)), 2)
