"""
run_tests.py
─────────────────────────────────────────────────────
Comprehensive Automated test runner with LARGE descriptions.
Includes 15 scenarios covering the full flow.
Results are saved to 'test_report_full.txt'.
"""

import os
import sys
import datetime
from app.chatbot.engine import get_chatbot_reply
from app.chatbot.db import SessionLocal
from app.chatbot.state_manager import clear_state
from app.database import get_users_by_mobile

# ── ANSI Colors ───────────────────────────────────────────────────────────────
GRN  = "\033[92m"
RED  = "\033[91m"
YEL  = "\033[93m"
BLU  = "\033[94m"
CYN  = "\033[96m"
MAG  = "\033[95m"
DIM  = "\033[2m"
BOLD = "\033[1m"
RST  = "\033[0m"

TEST_PHONE = "8077043887"

TEST_CASES = [
    ("TC-01", "Large Equipment Description (Active Device)", [
        ("The SEM tool in the characterization lab is showing a vacuum error code V-01 and the filament seems to be burnt out. We tried restarting the system twice but it is not responding to the console commands.", ["classified", "equipment"]),
        ("y", ["reply with the number", "miscellaneous"]),
        ("1", ["confirm", "description", "type"]),
        ("y", ["registered"])
    ]),

    ("TC-02", "Large Facility Complaint", [
        ("There is severe water leakage from the ceiling in the photolithography lab, right above the spin coater area. It is creating a safety hazard and we might need to shut down the main power if it continues.", ["classified", "facility"]),
        ("y", ["reply with the number", "miscellaneous"]),
        ("1", ["confirm", "description"]),
        ("y", ["registered"])
    ]),

    ("TC-03", "Large Safety Complaint", [
        ("The fire alarm in the chemical storage room went off briefly this morning even though there was no smoke. We need a technician to check if the sensors are faulty or if there is a hidden leak.", ["classified", "safety"]),
        ("y", ["reply with the number"]),
        ("1", ["confirm"]),
        ("y", ["registered"])
    ]),

    ("TC-04", "Type Edit Flow (Equipment to Safety)", [
        ("The biometric access scanner at the main entrance of the Nano lab is not reading any cards and is showing a 'Database Connection Failed' error on the small screen.", ["classified", "equipment"]),
        ("e", ["correct type", "reply with the number"]),
        ("3", ["reply with the number", "miscellaneous"]),
        ("1", ["confirm"]),
        ("y", ["registered"])
    ]),

    ("TC-05", "HR Complaint (Long)", [
        ("I have noticed a discrepancy in my salary slip for the month of March regarding the HRA calculation. Also, I need to know the procedure for applying for a paternity leave for 2 weeks.", ["classified", "hr"]),
        ("y", ["confirm", "description"]),
        ("y", ["registered"])
    ]),

    ("TC-06", "IT Support (Multi-step)", [
        ("The local area network in our office block has been extremely unstable since yesterday afternoon. We are unable to access the internal file server and the printer is showing as offline for all users.", ["classified", "it"]),
        ("y", ["confirm", "description"]),
        ("y", ["registered"])
    ]),

    ("TC-07", "Purchase Routing (Large)", [
        ("We urgently need to procure a fresh batch of ultra-high purity nitrogen cylinders and some 1000ml borosilicate glass beakers for the upcoming research project starting next Monday.", ["classified", "purchase"]),
        ("y", ["confirm", "description"]),
        ("y", ["registered"])
    ]),

    ("TC-08", "Inventory Stock (Large)", [
        ("The chemical inventory in the wet chemistry lab is running very low on Isopropyl Alcohol and Acetone. We only have two bottles left and we need to restock before the weekend.", ["classified", "inventory"]),
        ("y", ["confirm", "description"]),
        ("y", ["registered"])
    ]),

    ("TC-09", "Admin/Cleaning (Large)", [
        ("The floor in the lobby area near the elevators is extremely slippery due to some oil spill and needs immediate cleaning by the housekeeping team to avoid any accidents.", ["classified", "admin"]),
        ("y", ["confirm", "description"]),
        ("y", ["registered"])
    ]),

    ("TC-10", "Training Request (Large)", [
        ("I am a new PhD student and I would like to schedule a training session for the Atomic Force Microscope (AFM) and the XRD tool so that I can start my experiments independently.", ["classified", "training"]),
        ("y", ["confirm", "description"]),
        ("y", ["registered"])
    ]),

    ("TC-11", "Process Support (Large)", [
        ("The recipe for the gold deposition process in the sputtering unit is not yielding consistent results. The thickness of the film is varying by more than 20 percent across different samples.", ["classified", "process"]),
        ("y", ["confirm", "description"]),
        ("y", ["registered"])
    ]),

    ("TC-12", "Cancellation Mid-flow", [
        ("The vacuum pump is making a very loud grinding noise.", ["classified"]),
        ("n", ["canceled"])
    ]),

    ("TC-13", "Miscellaneous Selection (Large Description)", [
        ("There is a strange smell coming from the ventilation ducts in the office area. It doesn't smell like smoke but it is very irritating and making it hard to work.", ["classified", "facility"]),
        ("y", ["reply with the number"]),
        ("0", ["miscellaneous", "confirm"]),
        ("y", ["registered"])
    ]),

    ("TC-14", "Undo Registration", [
        ("The UPS battery is showing a low voltage warning.", ["classified", "facility"]),
        ("y", ["number"]),
        ("1", ["confirm"]),
        ("y", ["registered"]),
        ("undo", ["deleted"])
    ]),

    ("TC-15", "Complex Location Fallback", [
        ("Something is making a buzzing sound behind the main control panel inside the high voltage characterization lab area.", ["classified", "equipment"]),
        ("y", ["reply with the number"]),
        ("0", ["miscellaneous", "confirm"]),
        ("y", ["registered"])
    ]),
]

def run_test(user: dict, tc_id: str, description: str, turns: list, report_file):
    phone = user["mobile"]
    db = SessionLocal()
    try:
        clear_state(db, phone)
    finally:
        db.close()

    print(f"\n{BOLD}{BLU}{'─'*60}{RST}")
    print(f"{BOLD}{BLU}{tc_id}{RST} — {description}")
    report_file.write(f"\n{'='*70}\n{tc_id}: {description}\n{'='*70}\n")

    passed = True
    for i, (user_input, expected_keywords) in enumerate(turns, start=1):
        reply = get_chatbot_reply(user, user_input)
        reply_lower = reply.lower()

        ok = all(kw.lower() in reply_lower for kw in expected_keywords)
        status = f"{GRN}✓ PASS{RST}" if ok else f"{RED}✗ FAIL{RST}"
        if not ok:
            passed = False

        print(f"  Turn {i}: {DIM}You:{RST} {CYN}{user_input}{RST}")
        print(f"           {DIM}Bot:{RST} {reply.strip()[:150]}...")
        print(f"           {status}")
        
        report_file.write(f"Turn {i} | User: {user_input}\n")
        report_file.write(f"       | Bot : {reply.strip()}\n")
        report_file.write(f"       | Result: {'PASSED' if ok else 'FAILED'}\n\n")

    return passed

def main():
    if sys.platform == "win32":
        os.system("color")

    users = get_users_by_mobile(TEST_PHONE)
    if not users: sys.exit(1)
    user = users[0]

    report_path = "test_report_full.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"IITBNF CHATBOT - LARGE DESCRIPTION TEST REPORT\n")
        f.write(f"Tester: {user['fname']} {user['lname']}\n")
        f.write(f"{'='*70}\n")

        results = []
        for tc_id, description, turns in TEST_CASES:
            passed = run_test(user, tc_id, description, turns, f)
            results.append((tc_id, description, passed))

        passed_count = sum(1 for _, _, p in results if p)
        f.write(f"\nFINAL SUMMARY: {passed_count}/{len(results)} PASSED\n")

    print(f"\nReport saved to: {report_path}")

if __name__ == "__main__":
    main()
