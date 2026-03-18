import traceback
from datetime import datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from app.database import (
    get_users_by_mobile, 
    get_user_by_mobile_and_email,
    get_session, 
    save_session, 
    delete_session,
    get_pending_ver, 
    save_pending_ver, 
    delete_pending_ver
)
from datetime import datetime
from app.chatbot.engine import get_chatbot_reply   # top-level: crash on startup if broken

router = APIRouter()


def twiml_response(resp: MessagingResponse) -> Response:
    """Return a properly formatted TwiML HTTP response for Twilio."""
    return Response(
        content=str(resp),
        media_type="text/xml",
        headers={"Content-Type": "text/xml; charset=utf-8"},
    )

# Sessions and pending verifications are now handled via database persistence (app/database.py)
# The local dicts are removed to ensure multi-process safety and persistence after restarts.

MAX_EMAIL_ATTEMPTS = 3   # lock out after this many wrong emails


def normalize_number(from_field: str) -> str:
    """Convert Twilio sender values to a normalized 10-digit number."""
    number = from_field.strip()

    if number.startswith("whatsapp:"):
        number = number[len("whatsapp:") :]
    if number.startswith("+91"):
        number = number[3:]
    elif number.startswith("+"):
        number = number[1:]

    number = number.replace(" ", "").replace("-", "")

    if len(number) > 10:
        number = number[-10:]

    return number


def is_account_expired(expiry_date_str: str) -> bool:
    """Return True if the user's account has expired."""
    try:
        if not expiry_date_str or expiry_date_str.strip() in ["", "0000-00-00"]:
            return False
        expiry = datetime.strptime(expiry_date_str.strip(), "%m/%d/%Y")
        return datetime.now() > expiry
    except Exception:
        return False


def handle_message(user: dict, message: str) -> str:
    """Route authenticated user messages to the chatbot engine."""
    msg_lower = message.lower().strip()

    if msg_lower in ["hi", "hello", "hey"]:
        return (
            f"Hello, {user['fname']}! 👋\n"
            f"Just tell me what the issue is, and I'll route it correctly."
        )

    if msg_lower == "whoami":
        return (
            f"Your Info\n\n"
            f"Name: {user['fname']} {user['lname']}\n"
            f"Role: {user['position']}\n"
            f"Email: {user['email']}"
        )

    try:
        return get_chatbot_reply(user, message)
    except Exception as exc:
        print(f"[WEBHOOK] Unhandled engine error: {exc}")
        traceback.print_exc()
        return "Something went wrong. Please try again."


def _admit_user(mobile: str, user: dict, incoming_msg: str) -> str:
    """
    Save user to session and return the first response.
    Called once authentication is complete (either path).
    """
    save_session(mobile, user)
    print(f"✅ Logged in: {user['fname']} {user['lname']} ({user['position']})")

    msg_lower = incoming_msg.lower().strip()

    if msg_lower in ["hi", "hello", "hey", ""]:
        return (
            f"Welcome, {user['fname']}! 👋\n"
            f"Just tell me what the issue is, and I'll route it correctly."
        )

    # Authenticate silently and process message right away
    return handle_message(user, incoming_msg)


@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
):
    """
    Twilio calls this endpoint when a WhatsApp message arrives.

    Auth flow:
      1. Returning session  → fast path (no DB hit)
      2. Pending email ver  → user must reply with email to disambiguate
      3. New number, unique → auth done immediately
      4. New number, dup    → ask for email, enter pending state
      5. Unknown number     → reject
    """
    incoming_msg = Body.strip()
    sender_raw   = From.strip()
    mobile       = normalize_number(sender_raw)

    print(f"[{mobile}]: {incoming_msg}")

    resp = MessagingResponse()

    # ── PATH 1: Returning user already in session ─────────────────
    session_user = get_session(mobile)
    if session_user:
        user = session_user

        # Explicit Logout Command
        if incoming_msg.lower().strip() == "logout":
            delete_session(mobile)
            resp.message("👋 You have been logged out successfully. You will be asked to authenticate again on your next message.")
            return twiml_response(resp)

        # Continual Expiry Check (Ensure they weren't removed while in-session)
        if is_account_expired(user.get("expiry_date", "")):
            delete_session(mobile)
            resp.message(
                f"Hi {user['fname']}! Your account expired on {user.get('expiry_date', 'unknown')}. "
                f"Please reach out to the administrator to renew access. 🙏"
            )
            return twiml_response(resp)

        resp.message(handle_message(user, incoming_msg))
        return twiml_response(resp)

    # ── PATH 2: Waiting for email verification ────────────────────
    state = get_pending_ver(mobile)
    if state:
        
        # Ignore basic greetings so we don't penalize the user
        if incoming_msg.lower().strip() in ["hi", "hello", "hey"]:
            resp.message(
                "📋 Please reply with your registered *email address* to verify your account:"
            )
            return twiml_response(resp)
            
        candidates = state["candidates"]
        state["attempts"] += 1
        save_pending_ver(mobile, candidates, state["attempts"])

        # Check if user typed their email
        matched_user = get_user_by_mobile_and_email(mobile, incoming_msg)

        if matched_user:
            # Correct email — clear pending state and admit
            delete_pending_ver(mobile)

            if is_account_expired(matched_user.get("expiry_date", "")):
                resp.message(
                    f"Hi {matched_user['fname']}! Your account expired on "
                    f"{matched_user['expiry_date']}. Please contact the administrator. 🙏"
                )
                return twiml_response(resp)

            resp.message(_admit_user(mobile, matched_user, ""))
            return twiml_response(resp)

        # Wrong email
        attempts_left = MAX_EMAIL_ATTEMPTS - state["attempts"]
        if attempts_left <= 0:
            delete_pending_ver(mobile)
            resp.message(
                "❌ Too many incorrect attempts. "
                "Please contact the lab administrator for help. 🙏"
            )
            return twiml_response(resp)

        resp.message(
            f"⚠️ That email didn't match any account on this number. "
            f"Please try again ({attempts_left} attempt(s) left).\n"
            f"Reply with your registered email address:"
        )
        return twiml_response(resp)

    # ── First contact: look up the number ─────────────────────────
    users = get_users_by_mobile(mobile)

    # PATH 5: Number not registered at all
    if not users:
        resp.message(
            "Hey! It looks like your number isn't registered with us. "
            "Please contact the lab administrator to get access. 🙏"
        )
        return twiml_response(resp)

    # ── PATH 3: Unique number → authenticate directly ─────────────
    if len(users) == 1:
        user = users[0]

        if is_account_expired(user.get("expiry_date", "")):
            resp.message(
                f"Hi {user['fname']}! Your account expired on {user['expiry_date']}. "
                f"Please reach out to the administrator to renew access. 🙏"
            )
            return twiml_response(resp)

        resp.message(_admit_user(mobile, user, incoming_msg))
        return twiml_response(resp)

    # ── PATH 4: Duplicate phone numbers → email verification ──────
    print(f"[AUTH] Duplicate mobile {mobile} — {len(users)} accounts found. Asking for email.")
    save_pending_ver(mobile, users, 0)

    resp.message(
        "📋 We found multiple accounts registered with this phone number.\n\n"
        "To identify you correctly, please reply with your registered *email address*:"
    )
    return twiml_response(resp)
