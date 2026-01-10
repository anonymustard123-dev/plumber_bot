import os
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from twilio.rest import Client

app = FastAPI()

# --- CONFIGURATION ---
# Load these from environment variables for security
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
PLUMBER_CELL = os.getenv("PLUMBER_CELL_PHONE")  # The plumber's real cell

# Simple "Service Area" Database (Pittsburgh ZIPs)
SERVICE_AREA_ZIPS = ["15201", "15202", "15203", "15212", "15213", "15222", "15232"]

# Initialize Twilio Client
twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)

# --- DATA MODELS (Structured Inputs from Vapi) ---
class EmergencyReport(BaseModel):
    customer_name: str
    customer_phone: str
    issue_type: str  # e.g., "Burst Pipe", "No Hot Water", "Clogged Drain"
    severity: str    # "High" (Flooding) or "Low" (Drip)
    zip_code: str

class BookingRequest(BaseModel):
    customer_name: str
    customer_phone: str
    preferred_time: str

# --- API ENDPOINTS (Tools for Vapi) ---

@app.get("/")
def home():
    return {"status": "The Plumber Dispatcher is Online 🟢"}

@app.post("/check-service-area")
async def check_service_area(zip_code: str):
    """
    Tool 1: Checks if the caller is in Pittsburgh.
    """
    if zip_code in SERVICE_AREA_ZIPS:
        return {"result": "authorized", "message": "You are in our service area."}
    else:
        return {"result": "out_of_area", "message": "Unfortunately, we do not service that zip code."}

@app.post("/report-emergency")
async def report_emergency(data: EmergencyReport):
    """
    Tool 2: THE MONEY MAKER. 
    If severity is HIGH, this sends an immediate SMS to the plumber.
    """
    print(f"🚨 EMERGENCY REPORTED: {data.issue_type} by {data.customer_name}")

    if data.severity.lower() == "high":
        # 1. Draft the SMS
        sms_body = (
            f"🚨 NEW EMERGENCY JOB 🚨\n\n"
            f"Issue: {data.issue_type}\n"
            f"Customer: {data.customer_name}\n"
            f"Phone: {data.customer_phone}\n"
            f"Location: {data.zip_code}\n"
            f"Status: Customer is waiting. Call immediately."
        )
        
        # 2. Send via Twilio
        try:
            message = twilio_client.messages.create(
                body=sms_body,
                from_=TWILIO_FROM_NUMBER,
                to=PLUMBER_CELL
            )
            return {"status": "dispatched", "sms_id": message.sid}
        except Exception as e:
            print(f"Twilio Error: {e}")
            return {"status": "error", "message": "Failed to send SMS"}
    
    else:
        # If it's low severity, we don't wake the plumber up. We log it.
        return {"status": "logged", "message": "Routine issue logged. Office will call back."}

@app.post("/book-routine")
async def book_routine(data: BookingRequest):
    """
    Tool 3: Handling the non-emergency stuff.
    """
    # In a real app, this would add to a Google Calendar.
    # For now, we just text the owner a "Low Priority" lead.
    sms_body = (
        f"🗓️ NEW ROUTINE LEAD\n"
        f"Name: {data.customer_name}\n"
        f"Requested: {data.preferred_time}\n"
        f"Action: Call back tomorrow."
    )
    twilio_client.messages.create(
        body=sms_body,
        from_=TWILIO_FROM_NUMBER,
        to=PLUMBER_CELL
    )
    return {"status": "booked", "message": "Appointment request received."}
