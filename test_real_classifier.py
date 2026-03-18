import app.chatbot.classifier as clf
test_msg = "computer wifi not working facing issue"
print(f"Testing message: {test_msg}")
res = clf._keyword_match(test_msg)
print(f"Winning Type: {res}")
print(f"TYPE_NAMES: {clf.TYPE_NAMES.get(res) if res else 'None'}")
