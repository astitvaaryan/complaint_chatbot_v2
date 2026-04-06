# IITBNF WhatsApp Chatbot — Startup Guide

## Step 1: Clone the Repo (first time only)
```bash
git clone -b bala-schema-update [YOUR_REPO_URL]
cd bala-chatbot
```

If already cloned, just pull latest:
```bash
git pull origin bala-schema-update
```

---

## Step 2: Configure `.env`
```bash
cp .env.example .env
```
Then edit `.env` and fill in the actual values:
```
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password

DB1=slotbooking
DB2=facility_management
DB3=safety
DB4=iitbnf_troubleshooting

TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxx

GEMINI_API_KEY=AIzaxxxxxxxxxxxxxxxx

PORT=8000
```

---

## Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

Download NLTK data (one time only):
```bash
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet')"
```

---

## Step 4: Set Up the Database Tables
Run this once to create chatbot-specific tables (`conversation_state`, `chatbot_error_logs`, etc.):
```bash
python -c "from app.chatbot.db import engine; from app.chatbot import models; models.Base.metadata.create_all(bind=engine)"
```

---

## Step 5: Start the Server

Run the server in the background — it keeps running even after you close the terminal:
```bash
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
```

```bash
# Check logs:   tail -f server.log
# Stop server:  kill $(pgrep -f uvicorn)
```

---

## Step 6: Configure Twilio Webhook
In [Twilio Console](https://console.twilio.com) → Messaging → Sandbox Settings:

Set **"When a message comes in"** to:
```
http://<SERVER_IP>:8000/webhook
```
Or if Apache proxy is configured:
```
https://www.cen.iitb.ac.in/webhook
```

---

## Step 7: Test
Send `Hi` to the WhatsApp sandbox number. You should get a reply from the chatbot.

Check logs for any errors:
```bash
tail -f server.log
```

---

## Database Structure (reference)
| Env Var | Database | Tables |
|---|---|---|
| `DB1` | `slotbooking` | login, resources, lab_incharge |
| `DB2` | `facility_management` | resources |
| `DB3` | `safety` | safety_device |
| `DB4` | `iitbnf_troubleshooting` | equipment_complaint, conversation_state, chatbot_error_logs, complaint_it_keywords |
