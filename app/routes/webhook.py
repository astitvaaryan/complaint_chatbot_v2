import traceback
from fastapi import APIRouter, Request, Form
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from app.database import get_users_by_mobile, get_user_by_mobile_and_email
from datetime import datetime
from app.chatbot.engine import get_chatbot_reply   # top-level: crash on startup if broken

router = APIRouter()

def twiml_response(resp: MessagingResponse) -> Response:
    """Return a properly formatted TwiML HTTP response for Twilio."""
    return Response(
        content=str(resp),
        media_type="text/xml",
        headers={"Content-Type": "text/xml; charset=utf-8"}
    )

# ─────────────────────────────────────────────────────────────────
# In-memory stores
#
# sessions          → key: mobile  | value: fully authenticated user dict
# pending_email_ver → key: mobile  | value: {"candidates": [user, …], "attempts": int}
#
# pending_email_ver holds numbers where the same phone belongs to
# multiple accounts.  The user must reply with their registered email
# to resolve which account to authenticate.
# ─────────────────────────────────────────────────────────────────
sessions:          dict = {}
pending_email_ver: dict = {}

MAX_EMAIL_ATTEMPTS = 3   # lock out after this many wrong emails


def normalize_number(from_field: str) -> str:
    """
    Convert Twilio's 'whatsapp:+919764670987' → '9764670987'
    """
    number = from_field.strip()

    if number.startswith("whatsapp:"):
        number = number[len("whatsapp:"):]
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
    """
    Route authenticated user messages to the chatbot engine.
    """
    msg_lower = message.lower().strip()

    # ── Basic commands handled locally ────────────────────────────
    if msg_lower in ["hi", "hello", "hey"]:
        return (
            f"Hello, {user['fname']}! 👋\n"
            f"Just tell me what the issue is, and I'll route it correctly."
        )

    if msg_lower == "whoami":
        return (
            f"👤 *Your Info*\n\n"
            f"Name: {user['fname']} {user['lname']}\n"
            f"Role: {user['position']}\n"
            f"Email: {user['email']}"
        )

    # ── All other messages → chatbot engine ───────────────────────
    try:
        return get_chatbot_reply(user, message)
    except Exception as e:
        print(f"[WEBHOOK] Unhandled engine error: {e}")
        traceback.print_exc()
        return "⚠️ Something went wrong. Please try again."


def _admit_user(mobile: str, user: dict, incoming_msg: str) -> str:
    """
    Save user to session and return the first response.
    Called once authentication is complete (either path).
    """
    sessions[mobile] = user
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

    print(f"📩 [{mobile}]: {incoming_msg}")

    resp = MessagingResponse()

    # ── PATH 1: Returning user already in session ─────────────────
    if mobile in sessions:
        user = sessions[mobile]

        # Explicit Logout Command
        if incoming_msg.lower().strip() == "logout":
            del sessions[mobile]
            resp.message("👋 You have been logged out successfully. You will be asked to authenticate again on your next message.")
            return twiml_response(resp)

        # Continual Expiry Check (Ensure they weren't removed while in-session)
        if is_account_expired(user.get("expiry_date", "")):
            del sessions[mobile]
            resp.message(
                f"Hi {user['fname']}! Your account expired on {user.get('expiry_date', 'unknown')}. "
                f"Please reach out to the administrator to renew access. 🙏"
            )
            return twiml_response(resp)

        resp.message(handle_message(user, incoming_msg))
        return twiml_response(resp)

    # ── PATH 2: Waiting for email verification ────────────────────
    if mobile in pending_email_ver:
        state      = pending_email_ver[mobile]
        
        # Ignore basic greetings so we don't penalize the user
        if incoming_msg.lower().strip() in ["hi", "hello", "hey"]:
            resp.message(
                "📋 Please reply with your registered *email address* to verify your account:"
            )
            return twiml_response(resp)
            
        candidates = state["candidates"]
        state["attempts"] += 1

        # Check if user typed their email
        matched_user = get_user_by_mobile_and_email(mobile, incoming_msg)

        if matched_user:
            # Correct email — clear pending state and admit
            del pending_email_ver[mobile]

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
            del pending_email_ver[mobile]
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
    pending_email_ver[mobile] = {"candidates": users, "attempts": 0}

    resp.message(
        "📋 We found multiple accounts registered with this phone number.\n\n"
        "To identify you correctly, please reply with your registered *email address*:"
    )
    return twiml_response(resp)
