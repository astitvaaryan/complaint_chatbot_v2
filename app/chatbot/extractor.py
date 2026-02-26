"""
app/chatbot/extractor.py
─────────────────────────────────────────
Improved machine extraction with 3-level matching:
  1. Exact full-name match (highest priority)
  2. Prefix match — user input matches START of machine name
     e.g. "Dehumidifier 1" → "Dehumidifier 1_M2_1" ✅
                           → "Dehumidifier 10_xxx" ❌ (digit boundary check)
  3. Token overlap fallback (lowest priority)

Only searches active machines (activation_status = 1).
"""

import re
from typing import Iterable, List

from app.chatbot import models

# Words that carry no machine-name meaning — stripped before prefix matching
STOP_WORDS = {
    "has", "have", "not", "the", "and", "for", "with", "this", "that",
    "issue", "problem", "working", "broken", "fault", "repair", "fix",
    "since", "down", "off", "from", "there", "its", "our", "please",
    "help", "check", "seems", "started", "stopped", "suddenly", "always",
    # IT/office words that should NOT match lab equipment names
    "laptop", "screen", "computer", "monitor", "keyboard", "mouse",
    "projector", "wifi", "internet", "network", "software", "email",
    "phone", "mobile", "printer", "scanner", "cable", "charger",
}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _tokenize(value: str) -> set:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _extract_machine_query(message: str) -> str:
    """
    Strip stop words from message to get the core machine name query.
    e.g. "Dehumidifier 1 has issue" → "dehumidifier 1"
    """
    words = _normalize_text(message).split()
    meaningful = [w for w in words if w not in STOP_WORDS and len(w) > 1]
    return " ".join(meaningful)


def _is_prefix_boundary(name_norm: str, query: str) -> bool:
    """
    True if name starts with query AND the next character is a word separator.
    This prevents "Dehumidifier 1" matching "Dehumidifier 10".
    """
    if not name_norm.startswith(query):
        return False
    remainder_idx = len(query)
    if remainder_idx >= len(name_norm):
        return True  # exact match
    next_char = name_norm[remainder_idx]
    return next_char in ('_', ' ', '-', '/', '.')


def extract_machine_candidates(message: str, machines: Iterable[models.Resources]) -> List[models.Resources]:
    """
    Return matched machines using 3-level priority:
    1. Exact full name in message
    2. Prefix boundary match
    3. Token overlap fallback
    """
    msg_norm = _normalize_text(message)
    msg_tokens = _tokenize(message)
    query = _extract_machine_query(message)

    exact_matches: List[models.Resources] = []
    prefix_matches: List[models.Resources] = []
    partial_matches: List[models.Resources] = []

    for machine in machines:
        name_norm = _normalize_text(machine.name or "")
        if not name_norm:
            continue

        # Level 1: Exact full name appears in message
        exact_pattern = rf"\b{re.escape(name_norm)}\b"
        if re.search(exact_pattern, msg_norm):
            exact_matches.append(machine)
            continue

        # Level 2: Prefix boundary match
        if query and _is_prefix_boundary(name_norm, query):
            prefix_matches.append(machine)
            continue

        # Level 3: Dynamic token overlap threshold
        # - 1 meaningful token in message (e.g. "ac") → need 1 overlap
        # - 2+ meaningful tokens (e.g. "spin coater") → need 2 overlaps
        #   This prevents "Spin AC_1" falsely matching "spin coater"
        name_tokens = _tokenize(name_norm)
        meaningful_msg_tokens = msg_tokens - STOP_WORDS
        overlap = name_tokens.intersection(meaningful_msg_tokens)
        required = 1 if len(meaningful_msg_tokens) <= 1 else 2
        if len(overlap) >= required:
            partial_matches.append(machine)

    # Return highest-priority non-empty list
    if exact_matches:
        return exact_matches
    if prefix_matches:
        return prefix_matches

    # Deduplicate partial matches
    unique = []
    seen = set()
    for machine in partial_matches:
        if machine.machid not in seen:
            seen.add(machine.machid)
            unique.append(machine)
    return unique


def narrow_by_location(message: str, machines: Iterable[models.Resources]) -> List[models.Resources]:
    """Narrow candidates by location string mentioned in the message."""
    msg_norm = _normalize_text(message)
    narrowed = [
        m for m in machines
        if _normalize_text(str(m.location or "")) and
           _normalize_text(str(m.location or "")) in msg_norm
    ]
    return narrowed


def extract_machine_db(message: str, db) -> List[models.Resources]:
    """
    Main entry point: query only ACTIVE machines, then apply smart matching.
    """
    all_machines = db.query(models.Resources).filter(
        models.Resources.activation_status == 1
    ).all()

    candidates = extract_machine_candidates(message, all_machines)

    # If still multiple after matching, try location narrowing
    if len(candidates) > 1:
        narrowed = narrow_by_location(message, candidates)
        if narrowed:
            candidates = narrowed

    return candidates
