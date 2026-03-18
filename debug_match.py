import re
from typing import Optional

_BASE_KEYWORDS = {
    1: ["not working", "broken"],
    6: ["computer", "wifi"]
}

KEYWORD_TYPE_MAP = {
    1: ["not working", "broken", "working", "issue", "facing"],
    6: ["computer", "wifi", "working", "connection"]
}

def _keyword_match(message: str) -> Optional[int]:
    msg_lower = message.lower()
    scores = {}

    for type_num, keywords in KEYWORD_TYPE_MAP.items():
        base_kws = set(_BASE_KEYWORDS.get(type_num, []))
        print(f"Checking Type {type_num}, base_kws: {base_kws}")
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', msg_lower):
                point = 20 if kw in base_kws else 1
                scores[type_num] = scores.get(type_num, 0) + point
                print(f"  Match: '{kw}' -> +{point} points")

    print(f"Final Scores: {scores}")
    if not scores: return None
    max_score = max(scores.values())
    top_types = [t for t, score in scores.items() if score == max_score]
    return top_types[0]

test_msg = "computer wifi not working facing issue"
result = _keyword_match(test_msg)
print(f"Result: {result}")
