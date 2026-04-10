# WhatsApp Complaint Chatbot Workflow

This document describes the current end-to-end workflow of the chatbot as implemented in the backend.

## 1. Purpose

The bot receives a WhatsApp complaint message through Twilio, identifies the complaint type, fills a backend complaint schema, asks only for missing information, shows the final schema for review, allows edits, and registers the complaint in the database after confirmation.

The system is designed to:

- identify the complaint type as early as possible
- use database lookups wherever possible instead of asking unnecessary questions
- use Gemini only as a support layer, not as the primary workflow
- keep the complaint conversation stateful across multiple user replies

## 2. Main Backend Modules

### `app/routes/webhook.py`

Handles Twilio WhatsApp webhook requests.

Responsibilities:

- normalize the sender phone number
- authenticate the user by mobile number
- handle duplicate mobile numbers using email verification
- route authenticated user messages to the chatbot engine
- return TwiML response text back to Twilio

### `app/chatbot/engine.py`

This is the main orchestration layer.

Responsibilities:

- create and update the complaint schema
- call classifier and extractor logic
- resolve locations and resource IDs from database tables
- decide the next question to ask
- manage confirmation, editing, and registration
- manage multi-turn complaint state

### `app/chatbot/new_classifier.py`

This is the production classifier module.

Responsibilities:

- preprocess user complaint text
- extract important words and phrases
- optionally use Gemini to improve extraction
- classify complaint type
- support fallback schema extraction when needed

`app/chatbot/classifier.py` is currently a compatibility wrapper over `new_classifier.py`.

### `app/chatbot/extractor.py`

Provides resource lookup logic.

Responsibilities:

- search physical resource tables
- search abstract complaint categories
- support RapidFuzz-based matching for noisy user text

### `app/chatbot/state_manager.py`

Stores conversation state in the database.

Responsibilities:

- save the current complaint schema per user
- resume multi-turn conversations
- clear state on cancel or completion

### `app/chatbot/models.py`

Contains SQLAlchemy models for the chatbot-relevant tables.

Current important models:

- `EqpProcessResource` -> `resources`
- `FacilityResource` -> `facility_resources`
- `SafetyDevice` -> `safety_device`
- `LabIncharge` -> `lab_incharge`
- `Complaint` -> `complaint`
- `ConversationState` -> `conversation_state`
- `ComplaintKeyword` -> `complaint_it_keywords`

## 3. Complaint Schema

The chatbot works around a backend schema that is initialized with `None` values.

Current schema fields:

```json
{
  "member_id": null,
  "machine_id": null,
  "complaint_description": null,
  "type": null,
  "status": null,
  "time_of_complaint": null,
  "location_name": null,
  "location_id": null,
  "resource_name": null,
  "resource_table": null
}
```

Not all fields are shown to the user. The editable confirmation currently exposes:

- `member_id`
- `machine_id`
- `complaint_description`
- `type`
- `status`
- `time_of_complaint`
- `location_name`
- `location_id`

## 4. Supported Complaint Types

The bot currently uses these type IDs:

| Type ID | Type Name |
|---|---|
| 1 | Equipment (Strict machine requirement) |
| 2 | Facility (Area-based, optional tool) |
| 3 | Safety (Area-based, optional tool) |
| 4 | Process |
| 5 | HR |
| 6 | IT |
| 7 | Purchase |
| 8 | Training |
| 9 | Inventory |
| 10 | Admin |

**Note: Type 0 (Miscellaneous) has been purged.** If a complaint cannot be classified, the system defaults to Type 1 (Equipment) to ensure it follows a professional workflow.

## 5. High-Level Runtime Flow

### Step 1: User sends a WhatsApp message

Twilio calls `POST /webhook`.

The webhook:

- extracts `From` and `Body`
- normalizes the sender number
- authenticates the user
- forwards the message to `get_chatbot_reply()`

### Step 2: Session and state check

`get_chatbot_reply()` in `engine.py` checks:

- whether the user wants to `cancel`, `reset`, `stop`, or `abort`
- whether the user wants to `undo`, `delete`, `remove`, or `revert` the latest complaint
- whether the user already has an active complaint conversation in `conversation_state`

If a conversation state exists, the engine continues that flow.

If not, it starts a new complaint flow.

### Step 3: Initial schema preparation

`_prepare_initial_schema()` creates a blank schema and fills:

- `member_id`
- preliminary `type`
- `status = "Open"`

Then it performs local extraction and DB enrichment.

### Step 4: Complaint text extraction

`extract_local_complaint_schema()` in `new_classifier.py` runs first.

It:

- preprocesses text
- normalizes tokens
- extracts keywords
- generates phrases
- tries to detect a location phrase
- optionally calls Gemini to extract better:
  - `important_terms`
  - `important_phrases`
  - `resource_name`
  - `location_name`

- Gemini is cached and rate-limited through backoff logic:
- `_extract_with_gemini()` uses `@lru_cache`
- If Gemini returns `429` (Rate Limit) or `503` (Service Unavailable), the system applies a **30-second backoff** and falls back to local NLP logic to ensure 0% downtime.

The extracted values are merged into the schema.

### Step 5: Initial location normalization

After extraction, the engine tries to resolve `location_name` into `location_id`.

This is done by `_resolve_schema_location()` and `_resolve_lab_location()`.

Location resolution rules:

- if the input is a numeric id, search `lab_incharge.locationid`
- else try direct text matching on `lab_incharge.location`
- else try normalized matching
- else use constrained fuzzy matching
- if no valid lab is found, unresolved free-text locations are cleared before final confirmation

This means invalid phrases like `the chamber` should not remain as final locations.

### Step 6: DB enrichment and type/resource discovery

`_enrich_schema_from_db()` tries to infer more information from database search.

It collects search nouns from:

- `resource_name`
- `important_phrases`
- `important_terms`
- raw message

Then it calls `smart_rapidfuzz_search()` from `extractor.py`.

That function performs a 2-layer search:

#### Layer A: Physical resource search

Searches these tables:

- `resources`
- `facility_resources`
- `safety_device`

The result is stored as `physical_matches`.

#### Layer B: Abstract category search

Searches keyword groups for:

- HR
- IT
- Purchase
- Training
- Inventory
- Admin

The result is stored as `abstract_matches`.

The union of these matches becomes `_rf_categories` in the schema.

### Step 7: Type classification

The classifier logic in `classify_complaint_type()` currently works in this order:

1. if a matched physical DB row is already known, use that signal
2. strong curated keyword checks for non-physical categories (HR, Admin, etc.)
3. **IT Priority Guard Layer 1:** Check for base IT keywords (laptop, wifi, password) → return IT immediately.
4. **Physical Table Search:** Search Equipment/Facility/Safety DB.
5. **IT Priority Guard Layer 2:** Check broader DB-loaded IT keywords ONLY if table search found nothing.
6. generic keyword scoring
7. Gemini classification fallback
8. Final fallback to Type 1 (Equipment) instead of 0.

Important points:

- `complaint_it_keywords` is used only as a strong IT signal
- noisy IT keywords are filtered using `IT_KEYWORD_BLACKLIST`
- table detection is intentionally prioritized before IT keyword forcing so physical resource mentions are not easily overridden by generic IT words

### Step 8: Resource match handling

If DB enrichment finds one matched physical resource:

- `machine_id` is filled
- `resource_name` is filled
- `resource_table` is filled
- location is taken from the matched resource row and mapped to `lab_incharge`

If multiple matching resources are found:

- the bot stores them in state
- the user is asked to choose one by number

If no physical match is found:

- the schema may still continue using abstract type classification
- the bot asks for missing information if needed

## 6. Which Fields Are Required

The engine decides the next missing field using `_next_missing_field()`.

Current rules:

- `type` is always required
- `complaint_description` is required
- `machine_id` is required only for resource-backed types:
  - Equipment
  - Facility
  - Safety
  - Process
- `location_name` is required for:
  - Equipment
  - Facility
  - Safety
  - Process
  - HR
  - IT
  - Inventory

## 7. Question Flow

The engine asks only one meaningful next question at a time.

Examples:

- unknown type -> asks the user to choose a type
- resource-backed type with missing machine -> asks which equipment/resource is affected
- missing location for location-relevant types -> asks where the issue is happening

Question text is generated by `_question_for_field()`.

## 8. Special Multi-Turn States

The chatbot stores state in `conversation_state` using `user_phone`.

Possible active steps include:

- `collecting_info`
- `select_resource`
- `select_category`
- `confirm_location`
- `confirming`

### `collecting_info`

Used when one field is missing and the bot needs a direct answer.

### `select_resource`

Used when multiple resource records match. The user replies with a number.

### `select_category`

Used when the search finds more than one possible complaint category.

### `confirm_location`

Used when a resource row gives a likely location and the bot wants explicit user confirmation.

### `confirming`

Used after the schema is complete enough to review.

## 9. Confirmation and Editing

Once the required schema fields are present, the bot shows the complaint schema to the user.

The user may then:

- reply `yes` to register
- reply `no` to cancel
- send an edit in the format:

```text
1.new_value
```

Example:

```text
7.AMAT Lab
```

This edits `location_name`.

The engine parses edits using `_parse_edit_message()` and applies them using `_apply_schema_edit()`.

For location edits:

- `location_name` is re-resolved through `lab_incharge`
- `location_id` is updated automatically

For `location_id` edits:

- the corresponding `location_name` is backfilled automatically

## 10. Registration

When the user replies `yes` in confirmation state:

- conversation state is cleared
- `_register_complaint()` is called
- `time_of_complaint` is set to `datetime.now()`
- the complaint is inserted into the `complaint` table

The bot then returns a success message followed by an explicit end marker.

## 11. Cancellation and Reset Behavior

At any time, the user can send:

- `cancel`
- `reset`
- `stop`
- `abort`

This clears the current complaint flow.

The user can also send:

- `undo`
- `delete`
- `remove`
- `revert`

This deletes the latest complaint registered by that `member_id`.

## 12. Message Delivery & Limits

To prevent Twilio API crashes (HTTP 21617) and ensure WhatsApp readability:

- **1600 Character Cap:** All outgoing messages are monitored. If a message exceeds 1550 characters, it is safely trimmed at the last new-line, and a note is added: _"(Note: Long description shortened for WhatsApp. Your full detailed complaint is saved in our system.)"_
- **Tool List Capping:** When multiple tools match, the bot only shows the **Top 10** items. 
- **Accessibility:** The `0. Miscellaneous / none of these` option is moved to the **Top** of the list (Choice 0) for faster selection on touch screens.
- **Async Sending:** All bot replies are sent via Twilio's Async Message API (4096 char limit) to bypass TwiML constraints.

## 13. Current Resource Search Logic

`extractor.py` currently provides:

- `smart_rapidfuzz_search()`
- `search_resource_candidates()`

The resource tables mapped in `RESOURCE_TABLE_MAP` are:

- type `1` -> `resources`
- type `2` -> `facility_resources`
- type `3` -> `safety_device`
- type `4` -> `resources`

These searches only look at active rows:

- `activation_status = 1` for `resources` and `facility_resources`
- `isworking = 1` for `safety_device`

## 13. Current Location Resolution Logic

Location mapping currently depends on `lab_incharge`.

`_resolve_lab_location()` returns:

```python
(location_name, location_id, memberid)
```

Matching order:

1. exact numeric `locationid`
2. direct `ilike` match on raw location string
3. direct `ilike` match on normalized location string
4. constrained fuzzy match using RapidFuzz

The fuzzy fallback now requires:

- token overlap between query and candidate
- a minimum score threshold

This reduces false mappings such as unrelated lab names getting selected from short vague text.

## 14. Gemini Usage Policy

Gemini is used to improve extraction and, if needed, classification.

Current design goals:

- do not use Gemini first if deterministic DB logic is enough
- cache repeated Gemini calls per message
- back off temporarily when quota is exhausted
- continue with local logic if Gemini is unavailable

Gemini currently supports:

- extracting important complaint terms
- extracting short important phrases
- suggesting resource phrase
- suggesting location phrase
- fallback complaint-type classification

## 15. Known Practical Behavior

The current workflow is designed so that:

- resource complaints should try DB search before asking the user extra questions
- location names should only remain in the schema if they resolve to real `lab_incharge` rows
- the user should see a reviewable schema before registration
- the user can edit schema fields before final registration

## 16. Known Limitations

These are current practical limitations of the workflow:

- classification may still be affected by noisy extracted phrases
- abstract keyword matches can still compete with physical signals in some edge cases
- Gemini availability depends on quota and environment
- if the app server is not restarted after code changes, WhatsApp behavior may still reflect older logic

## 17. Summary

The current chatbot workflow is:

1. receive WhatsApp message from Twilio
2. authenticate user
3. resume existing complaint flow or start a new one
4. initialize complaint schema
5. extract important words and phrases
6. resolve location from `lab_incharge`
7. search physical and abstract complaint sources
8. classify complaint type
9. fill resource and location fields from database when possible
10. ask only for missing information
11. show schema for review
12. allow confirmation or edit
13. register complaint
14. clear state and end conversation
