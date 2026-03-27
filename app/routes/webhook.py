import os
import traceback
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import Response
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from app.database import get_users_by_mobile, get_user_by_mobile_and_email
from datetime import datetime
from app.chatbot.db import SessionLocal
from app.chatbot.engine import get_chatbot_reply   # top-level: crash on startup if broken
from app.chatbot.state_manager import get_state

router = APIRouter()


def twiml_response(resp: MessagingResponse) -> Response:
    """Return a properly formatted TwiML HTTP response for Twilio."""
    return Response(
        content=str(resp),
        media_type="text/xml",
        headers={"Content-Type": "text/xml; charset=utf-8"},
    )


def _send_async_whatsapp_message(from_number: str, to_number: str, body: str) -> None:
    """Send the final WhatsApp reply outside the webhook response cycle."""
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
        if not account_sid or not auth_token or not from_number or not to_number or not body.strip():
            return

        client = Client(account_sid, auth_token)
        client.messages.create(
            from_=from_number,
            to=to_number,
            body=body,
        )
    except Exception as exc:
        print(f"[WEBHOOK] Async Twilio send failed: {exc}")


def should_use_processing(message: str, final_message: str) -> bool:
    """Use loading only for actual complaint processing, not quick control replies."""
    msg = (message or "").strip().lower()
    final = (final_message or "").strip().lower()

    if not final:
        return False

    immediate_commands = {
        "hi", "hello", "hey", "whoami", "logout",
        "cancel", "reset", "stop", "abort",
        "undo", "delete", "remove", "revert",
        "yes", "no", "y", "n", "ok", "okay", "confirm",
    }
    if msg in immediate_commands:
        return False

    terminal_prefixes = (
        "current complaint flow canceled.",
        "complaint registration canceled.",
        "complaint registered successfully.",
        "your latest complaint has been deleted.",
        "no recent complaint was found to delete.",
        "i reset the previous conversation state.",
        "sorry, something went wrong.",
        "something went wrong.",
    )
    if final.startswith(terminal_prefixes):
        return False

    return True


def processing_text_for_user(user_phone: str) -> str:
    """Choose a user-friendly loading message based on conversation stage."""
    db = SessionLocal()
    try:
        state = get_state(db, user_phone)
        if state is None:
            return "Processing your complaint..."
        return "Loading...."
    except Exception:
        return "Loading...."
    finally:
        db.close()


def respond_with_processing(
    resp: MessagingResponse,
    background_tasks: BackgroundTasks,
    from_number: str | None,
    to_number: str | None,
    incoming_message: str,
    final_message: str,
    processing_text: str,
) -> Response:
    """Return an immediate loading message and send the final reply asynchronously."""
    if from_number and not str(from_number).startswith("whatsapp:"):
        from_number = f"whatsapp:{from_number}"
    if to_number and not str(to_number).startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"

    if not should_use_processing(incoming_message, final_message):
        resp.message(final_message)
        return twiml_response(resp)

    resp.message(processing_text)

    if from_number and to_number and final_message.strip():
        background_tasks.add_task(_send_async_whatsapp_message, from_number, to_number, final_message)
    else:
        resp.message(final_message)

    return twiml_response(resp)

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
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(...),
    To: str = Form(""),
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

        return respond_with_processing(
            resp,
            background_tasks,
            To,
            From,
            incoming_msg,
            handle_message(user, incoming_msg),
            processing_text_for_user(mobile),
        )

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

            return respond_with_processing(
                resp,
                background_tasks,
                To,
                From,
                incoming_msg,
                _admit_user(mobile, matched_user, ""),
                processing_text_for_user(mobile),
            )

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

        return respond_with_processing(
            resp,
            background_tasks,
            To,
            From,
            incoming_msg,
            _admit_user(mobile, user, incoming_msg),
            processing_text_for_user(mobile),
        )

    # ── PATH 4: Duplicate phone numbers → email verification ──────
    print(f"[AUTH] Duplicate mobile {mobile} — {len(users)} accounts found. Asking for email.")
    pending_email_ver[mobile] = {"candidates": users, "attempts": 0}

    resp.message(
        "📋 We found multiple accounts registered with this phone number.\n\n"
        "To identify you correctly, please reply with your registered *email address*:"
    )
    return twiml_response(resp)
