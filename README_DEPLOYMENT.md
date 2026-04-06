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

## Step 6: Expose Server to the Internet (ngrok)

If the server doesn't have a public IP or Apache proxy configured yet, use ngrok to expose port 8000.

**For Linux:**
1. Install ngrok via snap:
   ```bash
   sudo snap install ngrok
   ```
2. Add your authtoken (get from your ngrok dashboard):
   ```bash
   ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
   ```
3. Run ngrok in the background using `nohup`:
   ```bash
   nohup ngrok http 8000 > ngrok.log 2>&1 &
   ```
4. To find the public URL ngrok assigned you, run:
   ```bash
   curl -s http://localhost:4040/api/tunnels | grep -q 'tunnels' && curl -s http://localhost:4040/api/tunnels | grep -o 'https://[^"]*ngrok-free.app'
   ```

**For Windows:**
1. Download from [ngrok.com/download](https://ngrok.com/download), unzip, and place `ngrok.exe` in this folder.
2. Add your authtoken:
   ```cmd
   ngrok.exe config add-authtoken YOUR_AUTHTOKEN_HERE
   ```
3. Run ngrok:
   ```cmd
   ngrok.exe http 8000
   ```
4. Copy the `Forwarding` URL printed in the terminal.

---

## Step 7: Configure Twilio Webhook
In [Twilio Console](https://console.twilio.com) → Messaging → Sandbox Settings:

Set **"When a message comes in"** to either your Apache proxy URL, or your ngrok URL combined with `/webhook`. Example:
```
https://xxxx-xxxx.ngrok-free.app/webhook
```

---

## Step 8: Test
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
