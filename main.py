import os
from typing import Optional # <--- ADD THIS
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from twilio.rest import Client

app = FastAPI()

# --- CONFIGURATION ---
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
PLUMBER_CELL = os.getenv("PLUMBER_CELL_PHONE") 

SERVICE_AREA_ZIPS = ["15201", "15202", "15203", "15212", "15213", "15222", "15232"]

twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)

# --- UPDATED DATA MODELS ---
# We make fields Optional so the tool doesn't crash if the AI 
# fires it before asking for a name or zip code.
class EmergencyReport(BaseModel):
    customer_name: Optional[str] = "Unknown Caller"
    customer_phone: Optional[str] = "No Number Provided"
    issue_type: str 
    severity: Optional[str] = "High" 
    zip_code: Optional[str] = "Unknown Area"

class BookingRequest(BaseModel):
    customer_name: str
    customer_phone: str
    preferred_time: str

# --- API ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "The Plumber Dispatcher is Online 🟢"}

@app.post("/check-service-area")
async def check_service_area(zip_code: str):
    if zip_code in SERVICE_AREA_ZIPS:
        return {"result": "authorized", "message": "You are in our service area."}
    else:
        return {"result": "out_of_area", "message": "Unfortunately, we do not service that zip code."}

@app.post("/report-emergency")
async def report_emergency(data: EmergencyReport):
    """
    Tool 2: EMERGENCY DISPATCH
    """
    print(f"🚨 EMERGENCY REPORTED: {data.issue_type}")

    # Force severity to high if the AI implies it
    if data.severity.lower() == "high":
        sms_body = (
            f"🚨 NEW EMERGENCY JOB 🚨\n\n"
            f"Issue: {data.issue_type}\n"
            f"Phone: {data.customer_phone}\n"
            f"Name: {data.customer_name}\n"
            f"Location: {data.zip_code}\n"
            f"Action: Call immediately."
        )
        
        try:
            message = twilio_client.messages.create(
                body=sms_body,
                from_=TWILIO_FROM_NUMBER,
                to=PLUMBER_CELL
            )
            return {"status": "success", "message": "Dispatcher alerted."}
        except Exception as e:
            print(f"Twilio Error: {e}")
            # Return success to the AI so the call doesn't drop, even if SMS fails internally
            return {"status": "error", "message": "Logged, but SMS failed."}
    
    else:
        return {"status": "logged", "message": "Routine issue logged."}

@app.post("/book-routine")
async def book_routine(data: BookingRequest):
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
