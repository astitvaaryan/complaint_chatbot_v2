import traceback
from datetime import datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse

from app.chatbot.engine import get_chatbot_reply
from app.database import get_user_by_mobile

router = APIRouter()


def twiml_response(resp: MessagingResponse) -> Response:
    """Return a properly formatted TwiML HTTP response for Twilio."""
    return Response(
        content=str(resp),
        media_type="text/xml",
        headers={"Content-Type": "text/xml; charset=utf-8"},
    )


sessions = {}


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
            f"Hello again, {user['fname']}!\n"
            "Describe your complaint in one message, and I'll help register it."
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


@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
):
    """Twilio calls this endpoint when a WhatsApp message arrives."""
    incoming_msg = Body.strip()
    sender_raw = From.strip()
    mobile = normalize_number(sender_raw)

    print(f"[{mobile}]: {incoming_msg}")

    resp = MessagingResponse()

    if mobile in sessions:
        user = sessions[mobile]
        resp.message(handle_message(user, incoming_msg))
        return twiml_response(resp)

    user = get_user_by_mobile(mobile)

    if user is None:
        resp.message(
            "Hey! It looks like your number isn't registered with us. "
            "Please contact the lab administrator to get access."
        )
        return twiml_response(resp)

    if is_account_expired(user.get("expiry_date", "")):
        resp.message(
            f"Hi {user['fname']}! Your account expired on {user['expiry_date']}. "
            "Please reach out to the administrator to renew access."
        )
        return twiml_response(resp)

    sessions[mobile] = user
    print(f"Logged in: {user['fname']} {user['lname']} ({user['position']})")

    msg_lower = incoming_msg.lower().strip()

    if msg_lower in ["hi", "hello", "hey", ""]:
        resp.message(
            f"Hey {user['fname']}! I'm here to help register complaints. "
            "Describe your complaint in one message, and I'll collect the remaining details if needed."
        )
        return twiml_response(resp)

    resp.message(handle_message(user, incoming_msg))
    return twiml_response(resp)
