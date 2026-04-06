# 🤖 WhatsApp Equipment Troubleshooting Chatbot (v2)

A WhatsApp chatbot for lab equipment troubleshooting, built with **FastAPI + Twilio + MySQL + Gemini**.

This version includes smart complaint classification, fuzzy matching for machine names, stateful conversation flow, and automated non-equipment routing (HR, IT, etc).

---

## 📁 Project Structure

```
Chatbot/
├── app/
│   ├── main.py              ← FastAPI app entry point
│   ├── database.py          ← DB connection + user lookup
│   ├── routes/
│   │   └── webhook.py       ← Twilio WhatsApp webhook + Auth logic
│   └── chatbot/
│       ├── engine.py        ← Core conversation & state logic
│       ├── classifier.py    ← Gemini + Keyword classification
│       ├── extractor.py     ← Machine matching logic
│       ├── db.py            ← SQLAlchemy configuration
│       └── models.py        ← SQLAlchemy DB models
├── .env.example             ← Copy to .env and fill in your values
├── requirements.txt
└── README.md
```

---

## 🚀 Setup Guide

Follow these steps exactly to run the chatbot on your local machine using your own Twilio testing account.

### 1. Clone the Repository
```bash
git clone https://github.com/astitvaaryan/complaint_chatbot_v2.git
cd complaint_chatbot_v2
```

### 2. Install Dependencies
Make sure you have Python 3.9+ installed.
```bash
pip install -r requirements.txt
```

### 3. Setup Environment Variables
Create a file named `.env` in the root folder, and fill it like this:
```ini
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_PORT=3306

DB1=slotbooking
DB2=facility_management
DB3=safety
DB4=iitbnf_troubleshooting

PORT=8000

# Get a free Gemini API key from https://aistudio.google.com
GEMINI_API_KEY=your_gemini_api_key_here

# Twilio credentials required for async WhatsApp replies
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...

# PHP Backend Output (Provided by IT Admin)
PHP_API_URL=http://localhost/api/insert_complaint_api.php
PHP_API_TOKEN=iitbnf_api_7YxF2P9h
```

### 4. Import the Database
You need MySQL installed. Create the four required databases and import your schema files:
```bash
mysql -u root -p
```
```sql
CREATE DATABASE slotbooking;
CREATE DATABASE facility_management;
CREATE DATABASE safety;
CREATE DATABASE iitbnf_troubleshooting;

-- Import core tables into their respective databases
USE slotbooking;
SOURCE login.sql;
SOURCE lab_incharge.sql;

USE facility_management;
SOURCE facility_resources.sql;
```

Then, run the migration script to automatically generate the chatbot's internal routing tables (like complaints, conversation states, and error logs) inside `iitbnf_troubleshooting`:
```bash
python -c "from app.chatbot.db import engine; from app.chatbot import models; models.Base.metadata.create_all(bind=engine)"
```

### 5. Whitelist Your Phone Number in the DB
Since the chatbot blocks unknown numbers, you must add your own phone number to your local database to test it. Open MySQL and run:
```sql
USE slotbooking;
INSERT INTO login (fname, lname, mobile, email, position, expiry_date) 
VALUES ('YourName', 'Test', '+919876543210', 'test@example.com', 'Researcher', '31/12/2030');
```
*(Match the format Twilio uses, usually with the country code like `+91...` or `9876543210` depending on your setup).*

### 6. Start the Backend Server
```bash
uvicorn app.main:app --reload
```
The server will start running at `http://localhost:8000`.

### 7. Expose Server to the Internet (ngrok)
To allow Twilio to reach your local server, you need `ngrok`.

**For Windows:**
1. Download from [ngrok.com/download](https://ngrok.com/download), unzip, and place `ngrok.exe` in this folder.
2. Log in to your ngrok dashboard, copy your Authtoken, and run:
   ```cmd
   ngrok.exe config add-authtoken YOUR_AUTHTOKEN_HERE
   ```
3. Run ngrok in a new terminal:
   ```cmd
   ngrok.exe http 8000
   ```
4. Copy the `Forwarding` URL printed in the terminal (e.g., `https://1234-abcd.ngrok-free.app`).

**For Linux:**
1. Install ngrok via snap:
   ```bash
   sudo snap install ngrok
   ```
2. Add your authtoken:
   ```bash
   ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
   ```
3. Run ngrok:
   ```bash
   ngrok http 8000
   ```
4. Copy the `Forwarding` URL printed in the terminal.

### 8. Configure Twilio Sandbox
1. Go to [console.twilio.com](https://console.twilio.com) and sign up for a free account.
2. Navigate to **Messaging → Try it out → Send a WhatsApp message**.
3. Open WhatsApp on your phone and send the join code (e.g., `join purple-tiger`) to the Twilio Sandbox number.
4. On the Twilio Sandbox Settings page, paste your ngrok URL into the **"When a message comes in"** box, exactly like this:
`https://1234-abcd.ngrok-free.app/webhook`
5. Set the method to **HTTP POST** and click **Save**.

---

## 💬 Bot Chatbot Commands

| Command | Action |
|---|---|
| `hi` / `hello` | Greetings |
| `[machine name]` | Start a complaint about a specific machine |
| `cancel` / `stop` | **Clear conversation state**. Use this if the bot gets stuck asking you a question. |
| `undo` / `delete` | **Delete your last registered complaint** from the database. |

*(For categories like HR, Admin, IT, or Finance, simply type your request and the bot will automatically classify and route it without prompting for an equipment location.)*
