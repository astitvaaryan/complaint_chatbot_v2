from app.chatbot import classifier
import random

print("--- CSV EXTRACTION CHECK ---")
for type_num, keywords in classifier.KEYWORD_TYPE_MAP.items():
    base_kws = set(classifier._BASE_KEYWORDS.get(type_num, []))
    learned_kws = [kw for kw in keywords if kw not in base_kws]
    
    type_name = classifier.TYPE_NAMES.get(type_num, f"Type {type_num}")
    print(f"\n{type_name} ({type_num}):")
    print(f"  Base Keywords Count: {len(base_kws)}")
    print(f"  Learned (CSV) Keywords Count: {len(learned_kws)}")
    
    if learned_kws:
        sample = random.sample(learned_kws, min(10, len(learned_kws)))
        print(f"  Sample Learned: {sample}")
    else:
        print("  No learned keywords found.")
