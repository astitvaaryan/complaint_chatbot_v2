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
    "issue", "problem", "working", "workng", "workin", "works", "worked",
    "broken", "fault", "repair", "fix", "fail", "failed", "failure",
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


def extract_machine_candidates(message: str, machines: List[any]) -> List[any]:
    """
    Return matched machines using 3-level priority:
    1. Exact full name in message
    2. Prefix boundary match
    3. Token overlap fallback
    """
    msg_norm = _normalize_text(message)
    msg_tokens = _tokenize(message)
    query = _extract_machine_query(message)

    exact_matches = []
    prefix_matches = []
    partial_matches = []

    for machine in machines:
        # Normalize attributes based on class type
        if hasattr(machine, 'device_name'):
            name = machine.device_name
            obj_id = machine.device_id
        else:
            name = machine.name
            obj_id = machine.machid

        name_norm = _normalize_text(name or "")
        cat_norm  = _normalize_text(machine.category or "")
        
        # Level 1: Exact full name or category appears in message
        if (name_norm and re.search(rf"\b{re.escape(name_norm)}\b", msg_norm)) or \
           (cat_norm and re.search(rf"\b{re.escape(cat_norm)}\b", msg_norm)):
            exact_matches.append(machine)
            continue

        # Level 2: Prefix boundary match (Name or Category)
        if query and (_is_prefix_boundary(name_norm, query) or _is_prefix_boundary(cat_norm, query)):
            prefix_matches.append(machine)
            continue

        # Level 3: Token overlap fallback
        name_tokens = _tokenize(name_norm)
        cat_tokens  = _tokenize(cat_norm)
        meaningful_msg_tokens = msg_tokens - STOP_WORDS
        
        overlap = (name_tokens | cat_tokens).intersection(meaningful_msg_tokens)
        required = 1 if len(meaningful_msg_tokens) <= 1 else 2
        if len(overlap) >= required:
            partial_matches.append(machine)
            continue

    # Return highest-priority non-empty list
    if exact_matches:
        return exact_matches
    if prefix_matches:
        return prefix_matches

    # Deduplicate partial matches
    unique = []
    seen = set()
    for machine in partial_matches:
        mid = getattr(machine, 'machid', getattr(machine, 'device_id', None))
        mtype = type(machine).__name__
        key = (mtype, mid)
        if mid is not None and key not in seen:
            seen.add(key)
            unique.append(machine)
    return unique


def narrow_by_location(message: str, machines: List[any]) -> List[any]:
    """Narrow candidates by location string mentioned in the message."""
    msg_norm = _normalize_text(message)
    narrowed = [
        m for m in machines
        if _normalize_text(str(m.location or "")) and
           _normalize_text(str(m.location or "")) in msg_norm
    ]
    return narrowed


def extract_machine_db(message: str, db) -> List[any]:
    """
    Main entry point: query multiple tables, then apply smart matching.
    """
    # 1. Fetch from all 3 tables
    facility_list = db.query(models.Resources).filter(models.Resources.isworking == 1).all()
    eqp_list      = db.query(models.EqpProcessResource).filter(models.EqpProcessResource.isworking == 1).all()
    safety_list   = db.query(models.SafetyDevice).filter(models.SafetyDevice.isworking == 1).all()

    all_candidates = facility_list + eqp_list + safety_list

    candidates = extract_machine_candidates(message, all_candidates)

    # If still multiple after matching, try location narrowing
    if len(candidates) > 1:
        narrowed = narrow_by_location(message, candidates)
        if narrowed:
            candidates = narrowed

    return candidates
