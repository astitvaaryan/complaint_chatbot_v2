"""Schema-driven complaint engine with typed resource-table lookups."""

import json
import re
import os
import requests
import traceback
from datetime import datetime

from rapidfuzz import fuzz

from app.chatbot import models
from app.chatbot.classifier import (
    classify_complaint_type,
    extract_complaint_schema,
    extract_local_complaint_schema,
    has_physical_lookup_signal,
)
from app.chatbot.db import SessionLocal
from app.chatbot.extractor import RESOURCE_TABLE_MAP, search_resource_candidates, smart_rapidfuzz_search
from app.chatbot.state_manager import clear_state, get_state, parse_collected_data, upsert_state

TYPE_NAMES = {
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

YES_WORDS = {"yes", "y", "confirm", "ok", "okay"}
NO_WORDS = {"no", "n", "cancel"}
EDIT_WORDS = {"edit", "e"}
RESOURCE_REQUIRED_TYPES = {1, 2, 3, 4}
LOCATION_RELEVANT_TYPES = {1, 2, 3, 4, 9}

def _get_editable_fields(schema: dict) -> dict:
    fields = {1: "type"}
    idx = 2
    if schema.get("type", 0) in RESOURCE_REQUIRED_TYPES:
        fields[idx] = "resource_name"
        idx += 1
    
    return fields

# Types that do NOT require a physical machine / location
# 2=Facility, 3=Safety, 5=HR, 6=IT, etc.
NON_EQUIPMENT_TYPES = {2, 3, 5, 6, 7, 8, 9, 10}


def _blank_schema() -> dict:
    return {
        "member_id": None,
        "machine_id": None,
        "complaint_description": None,
        "type": None,
        "status": None,
        "time_of_complaint": None,
        "location_name": None,
        "location_id": None,
        "resource_name": None,
        "resource_table": None,
    }


def _resource_label(complaint_type: int | None) -> str:
    return {
        1: "equipment",
        2: "facility resource",
        3: "safety device",
        4: "tool or equipment",
    }.get(complaint_type, "resource")


def _fallback_to_misc(schema: dict) -> dict:
    # Keep the original type (1-10) instead of resetting to 0
    if schema.get("type") in (None, 0):
         schema["type"] = 1 # Default only if truly unknown
         
    schema["machine_id"] = None
    schema["resource_table"] = None
    schema["_misc_tool_skipped"] = True
    schema["_rf_candidates"] = {}
    
    # Force the display text to "Miscellaneous"
    schema["resource_name"] = "Miscellaneous"
    return schema


def _normalize_location_text(value: str) -> str:
    text = re.sub(r"[^a-z0-9\s]", " ", str(value).lower())
    tokens = [
        token for token in text.split()
        if token not in {"in", "the", "at", "inside", "near", "lab", "room", "area", "block"}
    ]
    return " ".join(tokens).strip()


def _score_lab_match(query: str, candidate: str) -> float:
    query_norm = _normalize_location_text(query)
    candidate_norm = _normalize_location_text(candidate)
    if not query_norm or not candidate_norm:
        return 0.0
    query_tokens = set(query_norm.split())
    candidate_tokens = set(candidate_norm.split())
    if query_tokens and not query_tokens.intersection(candidate_tokens):
        return 0.0
    return max(
        fuzz.ratio(query_norm, candidate_norm),
        fuzz.token_set_ratio(query_norm, candidate_norm),
    )


def _resolve_lab_location(db, location_str):
    try:
        if not location_str:
            return None, None, None

        raw_location = str(location_str).strip()
        normalized_location = _normalize_location_text(raw_location)

        try:
            loc_id = int(raw_location)
            incharge = db.query(models.LabIncharge).filter(
                models.LabIncharge.locationid == loc_id
            ).first()
            if incharge:
                return incharge.location, incharge.locationid, incharge.memberid
        except ValueError:
            pass

        incharge = db.query(models.LabIncharge).filter(
            models.LabIncharge.location.ilike(f"%{raw_location}%")
        ).first()
        if incharge:
            return incharge.location, incharge.locationid, incharge.memberid

        if normalized_location:
            incharge = db.query(models.LabIncharge).filter(
                models.LabIncharge.location.ilike(f"%{normalized_location}%")
            ).first()
            if incharge:
                return incharge.location, incharge.locationid, incharge.memberid

            best_match = None
            best_score = 0.0
            for row in db.query(models.LabIncharge).all():
                row_location = row.location or ""
                row_normalized = _normalize_location_text(row_location)
                if not row_normalized:
                    continue

                score = _score_lab_match(normalized_location, row_location)
                if score > best_score:
                    best_match = row
                    best_score = score

            if best_match and best_score >= 70.0:
                return best_match.location, best_match.locationid, best_match.memberid
    except Exception as exc:
        print(f"[ENGINE] Lab lookup failed: {exc}")

    return None, None, None


def _merge_schema(schema: dict, extracted: dict) -> dict:
    for key, value in extracted.items():
        if key in schema and value not in (None, "", "null"):
            schema[key] = value
    return schema


def _resolve_schema_location(db, schema: dict, clear_unresolved: bool = False) -> dict:
    location_name = schema.get("location_name")
    location_id = schema.get("location_id")

    if location_name:
        loc_name, loc_id, _ = _resolve_lab_location(db, location_name)
        if loc_id is not None:
            schema["location_name"] = loc_name
            schema["location_id"] = loc_id
        elif clear_unresolved:
            schema["location_name"] = None
            schema["location_id"] = None
    elif location_id is not None:
        loc_name, loc_id, _ = _resolve_lab_location(db, location_id)
        schema["location_name"] = loc_name
        schema["location_id"] = loc_id

    return schema


def _resolve_resource_candidates(db, schema: dict, raw_message: str):
    complaint_type = schema.get("type", 1)
    if complaint_type not in RESOURCE_TABLE_MAP:
        return []

    query_candidates = []
    
    # Layer 1: Build list of potential tool names from schema and message
    resource_name = schema.get("resource_name")
    if resource_name:
        query_candidates.append(resource_name)

    for key in ("important_phrases", "important_terms"):
        values = schema.get(key) or []
        for v in values[:6]:
            if v and v not in query_candidates:
                query_candidates.append(v)

    if raw_message and raw_message not in query_candidates:
        query_candidates.append(raw_message)

    # Layer 1: Look for matches by name/word in the database
    for query in query_candidates:
        rows = search_resource_candidates(db, complaint_type, query, schema.get("location_name"))
        if rows:
            return rows

    # Layer 2: If no name match, but we have lab names, try fetching EVERYTHING in those labs
    location_name = schema.get("location_name")
    if location_name:
        rows = search_resource_candidates(db, complaint_type, "FALLBACK_TO_LOCATION", location_name)
        if rows:
            return rows

    # Layer 3: No tool found, no lab found. Return empty so the bot can default to Miscellaneous.
    return []


def _resolve_misc_resource(db, query: str, location_name: str | None = None):
    for complaint_type in (1, 2, 3, 4):
        rows = search_resource_candidates(db, complaint_type, query, location_name)
        if len(rows) == 1:
            return complaint_type, rows[0], rows
        if len(rows) > 1:
            return complaint_type, None, rows
    return None, None, []


def _apply_matched_resource(db, schema: dict, resource: object) -> dict:
    config = RESOURCE_TABLE_MAP[schema["type"]]
    schema["machine_id"] = getattr(resource, config["id_field"])
    schema["resource_name"] = getattr(resource, config["name_field"])
    schema["resource_table"] = config["model"].__tablename__

    existing_location_id = schema.get("location_id")
    existing_location_name = schema.get("location_name")
    if existing_location_name and existing_location_id is None:
        loc_name, loc_id, _ = _resolve_lab_location(db, existing_location_name)
        schema["location_name"] = loc_name
        schema["location_id"] = loc_id
        existing_location_id = schema.get("location_id")

    if existing_location_id is None:
        location_value = getattr(resource, config["location_field"])
        loc_name, loc_id, _ = _resolve_lab_location(db, location_value)
        schema["location_name"] = loc_name
        schema["location_id"] = loc_id

    return schema


def _enrich_schema_from_db(db, schema: dict, raw_message: str):
    if not has_physical_lookup_signal(raw_message, schema):
        schema["_rf_candidates"] = {}
        schema["_rf_categories"] = []
        return schema, None, []

    nouns = []
    r_name = schema.get("resource_name")
    if r_name and str(r_name).strip():
        nouns.append(r_name)
    for key in ("important_phrases", "important_terms"):
        for val in schema.get(key, []):
            if val and str(val).strip() and val not in nouns:
                nouns.append(val)
    if not nouns and raw_message:
        nouns.append(raw_message)

    results = smart_rapidfuzz_search(db, nouns)
    p_matches = results["physical_matches"]
    a_matches = results["abstract_matches"]
    
    unique_cats = set(p_matches.keys()).union(a_matches)
    
    p_matches_ids = {}
    for t_id, rows in p_matches.items():
        p_matches_ids[str(t_id)] = [
            getattr(r, "machid", getattr(r, "device_id", None)) 
            for r in rows
        ]
    schema["_rf_candidates"] = p_matches_ids
    schema["_rf_categories"] = list(unique_cats)

    candidates = []
    if not unique_cats:
        if not schema.get("resource_name") and nouns:
            schema["resource_name"] = nouns[0]
        return schema, None, []

    if len(unique_cats) == 1:
        cat_id = list(unique_cats)[0]
        schema["type"] = cat_id
        if cat_id in p_matches:
            candidates = p_matches[cat_id]
            if len(candidates) == 1:
                matched_resource = candidates[0]
                schema = _apply_matched_resource(db, schema, matched_resource)
                if schema.get("location_name"):
                    schema["_require_location_confirm"] = True
    else:
        for c in unique_cats:
            if c in p_matches:
                candidates.extend(p_matches[c])

    return schema, None, candidates


def _next_missing_field(schema: dict) -> str | None:
    complaint_type = schema.get("type")

    if complaint_type is None:
        return "type"

    if not schema.get("complaint_description"):
        return "complaint_description"

    if complaint_type == 0 and not schema.get("resource_name") and not schema.get("_misc_tool_skipped"):
        return "resource_name"

    if complaint_type in RESOURCE_REQUIRED_TYPES and not schema.get("machine_id"):
        return "resource_name"

    if complaint_type in LOCATION_RELEVANT_TYPES and not schema.get("location_name"):
        return "location_name"

    return None


def _question_for_field(field: str, complaint_type: int | None) -> str:
    type_name = TYPE_NAMES.get(complaint_type, "this")
    res = ""

    if field == "complaint_description":
        res = f"I've classified this as a {type_name.lower()} complaint. What exactly is the issue?"
    elif field == "type":
        res = "I couldn't confidently identify the complaint type. Reply with one of: Miscellaneous, Equipment, Facility, Safety, Process, HR, IT, Purchase, Training, Inventory, Admin."
    elif field == "resource_name":
        if complaint_type == 0:
            res = "I couldn't confidently match this issue. If a specific tool or equipment is involved, reply with its name. Otherwise reply 'skip' and I'll register this under Miscellaneous."
        else:
            res = f"This looks like a {type_name.lower()} complaint. Which {_resource_label(complaint_type)} is affected?"
    elif field == "location_name":
        res = f"Noted. Where is this {type_name.lower()} issue happening?"
    else:
        res = f"Please provide {field}."
        
    return res + "\n\n*(Tip: Type 'cancel' at any time to abort)*"


def _format_candidate_options(candidates) -> str:
    MAX_SHOW = 10  # Keep well within Twilio's limits
    display = candidates[:MAX_SHOW]
    lines = ["I found multiple matching records. Reply with the number:"]
    
    # Move 0 to the top for better accessibility
    lines.append("0. Miscellaneous / none of these")
    
    for idx, resource in enumerate(display, start=1):
        label = getattr(resource, "name", getattr(resource, "device_name", "Unknown"))
        location = getattr(resource, "location", "")
        lines.append(f"{idx}. {label} ({location})")
        
    lines.append("\n*(Tip: Type 'cancel' at any time to abort)*")
    return "\n".join(lines)


def _render_schema(schema: dict) -> str:
    type_id = schema.get("type", 1)
    type_name = TYPE_NAMES.get(type_id, "Equipment")
    
    # rule: 1=Equipment, 2=Facility, 3=Safety, 4=Process -> category is the tool/resource
    # else (5-10) -> category is just the type name itself
    if type_id not in {1, 2, 3, 4}:
        tool_name = type_name
    else:
        # Default to "Miscellaneous" string if tool not found in table
        tool_name = schema.get("resource_name") or (schema.get("machine_id", "Miscellaneous") if schema.get("machine_id") else "Miscellaneous")
    
    lines = [
        f"*Description:* {schema.get('complaint_description', 'N/A')}",
        f"*Type:* {type_name}",
        f"*Tool/Category:* {tool_name}"
    ]
    return "\n".join(lines)


def _get_editable_fields(schema: dict) -> dict:
    type_id = schema.get("type", 1)
    fields = {
        1: "complaint_description",
        2: "type"
    }
    # Location relevant fields: Facility (2), Safety (3)
    if type_id in {2, 3}:
        fields[3] = "location_id"
    return fields


def _confirm_step_msg(schema: dict):
    type_id = schema.get("type", 0)
    type_name = TYPE_NAMES.get(type_id, "Miscellaneous")
    
    return (
        f"I've mapped this as a *{type_name}* complaint.\n\n"
        f"Please confirm your final complaint details:\n\n{_render_schema(schema)}\n\n"
        f"Reply *'y'* to proceed, *'n'* to cancel, or *'e'* to edit type."
    )


def _show_confirmation(schema: dict) -> str:
    return _confirm_step_msg(schema)


def _coerce_edited_value(field_name: str, raw_value: str):
    value = raw_value.strip()
    if value.lower() in {"null", "none", ""}:
        return None

    if field_name == "type":
        return _parse_type_value(value)

    if field_name in {"member_id", "machine_id", "location_id"}:
        return int(value)

    return value


def _parse_type_value(raw_value: str):
    value = raw_value.strip().lower()
    type_map = {
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
    if value.isdigit():
        type_num = int(value)
        if type_num in TYPE_NAMES:
            return type_num
    if value in type_map:
        return type_map[value]
    raise ValueError("invalid complaint type")


def _apply_schema_edit(db, schema: dict, field_number: int, raw_value: str) -> dict:
    fields = _get_editable_fields(schema)
    field_name = fields.get(field_number)
    if not field_name: return schema
    
    value = _coerce_edited_value(field_name, raw_value)
    schema[field_name] = value

    if field_name == "type":
        # If type changed to a non-physical one (like HR/IT), clear machine data
        if value not in {1, 2, 3, 4}:
            schema.pop("machine_id", None)
            schema.pop("resource_name", None)
            schema.pop("location_id", None)
            schema.pop("location_name", None)

    elif field_name == "location_name":
        loc_name, loc_id, _ = _resolve_lab_location(db, value)
        schema["location_name"] = loc_name
        schema["location_id"] = loc_id
    elif field_name == "location_id" and value is not None:
        loc_name, loc_id, _ = _resolve_lab_location(db, value)
        schema["location_name"] = loc_name
        schema["location_id"] = loc_id

    return schema


def _parse_edit_message(message: str, schema: dict):
    match = re.match(r"^\s*(\d+)\.(.+?)\s*$", message, re.DOTALL)
    if not match:
        return None, None
    field_number = int(match.group(1))
    field_value = match.group(2).strip()
    
    fields = _get_editable_fields(schema)
    if field_number not in fields:
        return None, None
    return field_number, field_value


def _register_complaint(db, schema: dict) -> str:
    url = os.getenv("PHP_API_URL")
    if not url:
        return "❌ *System Error*\nPHP_API_URL is not configured in the server environment. Please contact the IT Admin."

    payload = {
        "api_token": os.getenv("PHP_API_TOKEN", ""),
        "member_id": schema["member_id"],
        "type": schema["type"],
        "machine_id": schema.get("machine_id", 0),
        "complaint_description": schema["complaint_description"]
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            return (
                f"✅ *Complaint Registered Successfully by IITBNF Server*\n\n"
                f"Your issue has been formally recorded under the *{TYPE_NAMES.get(schema['type'], 'General')}* category and sent to the technical team. "
                "You may type a new message at any time to report another issue."
            )
        else:
            return (
                f"❌ *Registration Failed*\n\n"
                f"The IITBNF server rejected the complaint. (Status Code: {response.status_code})\n"
                f"Server response: {response.text}\n"
                "Please try again or contact the administrator."
            )
    except Exception as e:
        return (
            "❌ *Connection Error*\n\n"
            f"Failed to reach the IITBNF server.\nDetails: {str(e)}"
        )


def _prepare_initial_schema(db, member_id: int, message: str):
    schema = _blank_schema()
    schema["member_id"] = member_id
    schema["type"] = classify_complaint_type(message) or 0
    schema["status"] = 0  # 0 = Pending

    local_extracted = extract_local_complaint_schema(message, schema["type"])
    schema = _merge_schema(schema, local_extracted)
    schema = _resolve_schema_location(db, schema)

    if not schema.get("complaint_description"):
        schema["complaint_description"] = message

    schema, matched_resource, candidates = _enrich_schema_from_db(db, schema, message)
    schema["type"] = classify_complaint_type(message, matched_machine=matched_resource) or schema["type"]

    if schema["type"] in RESOURCE_TABLE_MAP and not schema.get("machine_id") and not schema.get("resource_name"):
        extracted = extract_complaint_schema(message, schema["type"])
        schema = _merge_schema(schema, extracted)
        schema, matched_resource, candidates = _enrich_schema_from_db(db, schema, message)
        schema["type"] = classify_complaint_type(message, matched_machine=matched_resource) or schema["type"]

    schema = _resolve_schema_location(db, schema, clear_unresolved=True)
    schema.pop("important_terms", None)
    schema.pop("important_phrases", None)

    return schema, candidates

def _store_collection_state(db, user_phone: str, schema: dict, current_field: str):
    upsert_state(db, user_phone, "collecting_info", {"schema": schema, "current_field": current_field})

def _store_selection_state(db, user_phone: str, schema: dict, candidates):
    upsert_state(
        db,
        user_phone,
        "select_resource",
        {
            "schema": schema,
            "candidates": [
                {
                    "machine_id": getattr(resource, "machid", getattr(resource, "device_id", None)),
                    "resource_name": getattr(resource, "name", getattr(resource, "device_name", None)),
                    "location_name": str(getattr(resource, "location", "")),
                }
                for resource in candidates
            ],
        },
    )


def _continue_or_confirm(db, user_phone: str, schema: dict, candidates=None) -> str:
    schema = _resolve_schema_location(db, schema, clear_unresolved=True)
    rf_cats = schema.get("_rf_categories", [])
    
    if len(rf_cats) > 1 and schema.get("type") in (None, 0):
        upsert_state(db, user_phone, "select_category", {"schema": schema, "categories": rf_cats})
        lines = ["Which type of issue is it? Reply with the number:"]
        for idx, c in enumerate(rf_cats, start=1):
            lines.append(f"{idx}. {TYPE_NAMES.get(c, 'Unknown')}")
        return "\n".join(lines)
        
    if schema.pop("_require_location_confirm", False):
        loc = schema.get("location_name")
        upsert_state(db, user_phone, "confirm_location", {"schema": schema})
        return f"I found this equipment is normally located in {loc}. Is that correct? (Yes/No)"

    complaint_type = schema.get("type")

    if candidates and len(candidates) > 1 and complaint_type in RESOURCE_REQUIRED_TYPES and not schema.get("machine_id"):
        _store_selection_state(db, user_phone, schema, candidates)
        return _format_candidate_options(candidates)

    next_field = _next_missing_field(schema)
    if next_field:
        # Layer 3 Fallback: If we can't find a tool after searching names and labs,
        # just label it Miscellaneous and proceed to confirmation screen.
        if next_field == "resource_name" and (complaint_type in RESOURCE_REQUIRED_TYPES or (complaint_type in {1,2,3,4})):
            schema["resource_name"] = "Miscellaneous"
            schema["machine_id"] = None
            # After setting these, re-check if we can confirm
            upsert_state(db, user_phone, "confirming", {"schema": schema})
            return _show_confirmation(schema)
            
        _store_collection_state(db, user_phone, schema, next_field)
        return _question_for_field(next_field, complaint_type)

    upsert_state(db, user_phone, "confirming", {"schema": schema})
    return _show_confirmation(schema)


def _handle_resource_selection(db, state, message: str, user_phone: str) -> str:
    data = parse_collected_data(state)
    schema = data.get("schema", {})
    candidates = data.get("candidates", [])

    if not message.strip().isdigit():
        schema = _fallback_to_misc(schema)
        return "Okay, skipping the tool selection.\n\n" + _continue_or_confirm(db, user_phone, schema)

    choice = int(message.strip())
    if choice == 0 or choice < 1 or choice > len(candidates):
        schema = _fallback_to_misc(schema)
        return "Okay, skipping the tool selection.\n\n" + _continue_or_confirm(db, user_phone, schema)

    selected = candidates[choice - 1]
    schema["machine_id"] = selected["machine_id"]
    schema["resource_name"] = selected["resource_name"]

    if not schema.get("location_name"):
        loc_name, loc_id, _ = _resolve_lab_location(db, selected.get("location_name"))
        schema["location_name"] = loc_name or selected.get("location_name")
        schema["location_id"] = loc_id

    return _continue_or_confirm(db, user_phone, schema)


def _handle_collecting_info(db, state, message: str, user_phone: str) -> str:
    data = parse_collected_data(state)
    schema = data.get("schema", {})
    current_field = data.get("current_field")
    answer = message.strip()

    if not answer:
        return _question_for_field(current_field, schema.get("type"))

    if current_field == "complaint_description":
        schema["complaint_description"] = answer
    elif current_field == "type":
        schema["type"] = _parse_type_value(answer)
    elif current_field == "location_name":
        loc_name, loc_id, _ = _resolve_lab_location(db, answer)
        if loc_id is None:
            return "I could not find that location in our records. Please enter the lab name as stored in the system."
        schema["location_name"] = loc_name
        schema["location_id"] = loc_id
    elif current_field == "resource_name":
        if schema.get("type") == 0 and answer.lower() == "skip":
            schema["resource_name"] = None
            schema["_misc_tool_skipped"] = True
            return _continue_or_confirm(db, user_phone, schema)

        schema["resource_name"] = answer

        if schema.get("type") == 0:
            matched_type, matched_resource, candidates = _resolve_misc_resource(
                db,
                answer,
                schema.get("location_name"),
            )
            if matched_type and matched_resource:
                schema["type"] = matched_type
                schema = _apply_matched_resource(db, schema, matched_resource)
                return _continue_or_confirm(db, user_phone, schema)
            if matched_type and len(candidates) > 1:
                schema["type"] = matched_type
                return _continue_or_confirm(db, user_phone, schema, candidates)
            return _continue_or_confirm(db, user_phone, schema)

        candidates = _resolve_resource_candidates(db, schema, answer)

        if len(candidates) == 1:
            schema = _apply_matched_resource(db, schema, candidates[0])
            return _continue_or_confirm(db, user_phone, schema)

        if len(candidates) > 1:
            return _continue_or_confirm(db, user_phone, schema, candidates)

    return _continue_or_confirm(db, user_phone, schema)


def _handle_confirmation(db, state, message: str, user_phone: str) -> str:
    data = parse_collected_data(state)
    schema = data.get("schema", {})
    msg = message.lower().strip()

    if msg in YES_WORDS:
        clear_state(db, user_phone)
        return _register_complaint(db, schema)

    if msg in NO_WORDS:
        clear_state(db, user_phone)
        return "Complaint registration canceled."

    if msg in EDIT_WORDS:
        upsert_state(db, user_phone, "editing_type", {"schema": schema})
        lines = ["What is the correct Type? Reply with the number:"]
        for i in range(1, 11):
            lines.append(f"{i}. {TYPE_NAMES.get(i)}")
        return "\n".join(lines)

    field_number, field_value = _parse_edit_message(message, schema)
    if field_number is not None:
        return "Please reply with exactly 'edit' to make changes, or 'yes' to confirm."

    return "Reply 'yes' to register the complaint or 'no' to cancel."


def _handle_category_selection(db, state, message: str, user_phone: str) -> str:
    data = parse_collected_data(state)
    schema = data.get("schema", {})
    categories = data.get("categories", [])
    
    if not message.strip().isdigit():
        schema = _fallback_to_misc(schema)
        return "I couldn't map that selection to a valid category, so I'm routing this to Miscellaneous.\n\n" + _continue_or_confirm(db, user_phone, schema)
        
    choice = int(message.strip())
    if choice == 0 or choice < 1 or choice > len(categories):
        schema = _fallback_to_misc(schema)
        return "I couldn't map that selection to a valid category, so I'm routing this to Miscellaneous.\n\n" + _continue_or_confirm(db, user_phone, schema)
        
    selected_cat = categories[choice - 1]
    schema["type"] = selected_cat
    schema["_rf_categories"] = [selected_cat]
    
    p_matches_ids = schema.get("_rf_candidates", {})
    ids = p_matches_ids.get(str(selected_cat), [])
    
    config = RESOURCE_TABLE_MAP.get(selected_cat)
    candidates = []
    if config and ids:
        model = config["model"]
        id_field = getattr(model, config["id_field"])
        candidates = db.query(model).filter(id_field.in_(ids)).all()
        
    if len(candidates) == 1:
        schema = _apply_matched_resource(db, schema, candidates[0])
        if schema.get("location_name"):
            schema["_require_location_confirm"] = True

    return _continue_or_confirm(db, user_phone, schema, candidates)



def _handle_location_confirmation(db, state, message: str, user_phone: str) -> str:
    data = parse_collected_data(state)
    schema = data.get("schema", {})
    msg = message.lower().strip()

    if msg in YES_WORDS:
        pass
    elif msg in NO_WORDS:
        schema["location_name"] = None
        schema["location_id"] = None
    else:
        return "Please reply 'y' or 'n'."
        
    return _continue_or_confirm(db, user_phone, schema)


def _handle_editing_type(db, state, message: str, user_phone: str) -> str:
    data = parse_collected_data(state)
    schema = data.get("schema", {})
    try:
        new_type = _parse_type_value(message)
        schema["type"] = new_type
        # When type changes, we should clear the old machine match
        schema["machine_id"] = None
        schema["resource_name"] = None
        
        upsert_state(db, user_phone, "confirming", {"schema": schema})
        return _continue_or_confirm(db, user_phone, schema)
    except ValueError:
        return "Invalid selection. Please reply with a valid type (e.g., Equipment, Facility, Safety, IT, HR)."

def _handle_ongoing_conversation(db, state, message: str, user_phone: str) -> str:
    if state.current_step == "select_category":
        return _handle_category_selection(db, state, message, user_phone)
    if state.current_step == "confirm_location":
        return _handle_location_confirmation(db, state, message, user_phone)
    if state.current_step == "select_resource":
        return _handle_resource_selection(db, state, message, user_phone)

    if state.current_step == "collecting_info":
        return _handle_collecting_info(db, state, message, user_phone)

    if state.current_step == "confirming":
        return _handle_confirmation(db, state, message, user_phone)

    if state.current_step == "editing_type":
        return _handle_editing_type(db, state, message, user_phone)

    clear_state(db, user_phone)
    return "I reset the previous conversation state. Please send your complaint again."


def get_chatbot_reply(user: dict, message: str) -> str:
    user_phone = user.get("mobile", "unknown")
    member_id = user.get("memberid", 1)
    msg = message.strip()
    msg_lower = msg.lower()

    db = SessionLocal()
    try:
        if msg_lower in {"cancel", "reset", "stop", "abort"}:
            clear_state(db, user_phone)
            return "Current complaint flow canceled."

        if msg_lower in {"undo", "delete", "remove", "revert"}:
            last_complaint = db.query(models.Complaint).filter(
                models.Complaint.member_id == member_id
            ).order_by(models.Complaint.complaint_id.desc()).first()
            if not last_complaint:
                return "No recent complaint was found to delete."

            db.delete(last_complaint)
            db.commit()
            return "Your latest complaint has been deleted."

        state = get_state(db, user_phone)
        if state:
            return _handle_ongoing_conversation(db, state, msg, user_phone)

        schema, candidates = _prepare_initial_schema(db, member_id, msg)
        return _continue_or_confirm(db, user_phone, schema, candidates)
    except Exception as exc:
        print(f"[ENGINE] Error: {exc}")
        traceback.print_exc()
        
        try:
            db.rollback()
            error_log = models.ChatbotErrorLog(
                user_phone=user_phone,
                error_message=str(exc),
                stack_trace=traceback.format_exc()
            )
            db.add(error_log)
            db.commit()
        except Exception as db_exc:
            print(f"[ENGINE] Failed to save error log: {db_exc}")

        return "Sorry, something went wrong processing your request. Please try again."
    finally:
        db.close()
