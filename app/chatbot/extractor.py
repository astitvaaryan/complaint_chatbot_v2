"""Structured resource lookup helpers using 2-Tier RapidFuzz Smart Search."""

import re
from typing import Iterable, List, Dict, Any
from rapidfuzz import fuzz

from app.chatbot import models

STOP_WORDS = {
    "has", "have", "not", "the", "and", "for", "with", "this", "that",
    "issue", "problem", "working", "workng", "workin", "works", "worked",
    "broken", "fault", "repair", "fix", "fail", "failed", "failure",
    "since", "down", "off", "from", "there", "its", "our", "please",
    "help", "check", "seems", "started", "stopped", "suddenly", "always",
    "complaint", "device", "equipment", "machine", "resource", "safety",
}

# Tier 2: Static dictionary mappings for abstract classes
ABSTRACT_MAPPINGS = {
    5: ["hr", "human resources", "salary", "leave", "payroll", "employee", "manager", "benefits"],
    6: ["it", "computer", "network", "internet", "wifi", "software", "printer", "login", "password", "server", "email", "hardware"],
    7: ["purchase", "buy", "order", "vendor", "procurement", "invoice", "payment", "quote"],
    8: ["training", "learn", "course", "tutorial", "guide", "onboarding", "workshop"],
    9: ["inventory", "stock", "supply", "spare", "material", "warehouse", "shortage"],
    10: ["admin", "administration", "cleaning", "housekeeping", "security", "access", "badge", "id card"]
}

RESOURCE_TABLE_MAP = {
    1: {
        "model": models.EqpProcessResource,
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
        "model": models.EqpProcessResource,
        "name_field": "name",
        "id_field": "machid",
        "location_field": "location",
        "active_field": "activation_status",
        "active_value": 1,
    },
}

def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())

def _extract_lookup_query(message: str) -> str:
    words = _normalize_text(message).split()
    meaningful = [word for word in words if word not in STOP_WORDS and len(word) > 1]
    return " ".join(meaningful)

def _tier1_physical_search(db, nouns: List[str]) -> Dict[int, List[object]]:
    """Tier 1: Search Physical DB tables using fuzz.token_set_ratio with 65% threshold."""
    results = {}
    
    for noun in nouns:
        query_norm = _extract_lookup_query(noun)
        if not query_norm:
            continue
            
        for type_id in [1, 2, 3]:
            config = RESOURCE_TABLE_MAP[type_id]
            model = config["model"]
            active_field = getattr(model, config["active_field"])
            
            rows = db.query(model).filter(active_field == config["active_value"]).all()
            
            for row in rows:
                name_val = getattr(row, config["name_field"], "")
                if not name_val:
                    continue
                name_norm = _normalize_text(name_val)
                
                score = fuzz.token_set_ratio(query_norm, name_norm)
                if score >= 65.0:
                    if type_id not in results:
                        results[type_id] = []
                    # Keep unique objects
                    if not any(id(existing) == id(row) for existing in results[type_id]):
                        results[type_id].append(row)
                        
    return results

def _tier2_abstract_search(nouns: List[str]) -> List[int]:
    """Tier 2: Search abstract classes using fuzz.WRatio."""
    matched_types = set()
    
    for noun in nouns:
        query_norm = _normalize_text(noun)
        if not query_norm:
            continue
            
        for type_id, keywords in ABSTRACT_MAPPINGS.items():
            for kw in keywords:
                score = fuzz.WRatio(query_norm, kw)
                if score >= 80.0:  # Strong match required for WRatio
                    matched_types.add(type_id)
                    break
                    
    return list(matched_types)

def smart_rapidfuzz_search(db, nouns: List[str]) -> Dict[str, Any]:
    """
    Executes the comprehensive 2-Tier RapidFuzz search across all nouns.
    Returns:
        {
            "physical_matches": {category_id: [resource_objects]},
            "abstract_matches": [category_id_1, category_id_2]
        }
    """
    valid_nouns = [n for n in nouns if str(n).strip()]
    
    return {
        "physical_matches": _tier1_physical_search(db, valid_nouns),
        "abstract_matches": _tier2_abstract_search(valid_nouns)
    }

def _narrow_by_location(location_hint: str, rows: Iterable[object], location_getter) -> List[object]:
    if not location_hint:
        return list(rows)
    hint = _normalize_text(location_hint)
    return [
        row for row in rows
        if hint in _normalize_text(location_getter(row) or "")
    ]

def search_resource_candidates(db, complaint_type: int, lookup_text: str, location_hint: str | None = None) -> List[object]:
    """Fallback legacy support using RapidFuzz Tier 1."""
    if complaint_type not in RESOURCE_TABLE_MAP:
        return []
        
    res = _tier1_physical_search(db, [lookup_text])
    
    candidates = res.get(complaint_type, [])
    if not candidates and complaint_type == 2:
        candidates = res.get(1, [])  # Fallback to Equipment
        
    if len(candidates) > 1 and location_hint:
        config = RESOURCE_TABLE_MAP.get(complaint_type, RESOURCE_TABLE_MAP[1])
        narrowed = _narrow_by_location(
            location_hint,
            candidates,
            lambda row: getattr(row, config["location_field"], None),
        )
        if narrowed:
            candidates = narrowed

    return candidates

def extract_machine_db(message: str, db) -> List[models.EqpProcessResource]:
    return search_resource_candidates(db, 1, message)
