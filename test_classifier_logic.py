import sys
import os

# Set up to import local packages
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.chatbot.classifier import classify_complaint_type, extract_unknown_equipment

msg = "mbe main fire panel is not working properly. smokes are coming out frequently"
print(f"Message: {msg}")

type_num = classify_complaint_type(msg)
print(f"Classified Type: {type_num}")

extracted = extract_unknown_equipment(msg)
print(f"Extracted: {extracted}")
