from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.webhook import router as webhook_router


app = FastAPI(
    title="WhatsApp Chatbot API",
    description="Equipment Troubleshooting Chatbot via WhatsApp + Twilio",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(webhook_router)

@app.get("/")
def root():
    return {"status": "Chatbot backend is running ✅"}

