"""
app/chatbot/classifier.py
─────────────────────────────────────────
3-Layer Complaint Type Classifier + Unknown Equipment Extractor

Complaint types:
  1 = Equipment   2 = Facility   3 = Safety
  4 = Process     5 = HR         6 = IT
  7 = Purchase    8 = Training   9 = Inventory
  10 = Admin

Layer 1: Machine category → type (FREE, instant)
Layer 2: Keyword matching (FREE, instant)
Layer 3: Gemini 2.0 Flash (API call, last resort)

Extra: extract_unknown_equipment() — for machines not in DB
"""

import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────
# LAYER 1 — Machine category → complaint type
# ─────────────────────────────────────────────────────────────────
CATEGORY_TYPE_MAP = {
    "De humidifiers": 2, "DG Set": 2, "AC": 2, "AHU": 2,
    "Chiller": 2, "Exhaust Blower": 2, "UPS": 2, "N2 Plant": 2,
    "Lithography": 1, "Deposition": 1, "Etch": 1,
    "Characterization": 1, "Metrology": 1, "Thermal": 1,
    "Implant": 1, "CMP": 1, "Wet Process": 1,
}

# ─────────────────────────────────────────────────────────────────
# LAYER 2 — Keyword matching
# ─────────────────────────────────────────────────────────────────
KEYWORD_TYPE_MAP = {
    3:  ["fire", "hazard", "safety", "accident", "emergency", "leak", "gas", "toxic"],
    4:  ["process", "recipe", "parameter", "wafer", "deposition rate", "etch rate"],
    5:  ["salary", "leave", "hr", "payroll", "attendance", "holiday", "increment", "refund", "reimbursement", "payment", "bill", "invoice"],
    6:  ["laptop", "wifi", "internet", "software", "computer", "network", "email", "vpn", "printer"],
    7:  ["purchase", "order", "buy", "vendor", "quote", "chemical", "spare", "procurement"],
    8:  ["training", "workshop", "course", "seminar", "certification", "demo"],
    9:  ["inventory", "stock", "item", "quantity", "missing", "spare parts"],
    10: ["admin", "permission", "access", "policy", "document", "approval", "letter"],
}

# ─────────────────────────────────────────────────────────────────
# GEMINI SETUP  (google-genai SDK)
# ─────────────────────────────────────────────────────────────────
_gemini_client = None
GEMINI_MODEL = "gemini-2.0-flash"


def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key or api_key == "your_gemini_api_key_here":
            return None
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


# ─────────────────────────────────────────────────────────────────
# LAYER 3 — Gemini classification
# ─────────────────────────────────────────────────────────────────
def _classify_with_gemini(message: str) -> int:
    """Call Gemini to classify complaint type. Returns 1 if API fails."""
    try:
        client = _get_gemini()
        if not client:
            print("[CLASSIFIER] No Gemini API key, defaulting to type 1")
            return 1

        prompt = f"""You are classifying a lab complaint message.

Complaint types:
1=Equipment  2=Facility  3=Safety  4=Process
5=HR  6=IT  7=Purchase  8=Training  9=Inventory  10=Admin

Message: "{message}"

Reply with ONLY a single number (1-10)."""

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        result = response.text.strip()
        type_num = int(result)
        if 1 <= type_num <= 10:
            print(f"[CLASSIFIER] Gemini classified: '{message}' → type {type_num}")
            return type_num
        return 1

    except Exception as e:
        print(f"[CLASSIFIER] Gemini error: {e} — defaulting to type 1")
        return 1


# ─────────────────────────────────────────────────────────────────
# UNKNOWN EQUIPMENT — Gemini extracts name + type
# ─────────────────────────────────────────────────────────────────
def extract_unknown_equipment(message: str) -> dict:
    """
    When no machine is found in DB, use Gemini to extract:
      - complaint_type (1-10)
      - machine_name (best guess from message)

    Returns dict: {"complaint_type": int, "machine_name": str}
    """
    try:
        client = _get_gemini()
        if not client:
            return {"complaint_type": 1, "machine_name": "Unknown Equipment"}

        prompt = f"""You are analyzing a lab equipment complaint message.

Extract two things:
1. The equipment/machine name (or "Unknown Equipment" if unclear)
2. The category number:
   1=Equipment  2=Facility  3=Safety  4=Process
   5=HR  6=IT  7=Purchase  8=Training  9=Inventory  10=Admin

Message: "{message}"

Reply in this exact format:
MACHINE: <name>
TYPE: <number>"""

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        lines = response.text.strip().split("\n")

        machine_name = "Unknown Equipment"
        complaint_type = 1

        for line in lines:
            if line.startswith("MACHINE:"):
                machine_name = line.replace("MACHINE:", "").strip()
            elif line.startswith("TYPE:"):
                type_str = line.replace("TYPE:", "").strip()
                if type_str.isdigit():
                    t = int(type_str)
                    if 1 <= t <= 10:
                        complaint_type = t

        print(f"[CLASSIFIER] Unknown equipment: name='{machine_name}', type={complaint_type}")
        return {"complaint_type": complaint_type, "machine_name": machine_name}

    except Exception as e:
        print(f"[CLASSIFIER] Gemini extract error: {e}")
        # Basic smart fallback when Gemini is rate limited or broken:
        # Just use the original message but try to strip common issue words
        fallback_name = message
        for kw in ["not working", "broken", "issue", "problem", "faulty", "stopped", "failed"]:
            if kw in fallback_name.lower():
                # Take everything before the issue word
                idx = fallback_name.lower().find(kw)
                stripped = fallback_name[:idx].strip()
                if stripped:
                    fallback_name = stripped
                    break
        
        # Don't make it too long
        if len(fallback_name) > 30:
            fallback_name = "Unknown Equipment"

        return {"complaint_type": 1, "machine_name": fallback_name}


# ─────────────────────────────────────────────────────────────────
# MAIN CLASSIFIER
# ─────────────────────────────────────────────────────────────────
def classify_complaint_type(message: str, matched_machine=None) -> int:
    """
    3-Layer complaint type classifier.
    Returns int: complaint type (1-10)
    """
    # Layer 1: Machine category
    if matched_machine and matched_machine.category:
        category = matched_machine.category.strip()
        if category in CATEGORY_TYPE_MAP:
            type_num = CATEGORY_TYPE_MAP[category]
            print(f"[CLASSIFIER] Layer 1: category='{category}' → type {type_num}")
            return type_num

    # Layer 2: Keywords
    msg_lower = message.lower()
    for type_num, keywords in KEYWORD_TYPE_MAP.items():
        if any(kw in msg_lower for kw in keywords):
            print(f"[CLASSIFIER] Layer 2: keyword match → type {type_num}")
            return type_num

    # Layer 3: Gemini
    print(f"[CLASSIFIER] Layer 3: calling Gemini for → '{message}'")
    return _classify_with_gemini(message)
