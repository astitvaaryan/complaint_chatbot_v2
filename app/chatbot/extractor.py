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
    "automatic", "manual", "system", "standard", "unit", "module", "device",
    "kindly", "verify", "replace", "tool", "lab", "room", "area", "bldg",
    "floor", "building", "number", "sd", "near"
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

# Mapping of Type ID to database table and field names
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
    """Tier 1: Search Physical DB tables.
    
    First tries exact/substring word match (catches acronyms like SEM, UPS).
    Then falls back to fuzz.token_set_ratio with 65% threshold.
    """
    results = {}
    
    for noun in nouns:
        # Skip the internal fallback sentinel
        if noun == "FALLBACK_TO_LOCATION":
            continue
            
        query_norm = _extract_lookup_query(noun)
        if not query_norm:
            continue

        # Extract individual meaningful words from the query
        query_words = [w for w in query_norm.split() if len(w) >= 2]
            
        for type_id in [1, 2, 3]:
            config = RESOURCE_TABLE_MAP[type_id]
            model = config["model"]
            active_field = getattr(model, config["active_field"])
            
            q = db.query(model).filter(active_field == config["active_value"])
            if type_id in [1, 2, 4]:
                q = q.filter(model.display != 3)
            rows = q.all()
            
            for row in rows:
                name_val = getattr(row, config["name_field"], "")
                if not name_val:
                    continue
                name_norm = _normalize_text(name_val)
                
                matched = False
                
                # Priority check: direct word-level substring match
                # This catches acronyms like SEM, UPS, AHU even if fuzzy score is low
                for word in query_words:
                    if len(word) >= 2 and re.search(r'\b' + re.escape(word) + r'\b', name_norm):
                        matched = True
                        break
                
                # Fallback: fuzzy match for longer phrases
                if not matched:
                    score = fuzz.token_set_ratio(query_norm, name_norm)
                    if score >= 65.0:
                        matched = True
                
                if matched:
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

def search_by_location(db, complaint_type: int, location_hint: str) -> List[object]:
    """Layer 2 Fallback: Fetch all active resources for a specific location string."""
    if complaint_type not in RESOURCE_TABLE_MAP:
        return []
    
    config = RESOURCE_TABLE_MAP[complaint_type]
    model = config["model"]
    active_field = getattr(model, config["active_field"])
    
    # Base query for active devices
    q = db.query(model).filter(active_field == config["active_value"])
    if complaint_type in [1, 2, 4]:
        q = q.filter(model.display != 3)
    
    all_rows = q.all()
    hint_norm = _normalize_text(location_hint)
    
    if not hint_norm:
        return []

    # Match rows where the location column contains our hint
    matched = [
        row for row in all_rows
        if hint_norm in _normalize_text(getattr(row, config["location_field"], "") or "")
    ]
    return matched


def search_resource_candidates(db, complaint_type: int, lookup_text: str, location_hint: str | None = None) -> List[object]:
    """
    Core search logic for Physical Types (1-4).
    Layer 1: Word-based name match.
    Layer 2: Multi-Lab fallback (if name match fails).
    """
    if complaint_type not in RESOURCE_TABLE_MAP:
        return []
        
    # Layer 1: Try direct name match first
    candidates = _tier1_physical_search(db, [lookup_text]).get(complaint_type, [])
        
    # Layer 2: If no direct name match, but we have a lab name, show everything in that lab
    if not candidates and location_hint:
        # location_hint might contain multiple labs separated by commas/text
        # We split and search for each recognized lab
        labs = [l.strip() for l in re.split(r"[,/]", location_hint) if l.strip()]
        for lab in labs:
            candidates.extend(search_by_location(db, complaint_type, lab))
            
        # Deduplicate
        seen_ids = set()
        unique_candidates = []
        id_field = RESOURCE_TABLE_MAP[complaint_type]["id_field"]
        for c in candidates:
            cid = getattr(c, id_field)
            if cid not in seen_ids:
                unique_candidates.append(c)
                seen_ids.add(cid)
        candidates = unique_candidates

    # If we have too many candidates still, try to narrow them by location_hint if provided
    if len(candidates) > 1 and location_hint:
        config = RESOURCE_TABLE_MAP.get(complaint_type, RESOURCE_TABLE_MAP[1])
        narrowed = _narrow_by_location(
            location_hint,
            candidates,
            lambda row: getattr(row, config["location_field"], None),
        )
        if narrowed:
            candidates = narrowed

    # Limit to top 15 results to prevent WhatsApp message bloat
    return candidates[:15]


def extract_machine_db(message: str, db) -> List[models.EqpProcessResource]:
    return search_candidate_objects(db, 1, message)

def search_candidate_objects(db, complaint_type: int, message: str) -> List[object]:
    """Wrapper for backward compatibility."""
    return search_resource_candidates(db, complaint_type, message)
