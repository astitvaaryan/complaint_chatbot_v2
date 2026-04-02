# IITBNF WhatsApp Chatbot Production Deployment Guide

## 1. Codebase Transfer
To pull the physical application architecture securely onto the server, physically navigate to your web root and clone out the specific production branch:
```bash
git clone -b bala-schema-update [YOUR_REPO_URL]
cd bala-chatbot
```

## 2. Environment Configuration
Dynamically create the secure `.env` credential file. DO NOT commit this to version control!
```bash
cp .env.example .env
```
Inside `.env`, formally inject the production Twilio credentials and specifically update the **MySQL DATABASE_URL** mathematically mapping strictly to the correct schema:
`DATABASE_URL=mysql+pymysql://<user>:<pass>@localhost:3306/iitbnf_troubleshooting`

## 3. Dependency Injection
Legally download the core Python packages:
```bash
pip install -r requirements.txt
```

**CRITICAL: NLTK Data Allocation**
The AI categorization logic relies heavily on NLTK data blocks. You must uniquely run this exact Python command to permanently cache the language metadata into the server:
```bash
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet')"
```

## 4. Boot-up the Database Architecture
Execute the physical startup script to mathematically force SQLAlchemy to magically bind all native schema representations (like the `chatbot_error_logs` telemetry table) permanently into your live MySQL server:
```bash
python -c "from app.chatbot.db import engine; from app.chatbot.models import Base; Base.metadata.create_all(bind=engine)"
```

## 5. Live Server Daemon Execution
Finally, uniquely spin up the core Uvicorn ASGI execution runtime safely in the background (using `pm2`, `tmux`, `supervisor`, or `systemd`) permanently locked onto port `8000`:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

*(Note: Don't forget to dynamically update the official Twilio Webhook callback console mapping completely to your server's public physical IP address + `/chatbot/webhook`!)*
