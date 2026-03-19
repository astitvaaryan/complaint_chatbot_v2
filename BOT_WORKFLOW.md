# WhatsApp Complaint Chatbot - Complete Workflow Architecture

This document completely outlines the architecture, data-flow, and internal logic of the WhatsApp Complaint Chatbot backend.

## 1. Overview
The bot is designed to receive natural language complaints via a WhatsApp Twilio webhook, intelligently identify the affected equipment/issue type, confirm its location, and successfully register the complaint in the MySQL Database (`slotbooking` via `.env`).

The bot handles complex natural language scenarios by passing the message through a 3-step pipeline: **Extraction**, **Search**, and **Neural Routing**.

---

## 2. The Processing Pipeline

### Step 1: Message Ingestion (`classifier.py`)
When a user sends a message, it is passed into the `new_classifier.py`:
- Nouns and contextual tokens are extracted to identify the issue.
- The system generates a base `schema` dictionary caching variables like: `resource_name`, `important_phrases`, and `important_terms`.
- A preliminary complaint `type` prediction (e.g., Equipment, Facility, IT, HR) is attached.

### Step 2: 2-Tier RapidFuzz Smart Search (`extractor.py`)
Rather than relying on basic substring matching, the chatbot uses a massive **2-Tier RapidFuzz** search engine to map the extracted nouns to internal DB categories:

*   **Tier 1 (Physical Matches):** The system scans 3 physical hardware tables (`eqp-process_resources`, `resources`, `safety_device`).
    *   It filters strictly for ACTIVE records (using `isworking` / `activation_status`).
    *   It uses `fuzz.token_set_ratio` with a cutoff threshold of `>= 65.0`.
*   **Tier 2 (Keyword/Abstract Matches):** The system cross-references non-physical nouns against 6 abstract categories (HR, IT, Admin, Training, Purchase, Inventory).
    *   It uses `fuzz.WRatio` with a strict cutoff of `>= 80.0`.

### Step 3: The 5-Case Neural Routing Logic (`engine.py`)
Once `smart_rapidfuzz_search()` returns the dictionary of matches and categories, `engine.py` dictates the flow of the conversation across 5 intelligently handled cases:

1.  **Exact Hit (Single Category, Single Machine):**
    *   *Logic:* Extracts the machine ID, automatically fetches the lab Location, and safely prompts the user to verify.
    *   *Bot says:* "I found this equipment is normally located in [Location]. Is that correct? (Yes/No)"
2.  **Category Collision (Multiple unique Categories hit):**
    *   *Logic:* Prioritizes categorizing the general issue first. Stores only the raw Database IDs into the serialized state (to avoid JSON crashes).
    *   *Bot says:* "Which type of issue is it?" *(Proceeds to list the identified categories)*
3.  **Machine Collision (Single Category, Multiple Machines):**
    *   *Logic:* If the keyword (e.g., "Fan") matches multiple active entries in that category, the bot lists them cleanly across location lines.
    *   *Bot says:* "I found multiple matching records. Reply with the number:"
4.  **Confirming Missing Data:**
    *   *Logic:* Evaluates if any explicit pieces are missing (e.g., a "type" but no "location"). 
    *   *Bot says:* "Noted. Where is this facility issue happening?"
5.  **0-Match Fallback (The Smart Buffer):**
    *   *Logic:* If the hardware isn't registered in the DB, the engine prevents frustrating fallback loops. It bypasses Database confirmation, directly injecting the raw user string natively into `schema["resource_name"]`.

---

## 3. Persistent State Management
To support multi-turn conversations without blocking threads, the chatbot implements a conversational State Manager (`state_manager.py` & `engine.py`):
- All ongoing interactions cache the active `schema` configuration dictionary against the user's phone number inside the `conversation_state` database table.
- Temporary contexts (like `select_category` or `confirm_location`) track what exactly the bot is expecting next.
- If a user says `"cancel"`, `"reset"`, or says `"no"` during confirmation, the context row is immediately deleted so the process starts fresh.

---

## 4. Final Complaint Registration
Once all `EDITABLE_FIELDS` in the schema are populated and the user replies `"yes"` to the final JSON-rendered prompt, the engine invokes `_register_complaint()`:
- Automatically formats timestamps (`time_of_complaint`).
- Converts the final mapped keys into the SQLAlchemy `Complaint` model.
- Registers it under the respective `member_id` into the complaint table.
- Appends the ultimate success message bridging back to WhatsApp. 

---

### Database Configurations
The central database relies heavily on the environment configuration for portability. Ensure your local `.env` contains the required keys:
```
DB_HOST=localhost
DB_PORT=3306
DB_NAME=slotbooking
DB_USER=root
DB_PASSWORD=your_password
```
*(Any DB configurations are loaded through `app.chatbot.db` & `app.database.py` defaults.)*
