"""Production complaint classifier based on the new_classifier workflow."""

import json
import os
import re
import time
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from google import genai

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer
    from nltk.tokenize import word_tokenize
except ImportError:  # pragma: no cover
    nltk = None
    stopwords = None
    WordNetLemmatizer = None
    word_tokenize = None

from app.chatbot import models
from app.chatbot.db import SessionLocal
from app.chatbot.extractor import search_resource_candidates

load_dotenv()

TYPE_NAMES = {
    0: "Miscellaneous",
    1: "Equipment",
    2: "Facility",
    3: "Safety",
    4: "Process",
    5: "HR",
    6: "IT",
    7: "Purchase",
    8: "Training",
    9: "Inventory",
    10: "Admin",
}
VALID_TYPES = set(TYPE_NAMES.keys())

TYPE_NAME_TO_ID = {
    "miscellaneous": 0,
    "misc": 0,
    "other": 0,
    "unknown": 0,
    "equipment": 1,
    "facility": 2,
    "safety": 3,
    "process": 4,
    "hr": 5,
    "it": 6,
    "purchase": 7,
    "training": 8,
    "inventory": 9,
    "admin": 10,
}

CATEGORY_TYPE_MAP: dict[str, int] = {
    "De humidifiers": 2,
    "DG Set": 2,
    "AC": 2,
    "AHU": 2,
    "Chiller": 2,
    "Exhaust Blower": 2,
    "UPS": 2,
    "N2 Plant": 2,
    "Lithography": 1,
    "Deposition": 1,
    "Etch": 1,
    "Characterization": 1,
    "Metrology": 1,
    "Thermal": 1,
    "Implant": 1,
    "CMP": 1,
    "Wet Process": 1,
    "Safety": 3,
    "Process": 4,
}

_BASE_KEYWORDS: dict[int, list[str]] = {
    1: ["equipment", "instrument", "device", "tool", "repair", "maintenance", "machine", "broken", "malfunction"],
    2: ["ac", "air conditioning", "hvac", "ahu", "chiller", "dg set", "ups", "generator", "blower", "dehumidifier"],
    3: ["fire", "smoke", "hazard", "safety", "accident", "emergency", "spill", "gas leak", "alarm", "detector"],
    4: ["process", "recipe", "parameter", "wafer", "yield", "sop", "uniformity", "contamination"],
    5: ["salary", "payroll", "leave", "attendance", "holiday", "hr", "reimbursement", "appraisal", "promotion", "office", "recruitment", "letter"],
    6: ["laptop", "computer", "printer", "wifi", "internet", "network", "vpn", "email", "password", "software", "login"],
    7: ["purchase", "procurement", "order", "vendor", "supplier", "invoice", "quote", "chemical", "consumable", "spare"],
    8: ["training", "workshop", "course", "seminar", "certification", "orientation", "session"],
    9: ["inventory", "stock", "missing item", "spare parts", "shortage", "out of stock", "reorder", "asset"],
    10: ["admin", "permission", "access", "approval", "policy", "document", "gate pass", "certificate", "noc"],
}
KEYWORD_TYPE_MAP: dict[int, list[str]] = {k: list(v) for k, v in _BASE_KEYWORDS.items()}

LOCAL_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "with", "for", "from", "this", "that",
    "there", "here", "have", "has", "had", "been", "being", "was", "were", "is",
    "are", "am", "to", "of", "in", "on", "at", "near", "inside", "issue", "problem",
    "complaint", "please", "kindly", "help", "need", "want", "very", "too", "so",
    "not", "working", "work", "broken", "faulty", "slow", "down", "up", "again",
}
GENERIC_RESOURCE_TERMS = {
    "issue", "problem", "complaint", "equipment", "machine", "device", "resource",
    "tool", "system", "lab", "room", "area",
}
PHYSICAL_SIGNAL_TERMS = {
    "equipment", "instrument", "device", "tool", "machine", "hardware",
    "facility", "resource", "tv", "screen", "monitor", "microscope", "printer",
    "furnace", "oven", "reactor",
    "ups", "ahu", "chiller", "generator", "blower", "detector", "alarm", "sensor",
    "wafer", "process", "recipe", "chamber", "pump", "valve", "gas", "leak",
    "lithography", "etch", "deposition", "cmp",
}
ABSTRACT_SIGNAL_TYPES = (5, 6, 7, 8, 9, 10)
RESOURCE_TOKEN_SET: set[str] = set()
RESOURCE_PHRASE_SET: set[str] = set()

_gemini_client = None
GEMINI_MODEL = "gemini-2.5-flash"
IT_KEYWORD_SET: set[str] = set()
_gemini_backoff_until = 0.0
IT_KEYWORD_BLACKLIST = {
    "load",
    "feature",
    "product",
    "feedback",
    "marketing",
    "organization",
    "campaign",
    "account",
}


def _get_gemini():
    global _gemini_backoff_until
    if time.time() < _gemini_backoff_until:
        return None
    global _gemini_client
    if _gemini_client is None:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key or api_key == "your_gemini_api_key_here":
            return None
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _set_gemini_backoff(seconds: float = 60.0) -> None:
    global _gemini_backoff_until
    _gemini_backoff_until = max(_gemini_backoff_until, time.time() + seconds)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        cleaned = item.strip().lower()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _tokenize_simple(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text).lower())


def _build_resource_phrases(tokens: list[str]) -> set[str]:
    phrases = set()
    for size in (3, 2):
        for idx in range(len(tokens) - size + 1):
            phrase = " ".join(tokens[idx:idx + size]).strip()
            if phrase:
                phrases.add(phrase)
    return phrases


def _load_physical_lookup_vocabulary() -> None:
    global RESOURCE_TOKEN_SET, RESOURCE_PHRASE_SET
    if RESOURCE_TOKEN_SET or RESOURCE_PHRASE_SET:
        return

    db = SessionLocal()
    try:
        sources = [
            db.query(models.EqpProcessResource.name).filter(models.EqpProcessResource.activation_status == 1).all(),
            db.query(models.FacilityResource.name).filter(models.FacilityResource.activation_status == 1).all(),
            db.query(models.SafetyDevice.device_name).filter(models.SafetyDevice.isworking == 1).all(),
        ]

        token_set = set()
        phrase_set = set()
        for rows in sources:
            for row in rows:
                value = row[0]
                if not value:
                    continue
                tokens = [t for t in _tokenize_simple(value) if len(t) > 1 and t not in LOCAL_STOP_WORDS]
                token_set.update(tokens)
                phrase_set.update(_build_resource_phrases(tokens))

        RESOURCE_TOKEN_SET = token_set
        RESOURCE_PHRASE_SET = phrase_set
    except Exception as exc:
        print(f"[CLASSIFIER] Physical vocabulary load failed: {exc}")
    finally:
        db.close()


def _nltk_stop_words() -> set[str]:
    if stopwords is None:
        return set()
    try:
        return set(stopwords.words("english"))
    except LookupError:
        return set()


def _tokenize_text(text: str) -> list[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    if word_tokenize is None:
        return re.findall(r"[a-z0-9]+", cleaned)
    try:
        return word_tokenize(cleaned)
    except LookupError:
        return re.findall(r"[a-z0-9]+", cleaned)


def _normalize_token(token: str) -> str:
    token = token.lower().strip()
    if WordNetLemmatizer is not None:
        try:
            return WordNetLemmatizer().lemmatize(token)
        except LookupError:
            pass
    if len(token) > 4 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 3 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 3 and token.endswith("es"):
        return token[:-2]
    if len(token) > 2 and token.endswith("s"):
        return token[:-1]
    return token


def preprocess(text: str) -> list[str]:
    stop_words = LOCAL_STOP_WORDS | _nltk_stop_words()
    words = _tokenize_text(text)
    normalized = []
    for word in words:
        norm = _normalize_token(word)
        if len(norm) < 2 or norm in stop_words:
            continue
        normalized.append(norm)
    return normalized


def extract_keywords(words: list[str]) -> list[str]:
    if nltk is None:
        return words
    try:
        pos_tags = nltk.pos_tag(words)
        return [word for word, pos in pos_tags if pos.startswith(("NN", "JJ", "VB"))]
    except LookupError:
        return words


def normalize(words: list[str]) -> list[str]:
    return [_normalize_token(word) for word in words]


def generate_phrases(words: list[str], max_n: int = 3) -> list[str]:
    phrases = []
    seen = set()
    for n in range(max_n, 0, -1):
        for idx in range(len(words) - n + 1):
            phrase = " ".join(words[idx:idx + n]).strip()
            if phrase and phrase not in seen:
                seen.add(phrase)
                phrases.append(phrase)
    return phrases


@lru_cache(maxsize=256)
def _extract_with_gemini(message: str) -> dict | None:
    try:
        client = _get_gemini()
        if not client:
            return None

        prompt = f"""Extract the most important complaint words from this user message for downstream database lookup.

Rules:
- Focus on the affected resource/equipment words, issue words, and any explicit location.
- Prefer short concrete phrases, not full sentences.
- Do not invent anything.
- If no clear location is present, return null for location_name.

Return valid JSON only:
{{
  "important_terms": ["term1", "term2"],
  "important_phrases": ["phrase1", "phrase2"],
  "resource_name": "best resource phrase or null",
  "location_name": "location or null"
}}

Message: "{message}"
"""
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        result = response.text.strip()
        if result.startswith("```"):
            parts = result.split("```")
            if len(parts) >= 3:
                result = parts[1]
                if result.lower().startswith("json"):
                    result = result[4:].strip()
        extracted = json.loads(result)
        return {
            "important_terms": _dedupe_preserve_order([str(x) for x in extracted.get("important_terms", [])]),
            "important_phrases": _dedupe_preserve_order([str(x) for x in extracted.get("important_phrases", [])]),
            "resource_name": extracted.get("resource_name"),
            "location_name": extracted.get("location_name"),
        }
    except Exception as exc:
        if "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc):
            _set_gemini_backoff(120.0)
        print(f"[CLASSIFIER] Gemini term extraction error: {exc}")
        return None


def _extract_location_hint(message: str) -> str | None:
    match = re.search(
        r"\b(?:in|at|near|inside)\s+([a-z0-9][a-z0-9\s\-]{1,40}?)(?=\s+(?:is|has|was|were|with|not|very|too)\b|[.,!?]|$)",
        message.lower(),
    )
    if not match:
        return None
    location = match.group(1).strip(" .,!?:;")
    if location in {"lab", "the lab", "room", "area", "the room", "the area"}:
        return None
    return location or None


def _best_resource_phrase(terms: list[str]) -> str | None:
    phrases = generate_phrases(terms)
    for phrase in phrases:
        words = phrase.split()
        if any(word in GENERIC_RESOURCE_TERMS for word in words):
            continue
        if len(phrase) >= 3:
            return phrase
    for term in terms:
        if term not in GENERIC_RESOURCE_TERMS:
            return term
    return None


def _has_hard_physical_marker(text: str) -> bool:
    text_lower = str(text).lower()
    tokens = set(re.findall(r"[a-z0-9]+", text_lower))
    if tokens.intersection(PHYSICAL_SIGNAL_TERMS):
        return True
    if re.search(r"\b[a-z]{2,}\d+\b|\b\d+[a-z]{2,}\b", text_lower):
        return True
    if re.search(r"\b[A-Z]{2,}[A-Z0-9\s\-_/]{2,}\b", str(text)):
        return True
    return False


def _has_explicit_physical_marker(text: str) -> bool:
    _load_physical_lookup_vocabulary()
    text_lower = str(text).lower()
    filtered_tokens = {t for t in _tokenize_simple(text_lower) if len(t) > 1 and t not in LOCAL_STOP_WORDS}
    phrases = _build_resource_phrases([t for t in _tokenize_simple(text_lower) if len(t) > 1 and t not in LOCAL_STOP_WORDS])

    if filtered_tokens.intersection(RESOURCE_TOKEN_SET):
        return True
    if phrases.intersection(RESOURCE_PHRASE_SET):
        return True
    return _has_hard_physical_marker(text)


def _has_strong_abstract_marker(message: str) -> bool:
    message_lower = message.lower()
    for complaint_type in ABSTRACT_SIGNAL_TYPES:
        for keyword in _BASE_KEYWORDS.get(complaint_type, []):
            if re.search(r"\b" + re.escape(keyword) + r"\b", message_lower):
                return True
    if _match_it_keywords(message):
        return True
    return False


def has_physical_lookup_signal(message: str, local_schema: dict | None = None) -> bool:
    schema = local_schema or extract_local_complaint_schema(message)

    if _has_strong_abstract_marker(message) and not _has_hard_physical_marker(message):
        return False

    resource_name = schema.get("resource_name")
    if resource_name and _has_explicit_physical_marker(resource_name):
        return True

    searchable = []
    searchable.extend(schema.get("important_terms", []))
    searchable.extend(schema.get("important_phrases", [])[:8])

    for item in searchable:
        if _has_explicit_physical_marker(item):
            return True

    if _has_explicit_physical_marker(message):
        return True
    return False


def extract_local_complaint_schema(message: str, complaint_type: int | None = None) -> dict:
    words = preprocess(message)
    words = normalize(words)
    keywords = extract_keywords(words)
    all_terms = generate_phrases(keywords)
    location_hint = _extract_location_hint(message)
    gemini_extracted = _extract_with_gemini(message)

    if gemini_extracted:
        gemini_terms = _dedupe_preserve_order(gemini_extracted.get("important_terms", []))
        gemini_phrases = _dedupe_preserve_order(gemini_extracted.get("important_phrases", []))
        keywords = gemini_terms or keywords
        all_terms = gemini_phrases or all_terms
        location_hint = gemini_extracted.get("location_name") or location_hint

    resource_keywords = list(keywords)
    if location_hint:
        location_terms = set(preprocess(location_hint))
        resource_keywords = [word for word in resource_keywords if word not in location_terms]

    resource_name = None
    if gemini_extracted:
        resource_name = gemini_extracted.get("resource_name")
    if not resource_name:
        resource_name = _best_resource_phrase(resource_keywords)
    if complaint_type == 0 and resource_name and not _has_explicit_physical_marker(resource_name):
        resource_name = None
    if complaint_type in {5, 6, 7, 8, 9, 10}:
        resource_name = None

    return {
        "complaint_description": message.strip(),
        "location_name": location_hint,
        "resource_name": resource_name,
        "important_terms": keywords,
        "important_phrases": all_terms,
    }


def _load_it_keywords_from_db() -> None:
    global IT_KEYWORD_SET
    db = SessionLocal()
    try:
        rows = db.query(models.ComplaintKeyword).all()
        for row in rows:
            keyword = (row.keyword or "").strip().lower()
            if not keyword:
                continue
            KEYWORD_TYPE_MAP.setdefault(row.type, [])
            if keyword not in KEYWORD_TYPE_MAP[row.type]:
                KEYWORD_TYPE_MAP[row.type].append(keyword)
            if row.type == 6 and keyword not in IT_KEYWORD_BLACKLIST:
                IT_KEYWORD_SET.add(keyword)
    except Exception as exc:
        print(f"[CLASSIFIER] IT keyword load failed: {exc}")
    finally:
        db.close()


_load_it_keywords_from_db()


def classify_local(keywords: list[str], equipment_list: list[str], facility_list: list[str], safety_list: list[str]):
    equipment_set = set(equipment_list)
    facility_set = set(facility_list)
    safety_set = set(safety_list)

    for word in keywords:
        if word in equipment_set:
            return "Equipment"
        if word in facility_set:
            return "Facility"
        if word in safety_set:
            return "Safety"
    return "Unknown"


def _detect_type_from_tables(message: str) -> Optional[int]:
    db = SessionLocal()
    try:
        local_schema = extract_local_complaint_schema(message)
        if not has_physical_lookup_signal(message, local_schema):
            return None
        lookup_candidates = []
        if local_schema["resource_name"]:
            lookup_candidates.append(local_schema["resource_name"])
        lookup_candidates.extend(local_schema["important_phrases"][:6])
        lookup_candidates.append(message)

        seen_queries = set()
        for lookup_text in lookup_candidates:
            if not lookup_text or lookup_text in seen_queries:
                continue
            seen_queries.add(lookup_text)

            for candidate_type in (1, 2, 3, 4):
                rows = search_resource_candidates(
                    db,
                    candidate_type,
                    lookup_text,
                    local_schema.get("location_name"),
                )
                if not rows:
                    continue

                matched = rows[0]
                if candidate_type == 3:
                    return 3
                if candidate_type == 2:
                    return 2

                category = getattr(matched, "category", None)
                if category and category in CATEGORY_TYPE_MAP:
                    return CATEGORY_TYPE_MAP[category]
                return candidate_type
    except Exception as exc:
        print(f"[CLASSIFIER] Table detection failed: {exc}")
    finally:
        db.close()
    return None


def _match_it_keywords(message: str) -> bool:
    if not IT_KEYWORD_SET:
        return False

    local_schema = extract_local_complaint_schema(message)
    searchable = set(local_schema["important_terms"]) | set(local_schema["important_phrases"])
    searchable.add(message.lower())

    for keyword in IT_KEYWORD_SET:
        if " " in keyword:
            if any(keyword in item for item in searchable):
                return True
        elif keyword in searchable:
            return True
    return False


def _has_base_keyword(message: str, complaint_type: int) -> bool:
    msg_lower = message.lower()
    for keyword in _BASE_KEYWORDS.get(complaint_type, []):
        if re.search(r"\b" + re.escape(keyword) + r"\b", msg_lower):
            return True
    return False


def keyword_match(message: str) -> Optional[int]:
    msg_lower = message.lower()
    scores: dict[int, int] = {}

    for complaint_type, keywords in KEYWORD_TYPE_MAP.items():
        base_keywords = set(_BASE_KEYWORDS.get(complaint_type, []))
        for keyword in keywords:
            if re.search(r"\b" + re.escape(keyword) + r"\b", msg_lower):
                scores[complaint_type] = scores.get(complaint_type, 0) + (100 if keyword in base_keywords else 5)

    if _match_it_keywords(message):
        scores[6] = scores.get(6, 0) + 200

    if not scores:
        return None

    max_score = max(scores.values())
    top_types = [t for t, score in scores.items() if score == max_score]
    if max_score < 25:
        return None
    if len(top_types) > 1:
        return top_types
    return top_types[0]


@lru_cache(maxsize=256)
def _gemini_classify(message: str) -> Optional[int]:
    try:
        client = _get_gemini()
        if not client:
            return None

        prompt = f"""You are classifying a workplace / lab complaint message.

Reply with ONLY one number:
0=Miscellaneous
1=Equipment
2=Facility
3=Safety
4=Process
5=HR
6=IT
7=Purchase
8=Training
9=Inventory
10=Admin

If the complaint is unclear, generic, or cannot be confidently matched, reply 0.

Message: "{message}"
Reply:"""

        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        result = response.text.strip()
        if result.upper() == "UNCLEAR":
            return 0
        type_num = int(result)
        return type_num if type_num in VALID_TYPES else None
    except Exception as exc:
        if "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc):
            _set_gemini_backoff(120.0)
        print(f"[CLASSIFIER] Gemini error: {exc}")
        return None


def classify_complaint_type(message: str, matched_machine=None) -> Optional[int]:
    if matched_machine:
        cls_name = type(matched_machine).__name__
        if cls_name == "SafetyDevice":
            return 3
        if cls_name == "FacilityResource":
            return 2
        if getattr(matched_machine, "category", None):
            category = matched_machine.category.strip()
            if category in CATEGORY_TYPE_MAP:
                return CATEGORY_TYPE_MAP[category]

    for preferred_type in (5, 7, 8, 9, 10):
        if _has_base_keyword(message, preferred_type):
            return preferred_type

    table_type = _detect_type_from_tables(message)
    if table_type is not None:
        return table_type

    if _match_it_keywords(message):
        return 6

    keyword_result = keyword_match(message)
    if isinstance(keyword_result, int):
        return keyword_result

    tied_types = keyword_result if isinstance(keyword_result, list) else []
    gemini_type = _gemini_classify(message)
    if gemini_type is not None:
        return gemini_type

    if tied_types:
        for preferred in [6, 3, 2, 4, 5, 7, 8, 9, 10, 1, 0]:
            if preferred in tied_types:
                return preferred
    return 0


def extract_complaint_schema(message: str, complaint_type: int | None = None) -> dict:
    try:
        client = _get_gemini()
        if not client:
            local = extract_local_complaint_schema(message, complaint_type)
            return {
                "complaint_description": local["complaint_description"],
                "location_name": local["location_name"],
                "resource_name": local["resource_name"],
            }

        resource_label = {
            1: "equipment or machine name",
            2: "facility resource name",
            3: "safety device or safety equipment name",
            4: "tool or equipment involved in the process issue",
        }.get(complaint_type, "resource name if explicitly mentioned")

        prompt = f"""Extract only the minimum complaint registration details from this message.

Rules:
- Extract only the words needed to look up the affected resource in the database.
- Do not invent ids, status, timestamps, or categories.
- Keep complaint_description concise and faithful.
- If a field is unclear, return null.

Fields:
- resource_name: {resource_label}
- complaint_description: one short sentence describing the complaint
- location_name: lab, room, or area if explicitly mentioned

Message: "{message}"

Return valid JSON only:
{{
  "resource_name": "lookup phrase or null",
  "complaint_description": "short complaint description",
  "location_name": "location or null"
}}"""

        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        result = response.text.strip()
        if result.startswith("```"):
            parts = result.split("```")
            if len(parts) >= 3:
                result = parts[1]
                if result.lower().startswith("json"):
                    result = result[4:].strip()

        extracted = json.loads(result)
        return {
            "complaint_description": extracted.get("complaint_description", message.strip()),
            "location_name": extracted.get("location_name"),
            "resource_name": extracted.get("resource_name"),
        }
    except Exception as exc:
        print(f"[CLASSIFIER] Schema extraction error: {exc}")
        local = extract_local_complaint_schema(message, complaint_type)
        return {
            "complaint_description": local["complaint_description"],
            "location_name": local["location_name"],
            "resource_name": local["resource_name"],
        }


def extract_unknown_equipment(message: str) -> dict:
    local = extract_local_complaint_schema(message, 1)
    return {
        "complaint_type": classify_complaint_type(message) or 1,
        "machine_name": local.get("resource_name") or "Unknown Equipment",
    }


def process_complaint(text, equipment_list, facility_list, safety_list):
    words = preprocess(text)
    words = normalize(words)
    keywords = extract_keywords(words)
    all_terms = generate_phrases(keywords)
    category = classify_local(all_terms, equipment_list, facility_list, safety_list)
    if category != "Unknown":
        return category
    return "USE_GEMINI"
