"""Schema-driven complaint engine with typed resource-table lookups."""

import json
import re
import traceback
from datetime import datetime

from app.chatbot import models
from app.chatbot.classifier import classify_complaint_type, extract_complaint_schema
from app.chatbot.db import SessionLocal
from app.chatbot.extractor import RESOURCE_TABLE_MAP, search_resource_candidates
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
RESOURCE_REQUIRED_TYPES = {1, 2, 3, 4}
LOCATION_RELEVANT_TYPES = {1, 2, 3, 4, 6, 9}
EDITABLE_FIELDS = {
    1: "member_id",
    2: "machine_id",
    3: "complaint_description",
    4: "type",
    5: "status",
    6: "time_of_complaint",
    7: "location_name",
    8: "location_id",
}


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


def _normalize_location_text(value: str) -> str:
    text = re.sub(r"[^a-z0-9\s]", " ", str(value).lower())
    tokens = [
        token for token in text.split()
        if token not in {"in", "the", "at", "inside", "near", "lab", "room", "area", "block"}
    ]
    return " ".join(tokens).strip()


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

            query_tokens = set(normalized_location.split())
            best_match = None
            best_score = 0
            for row in db.query(models.LabIncharge).all():
                row_normalized = _normalize_location_text(row.location or "")
                row_tokens = set(row_normalized.split())
                if not row_tokens:
                    continue

                overlap = len(query_tokens.intersection(row_tokens))
                if overlap > best_score:
                    best_match = row
                    best_score = overlap

            if best_match and best_score > 0:
                return best_match.location, best_match.locationid, best_match.memberid
    except Exception as exc:
        print(f"[ENGINE] Lab lookup failed: {exc}")

    cleaned = str(location_str).strip() or None
    return cleaned, None, None


def _merge_schema(schema: dict, extracted: dict) -> dict:
    for key, value in extracted.items():
        if key in schema and value not in (None, "", "null"):
            schema[key] = value
    return schema


def _resolve_resource_candidates(db, schema: dict, raw_message: str):
    complaint_type = schema.get("type")
    query = schema.get("resource_name") or raw_message
    if complaint_type not in RESOURCE_TABLE_MAP or not query:
        return []
    return search_resource_candidates(db, complaint_type, query, schema.get("location_name"))


def _apply_matched_resource(db, schema: dict, resource: object) -> dict:
    config = RESOURCE_TABLE_MAP[schema["type"]]
    schema["machine_id"] = getattr(resource, config["id_field"])
    schema["resource_name"] = getattr(resource, config["name_field"])
    schema["resource_table"] = config["model"].__tablename__

    if not schema.get("location_name"):
        location_value = getattr(resource, config["location_field"])
        loc_name, loc_id, _ = _resolve_lab_location(db, location_value)
        schema["location_name"] = loc_name or str(location_value)
        schema["location_id"] = loc_id

    return schema


def _enrich_schema_from_db(db, schema: dict, raw_message: str):
    matched_resource = None
    candidates = _resolve_resource_candidates(db, schema, raw_message)

    if len(candidates) == 1:
        matched_resource = candidates[0]
        schema = _apply_matched_resource(db, schema, matched_resource)

    if schema.get("location_name") and not schema.get("location_id"):
        loc_name, loc_id, _ = _resolve_lab_location(db, schema["location_name"])
        schema["location_name"] = loc_name or schema["location_name"]
        schema["location_id"] = loc_id

    return schema, matched_resource, candidates


def _next_missing_field(schema: dict) -> str | None:
    complaint_type = schema.get("type")

    if not schema.get("complaint_description"):
        return "complaint_description"

    if complaint_type in RESOURCE_REQUIRED_TYPES and not schema.get("machine_id"):
        return "resource_name"

    if complaint_type in LOCATION_RELEVANT_TYPES and not schema.get("location_name"):
        return "location_name"

    return None


def _question_for_field(field: str, complaint_type: int | None) -> str:
    type_name = TYPE_NAMES.get(complaint_type, "this")

    if field == "complaint_description":
        return f"I've classified this as a {type_name.lower()} complaint. What exactly is the issue?"
    if field == "resource_name":
        return f"This looks like a {type_name.lower()} complaint. Which {_resource_label(complaint_type)} is affected?"
    if field == "location_name":
        return f"Noted. Where is this {type_name.lower()} issue happening?"
    return f"Please provide {field}."


def _format_candidate_options(candidates) -> str:
    lines = ["I found multiple matching records. Reply with the number:"]
    for idx, resource in enumerate(candidates, start=1):
        label = getattr(resource, "name", getattr(resource, "device_name", "Unknown"))
        location = getattr(resource, "location", "")
        lines.append(f"{idx}. {label} ({location})")
    return "\n".join(lines)


def _render_schema(schema: dict) -> str:
    lines = ["{"]
    for index, field_name in EDITABLE_FIELDS.items():
        value = schema.get(field_name)
        rendered = json.dumps(value, default=str)
        lines.append(f'  "{index}.{field_name}": {rendered},')
    lines[-1] = lines[-1].rstrip(",")
    lines.append("}")
    return "\n".join(lines)


def _show_confirmation(schema: dict) -> str:
    return (
        f"Please confirm this complaint schema:\n{_render_schema(schema)}\n\n"
        "Reply 'yes' to register, 'no' to cancel, or send an edit like '1.new_value'."
    )


def _coerce_edited_value(field_name: str, raw_value: str):
    value = raw_value.strip()
    if value.lower() in {"null", "none", ""}:
        return None

    if field_name in {"member_id", "machine_id", "type", "location_id"}:
        return int(value)

    return value


def _apply_schema_edit(db, schema: dict, field_number: int, raw_value: str) -> dict:
    field_name = EDITABLE_FIELDS[field_number]
    value = _coerce_edited_value(field_name, raw_value)
    schema[field_name] = value

    if field_name == "location_name":
        loc_name, loc_id, _ = _resolve_lab_location(db, value)
        schema["location_name"] = loc_name or value
        schema["location_id"] = loc_id
    elif field_name == "location_id" and value is not None:
        loc_name, loc_id, _ = _resolve_lab_location(db, value)
        schema["location_name"] = loc_name or schema.get("location_name")
        schema["location_id"] = loc_id

    return schema


def _parse_edit_message(message: str):
    match = re.match(r"^\s*(\d+)\.(.+?)\s*$", message, re.DOTALL)
    if not match:
        return None, None
    field_number = int(match.group(1))
    field_value = match.group(2).strip()
    if field_number not in EDITABLE_FIELDS:
        return None, None
    return field_number, field_value


def _register_complaint(db, schema: dict) -> str:
    schema["status"] = "Open"
    schema["time_of_complaint"] = datetime.now()

    complaint = models.Complaint(
        member_id=schema["member_id"],
        machine_id=schema.get("machine_id"),
        complaint_description=schema["complaint_description"],
        type=schema["type"],
        status=schema["status"],
        location_name=schema.get("location_name"),
        location_id=schema.get("location_id"),
        time_of_complaint=schema["time_of_complaint"],
    )
    db.add(complaint)
    db.commit()

    return (
        "Complaint registered successfully.\n"
        f"Type: {TYPE_NAMES.get(schema['type'], 'Unknown')}\n"
        f"Status: {schema['status']}\n"
        "❌ -------------------- End of complaint conversation --------------------"
    )


def _prepare_initial_schema(db, member_id: int, message: str):
    schema = _blank_schema()
    schema["member_id"] = member_id
    schema["type"] = classify_complaint_type(message)
    schema["status"] = "Open"

    if schema["type"] in RESOURCE_TABLE_MAP:
        extracted = extract_complaint_schema(message, schema["type"])
        schema = _merge_schema(schema, extracted)

    if not schema.get("complaint_description"):
        schema["complaint_description"] = message

    schema, matched_resource, candidates = _enrich_schema_from_db(db, schema, message)
    schema["type"] = classify_complaint_type(message, matched_machine=matched_resource)

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
    complaint_type = schema.get("type")

    if candidates and len(candidates) > 1 and complaint_type in RESOURCE_REQUIRED_TYPES and not schema.get("machine_id"):
        _store_selection_state(db, user_phone, schema, candidates)
        return _format_candidate_options(candidates)

    next_field = _next_missing_field(schema)
    if next_field:
        _store_collection_state(db, user_phone, schema, next_field)
        return _question_for_field(next_field, complaint_type)

    upsert_state(db, user_phone, "confirming", {"schema": schema})
    return _show_confirmation(schema)


def _handle_resource_selection(db, state, message: str, user_phone: str) -> str:
    data = parse_collected_data(state)
    schema = data.get("schema", {})
    candidates = data.get("candidates", [])

    if not message.strip().isdigit():
        return "Reply with the number from the list."

    choice = int(message.strip())
    if choice < 1 or choice > len(candidates):
        return "That number is not valid. Reply with one of the listed numbers."

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
    elif current_field == "location_name":
        loc_name, loc_id, _ = _resolve_lab_location(db, answer)
        schema["location_name"] = loc_name or answer
        schema["location_id"] = loc_id
    elif current_field == "resource_name":
        schema["resource_name"] = answer
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

    field_number, field_value = _parse_edit_message(message)
    if field_number is not None:
        try:
            schema = _apply_schema_edit(db, schema, field_number, field_value)
        except ValueError:
            return "That edited value is not valid for the selected field."

        upsert_state(db, user_phone, "confirming", {"schema": schema})
        return (
            f"Updated {EDITABLE_FIELDS[field_number]}.\n\n"
            f"{_show_confirmation(schema)}"
        )

    return "Reply 'yes' to register the complaint or 'no' to cancel."


def _handle_ongoing_conversation(db, state, message: str, user_phone: str) -> str:
    if state.current_step == "select_resource":
        return _handle_resource_selection(db, state, message, user_phone)

    if state.current_step == "collecting_info":
        return _handle_collecting_info(db, state, message, user_phone)

    if state.current_step == "confirming":
        return _handle_confirmation(db, state, message, user_phone)

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
        return "Sorry, something went wrong. Please try again."
    finally:
        db.close()
