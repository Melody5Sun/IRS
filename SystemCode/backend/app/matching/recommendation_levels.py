RECOMMENDED_THRESHOLD = 4.0
HIGHLY_RECOMMENDED_THRESHOLD = 16.0


def recommendation_level(score: float) -> str:
    if score >= HIGHLY_RECOMMENDED_THRESHOLD:
        return "highly_recommended"
    if score >= RECOMMENDED_THRESHOLD:
        return "recommended"
    return "limited_match"


def recommendation_level_rank(score: float) -> int:
    return {
        "limited_match": 0,
        "recommended": 1,
        "highly_recommended": 2,
    }[recommendation_level(score)]
