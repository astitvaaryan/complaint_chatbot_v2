import sys
sys.stdout.reconfigure(encoding='utf-8')
from app.chatbot.classifier import KEYWORD_TYPE_MAP, _load_csv_keywords
_load_csv_keywords()

print("Checking 'salary not received'...")
for t, kws in KEYWORD_TYPE_MAP.items():
    for kw in kws:
        if kw in 'salary not received':
            print(f'Type {t} matches keyword: "{kw}"')
