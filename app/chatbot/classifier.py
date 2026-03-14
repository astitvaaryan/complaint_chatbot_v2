"""Complaint type classification and minimal Gemini extraction helpers."""

import json
import os

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

CATEGORY_TYPE_MAP = {
    "De humidifiers": 2,
    "DG Set": 2,
    "AC": 2,
    "AHU": 2,
    "Chiller": 2,
    "Exhaust Blower": 2,
    "UPS": 2,
    "N2 Plant": 2,
    "Lithography": 1,
    "Deposition": 1,
    "Etch": 1,
    "Characterization": 1,
    "Metrology": 1,
    "Thermal": 1,
    "Implant": 1,
    "CMP": 1,
    "Wet Process": 1,
}

KEYWORD_TYPE_MAP = {
    3: ["fire", "hazard", "safety", "accident", "emergency", "leak", "gas", "toxic"],
    4: ["process", "recipe", "parameter", "wafer", "deposition rate", "etch rate"],
    5: ["salary", "leave", "hr", "payroll", "attendance", "holiday", "increment", "refund", "reimbursement", "payment", "bill", "invoice"],
    6: ["laptop", "wifi", "internet", "software", "computer", "network", "email", "vpn", "printer"],
    7: ["purchase", "order", "buy", "vendor", "quote", "chemical", "spare", "procurement"],
    8: ["training", "workshop", "course", "seminar", "certification", "demo"],
    9: ["inventory", "stock", "item", "quantity", "missing", "spare parts"],
    10: ["admin", "permission", "access", "policy", "document", "approval", "letter"],
}

_gemini_model = None
GEMINI_MODEL = "gemini-2.0-flash"


def _get_gemini():
    global _gemini_model
    if _gemini_model is None:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key or api_key == "your_gemini_api_key_here":
            return None
        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel(GEMINI_MODEL)
    return _gemini_model


def _classify_with_gemini(message: str) -> int:
    try:
        model = _get_gemini()
        if not model:
            return 1

        prompt = f"""You are classifying a lab complaint message.

Complaint types:
1=Equipment  2=Facility  3=Safety  4=Process
5=HR  6=IT  7=Purchase  8=Training  9=Inventory  10=Admin

Message: "{message}"

Reply with ONLY a single number (1-10)."""

        response = model.generate_content(prompt)
        type_num = int(response.text.strip())
        if 1 <= type_num <= 10:
            return type_num
        return 1
    except Exception as exc:
        print(f"[CLASSIFIER] Gemini error: {exc}")
        return 1


def classify_complaint_type(message: str, matched_machine=None) -> int:
    if matched_machine and getattr(matched_machine, "category", None):
        category = matched_machine.category.strip()
        if category in CATEGORY_TYPE_MAP:
            return CATEGORY_TYPE_MAP[category]

    msg_lower = message.lower()
    for type_num, keywords in KEYWORD_TYPE_MAP.items():
        if any(keyword in msg_lower for keyword in keywords):
            return type_num

    return _classify_with_gemini(message)


def extract_complaint_schema(message: str, complaint_type: int | None = None) -> dict:
    try:
        model = _get_gemini()
        if not model:
            return {
                "complaint_description": message,
                "location_name": None,
                "resource_name": None,
            }

        resource_label = {
            1: "equipment or machine name",
            2: "facility resource name",
            3: "safety device or safety equipment name",
            4: "tool or equipment involved in the process issue",
        }.get(complaint_type, "resource name if explicitly mentioned")

        prompt = f"""Extract only the minimum complaint registration details from this message.

Rules:
- Extract only the words needed to look up the affected resource in the database.
- Do not invent ids, status, timestamps, or categories.
- Keep complaint_description concise and faithful.
- If a field is unclear, return null.

Fields:
- resource_name: {resource_label}
- complaint_description: one short sentence describing the complaint
- location_name: lab, room, or area if explicitly mentioned

Message: "{message}"

Return valid JSON only:
{{
  "resource_name": "lookup phrase or null",
  "complaint_description": "short complaint description",
  "location_name": "location or null"
}}"""

        response = model.generate_content(prompt)
        result = response.text.strip()
        if result.startswith("```"):
            parts = result.split("```")
            if len(parts) >= 3:
                result = parts[1]
                if result.lower().startswith("json"):
                    result = result[4:].strip()

        extracted = json.loads(result)
        return {
            "complaint_description": extracted.get("complaint_description", message),
            "location_name": extracted.get("location_name"),
            "resource_name": extracted.get("resource_name"),
        }
    except Exception as exc:
        print(f"[CLASSIFIER] Schema extraction error: {exc}")
        return {
            "complaint_description": message,
            "location_name": None,
            "resource_name": None,
        }
