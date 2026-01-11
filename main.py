import os
import json
import datetime
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request
from pydantic import BaseModel
from twilio.rest import Client
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = FastAPI()

# --- CONFIGURATION ---
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM_NUMBER") 
PLUMBER_CELL = os.getenv("PLUMBER_CELL_PHONE")
SERVICE_AREA_ZIPS = ["15201", "15202", "15203", "15212", "15213", "15222", "15232"]

# --- 🚨 CRITICAL CHANGE HERE 🚨 ---
# Change 'primary' to the Gmail address you shared the calendar with.
# Example: CALENDAR_ID = 'sam.shah@gmail.com'
CALENDAR_ID = 'anonymustard123@gmail.com' 

# Google Auth
SCOPES = ['https://www.googleapis.com/auth/calendar']
creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
creds_dict = json.loads(creds_json) if creds_json else None
creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES) if creds_dict else None
twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)

# --- HELPER FUNCTIONS ---
def get_google_service():
    if not creds:
        print("❌ ERROR: No Google Credentials found.")
        return None
    return build('calendar', 'v3', credentials=creds)

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "Plumber Bot Online 🟢"}

@app.post("/check-service-area")
async def check_service_area(request: Request):
    # Flexible handler that prints what Vapi sends
    body = await request.json()
    print(f"🔍 DEBUG SERVICE AREA: {body}")
    
    # Try to find the zip code in various possible keys
    zip_code = body.get('zip_code') or body.get('zip') or body.get('code')
    
    if not zip_code:
         return {"result": "error", "message": "I didn't hear a zip code."}

    if zip_code in SERVICE_AREA_ZIPS:
        return {"result": "authorized", "message": "You are in our service area."}
    else:
        return {"result": "out_of_area", "message": "Unfortunately, we do not service that zip code."}

@app.post("/report-emergency")
async def report_emergency(request: Request):
    body = await request.json()
    print(f"🚨 DEBUG EMERGENCY: {body}")
    
    # Extract data safely
    issue = body.get('issue_type', 'Emergency')
    phone = body.get('customer_phone', 'Unknown')
    
    print(f"📲 [MOCK SMS] To Conrad: {issue} - {phone}")
    return {"status": "success", "message": "Dispatcher alerted."}

@app.post("/check-availability")
async def check_availability(request: Request):
    # 1. Capture the raw input from Vapi to debug the 422 error
    body = await request.json()
    print(f"📅 DEBUG CALENDAR CHECK: {body}")

    service = get_google_service()
    if not service:
        return {"status": "error", "message": "Calendar system offline."}
    
    # 2. Check the Calendar
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    try:
        events_result = service.events().list(
            calendarId=CALENDAR_ID, 
            timeMin=now,
            maxResults=10, 
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        
        if not events:
            return {"status": "free", "message": "I am completely wide open for the next 2 days."}
        
        # Format the busy times clearly for the AI
        busy_list = []
        for e in events:
            start = e['start'].get('dateTime', e['start'].get('date'))
            summary = e.get('summary', 'Busy')
            busy_list.append(f"{start} ({summary})")
            
        busy_string = ", ".join(busy_list)
        return {"status": "busy", "message": f"I have appointments at: {busy_string}"}
        
    except Exception as e:
        print(f"❌ CALENDAR ERROR: {e}")
        return {"status": "error", "message": "I am having trouble accessing the schedule right now."}

@app.post("/book-appointment")
async def book_appointment(request: Request):
    body = await request.json()
    print(f"📝 DEBUG BOOKING: {body}")
    
    service = get_google_service()
    
    customer_name = body.get('customer_name', 'Unknown')
    start_time = body.get('start_time')
    
    if not start_time:
        return {"status": "error", "message": "I need a valid start time."}

    try:
        start_dt = datetime.datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = start_dt + datetime.timedelta(hours=1)
        
        event_body = {
            'summary': f"PLUMBING: {customer_name}",
            'description': f"Booked via AI",
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'UTC'},
        }
        
        service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
        return {"status": "success", "message": "Appointment confirmed."}
    except Exception as e:
        print(f"❌ BOOKING ERROR: {e}")
        return {"status": "error", "message": "Failed to book slot."}
