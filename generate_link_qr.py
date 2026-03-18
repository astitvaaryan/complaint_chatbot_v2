"""
generate_link_qr.py
────────────────────────────────────────────────────────
Run this script to generate:
1. A WhatsApp deep link (wa.me URL) to open your chatbot
2. A QR code image (PNG) that users can scan

Usage:
    python generate_link_qr.py

Output:
    - Prints the link to console
    - Saves: chatbot_qr.png
"""

import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
import json

# ─────────────────────────────────────────────────────────────────
# CONFIGURATION — Edit these values
# ─────────────────────────────────────────────────────────────────

# Your Twilio Sandbox WhatsApp number (or production number)
# Sandbox default: +14155238886
# For production: your purchased Twilio number e.g. +919XXXXXXXXX
TWILIO_WHATSAPP_NUMBER = "+14155238886"

# The first message users need to send to join the sandbox
# (Only needed for Twilio Sandbox — not for production)
SANDBOX_JOIN_CODE = "join itself-pull"
# ^ Go to console.twilio.com → Messaging → Try it out → Send a WhatsApp message
# ^ Copy the 'join xxxx-xxxx' phrase shown there and paste it above

# Bot name shown in the QR code image
BOT_NAME = "Equipment Troubleshooting Bot"
INSTITUTION = "IIT Bombay Nanofabrication Facility"

# ─────────────────────────────────────────────────────────────────


def generate_whatsapp_link(phone_number: str, message: str = "Hi") -> str:
    """
    Generate a wa.me deep link.
    Format: https://wa.me/<number>?text=<encoded_message>
    """
    import urllib.parse

    # Remove + and spaces from phone number
    clean_number = phone_number.replace("+", "").replace(" ", "")

    # URL encode the message
    encoded_message = urllib.parse.quote(message)

    link = f"https://wa.me/{clean_number}?text={encoded_message}"
    return link


def generate_qr_code(link: str, output_file: str = "chatbot_qr.png"):
    """
    Generate a styled QR code PNG image.
    """
    # ─── Create QR code ───────────────────────────────────────────
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High correction (30%)
        box_size=10,
        border=4,
    )
    qr.add_data(link)
    qr.make(fit=True)

    # WhatsApp green color scheme
    qr_image = qr.make_image(fill_color="#128C7E", back_color="white")

    # ─── Add branding around the QR code ──────────────────────────
    qr_width, qr_height = qr_image.size
    canvas_width = qr_width + 60
    canvas_height = qr_height + 160  # Extra space for text

    # White canvas
    canvas = Image.new("RGB", (canvas_width, canvas_height), color="white")

    # Paste QR code in center
    qr_x = (canvas_width - qr_width) // 2
    canvas.paste(qr_image, (qr_x, 100))

    # Draw text
    draw = ImageDraw.Draw(canvas)

    # Title text (top)
    title_text = f"📱 {BOT_NAME}"
    draw.text((canvas_width // 2, 20), title_text, fill="#128C7E", anchor="mm")

    subtitle_text = INSTITUTION
    draw.text((canvas_width // 2, 50), subtitle_text, fill="#555555", anchor="mm")

    # Footer text (bottom)
    footer = "Scan to start chatting on WhatsApp"
    draw.text(
        (canvas_width // 2, qr_height + 120),
        footer,
        fill="#075E54",
        anchor="mm"
    )

    small_note = "Powered by Twilio + FastAPI"
    draw.text(
        (canvas_width // 2, qr_height + 145),
        small_note,
        fill="#AAAAAA",
        anchor="mm"
    )

    canvas.save(output_file)
    print(f"✅ QR code saved as: {output_file}")


def main():
    print("=" * 60)
    print("  WhatsApp Chatbot — Link & QR Code Generator")
    print("=" * 60)

    # ─── For SANDBOX (testing) ────────────────────────────────────
    # Users must first join the sandbox by sending the join code
    sandbox_link = generate_whatsapp_link(
        TWILIO_WHATSAPP_NUMBER,
        message=SANDBOX_JOIN_CODE
    )

    # ─── For PRODUCTION (after going live) ───────────────────────
    # Users just send "Hi" — no join code needed
    production_link = generate_whatsapp_link(
        TWILIO_WHATSAPP_NUMBER,
        message="Hi"
    )

    print("\n📋 SANDBOX LINK (for testing — users must join first):")
    print(f"   {sandbox_link}")

    print("\n📋 PRODUCTION LINK (for live bot):")
    print(f"   {production_link}")

    print("\n📌 SANDBOX JOIN INSTRUCTIONS:")
    print(f"   1. Users send this to {TWILIO_WHATSAPP_NUMBER} on WhatsApp:")
    print(f"      '{SANDBOX_JOIN_CODE}'")
    print(f"   2. Once joined, they can freely chat with the bot.")
    print(f"   3. OR share the sandbox link above — it pre-fills the join code.")

    print("\n🎨 Generating QR Code...")

    # Generate QR for the sandbox link (switch to production_link when ready)
    generate_qr_code(sandbox_link, output_file="chatbot_qr_sandbox.png")
    generate_qr_code(production_link, output_file="chatbot_qr_production.png")

    print("\n🎉 Done!")
    print("   → chatbot_qr_sandbox.png    (share this for testing)")
    print("   → chatbot_qr_production.png (share this when live)")
    print()

    # Save links to a JSON file for reference
    links = {
        "sandbox_link": sandbox_link,
        "production_link": production_link,
        "twilio_number": TWILIO_WHATSAPP_NUMBER,
        "sandbox_join_code": SANDBOX_JOIN_CODE
    }
    with open("chatbot_links.json", "w") as f:
        json.dump(links, f, indent=2)
    print("   → chatbot_links.json        (all links saved here)")


if __name__ == "__main__":
    main()
