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
DB_NAME=slotbooking
DB_PORT=3306

PORT=8000

# Get a free Gemini API key from https://aistudio.google.com
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. Import the Database
You need MySQL installed. Import the provided `.sql` files into a database named `slotbooking`.
```bash
mysql -u root -p
CREATE DATABASE slotbooking;
USE slotbooking;
SOURCE login.sql;
SOURCE equipment_complaint.sql;
SOURCE lab_incharge.sql;
SOURCE facility_resources.sql;
```
*(Make sure Astitva gives you the `.sql` dumps!)*

### 5. Whitelist Your Phone Number in the DB
Since the chatbot blocks unknown numbers, you must add your own phone number to your local database to test it. Open MySQL and run:
```sql
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
In a **new terminal window**, start ngrok:
```bash
ngrok http 8000
```
Copy the `Forwarding` URL it gives you (e.g., `https://1234-abcd.ngrok-free.app`).

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
