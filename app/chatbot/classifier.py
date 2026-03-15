"""
app/chatbot/classifier.py
─────────────────────────────────────────
Two-Layer Complaint Type Classifier + Unknown Equipment Extractor

Complaint types (active in this system):
  1 = Equipment   2 = Facility   3 = Safety   4 = Process
  5 = HR          6 = IT         7 = Purchase  10 = Admin

Classification pipeline
  Layer 1 — Dataset / DB category → type map  (instant, free)
             + Kaggle CSV keyword augmentation (loaded once at startup)
  Layer 2 — Gemini 2.0 Flash API             (called only when L1 fails)
  Fallback — Returns None so the engine can ask the user to clarify
             or pick from a manual menu.

Kaggle dataset (optional, enriches keyword set):
  https://www.kaggle.com/datasets/tobiasbueck/multilingual-customer-support-tickets
  Place the CSV as:  data/customer_support_tickets.csv
"""

import json
import os
import re
import json
from pathlib import Path
from typing import Optional

from google import genai
from dotenv import load_dotenv

from app.chatbot.db import SessionLocal
from app.chatbot import models

load_dotenv()

# ──────────────────────────────────────────────────────────────────
# COMPLAINT TYPE LABELS  (matches engine.py TYPE_NAMES)
# ──────────────────────────────────────────────────────────────────
TYPE_NAMES = {
    1: "Equipment", 2: "Facility", 3: "Safety",   4: "Process",
    5: "HR",        6: "IT",       7: "Purchase",  8: "Training",
    9: "Inventory", 10: "Admin",
}

VALID_TYPES = set(TYPE_NAMES.keys())   # {1,2,3,4,5,6,7,8,9,10}

# ──────────────────────────────────────────────────────────────────
# LAYER 1-A — Machine DB category  →  complaint type
# ──────────────────────────────────────────────────────────────────
# Keys are the values stored in resources.category column.
CATEGORY_TYPE_MAP: dict[str, int] = {
    # Facility / infra
    "De humidifiers": 2, "DG Set": 2, "AC": 2, "AHU": 2,
    "Chiller": 2, "Exhaust Blower": 2, "UPS": 2, "N2 Plant": 2,
    # Lab equipment
    "Lithography": 1, "Deposition": 1, "Etch": 1,
    "Characterization": 1, "Metrology": 1, "Thermal": 1,
    "Implant": 1, "CMP": 1, "Wet Process": 1,
    # Safety / process
    "Safety": 3, "Process": 4,
}

# ──────────────────────────────────────────────────────────────────
# LAYER 1-B — Keyword dictionaries  (case-insensitive, partial match)
# ──────────────────────────────────────────────────────────────────
# Base keywords — always present regardless of CSV availability.
# Organised per complaint type.  More terms = higher recall.
_BASE_KEYWORDS: dict[int, list[str]] = {

    1: [  # Equipment — lab machines
        "equipment", "instrument", "device", "apparatus", "tool",
        "sem", "tem", "xrd", "pvd", "cvd", "ald", "rtp", "mbe", "lpcvd",
        "furnace", "spin coater", "wire bonder", "die bonder", "profilometer",
        "ellipsometer", "afm", "raman", "fib", "pecvd", "icp", "rie",
        "not working", "broken", "damaged", "malfunction", "fault",
        "calibration", "repair", "maintenance",
    ],

    2: [  # Facility — building infra
        "ac", "air conditioning", "hvac", "ahu", "chiller", "dg set",
        "generator", "ups", "exhaust", "blower", "dehumidifier", "n2 plant",
        "nitrogen", "compressed air", "cleanroom", "fan", "ventilation",
        "water supply", "plumbing", "drain", "ceiling", "lighting", "bulb",
        "elevator", "lift", "power cut", "electricity", "switchboard",
        "watercooler", "water cooler", "drinking water", "ro plant", "dispenser",
        "vending machine", "coffee machine", "pantry", "cafeteria", "canteen",
    ],

    3: [  # Safety
        "fire", "smoke", "hazard", "safety", "accident", "emergency",
        "chemical spill", "spill", "gas leak", "gas", "toxic", "fumes",
        "ppe", "gloves", "goggles", "first aid", "injury", "burn",
        "electric shock", "radiation", "biohazard", "evacuation", "alarm",
        "fire panel", "smoke detector", "fire alarm"
    ],

    4: [  # Process
        "process", "recipe", "parameter", "wafer", "deposition rate",
        "etch rate", "uniformity", "yield", "contamination", "particle",
        "defect", "rework", "run card", "lot", "batch", "sop", "procedure",
    ],

    5: [  # HR
        "salary", "payroll", "leave", "attendance", "holiday", "increment",
        "appraisal", "promotion", "resignation", "offer letter", "joining",
        "pf", "provident fund", "gratuity", "insurance", "hr", "human resource",
        "employee", "transfer", "deputation", "reimbursement",
        "travel allowance", "medical claim", "dress code", "id card",
        "payment", "bill", "invoice", "refund",
    ],

    6: [  # IT
        "laptop", "desktop", "computer", "pc", "monitor", "screen",
        "keyboard", "mouse", "printer", "scanner", "projector",
        "wifi", "wi-fi", "internet", "network", "lan", "vpn",
        "software", "application", "app", "portal", "website",
        "email", "outlook", "teams", "zoom", "login", "password",
        "reset password", "account locked", "virus", "malware",
        "cable", "charger", "usb", "pen drive", "hard disk",
    ],

    7: [  # Purchase
        "purchase", "procurement", "order", "buy", "vendor", "supplier",
        "quotation", "quote", "indent", "po", "purchase order",
        "chemical", "reagent", "consumable", "spare", "spare part",
        "delivery", "shipment", "invoice", "billing", "payment",
        "stock out", "reorder", "catalog",
    ],

    8: [  # Training
        "training", "workshop", "seminar", "course", "lecture", "demo",
        "certification", "tutorial", "induction", "orientation", "session",
        "skill development", "e-learning", "online training", "lab training",
        "hands-on", "practical", "internship", "faculty training",
    ],

    9: [  # Inventory
        "inventory", "stock", "quantity", "item count", "missing item",
        "spare parts", "spare", "consumable stock", "out of stock",
        "reorder", "replenish", "stock check", "asset", "material",
        "component", "shortage", "excess", "audit", "stocktaking",
    ],

    10: [  # Admin
        "admin", "administration", "permission", "access", "approval",
        "policy", "rule", "regulation", "letter", "certificate",
        "document", "form", "noc", "nda", "agreement", "contract",
        "visitor", "gate pass", "security", "cctv", "canteen", "parking",
        "housekeeping", "cleanliness", "pest control",
    ],
}

# Runtime keyword store — starts as a copy, gets augmented from CSV
KEYWORD_TYPE_MAP: dict[int, list[str]] = {k: list(v) for k, v in _BASE_KEYWORDS.items()}


# ── CSV Tag/Queue → Our complaint type (best-effort mapping) ──────
_CSV_TAG_TYPE_MAP: dict[str, int] = {
    # Equipment / lab machines
    "equipment": 1, "machine": 1, "instrument": 1, "maintenance": 1,
    "calibration": 1, "repair": 1, "malfunction": 1, "hardware": 1,
    # Facility / infra
    "facility": 2, "building": 2, "infrastructure": 2, "hvac": 2,
    "utilities": 2, "electricity": 2, "power": 2, "cooling": 2,
    # Safety
    "safety": 3, "hazard": 3, "incident": 3, "fire": 3, "emergency": 3,
    # Process
    "process": 4, "procedure": 4, "workflow": 4, "quality": 4,
    "yield": 4, "recipe": 4, "sop": 4,
    # HR
    "hr": 5, "human resources": 5, "employee": 5, "payroll": 5,
    "leave": 5, "salary": 5, "attendance": 5, "recruitment": 5,
    # IT
    "it": 6, "tech support": 6, "technical support": 6, "network": 6,
    "software": 6, "account": 6, "password": 6, "login": 6,
    "laptop": 6, "computer": 6, "wifi": 6, "internet": 6,
    "security": 6, "data breach": 6, "breach": 6,
    # Purchase
    "billing": 7, "payment": 7, "purchase": 7, "invoice": 7,
    "order": 7, "vendor": 7, "procurement": 7, "shipping": 7,
    # Training
    "training": 8, "workshop": 8, "course": 8, "seminar": 8,
    "learning": 8, "certification": 8,
    # Inventory
    "inventory": 9, "stock": 9, "asset": 9, "spare": 9, "material": 9,
    # Admin
    "admin": 10, "administration": 10, "policy": 10, "document": 10,
    "access": 10, "permission": 10, "compliance": 10,
}

_CSV_QUEUE_TYPE_MAP: dict[str, int] = {
    "technical support": 6,
    "billing and payments": 7,
    "returns and exchanges": 7,
    "customer service": 10,
    "general inquiry": 10,
    "human resources": 5,
    "it support": 6,
    "facilities": 2,
    "safety": 3,
}

# Generic stop words to filter out from extracted keywords
_STOP = {
    "the", "and", "for", "with", "this", "that", "have", "from",
    "are", "was", "has", "been", "will", "not", "but", "our",
    "you", "your", "we", "they", "their", "its", "any", "all",
    "can", "could", "would", "should", "please", "thank", "dear",
    "regards", "sincerely", "hello", "hi", "issue", "problem",
    "request", "support", "team", "customer", "email", "message",
    "write", "writing", "help", "also", "more", "one", "two",
    "first", "further", "information", "questions", "let", "know",
    "provide", "currently", "which", "what", "how", "when", "where",
    "name", "reply", "contact", "reach", "out", "there", "here",
}


def _load_keywords_from_db() -> None:
    """
    Loads advanced keywords from the database. 
    If the database is empty, it attempts a one-time migration from CSV files.
    """
    global _CSV_LOADED
    db = SessionLocal()
    try:
        # 1. Try to load from DB
        db_keywords = db.query(models.ComplaintKeyword).all()
        
        if not db_keywords:
            print("[CLASSIFIER] Keyword table is empty. Running one-time CSV migration...")
            _migrate_csv_to_db(db)
            db_keywords = db.query(models.ComplaintKeyword).all()
        
        total = 0
        for kw in db_keywords:
            t = kw.type
            if t in KEYWORD_TYPE_MAP:
                if kw.keyword not in KEYWORD_TYPE_MAP[t]:
                    KEYWORD_TYPE_MAP[t].append(kw.keyword)
                    total += 1
        
        if total > 0:
            print(f"[CLASSIFIER] Success: Loaded {total} keywords from database.")
        _CSV_LOADED = True

    except Exception as e:
        print(f"[CLASSIFIER] Database keyword load failed: {e}")
        # Fallback: try CSV directly if DB fails
        _migrate_csv_to_db(None)
    finally:
        db.close()

def _migrate_csv_to_db(db=None) -> None:
    """
    Internal helper to parse CSV files and optionally save them to DB.
    """
    import re
    from pathlib import Path
    from collections import defaultdict, Counter

    try:
        import pandas as pd
    except ImportError:
        print("[CLASSIFIER] pandas not found — skipping migration.")
        return

    data_dir = Path(__file__).parent.parent.parent / "data"
    if not data_dir.exists(): return

    csv_files = list(data_dir.glob("*.csv"))
    if not csv_files: return

    type_word_counter: dict[int, Counter] = defaultdict(Counter)

    for csv_path in csv_files:
        try:
            df = pd.read_csv(csv_path, on_bad_lines="skip", dtype=str)
            df.fillna("", inplace=True)
            
            tag_cols = [c for c in df.columns if c.startswith("tag_")]
            has_queue = "queue" in df.columns
            has_text = "subject" in df.columns or "body" in df.columns
            if not has_text: continue

            # Filter for English only
            if "language" in df.columns:
                df = df[df["language"] == "en"]

            for _, row in df.iterrows():
                ctype = None
                # Check tags
                for tcol in tag_cols:
                    tag_val = str(row.get(tcol, "")).lower().strip()
                    if tag_val in _CSV_TAG_TYPE_MAP:
                        ctype = _CSV_TAG_TYPE_MAP[tag_val]
                        break
                
                # Check queue if tag failed
                if ctype is None and has_queue:
                    ctype = _CSV_QUEUE_TYPE_MAP.get(str(row.get("queue", "")).lower().strip())
                
                if ctype:
                    # ONLY use the tags as keywords. Do not extract from subjects or bodies.
                    for tcol in tag_cols:
                        tag_val = str(row.get(tcol, "")).lower().strip()
                        if tag_val and tag_val != "nan":
                            type_word_counter[ctype].update([tag_val])
        except Exception: continue

    # Collect all candidate keywords across all types first
    all_extracted: dict[str, int] = {} # keyword -> best type
    
    # Sort types so that more specific/higher priority types processed first if a word repeats?
    # Or just let the first one win.
    # Sort types: process IT (6) and Equipment (1) first, so they 'claim' their keywords
    # before general categories like Safety (3) or Admin (10) take them.
    # Priority: 6, 1, 4, 10, 3, 2, 5, 7, 8, 9
    priority_order = [6, 1, 4, 10, 3, 2, 5, 7, 8, 9]
    remaining_types = [t for t in type_word_counter.keys() if t not in priority_order]
    
    for ctype in (priority_order + remaining_types):
        if ctype not in type_word_counter: continue
        counter = type_word_counter[ctype]
        for word in counter.keys():
            if len(word) >= 3 and word not in all_extracted:
                all_extracted[word] = ctype

    added_to_map = 0
    added_to_db = 0
    
    # If we have a DB session, load what's already there to avoid duplicates
    existing_in_db = set()
    if db:
        try:
            res = db.query(models.ComplaintKeyword.keyword).all()
            existing_in_db = {r[0] for r in res}
        except Exception:
            pass

    for word, ctype in all_extracted.items():
        # Update runtime map
        if word not in KEYWORD_TYPE_MAP[ctype]:
            KEYWORD_TYPE_MAP[ctype].append(word)
            added_to_map += 1
        
        # Save to database if not already there
        if db and word not in existing_in_db:
            try:
                new_kw = models.ComplaintKeyword(keyword=word, type=ctype)
                db.add(new_kw)
                added_to_db += 1
                
                # Commit in batches of 100 to avoid long-running transactions
                if added_to_db % 100 == 0:
                    db.commit()
            except Exception:
                db.rollback() # Skip this specific one if it fails (e.g. race condition)
                continue

    if db and added_to_db > 0:
        try:
            db.commit()
            print(f"[CLASSIFIER] Migrated {added_to_db} keywords from CSV to database.")
        except Exception:
            db.rollback()

# Initialize keywords from DB (or CSV fallback/migration)
_load_keywords_from_db()


# ──────────────────────────────────────────────────────────────────
# GEMINI SETUP
# ──────────────────────────────────────────────────────────────────
_gemini_client = None
GEMINI_MODEL   = "gemini-2.0-flash"

_GEMINI_PROMPT_EXTRACT_NAME = """\
You are helping a lab manager identify a piece of equipment from a user's complaint message.
User Message: "{message}"

Task: Extract the specific noun or subject of the complaint.
- If it's an item (e.g., "coffee machine", "AC", "light"), return the item name.
- If it's a general area issue (e.g., "leaky ceiling", "slippery floor"), return the subject.
- If it's a structural or policy issue, return "General".

Your output will be used in a sentence like: "Where exactly is the <RESULT> located?".
Return ONLY the noun phrase (1-3 words). Do not add "the" unless necessary.
"""

def extract_unknown_smart(message: str) -> str:
    """
    Uses Gemini to intelligently extract the subject of the complaint.
    """
    try:
        client = _get_gemini()
        if not client: return "issue"
        
        prompt = _GEMINI_PROMPT_EXTRACT_NAME.format(message=message)
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        text = response.text.strip().rstrip(".!?-").lower()
        
        if len(text) > 40 or "unclear" in text or "general" in text:
            return "issue"
        return text
    except Exception:
        return "issue"

_GEMINI_PROMPT_CLASSIFY = """\
You are classifying a workplace / lab complaint message.

Categories available (reply with ONLY the number):
  1 = Equipment (lab machines, instruments, calibration, repair)
  2 = Facility  (AC, UPS, generator, building infrastructure)
  3 = Safety    (fire, chemical spill, gas leak, hazard, injury)
  4 = Process   (recipe, yield, SOP, wafer process, parameters)
  5 = HR        (salary, leave, payroll, reimbursement, appraisal)
  6 = IT        (laptop, wifi, software, password, network, email)
  7 = Purchase  (order, vendor, procurement, spare parts, chemicals)
  8 = Training  (workshop, course, seminar, certification, sessions)
  9 = Inventory (stock, spare, missing item, consumables, shortage)
 10 = Admin     (permissions, documents, policy, gate pass, approval)

If you cannot confidently classify, reply with the word: UNCLEAR

Message: "{message}"

Reply:"""

_GEMINI_PROMPT_EXTRACT = """\
You are analyzing a lab complaint message.

Extract:
1. The equipment/machine name (or "Unknown" if unclear)
2. The complaint category number:
   1=Equipment  2=Facility  3=Safety  4=Process
   5=HR  6=IT  7=Purchase  8=Training  9=Inventory  10=Admin

Reply in EXACTLY this format (nothing else):
MACHINE: <name>
TYPE: <number>

Message: "{message}"

Reply:"""


def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key or api_key in ("your_gemini_api_key_here", ""):
            return None
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


# ──────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ──────────────────────────────────────────────────────────────────

def keyword_match(message: str) -> Optional[int]:
    """
    Layer 1-B: word-boundary match against KEYWORD_TYPE_MAP.
    Returns the winning type number, or None if no match or if there is a tie.
    """
    msg_lower = message.lower()
    scores: dict[int, int] = {}

    # Standardize: check all categories
    for type_num, keywords in KEYWORD_TYPE_MAP.items():
        base_kws = set(_BASE_KEYWORDS.get(type_num, []))
        for kw in keywords:
            # strict word boundaries to avoid "cat" matching "category"
            if re.search(r'\b' + re.escape(kw) + r'\b', msg_lower):
                # Strong signal: +100 points if it's a curated base keyword
                # Weak signal: +1 point if it's just a common word from the CSV
                is_base = kw in base_kws
                point = 100 if is_base else 1
                scores[type_num] = scores.get(type_num, 0) + point
                
                if is_base:
                    print(f"[CLASSIFIER] L1-B Base Match: '{kw}' (+100) -> Type {type_num}")

    if not scores:
        return None

    # Find the maximum score
    max_score = max(scores.values())
    
    # Check for ties or near-ties
    top_types = [t for t, score in scores.items() if score == max_score]
    
    # NEW: CONFIDENCE THRESHOLD
    # If the match only comes from weak CSV keywords (low score), 
    # yield to Gemini instead of guessing. Base keywords give 100, so they still pass.
    if max_score < 25:
        print(f"[CLASSIFIER] Low confidence score ({max_score} pts). Yielding to Gemini...")
        return None

    if len(top_types) > 1:
        # Return the list of tied types so classifying function can decide (Gemini vs Fallback)
        return top_types

    return top_types[0]


def _gemini_classify(message: str) -> Optional[int]:
    """
    Layer 2: call Gemini to classify. Returns type int, or None if UNCLEAR/error.
    """
    try:
        client = _get_gemini()
        if not client:
            print("[CLASSIFIER] Gemini API key not configured.")
            return None

        prompt   = _GEMINI_PROMPT_CLASSIFY.format(message=message)
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        result   = response.text.strip()

        print(f"[CLASSIFIER] Gemini raw response: '{result}'")

        if result.upper() == "UNCLEAR":
            return None   # signal engine to ask user

        type_num = int(result)
        if type_num in VALID_TYPES:
            print(f"[CLASSIFIER] Gemini → type {type_num} ({TYPE_NAMES[type_num]})")
            return type_num

        return None   # invalid number → treat as unclear

    except (ValueError, AttributeError):
        print("[CLASSIFIER] Gemini returned non-numeric response — treating as UNCLEAR.")
        return None
    except Exception as e:
        print(f"[CLASSIFIER] Gemini error: {e}")
        return None


# ──────────────────────────────────────────────────────────────────
# PUBLIC API — classify_complaint_type
# ──────────────────────────────────────────────────────────────────

def classify_complaint_type(message: str, matched_machine=None) -> Optional[int]:
    """
    Two-layer complaint type classifier.

    Returns:
        int  — confident type number (1-10)
        None — all layers failed; engine should ask user to clarify

    Layer 1-A: Machine DB category or table-type (instant)
    Layer 1-B: Keyword scoring                  (instant)
    Layer 2:   Gemini 2.0 Flash                 (API call, only when L1 fails)
    """
    # ── Layer 1-A: machine category or table type ───────────────────────
    if matched_machine:
        # 1. Check by table type first
        cls_name = type(matched_machine).__name__
        if cls_name == "SafetyDevice":
            print(f"[CLASSIFIER] L1-A: Table 'safety_device' → type 3 (Safety)")
            return 3
        if cls_name == "Resources":
            print(f"[CLASSIFIER] L1-A: Table 'resources' → type 2 (Facility)")
            return 2
        
        if cls_name == "EqpProcessResource":
            # Differentiate between Equipment (1) and Process (4)
            cat = str(getattr(matched_machine, "category", "")).lower()
            if "process" in cat:
                print(f"[CLASSIFIER] L1-A: Table 'eqp-process_resources' with 'process' category → type 4")
                return 4
            print(f"[CLASSIFIER] L1-A: Table 'eqp-process_resources' → type 1 (Equipment)")
            return 1
        if getattr(matched_machine, "category", None):
            category = matched_machine.category.strip()
            if category in CATEGORY_TYPE_MAP:
                t = CATEGORY_TYPE_MAP[category]
                print(f"[CLASSIFIER] L1-A: category='{category}' → type {t}")
                return t

    # ── Layer 1-B: keyword scoring ────────────────────────────────
    k_result = keyword_match(message)
    
    if isinstance(k_result, int):
        # Single clear winner
        return k_result
        
    # k_result is a list (tie) or None
    tied_types = k_result if isinstance(k_result, list) else []

    # ── Layer 2: Gemini ───────────────────────────────────────────
    # We call Gemini if Layer 1-B was inconclusive (None) or had a tie.
    print(f"[CLASSIFIER] L2: calling Gemini for → '{message}'")
    t = _gemini_classify(message)
    
    if t is not None:
        return t

    # ── Fallback: Tie-breaker ─────────────────────────────────────
    # If Gemini failed but we had a keyword tie, pick by priority
    if tied_types:
        # Priority: Safety(3) > IT(6) > Facility(2) > Process(4) > HR(5) > ... > Equipment(1)
        priority_order = [3, 6, 2, 4, 5, 7, 8, 9, 10, 1] 
        for p_type in priority_order:
            if p_type in tied_types:
                print(f"[CLASSIFIER] Gemini failed. Breaking tie {tied_types} using priority → {p_type}")
                return p_type
                
    # All layers failed
    print(f"[CLASSIFIER] All layers failed for: '{message}'")
    return None


# ──────────────────────────────────────────────────────────────────
# PUBLIC API — extract_unknown_equipment
# ──────────────────────────────────────────────────────────────────

def extract_unknown_equipment(message: str) -> dict:
    """
    When no machine is found in DB, attempt to extract:
      - machine_name    (str)
      - complaint_type  (int, defaults to 1 if unknown)

    Uses local keyword matching only (no Gemini) to avoid quota issues.
    Returns {"complaint_type": int, "machine_name": str}
    """
    # Get type from keyword layer (with priority tiebreak — no Gemini needed)
    keyword_type = keyword_match(message)

    # ── Local fallback: strip issue words to isolate machine name ──
    fallback_name = message.strip()
    triggers = [
        "is not working", "isnt working", "not turning on", "wont start",
        "won't start", "not working", "not workng", "working", "workng",
        "broken", "issue", "problem", "faulty", "stopped", "failed",
        "error", "down", "off"
    ]
    # Sort triggers by length descending so longer phrases hit first
    triggers.sort(key=len, reverse=True)
    
    for issue_kw in triggers:
        idx = fallback_name.lower().find(issue_kw)
        if idx != -1:
            candidate = fallback_name[:idx].strip().rstrip(",.!?-")
            if candidate:
                fallback_name = candidate
                break

    # Preserve all-caps abbreviations (AC, UPS, RIE); title-case longer words
    if len(fallback_name) > 40 or not fallback_name:
        fallback_name = "Unknown Equipment"
    else:
        words = fallback_name.split()
        fallback_name = " ".join(
            w.upper() if len(w) <= 4 and w.isalpha() else w.capitalize()
            for w in words
        )

    print(f"[CLASSIFIER] extract_unknown (local): name='{fallback_name}', type={keyword_type or 1}")
    return {
        "complaint_type": keyword_type or 1,
        "machine_name":   fallback_name,
    }

