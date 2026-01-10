import os
import json
import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from twilio.rest import Client
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = FastAPI()

# --- CONFIGURATION ---
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
# Use the Magic Number for testing (+15005550006) or your real one
TWILIO_FROM = os.getenv("TWILIO_FROM_NUMBER") 
PLUMBER_CELL = os.getenv("PLUMBER_CELL_PHONE")

SERVICE_AREA_ZIPS = ["15201", "15202", "15203", "15212", "15213", "15222", "15232"]

# Google Calendar Config
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'primary'

# --- AUTHENTICATION ---
creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
creds_dict = json.loads(creds_json) if creds_json else None
creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES) if creds_dict else None

twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)

# --- DATA MODELS ---
class EmergencyReport(BaseModel):
    customer_name: Optional[str] = "Unknown Caller"
    customer_phone: Optional[str] = "No Number Provided"
    issue_type: Optional[str] = "Unspecified Emergency"
    severity: Optional[str] = "High"
    zip_code: Optional[str] = "Unknown Area"

class AvailabilityRequest(BaseModel):
    day: str  # e.g., "Tuesday", "2026-01-12", "tomorrow"

class BookingRequest(BaseModel):
    customer_name: str
    customer_phone: str
    start_time: str # ISO format, e.g. "2026-01-12T15:00:00"

# --- HELPER FUNCTIONS ---
def get_google_service():
    if not creds:
        print("❌ ERROR: No Google Credentials found.")
        return None
    return build('calendar', 'v3', credentials=creds)

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "The Plumber Dispatcher is Online 🟢"}

# Tool 1: Check Service Area (RESTORED)
@app.post("/check-service-area")
async def check_service_area(zip_code: str):
    if zip_code in SERVICE_AREA_ZIPS:
        return {"result": "authorized", "message": "You are in our service area."}
    else:
        return {"result": "out_of_area", "message": "Unfortunately, we do not service that zip code."}

# Tool 2: Report Emergency (RESTORED)
@app.post("/report-emergency")
async def report_emergency(data: EmergencyReport):
    print(f"🚨 TOOL TRIGGERED: {data}")
    
    # --- MOCK SMS (For Test Mode) ---
    print(f"========================================")
    print(f"📲 [SMS SENT] To: {PLUMBER_CELL}")
    print(f"💬 Message: New Emergency! {data.issue_type} at {data.zip_code}")
    print(f"========================================")
    
    # Optional: Uncomment this to send real SMS if credentials allow
    try:
        if TWILIO_SID and TWILIO_TOKEN:
             sms_body = f"🚨 NEW JOB: {data.issue_type} - {data.customer_phone}"
             twilio_client.messages.create(
                body=sms_body,
                from_=TWILIO_FROM,
                to=PLUMBER_CELL
             )
    except Exception as e:
        print(f"Twilio Error (Ignored for test): {e}")

    return {"status": "success", "message": "Dispatcher alerted."}

# Tool 3: Check Availability (NEW)
@app.post("/check-availability")
async def check_availability(data: AvailabilityRequest):
    service = get_google_service()
    if not service:
        return {"status": "error", "message": "Calendar system is offline."}
    
    # Check next 48 hours relative to "now"
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId=CALENDAR_ID, timeMin=now,
        maxResults=10, singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])

    if not events:
        return {"status": "free", "message": "I am completely wide open for the next 2 days."}
    
    busy_times = ", ".join([f"{e['start'].get('dateTime', 'All Day')} ({e['summary']})" for e in events])
    return {"status": "busy", "message": f"I have appointments at these times: {busy_times}. Any other time is good."}

# Tool 4: Book Appointment (NEW)
@app.post("/book-appointment")
async def book_appointment(data: BookingRequest):
    service = get_google_service()
    if not service:
        return {"status": "error", "message": "Calendar system is offline."}

    try:
        # Create a 1-hour slot
        start_dt = datetime.datetime.fromisoformat(data.start_time.replace("Z", "+00:00"))
        end_dt = start_dt + datetime.timedelta(hours=1)
        
        event_body = {
            'summary': f"PLUMBING: {data.customer_name}",
            'description': f"Phone: {data.customer_phone}",
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'UTC'},
        }
        
        service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
        print(f"✅ CALENDAR BOOKED for {data.customer_name}")
        return {"status": "success", "message": "Appointment confirmed and added to calendar."}
    except Exception as e:
        print(f"❌ BOOKING FAILED: {e}")
        return {"status": "error", "message": f"Failed to book: {str(e)}"}
