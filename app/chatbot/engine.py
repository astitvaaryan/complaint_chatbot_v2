"""
app/chatbot/engine.py
─────────────────────────────────────────
Main chatbot logic engine.

Flow (single machine found):
  1. User sends "DG SET not working"
  2. Machine matched → type auto-classified → complaint logged

Flow (multiple machines found):
  1. User sends "Dehumidifier has issue"
  2. Bot sends numbered list of matches
  3. User replies "2"
  4. Bot logs complaint for machine #2

Complaint Types:
  1=Equipment, 2=Facility, 3=Safety, 4=Process,
  5=HR, 6=IT, 7=Purchase, 8=Training, 9=Inventory, 10=Admin
"""

import json
import difflib
import traceback
from app.chatbot.db import SessionLocal
from app.chatbot import models
from app.chatbot.extractor import extract_machine_db
from app.chatbot.classifier import classify_complaint_type, extract_unknown_equipment
from app.chatbot.state_manager import get_state, upsert_state, clear_state, parse_collected_data

# Complaint type display names (1-10)
TYPE_NAMES = {
    1: "Equipment", 2: "Facility",  3: "Safety",
    4: "Process",   5: "HR",        6: "IT",
    7: "Purchase",  8: "Training",  9: "Inventory",
    10: "Admin"
}


def _resolve_lab_location(db, location_str: str):
    """
    Look up lab incharge from lab_incharge table.
    resources.location stores an integer (locationid).
    Returns (location_name, location_id, memberid_of_incharge)
    """
    try:
        if not location_str:
            return location_str, None, None

        # Try integer match first (resources.location stores locationid as int)
        try:
            loc_id = int(location_str)
            incharge = db.query(models.LabIncharge).filter(
                models.LabIncharge.locationid == loc_id
            ).first()
            if incharge:
                return incharge.location, incharge.locationid, incharge.memberid
        except ValueError:
            pass

        # Fallback: string match on location name
        incharge = db.query(models.LabIncharge).filter(
            models.LabIncharge.location.ilike(f"%{location_str}%")
        ).first()
        if incharge:
            return incharge.location, incharge.locationid, incharge.memberid

    except Exception as e:
        print(f"[ENGINE] Lab incharge lookup failed: {e}")

    return location_str, None, None


def _log_complaint(db, member_id: int, machine: models.Resources, description: str, location_name, location_id, complaint_type: int) -> str:
    """Log complaint to DB and return confirmation message."""
    type_name = TYPE_NAMES.get(complaint_type, "Equipment")

    new_complaint = models.Complaint(
        member_id=member_id,
        machine_id=machine.machid,
        location_name=location_name or str(machine.location),
        location_id=location_id,
        complaint_description=description,
        type=complaint_type,
        status="Open"
    )
    db.add(new_complaint)
    db.commit()

    print(f"✅ Complaint logged: {machine.name} | Type: {type_name} ({complaint_type}) | Member: {member_id}")

    return (
        f"Got it! I've logged your complaint for *{machine.name}* at {location_name or machine.location}. "
        f"Our team will look into it shortly. 👍\n"
        f"_(Ref: {type_name} complaint — Status: Open)_"
    )

def needs_issue_description(msg: str) -> bool:
    """Check if the user only provided a machine name without any problem description."""
    issue_keywords = {
        "work", "issue", "problem", "broken", "fault", "error", 
        "fail", "repair", "down", "stop", "noise", "spill", 
        "leak", "damage", "not", "fix", "refund", "reimbursement", 
        "payment", "bill"
    }
    msg_lower = msg.lower()
    
    # If the user explicitly used problem words, they provided a problem
    if any(kw in msg_lower for kw in issue_keywords):
        return False
        
    # If there are no problem words and the message is short (e.g. just a machine name like "AC" or "Furnace")
    # Tell them we need the issue described
    if len(msg.split()) <= 4:
        return True
        
    return False


def get_chatbot_reply(user: dict, message: str) -> str:
    """
    Main entry point called from webhook.py after login check.
    """
    user_phone = user.get("mobile", "unknown")
    member_id = user.get("memberid", 1)

    db = SessionLocal()
    try:
        # ── Check for active conversation state ────────────────────
        state = get_state(db, user_phone)
        msg_lower_check = message.lower().strip()

        # Global escape word check (Works anytime, whether in state or not)
        if msg_lower_check in ["cancel", "reset", "stop", "abort"]:
            clear_state(db, user_phone)
            state = None
            return "Sure, I've canceled your current action. 🧹 What else can I help you with?"

        # Global 'undo' rule to delete the LAST registered complaint
        if msg_lower_check in ["undo", "delete", "remove", "revert"]:
            last_complaint = db.query(models.Complaint).filter(
                models.Complaint.member_id == member_id
            ).order_by(models.Complaint.complaint_id.desc()).first()
            
            if last_complaint:
                db.delete(last_complaint)
                db.commit()
                return "I've successfully deleted your last registered complaint. 🗑️ What's next?"
            else:
                return "You don't have any recent complaints to delete! 🤔"

        if state:
            # Universal escape hatchet: if user starts a NEW complaint,
            # we clear the stale state and proceed as a fresh query.
            # EXCEPTION: If we are actively waiting for a problem description, don't clear!
            issue_keywords = {"not working", "issue", "problem", "broken", "fault",
                              "error", "failed", "repair", "down", "stopped"}
            is_new_complaint = any(kw in msg_lower_check for kw in issue_keywords)
            
            if is_new_complaint and state.current_step != "waiting_for_problem":
                clear_state(db, user_phone)
                state = None
                print(f"[ENGINE] Stale state cleared — new complaint detected: '{message}'")

        # ── STEP: User provided the problem description ──────────────
        if state and state.current_step == "waiting_for_problem":
            data = parse_collected_data(state)
            complaint_desc = message.strip()
            
            machine_id = data.get("machine_id")
            machine_name = data.get("machine_name", "Unknown Equipment")
            location_name = data.get("location_name", "N/A")
            location_id = data.get("location_id")
            complaint_type = data.get("complaint_type", 1)
            type_name = TYPE_NAMES.get(complaint_type, "Equipment")
            
            if machine_id: # known machine
                machine = db.query(models.Resources).filter(models.Resources.machid == machine_id).first()
                clear_state(db, user_phone)
                return _log_complaint(db, member_id, machine, complaint_desc, location_name, location_id, complaint_type)
            else: # unknown machine or general complaint bypasses _log_complaint
                new_complaint = models.Complaint(
                    member_id=member_id,
                    machine_id=None,
                    location_name=location_name,
                    location_id=None,
                    complaint_description=complaint_desc,
                    type=complaint_type,
                    status="Open"
                )
                db.add(new_complaint)
                db.commit()
                clear_state(db, user_phone)
                return (
                    f"Done! I've noted the issue with *{machine_name}*. "
                    f"Someone will get back to you soon. 👍\n"
                    f"_(Ref: {type_name} complaint — Status: Open)_"
                )

        # ── STEP: User selecting from numbered list ─────────────────
        if state and state.current_step == "waiting_for_selection":
            data = parse_collected_data(state)
            machines_data = data.get("machines", [])
            original_msg = data.get("original_message", message)

            # Try to parse user's selection number
            selection = message.strip()
            if selection.isdigit():
                idx = int(selection) - 1
                if 0 <= idx < len(machines_data):
                    machine_info = machines_data[idx]

                    # Re-query the actual machine object
                    machine = db.query(models.Resources).filter(
                        models.Resources.machid == machine_info["machid"]
                    ).first()

                    if machine:
                        clear_state(db, user_phone)
                        location_name, location_id, _ = _resolve_lab_location(db, str(machine.location))
                        complaint_type = classify_complaint_type(original_msg, machine)
                        
                        if needs_issue_description(original_msg):
                            upsert_state(db, user_phone, "waiting_for_problem", {
                                "machine_id": machine.machid,
                                "machine_name": machine.name,
                                "location_name": location_name,
                                "location_id": location_id,
                                "complaint_type": complaint_type
                            })
                            return f"Got it, you picked *{machine.name}*. What exact issue are you facing with it?"

                        return _log_complaint(db, member_id, machine, original_msg, location_name, location_id, complaint_type)

            # Invalid selection
            options = "\n".join(
                [f"{i+1}. {m['name']} — {m['location']}"
                 for i, m in enumerate(machines_data)]
            )
            return (
                f"Hmm, just send the number next to the machine you mean 😊\n\n"
                f"{options}"
            )

        # ── STEP: User narrowed by location ────────────────────────
        if state and state.current_step == "waiting_for_narrowing":
            data = parse_collected_data(state)
            all_machines = data.get("machines", [])
            unique_locs = data.get("unique_locs", [])
            original_msg = data.get("original_message", message)
            
            user_input = message.strip().lower()
            location_filter = None

            # Check if user replied with a digit index
            if user_input.isdigit():
                idx = int(user_input) - 1
                if 0 <= idx < len(unique_locs):
                    location_filter = unique_locs[idx].lower()
            
            # If not a digit, fall back to loose string matching
            if not location_filter:
                location_filter = user_input

            # Filter stored candidates by location string
            narrowed = [
                m for m in all_machines
                if location_filter in m["location"].lower() or
                   location_filter in m["name"].lower()
            ]

            if not narrowed:
                # Location not recognized — tell user and re-show valid options
                locs_text = "\n".join(f"{i+1}. {loc}" for i, loc in enumerate(unique_locs))
                return (
                    f"I couldn't find *'{message.strip()}'* in our lab list. Could you try sending one of these numbers?\n\n"
                    f"{locs_text}"
                )

            # Always display the list of narrowed items now, regardless of how many there are.
            upsert_state(db, user_phone, "waiting_for_selection", {
                "machines": narrowed,
                "original_message": original_msg,
                "member_id": member_id,
            })
            options = "\n".join(
                [f"{i+1}. {m['name']} — {m['location']}"
                 for i, m in enumerate(narrowed)]
            )
            return f"Here's what I found in that area. Which one is it?\n\n{options}"

        # ── STEP: User provided location for unknown equipment ─────

        if state and state.current_step == "waiting_for_location":
            data = parse_collected_data(state)

            # Use this message as the location answer
            location_str = message.strip()
            complaint_type = data.get("complaint_type", 1)
            machine_name = data.get("machine_name", "Unknown Equipment")
            type_name = TYPE_NAMES.get(complaint_type, "Equipment")
            original_msg = data.get("original_message", "")

            if needs_issue_description(original_msg):
                upsert_state(db, user_phone, "waiting_for_problem", {
                    "machine_id": data.get("machine_id"),
                    "machine_name": machine_name,
                    "location_name": location_str,
                    "location_id": data.get("location_id"),
                    "complaint_type": complaint_type
                })
                return f"Got it, location is {location_str}. What exact issue are you facing with *{machine_name}*?"

            new_complaint = models.Complaint(
                member_id=member_id,
                machine_id=None,
                location_name=location_str,
                location_id=None,
                complaint_description=data.get("original_message", ""),
                type=complaint_type,
                status="Open"
            )
            db.add(new_complaint)
            db.commit()
            clear_state(db, user_phone)

            print(f"✅ Unknown equipment complaint: {machine_name} | Location: {location_str}")
            return (
                f"Done! I've noted the issue with *{machine_name}* at {location_str}. "
                f"Someone will get back to you soon. 👍\n"
                f"_(Ref: {type_name} complaint — Status: Open)_"
            )

        # ── Match machine from ACTIVE resources ────────────────────

        matched = extract_machine_db(message, db)

        # ── No machine found → unknown equipment flow ──────────────
        if not matched:
            # ── Keyword fallback BEFORE Gemini (works even if Gemini fails) ──
            KEYWORD_FALLBACK = {
                3:  ["fire", "hazard", "safety", "accident", "emergency", "leak", "gas", "toxic", "smoke"],
                5:  ["salary", "leave", "hr", "payroll", "attendance", "holiday", "increment", "refund", "reimbursement", "payment", "bill", "invoice"],
                6:  ["laptop", "wifi", "internet", "software", "computer", "network", "email", "vpn"],
                7:  ["purchase", "order", "buy", "vendor", "quote", "chemical", "spare", "procurement"],
                8:  ["training", "workshop", "course", "seminar", "certification", "demo"],
                9:  ["inventory", "stock", "quantity", "missing", "spare parts"],
                10: ["admin", "permission", "access", "policy", "approval", "letter", "document"],
            }
            msg_lower_kw = message.lower()
            keyword_type = None
            for t, kws in KEYWORD_FALLBACK.items():
                if any(kw in msg_lower_kw for kw in kws):
                    keyword_type = t
                    break

            # Use Gemini to extract machine name + type from message
            extracted = extract_unknown_equipment(message)
            machine_name = extracted["machine_name"]
            
            # Unconditionally trust local keyword matches over Gemini's guess
            complaint_type = extracted["complaint_type"]
            if keyword_type:
                complaint_type = keyword_type
                print(f"[ENGINE] Keyword override: type → {complaint_type}")

            # Non-equipment types (HR, IT, Admin, Safety, Purchase, Training, Inventory)
            # don't need a physical location — log directly
            NON_EQUIPMENT_TYPES = {3, 5, 6, 7, 8, 9, 10}  # Safety, HR, IT, Purchase, Training, Inventory, Admin

            if complaint_type in NON_EQUIPMENT_TYPES:
                if needs_issue_description(message):
                    upsert_state(db, user_phone, "waiting_for_problem", {
                        "machine_id": None,
                        "machine_name": "General Request",
                        "location_name": "N/A",
                        "location_id": None,
                        "complaint_type": complaint_type
                    })
                    type_name_friendly = TYPE_NAMES.get(complaint_type, "General").lower()
                    return f"You want to log an {type_name_friendly} request. What exactly is the issue or details?"

                new_complaint = models.Complaint(
                    member_id=member_id,
                    machine_id=None,
                    location_name="N/A",
                    location_id=None,
                    complaint_description=message,
                    type=complaint_type,
                    status="Open"
                )
                db.add(new_complaint)
                db.commit()
                type_name = TYPE_NAMES.get(complaint_type, "General")
                print(f"✅ Non-equipment complaint: {machine_name} | Type: {type_name}")
                return (
                    f"Noted! Your {type_name} request has been logged and will be taken up soon. 👍\n"
                    f"_(Status: Open)_"
                )

            # Equipment / Facility types → ask for location
            upsert_state(db, user_phone, "waiting_for_location", {
                "machine_name": machine_name,
                "complaint_type": complaint_type,
                "original_message": message,
                "member_id": member_id,
            })

            return (
                f"Hmm, I don't have *{machine_name}* in my database yet. "
                f"Which lab or room is it in? Just type the name and I'll log it for you."
            )


        # ── Single match → log directly ────────────────────────────
        if len(matched) == 1:
            machine = matched[0]
            location_name, location_id, _ = _resolve_lab_location(db, str(machine.location))

            # If location is missing/unresolvable → ask user
            if not location_name or location_name.strip() in ["", "None", "0", "none"]:
                complaint_type = classify_complaint_type(message, machine)
                upsert_state(db, user_phone, "waiting_for_location", {
                    "machine_name": machine.name,
                    "machine_id": machine.machid,
                    "complaint_type": complaint_type,
                    "original_message": message,
                    "member_id": member_id,
                })
                return (
                    f"I found *{machine.name}* but its location isn't set in our system yet. "
                    f"Which lab or room is it in?"
                )

            complaint_type = classify_complaint_type(message, machine)
            
            if needs_issue_description(message):
                upsert_state(db, user_phone, "waiting_for_problem", {
                    "machine_id": machine.machid,
                    "machine_name": machine.name,
                    "location_name": location_name,
                    "location_id": location_id,
                    "complaint_type": complaint_type
                })
                return f"Got it, you mean *{machine.name}*. What exact issue are you facing with it?"
                
            return _log_complaint(db, member_id, machine, message, location_name, location_id, complaint_type)

        # ── Multiple matches → bulk-load locations, then decide ────
        # Batch load ALL lab locations in one query (avoids N+1 per machine)
        all_incharge = db.query(models.LabIncharge).all()
        loc_map = {row.locationid: row.location for row in all_incharge}

        def resolve_loc(loc_val):
            try:
                lid = int(str(loc_val))
                return loc_map.get(lid) or str(loc_val)
            except (ValueError, TypeError):
                return str(loc_val)

        # Build machine data using the pre-loaded map
        machines_data = []
        for m in matched:
            machines_data.append({
                "machid": m.machid,
                "name": m.name,
                "location": resolve_loc(m.location)
            })

        # If too many matches → ask for location to narrow down FIRST
        if len(machines_data) > 20:
            unique_locs = sorted(list(set(m["location"] for m in machines_data if m.get("location"))))
            upsert_state(db, user_phone, "waiting_for_narrowing", {
                "machines": machines_data,
                "unique_locs": unique_locs,
                "original_message": message,
                "member_id": member_id,
            })
            locs_text = "\n".join(f"{i+1}. {loc}" for i, loc in enumerate(unique_locs))
            return (
                f"I found {len(matched)} machines with that name across different labs. "
                f"Please reply with the number for your lab:\n\n{locs_text}"
            )

        # 20 or fewer → show numbered list
        upsert_state(db, user_phone, "waiting_for_selection", {
            "machines": machines_data,
            "original_message": message,
            "member_id": member_id,
        })
        options = "\n".join(
            [f"{i+1}. {m['name']} — {m['location']}"
             for i, m in enumerate(machines_data)]
        )
        return (
            f"I found a few matches. Which one are you referring to?\n\n"
            f"{options}"
        )




    except Exception as e:
        print(f"[CHATBOT ENGINE ERROR] {e}")
        traceback.print_exc()
        return "Sorry, something went wrong on my end. Could you try again?"

    finally:
        db.close()
