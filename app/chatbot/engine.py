"""
app/chatbot/engine.py
─────────────────────────────────────────
Main chatbot logic engine.

Classification pipeline (see classifier.py):
  Layer 1-A  Machine DB category → type  (instant)
  Layer 1-B  Keyword scoring             (instant, augmented from Kaggle CSV)
  Layer 2    Gemini 2.0 Flash API        (only when L1 fails)
  Fallback   Ask user to clarify once → then show manual menu

Complaint Types in this system:
  1=Equipment, 2=Facility, 3=Safety, 4=Process,
  5=HR, 6=IT, 7=Purchase, 10=Admin

Conversation steps:
  waiting_for_problem        — need the issue description from the user
  waiting_for_selection      — user picks one of several matched machines
  waiting_for_narrowing      — too many matches; narrowing by location first
  waiting_for_location       — known/unknown machine but location missing
  waiting_for_clarification  — classifier returned None; ask to rephrase
  waiting_for_type_selection — second failure; show manual type-number menu
"""

import json
import traceback
from app.chatbot.db import SessionLocal
from app.chatbot import models
from app.chatbot.extractor import extract_machine_db
from app.chatbot.classifier import classify_complaint_type, extract_unknown_equipment, extract_unknown_smart, keyword_match
from app.chatbot.state_manager import get_state, upsert_state, clear_state, parse_collected_data

# Complaint type display names (1-10)
TYPE_NAMES = {
    1: "Equipment", 2: "Facility",  3: "Safety",
    4: "Process",   5: "HR",        6: "IT",
    7: "Purchase",  8: "Training",  9: "Inventory",
    10: "Admin"
}

# Types that do NOT require a physical machine / location
# 2=Facility, 3=Safety, 5=HR, 6=IT, etc.
NON_EQUIPMENT_TYPES = {2, 3, 5, 6, 7, 8, 9, 10}


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


def _log_complaint(db, member_id: int, machine: any, description: str, location_name, location_id, complaint_type: int) -> str:
    """Log complaint to DB and return confirmation message."""
    type_name = TYPE_NAMES.get(complaint_type, "Equipment")
    
    # Normalize attributes based on class type
    m_name = getattr(machine, "name", getattr(machine, "device_name", "Unknown Machine"))
    m_id = getattr(machine, "machid", getattr(machine, "device_id", None))

    new_complaint = models.Complaint(
        member_id=member_id,
        machine_id=m_id,
        location_name=location_name or str(machine.location),
        location_id=location_id,
        complaint_description=description,
        type=complaint_type,
        status="Open"
    )
    db.add(new_complaint)
    db.commit()

    print(f"✅ Complaint logged: {m_name} | Type: {type_name} ({complaint_type}) | Member: {member_id}")

    return (
        f"Got it! I've logged your complaint for *{m_name}* at {location_name or machine.location}. "
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
            # ── UNIVERSAL ESCAPE HATCH ──
            # If user starts a NEW specific complaint while in a menu, clear state.
            # We check if:
            # 1. Message contains a known machine name from DB
            # 2. Message has a very clear category match (Layer 1 scoring)
            # 3. Message contains "issue" keywords and NOT a menu digit
            
            is_digit = message.strip().isdigit()
            
            # Categories that are usually "sticky" until answered
            PRESERVE_STEPS = {"waiting_for_problem"} 
            
            new_machines = extract_machine_db(message, db)
            high_conf_type = keyword_match(message) # Only returns if confident
            
            issue_keywords = {"is not", "isnt", "broken", "spill", "leak", "stopped", "fault", "off"}
            has_issue_words = any(kw in msg_lower_check for kw in issue_keywords)

            # If it's a confident new machine or strong keywords, and user didn't just send a number
            if (new_machines or high_conf_type or has_issue_words) and not is_digit:
                if state.current_step not in PRESERVE_STEPS:
                    clear_state(db, user_phone)
                    state = None
                    print(f"[ENGINE] Escape Hatch: Clear state '{state}' for new input: '{message}'")

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
                m_type = data.get("model_type", "Resources")
                # Precise re-query based on stored model type
                if m_type == "SafetyDevice":
                    machine = db.query(models.SafetyDevice).filter(models.SafetyDevice.device_id == machine_id).first()
                elif m_type == "EqpProcessResource":
                    machine = db.query(models.EqpProcessResource).filter(models.EqpProcessResource.machid == machine_id).first()
                else:
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

        # ── STEP: Classifier returned None → asked user to clarify ────
        if state and state.current_step == "waiting_for_clarification":
            data          = parse_collected_data(state)
            original_msg  = data.get("original_message", "")
            machine_id    = data.get("machine_id")

            # Try to classify the new rephrased message
            clarified_type = classify_complaint_type(message)

            if clarified_type is not None:
                # Great — we now know the type; proceed normally
                clear_state(db, user_phone)
                complaint_type = clarified_type
                type_name = TYPE_NAMES.get(complaint_type, "General")
                
                if complaint_type in NON_EQUIPMENT_TYPES:
                    new_complaint = models.Complaint(
                        member_id=member_id, machine_id=None,
                        location_name="N/A", location_id=None,
                        complaint_description=f"{original_msg} | {message}".strip(" |"),
                        type=complaint_type, status="Open"
                    )
                    db.add(new_complaint)
                    db.commit()
                    return (
                        f"Noted! Your *{type_name}* complaint has been logged. 👍\n"
                        f"_(Status: Open)_"
                    )

                if machine_id:
                    machine = db.query(models.Resources).filter(
                        models.Resources.machid == machine_id).first()
                    if machine:
                        location_name, location_id, _ = _resolve_lab_location(db, str(machine.location))
                        return _log_complaint(db, member_id, machine, message,
                                             location_name, location_id, complaint_type)

                # Unknown equipment — fall through to location step
                machine_name = data.get("machine_name", "Unknown Equipment")
                upsert_state(db, user_phone, "waiting_for_location", {
                    "machine_name": machine_name, "complaint_type": complaint_type,
                    "original_message": message, "member_id": member_id,
                })
                return (f"Got it! Which lab or room is *{machine_name}* located in?")

            # Still unclear → escalate to manual menu
            clear_state(db, user_phone)
            MANUAL_MENU = (
                "I'm still not sure what type of complaint this is. "
                "Please pick a number:\n\n"
                "1️⃣  Equipment (lab machines)\n"
                "2️⃣  Facility (AC, power, building)\n"
                "3️⃣  Safety (fire, spill, hazard)\n"
                "4️⃣  Process (recipe, yield)\n"
                "5️⃣  HR (salary, leave, payroll)\n"
                "6️⃣  IT (laptop, wifi, software)\n"
                "7️⃣  Purchase (order, vendor, spares)\n"
                "8️⃣  Training (workshop, course, seminar)\n"
                "9️⃣  Inventory (stock, missing items, spares)\n"
                "🔟  Admin (documents, policy, access)"
            )
            upsert_state(db, user_phone, "waiting_for_type_selection", {
                "original_message": original_msg or message,
                "machine_id":       machine_id,
                "machine_name":     data.get("machine_name", "Unknown Equipment"),
            })
            return MANUAL_MENU

        # ── STEP: Manual type-number selection menu ───────────────────
        if state and state.current_step == "waiting_for_type_selection":
            data           = parse_collected_data(state)
            original_msg   = data.get("original_message", message)
            machine_id     = data.get("machine_id")
            machine_name   = data.get("machine_name", "Unknown Equipment")
            ALLOWED_INPUTS = {"1":1, "2":2, "3":3, "4":4, "5":5,
                              "6":6, "7":7, "8":8, "9":9, "10":10}

            selection = message.strip()
            if selection in ALLOWED_INPUTS:
                complaint_type = ALLOWED_INPUTS[selection]
                type_name      = TYPE_NAMES.get(complaint_type, "General")
                if complaint_type in NON_EQUIPMENT_TYPES:
                    new_complaint = models.Complaint(
                        member_id=member_id, machine_id=None,
                        location_name="N/A", location_id=None,
                        complaint_description=original_msg,
                        type=complaint_type, status="Open"
                    )
                    db.add(new_complaint)
                    db.commit()
                    return (
                        f"Done! Your *{type_name}* complaint has been logged. 👍\n"
                        f"_(Status: Open)_"
                    )

                if machine_id:
                    machine = db.query(models.Resources).filter(
                        models.Resources.machid == machine_id).first()
                    if machine:
                        location_name, location_id, _ = _resolve_lab_location(db, str(machine.location))
                        return _log_complaint(db, member_id, machine, original_msg,
                                             location_name, location_id, complaint_type)

                # Unknown equipment path
                upsert_state(db, user_phone, "waiting_for_location", {
                    "machine_name": machine_name, "complaint_type": complaint_type,
                    "original_message": original_msg, "member_id": member_id,
                })
                return (f"Got it! Which lab or room is *{machine_name}* located in?")

            # Invalid menu input
            return (
                "Please reply with just the number from the list:\n"
                "1 Equipment · 2 Facility · 3 Safety · 4 Process\n"
                "5 HR · 6 IT · 7 Purchase · 8 Training · 9 Inventory · 10 Admin"
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

                    # Re-query the actual machine object from the SPECIFIC table (prevents ID collisions)
                    m_type = machine_info.get("model_type", "Resources")
                    mid = machine_info["machid"]
                    
                    if m_type == "SafetyDevice":
                        machine = db.query(models.SafetyDevice).filter(models.SafetyDevice.device_id == mid).first()
                    elif m_type == "EqpProcessResource":
                        machine = db.query(models.EqpProcessResource).filter(models.EqpProcessResource.machid == mid).first()
                    else:
                        machine = db.query(models.Resources).filter(models.Resources.machid == mid).first()

                    if machine:
                        clear_state(db, user_phone)
                        location_name, location_id, _ = _resolve_lab_location(db, str(machine.location))
                        complaint_type = classify_complaint_type(original_msg, machine)
                        
                        if needs_issue_description(original_msg):
                            upsert_state(db, user_phone, "waiting_for_problem", {
                                "machine_id": getattr(machine, 'machid', getattr(machine, 'device_id', None)),
                                "model_type": type(machine).__name__,
                                "machine_name": getattr(machine, 'name', getattr(machine, 'device_name', '')),
                                "location_name": location_name,
                                "location_id": location_id,
                                "complaint_type": complaint_type
                            })
                            return f"Got it, you picked *{machine.name}*. What exact issue are you facing with it?"

                        return _log_complaint(db, member_id, machine, original_msg, location_name, location_id, complaint_type)

                elif idx == len(machines_data):
                    # Use the full intelligent pipeline (DB -> Key -> Gemini)
                    complaint_type = classify_complaint_type(original_msg) or 1
                    
                    # ── Logic Shift: If it's a non-equipment type, don't ask for a machine/location ──
                    if complaint_type in NON_EQUIPMENT_TYPES:
                        type_name_friendly = TYPE_NAMES.get(complaint_type, "General")
                        
                        # Always ask for details instead of logging directly
                        upsert_state(db, user_phone, "waiting_for_problem", {
                            "machine_id":    None,
                            "machine_name":  "General Request",
                            "location_name": "N/A",
                            "location_id":   None,
                            "complaint_type": complaint_type
                        })
                        return f"Got it, this sounds like a *{type_name_friendly}* request. Could you give me a bit more detail about the issue?"

                    # ── Conversational Extraction ──────────────────────
                    # Instead of "Unknown Equipment", get a smart name (e.g., "Lighting", "AC")
                    machine_name = extract_unknown_smart(original_msg)
                    
                    upsert_state(db, user_phone, "waiting_for_location", {
                        "machine_name": machine_name,
                        "complaint_type": complaint_type,
                        "original_message": original_msg,
                        "member_id": member_id,
                    })
                    
                    if machine_name in ["this issue", "item"]:
                        return "Got it! Which lab or room are you talking about?"
                    return f"Okay! Which lab or room is the *{machine_name}* located in?"

            # Invalid selection
            options = "\n".join(
                [f"{i+1}. {m['name']} — {m['location']}"
                 for i, m in enumerate(machines_data)]
            )
            options += f"\n{len(machines_data) + 1}. Other (Not listed)"
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
                elif idx == len(unique_locs):
                    # Use the full intelligent pipeline (DB -> Key -> Gemini)
                    complaint_type = classify_complaint_type(original_msg) or 1
                    
                    if complaint_type in NON_EQUIPMENT_TYPES:
                        type_name_friendly = TYPE_NAMES.get(complaint_type, "General")
                        
                        # Always ask for details instead of logging directly
                        upsert_state(db, user_phone, "waiting_for_problem", {
                            "machine_id":    None,
                            "machine_name":  "General Request",
                            "location_name": "N/A",
                            "location_id":   None,
                            "complaint_type": complaint_type
                        })
                        return f"I understand this is a *{type_name_friendly}* request. What exactly is the issue or details?"

                    # Otherwise, proceed to unknown location flow
                    result = extract_unknown_equipment(original_msg)
                    machine_name = result["machine_name"]
                    upsert_state(db, user_phone, "waiting_for_location", {
                        "machine_name": machine_name,
                        "complaint_type": complaint_type,
                        "original_message": original_msg,
                        "member_id": member_id,
                    })
                    return f"Okay! Which lab or room is *{machine_name}* located in?"
            
            # If not a digit, fall back to loose string matching
            if not location_filter:
                location_filter = user_input

            # Filter stored candidates by location, name, or category string
            narrowed = [
                m for m in all_machines
                if location_filter in (str(m.get("location") or "")).lower() or
                   location_filter in (str(m.get("name") or "")).lower() or
                   location_filter in (str(m.get("category") or "")).lower()
            ]

            if not narrowed:
                # Location not recognized — tell user and re-show valid options
                locs_text = "\n".join(f"{i+1}. {loc}" for i, loc in enumerate(unique_locs))
                locs_text += f"\n{len(unique_locs) + 1}. Other (Not listed)"
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
            options += f"\n{len(narrowed) + 1}. Other (Not listed)"
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

        # ── No machine found → classify & route by complaint type ───
        if not matched:
            # First, classify the complaint without heavy extraction
            complaint_type = classify_complaint_type(message)   # may return None

            # ── Classifier failed → ask user to clarify (once) ────────
            if complaint_type is None:
                upsert_state(db, user_phone, "waiting_for_clarification", {
                    "original_message": message,
                    "machine_name":     "Unknown Equipment",
                    "machine_id":       None,
                })
                return (
                    "🤔 I'm not sure what kind of issue that is. "
                    "Could you describe the problem in a bit more detail? "

                )

            if complaint_type in NON_EQUIPMENT_TYPES:
                type_name_friendly = TYPE_NAMES.get(complaint_type, "General")
                if needs_issue_description(message):
                    upsert_state(db, user_phone, "waiting_for_problem", {
                        "machine_id":    None,
                        "machine_name":  "General Request",
                        "location_name": "N/A",
                        "location_id":   None,
                        "complaint_type": complaint_type
                    })
                    return (
                        f"You want to log a *{type_name_friendly}* request. "
                        f"What exactly is the issue or details?"
                    )

                new_complaint = models.Complaint(
                    member_id=member_id, machine_id=None,
                    location_name="N/A", location_id=None,
                    complaint_description=message,
                    type=complaint_type, status="Open"
                )
                db.add(new_complaint)
                db.commit()
                print(f"✅ Non-equipment complaint logged | Type: {type_name_friendly}")
                return (
                    f"Noted! Your *{type_name_friendly}* complaint has been logged. 👍\n"
                    f"_(Status: Open)_"
                )

            # Equipment / Facility / Process → need a physical location
            extracted = extract_unknown_equipment(message)
            machine_name = extracted["machine_name"]
            
            upsert_state(db, user_phone, "waiting_for_location", {
                "machine_name":   machine_name,
                "complaint_type": complaint_type,
                "original_message": message,
                "member_id":      member_id,
            })
            return (
                f"Hmm, I don't recognize *{machine_name}* in my database yet. "
                f"Is it located in a specific lab or room? Just tell me where it is, and I'll log it for you."
            )


        # ── Single match → log directly ────────────────────────────
        if len(matched) == 1:
            machine = matched[0]
            location_name, location_id, _ = _resolve_lab_location(db, str(machine.location))
            m_name = getattr(machine, "name", getattr(machine, "device_name", "Unknown Machine"))

            # If location is missing/unresolvable → ask user
            if not location_name or location_name.strip() in ["", "None", "0", "none"]:
                complaint_type = classify_complaint_type(message, machine)
                upsert_state(db, user_phone, "waiting_for_location", {
                    "machine_name": m_name,
                    "machine_id": getattr(machine, "machid", getattr(machine, "device_id", None)),
                    "complaint_type": complaint_type,
                    "original_message": message,
                    "member_id": member_id,
                })
                return (
                    f"I found *{m_name}* but its location isn't set in our system yet. "
                    f"Which lab or room is it in?"
                )

            complaint_type = classify_complaint_type(message, machine) or 1  # default Equipment if unclear

            if needs_issue_description(message):
                upsert_state(db, user_phone, "waiting_for_problem", {
                    "machine_id":    getattr(machine, "machid", getattr(machine, "device_id", None)),
                    "model_type":    type(machine).__name__,
                    "machine_name":  m_name,
                    "location_name": location_name,
                    "location_id":   location_id,
                    "complaint_type": complaint_type
                })
                return f"Got it, you mean *{m_name}*. What exact issue are you facing with it?"

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
                "machid": getattr(m, "machid", getattr(m, "device_id", None)),
                "model_type": type(m).__name__,
                "name": getattr(m, "name", getattr(m, "device_name", "Unknown Machine")),
                "location": resolve_loc(m.location),
                "category": m.category
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
            locs_text += f"\n{len(unique_locs) + 1}. Other (Not listed)"
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
        options += f"\n{len(machines_data) + 1}. Other (Not listed)"
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
