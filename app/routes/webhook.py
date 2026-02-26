import traceback
from fastapi import APIRouter, Request, Form
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from app.database import get_user_by_mobile
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
# In-memory session store
# key: normalized mobile number
# value: user dict from DB
# ─────────────────────────────────────────────────────────────────
sessions = {}


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
            f"Hello again, {user['fname']}!\n"
            "Send a machine name to register a complaint."
        )

    # if msg_lower == "help":
    #     return (
    #         "🔧 *Equipment Troubleshooting Bot*\n\n"
    #         "How to use:\n"
    #         "1️⃣ Send the machine name with your issue\n"
    #         "   _Example: 'SEM not working'_\n\n"
    #         "2️⃣ Bot will ask for issue type\n"
    #         "   Reply: *hardware*, *process*, or *electrical*\n\n"
    #         "3️⃣ Complaint is registered ✅\n\n"
    #         "Other commands:\n"
    #         "• *whoami* — Your account info\n"
    #         "• *help* — This menu"
    #     )

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


@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
):
    """
    Twilio calls this endpoint when a WhatsApp message arrives.
    """
    incoming_msg = Body.strip()
    sender_raw = From.strip()
    mobile = normalize_number(sender_raw)

    print(f"📩 [{mobile}]: {incoming_msg}")

    resp = MessagingResponse()

    # ── Returning user: already in session, skip DB lookup ────────
    if mobile in sessions:
        user = sessions[mobile]
        resp.message(handle_message(user, incoming_msg))
        return twiml_response(resp)

    # ── New user: check DB ────────────────────────────────────────
    user = get_user_by_mobile(mobile)

    if user is None:
        resp.message(
            "Hey! It looks like your number isn't registered with us. "
            "Please contact the lab administrator to get access. 🙏"
        )
        return twiml_response(resp)

    # ── Check if account is expired ───────────────────────────────
    if is_account_expired(user.get("expiry_date", "")):
        resp.message(
            f"Hi {user['fname']}! Your account expired on {user['expiry_date']}. "
            f"Please reach out to the administrator to renew access. 🙏"
        )
        return twiml_response(resp)

    # ── Valid user: save session silently ────────────────────────
    sessions[mobile] = user
    print(f"✅ Logged in: {user['fname']} {user['lname']} ({user['position']})")

    msg_lower = incoming_msg.lower().strip()

    # Only show welcome banner if user explicitly says hi
    if msg_lower in ["hi", "hello", "hey", ""]:
        resp.message(
            f"Hey {user['fname']}! 👋 I'm here to help with equipment issues. "
            f"Just tell me the machine name and what's wrong, and I'll log it right away."
        )
        return twiml_response(resp)

    # Otherwise: authenticate silently and process their message right away
    resp.message(handle_message(user, incoming_msg))
    return twiml_response(resp)
