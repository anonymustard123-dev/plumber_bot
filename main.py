import os
import json
import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from twilio.rest import Client
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = FastAPI()

# --- CONFIGURATION ---
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM_NUMBER") # Use your +15005550006 for testing
PLUMBER_CELL = os.getenv("PLUMBER_CELL_PHONE")

# Google Calendar Config
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'primary' # Uses the calendar you shared with the bot

# --- AUTHENTICATION (The Smart Part) ---
# This reads the JSON from Railway's variable instead of a file
creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
creds_dict = json.loads(creds_json) if creds_json else None
creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES) if creds_dict else None

twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)

# --- DATA MODELS ---
class EmergencyReport(BaseModel):
    customer_name: Optional[str] = "Unknown"
    customer_phone: Optional[str] = "Unknown"
    issue_type: Optional[str] = "Emergency"
    zip_code: Optional[str] = "Unknown"

class AvailabilityRequest(BaseModel):
    day: str  # e.g., "Tuesday", "2026-01-12", "tomorrow"

class BookingRequest(BaseModel):
    customer_name: str
    customer_phone: str
    start_time: str # ISO format preferred by AI, e.g. "2026-01-12T15:00:00"

# --- HELPER FUNCTIONS ---
def get_google_service():
    return build('calendar', 'v3', credentials=creds)

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "Plumber Bot 2.0 (Calendar Active) 📅"}

@app.post("/check-availability")
async def check_availability(data: AvailabilityRequest):
    """
    Tool 3: CHECK CALENDAR
    AI asks: "Is Tuesday free?" -> We check Google Calendar.
    """
    service = get_google_service()
    
    # Simple logic: Check the next 48 hours for now
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId=CALENDAR_ID, timeMin=now,
        maxResults=10, singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])

    if not events:
        return {"status": "free", "message": "I am completely wide open for the next 2 days."}
    
    # Create a summary string for the AI
    busy_times = ", ".join([f"{e['start'].get('dateTime', 'All Day')} ({e['summary']})" for e in events])
    return {"status": "busy", "message": f"I have appointments at these times: {busy_times}. Any other time is good."}

@app.post("/book-appointment")
async def book_appointment(data: BookingRequest):
    """
    Tool 4: BOOK SLOT
    AI says: "Book Tuesday at 3pm" -> We write to Google Calendar.
    """
    service = get_google_service()
    
    # Parse the time (AI usually sends ISO). We create a 1-hour slot.
    start_dt = datetime.datetime.fromisoformat(data.start_time.replace("Z", "+00:00"))
    end_dt = start_dt + datetime.timedelta(hours=1)
    
    event_body = {
        'summary': f"PLUMBING: {data.customer_name}",
        'description': f"Phone: {data.customer_phone}",
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'UTC'},
        'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'UTC'},
    }
    
    try:
        service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
        return {"status": "success", "message": "Appointment confirmed and added to calendar."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to book: {str(e)}"}

# (Keep your existing report_emergency and check_service_area endpoints here too!)
@app.post("/report-emergency")
async def report_emergency(data: EmergencyReport):
    # ... (Paste your existing code here) ...
    print(f"🚨 EMERGENCY: {data.issue_type}")
    return {"status": "success", "message": "Dispatcher alerted."}
