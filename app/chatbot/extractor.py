"""Structured resource lookup helpers for complaint registration."""

import re
from typing import Iterable, List

from app.chatbot import models

STOP_WORDS = {
    "has", "have", "not", "the", "and", "for", "with", "this", "that",
    "issue", "problem", "working", "workng", "workin", "works", "worked",
    "broken", "fault", "repair", "fix", "fail", "failed", "failure",
    "since", "down", "off", "from", "there", "its", "our", "please",
    "help", "check", "seems", "started", "stopped", "suddenly", "always",
    "complaint", "device", "equipment", "machine", "resource", "safety",
}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _compact_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _tokenize(value: str) -> set:
    tokens = set(re.findall(r"[a-z0-9]+", str(value).lower()))
    expanded = set(tokens)
    for token in tokens:
        parts = re.findall(r"[a-z]+|\d+", token)
        expanded.update(parts)
    return expanded


def _extract_lookup_query(message: str) -> str:
    words = _normalize_text(message).split()
    meaningful = [word for word in words if word not in STOP_WORDS and len(word) > 1]
    return " ".join(meaningful)


def _is_prefix_boundary(name_norm: str, query: str) -> bool:
    if not name_norm.startswith(query):
        return False
    remainder_idx = len(query)
    if remainder_idx >= len(name_norm):
        return True
    return name_norm[remainder_idx] in ("_", " ", "-", "/", ".")


def _match_candidates(query_text: str, rows: Iterable[object], name_getter) -> List[object]:
    msg_norm = _normalize_text(query_text)
    msg_tokens = _tokenize(query_text)
    query = _extract_lookup_query(query_text)

    exact_matches = []
    prefix_matches = []
    partial_matches = []

    for row in rows:
        name_norm = _normalize_text(name_getter(row) or "")
        name_compact = _compact_text(name_getter(row) or "")
        if not name_norm:
            continue

        if re.search(rf"\b{re.escape(name_norm)}\b", msg_norm):
            exact_matches.append(row)
            continue

        if _compact_text(query_text) and _compact_text(query_text) in name_compact:
            exact_matches.append(row)
            continue

        if query and _is_prefix_boundary(name_norm, query):
            prefix_matches.append(row)
            continue

        name_tokens = _tokenize(name_norm)
        meaningful_msg_tokens = msg_tokens - STOP_WORDS
        
        overlap = name_tokens.intersection(meaningful_msg_tokens)
        required = 1 if len(meaningful_msg_tokens) <= 1 else 2
        if len(overlap) >= required:
            partial_matches.append(row)

    if exact_matches:
        return exact_matches
    if prefix_matches:
        return prefix_matches

    unique = []
    seen = set()
    for row in partial_matches:
        record_id = id(row)
        if record_id not in seen:
            seen.add(record_id)
            unique.append(row)
    return unique


def _narrow_by_location(location_hint: str, rows: Iterable[object], location_getter) -> List[object]:
    if not location_hint:
        return list(rows)

    hint = _normalize_text(location_hint)
    return [
        row for row in rows
        if hint in _normalize_text(location_getter(row) or "")
    ]


RESOURCE_TABLE_MAP = {
    1: {
        "model": models.Resources,
        "name_field": "name",
        "id_field": "machid",
        "location_field": "location",
        "active_field": "activation_status",
        "active_value": 1,
    },
    2: {
        "model": models.FacilityResource,
        "name_field": "name",
        "id_field": "machid",
        "location_field": "location",
        "active_field": "activation_status",
        "active_value": 1,
    },
    3: {
        "model": models.SafetyDevice,
        "name_field": "device_name",
        "id_field": "device_id",
        "location_field": "location",
        "active_field": "isworking",
        "active_value": 1,
    },
    4: {
        "model": models.Resources,
        "name_field": "name",
        "id_field": "machid",
        "location_field": "location",
        "active_field": "activation_status",
        "active_value": 1,
    },
}


def search_resource_candidates(db, complaint_type: int, lookup_text: str, location_hint: str | None = None) -> List[object]:
    config = RESOURCE_TABLE_MAP.get(complaint_type)
    if not config or not lookup_text:
        return []

    model = config["model"]
    active_field = getattr(model, config["active_field"])
    rows = db.query(model).filter(active_field == config["active_value"]).all()
    if not rows and complaint_type == 2:
        fallback = RESOURCE_TABLE_MAP[1]
        model = fallback["model"]
        active_field = getattr(model, fallback["active_field"])
        rows = db.query(model).filter(active_field == fallback["active_value"]).all()
        config = fallback

    candidates = _match_candidates(
        lookup_text,
        rows,
        lambda row: getattr(row, config["name_field"], None),
    )

    if len(candidates) > 1 and location_hint:
        narrowed = _narrow_by_location(
            location_hint,
            candidates,
            lambda row: getattr(row, config["location_field"], None),
        )
        if narrowed:
            candidates = narrowed

    return candidates


def extract_machine_db(message: str, db) -> List[models.Resources]:
    return search_resource_candidates(db, 1, message)
