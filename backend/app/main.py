from fastapi import FastAPI, Depends, HTTPException  # type: ignore[reportMissingImports]
from fastapi.middleware.cors import CORSMiddleware  # type: ignore[reportMissingImports]
from pydantic import BaseModel, EmailStr  # type: ignore[reportMissingImports]
from dotenv import load_dotenv  # type: ignore[reportMissingImports]
from supabase import create_client  # type: ignore[reportMissingImports]
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from google import genai
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[reportMissingImports]
from datetime import datetime, timedelta, timezone
import os
import json
from .security import issue_session
from .workflow import allow, can_view, router as workflow_router, user_from_claims
from .gmail_service import unread_messages, mark_read, send_reply

load_dotenv()

app = FastAPI(title="Smart Query Routing API")
app.include_router(workflow_router)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
CATEGORIES = ["Fee", "Result", "Attendance", "Degree", "IT Support", "Enrollment", "Course/Academic", "General"]

CATEGORY_TO_DEPARTMENT = {
    "Fee": "Finance",
    "Result": "Exam",
    "Attendance": "Exam",
    "Degree": "Registrar",
    "IT Support": "IT Support",
    "Enrollment": "Registrar",
    "Course/Academic": "Academic",
    "General": "Admin",
}
CATEGORY_TO_ROLE = {
    "Fee": "Department",
    "Result": "Department",
    "Attendance": "Department",
    "Degree": "Department",
    "IT Support": "Department",
    "Enrollment": "Department",
    "Course/Academic": "Instructor",
    "General": "Admin",
}


def classify_query(subject: str, body: str) -> dict:
    prompt = f"""
    Classify this university student email into exactly one of these categories:
    {", ".join(CATEGORIES)}

    Subject: {subject}
    Body: {body}

    Respond ONLY with valid JSON in this exact format, no other text, no markdown:
    {{"category": "...", "confidence": 0.0}}
    """
    response = gemini_client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=prompt
    )
    text = response.text.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def generate_reply_draft(subject: str, body: str, category: str) -> str:
    prompt = f"""
    Write a short, polite, professional email reply from a university department
    to a student. The query category is "{category}".

    Student's subject: {subject}
    Student's message: {body}

    Write only the reply body text, no subject line, no placeholders like [Name].
    """
    response = gemini_client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=prompt
    )
    return response.text.strip()


def query_visible_to(query_id: str, user: dict) -> dict:
    """Return a query only when the signed-in staff member may access it."""
    result = supabase.table("queries").select("*").eq("query_id", query_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Query not found")
    query = result.data[0]
    if not can_view(query, user):
        raise HTTPException(status_code=403, detail="Query is outside your scope")
    return query


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

def check_for_escalations():
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    stuck = supabase.table("queries") \
        .select("*").eq("status", "Pending").lt("created_at", cutoff).execute()

    for q in stuck.data:
        supabase.table("queries").update({
            "status": "Escalated",
            "escalated_to_role": "HOD",
        }).eq("query_id", q["query_id"]).execute()

    print(f"Escalation check ran — {len(stuck.data)} quer(ies) escalated.")
def classify_and_route(query_id: str, subject: str, query_text: str):
    try:
        classification = classify_query(subject, query_text)
    except Exception as e:
        print("CLASSIFY ERROR:", e)
        classification = {"category": "General", "confidence": 0.0}

    supabase.table("queries").update({"category": classification["category"]}).eq("query_id", query_id).execute()
    supabase.table("ai_classification_log").insert({
        "query_id": query_id,
        "predicted_category": classification["category"],
        "confidence_score": classification["confidence"],
    }).execute()
    route_query_by_id(query_id)

def poll_gmail():
    """Create, classify and route one database query for every unread Gmail message."""
    try:
        for message in unread_messages():
            seen = supabase.table("queries").select("query_id").eq("gmail_message_id", message["gmail_message_id"]).execute()
            if seen.data:
                mark_read(message["gmail_message_id"])
                continue
            row = supabase.table("queries").insert({**message, "source": "gmail"}).execute().data[0]

            try:
                send_reply(
                    row["student_email"],
                    row["subject"],
                    "Thank you for contacting us. Your query has been received and is being reviewed. "
                    "You will receive a follow-up email once it has been resolved.",
                    row.get("gmail_thread_id"),
                )
            except Exception as e:
                print("Acknowledgment email failed:", e)

            classify_and_route(row["query_id"], row["subject"], row["query_text"])
            mark_read(message["gmail_message_id"])
    except Exception as exc:
        print(f"Gmail polling skipped/failed: {exc}")

# ... @app.get("/") and other endpoints follow below, unchanged ...

@app.get("/")
def health_check():
    return {"status": "running"}

@app.get("/api/query/{query_id}")
def get_query(query_id: str, user=Depends(user_from_claims)):
    return query_visible_to(query_id, user)

class QueryCreate(BaseModel):
    student_email: EmailStr
    subject: str
    query_text: str

class ReplySend(BaseModel):
    query_id: str
    body: str

@app.post("/api/query")
def create_query(payload: QueryCreate, _user=Depends(user_from_claims)):
    result = supabase.table("queries").insert(payload.model_dump()).execute()
    row = result.data[0]
    classify_and_route(row["query_id"], row["subject"], row["query_text"])
    return supabase.table("queries").select("*").eq("query_id", row["query_id"]).execute().data[0]

def verify_google_token(token: str):
    idinfo = id_token.verify_oauth2_token(
        token, grequests.Request(), os.getenv("GOOGLE_CLIENT_ID")
    )
    return idinfo["email"]


@app.post("/api/auth/login")
def login(payload: dict):
    try:
        email = verify_google_token(payload["token"])
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {str(e)}")

    user = supabase.table("users").select("*").eq("email", email).execute()
    if not user.data:
        raise HTTPException(status_code=403, detail="Not a registered staff member")

    if user.data[0].get("is_active") is False:
        raise HTTPException(status_code=403, detail="You have been deactivated by Admin.")

    access_token = issue_session(user.data[0]["user_id"])
    return {"user": user.data[0], "access_token": access_token}

@app.post("/api/query/classify")
def classify(query_id: str, user=Depends(user_from_claims)):
    q = query_visible_to(query_id, user)

    print("SUBJECT SENT TO AI:", q["subject"])
    print("BODY SENT TO AI:", q["query_text"])

    try:
        result = classify_query(q["subject"], q["query_text"])
    except Exception as e:
        print("CLASSIFY ERROR:", e)
        result = {"category": "General", "confidence": 0.0}

    supabase.table("queries").update({"category": result["category"]}) \
        .eq("query_id", query_id).execute()

    supabase.table("ai_classification_log").insert({
        "query_id": query_id,
        "predicted_category": result["category"],
        "confidence_score": result["confidence"],
    }).execute()

    return result
@app.post("/api/reply/generate")
def generate_reply(query_id: str, user=Depends(user_from_claims)):
    q = query_visible_to(query_id, user)

    try:
        draft = generate_reply_draft(q["subject"], q["query_text"], q.get("category", "General"))
    except Exception as e:
        print("REPLY GENERATION ERROR:", e)
        raise HTTPException(status_code=503, detail="AI reply generation unavailable, please try again")

    supabase.table("reply_history").insert({
        "query_id": query_id,
        "generated_reply": draft,
    }).execute()

    return {"draft": draft}

@app.post("/api/reply/send")
def send_approved_reply(payload: ReplySend, user=Depends(user_from_claims)):
    """Gmail delivery is available once GMAIL_TOKEN_JSON is configured."""
    query = query_visible_to(payload.query_id, user)
    now_utc = datetime.now(timezone.utc).isoformat()
    try:
        send_reply(query["student_email"], query["subject"], payload.body, query.get("gmail_thread_id"))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    supabase.table("reply_history").insert({"query_id": payload.query_id, "generated_reply": payload.body, "sent_time": now_utc}).execute()
    supabase.table("queries").update({"status": "Resolved", "resolved_at": now_utc}).eq("query_id", payload.query_id).execute()
    return {"status": "sent"}

def route_query_by_id(query_id: str):
    q = supabase.table("queries").select("*").eq("query_id", query_id).execute()
    if not q.data:
        raise HTTPException(status_code=404, detail="Query not found")
    q = q.data[0]

    dept_name = CATEGORY_TO_DEPARTMENT.get(q["category"], "Admin")
    dept = supabase.table("departments").select("*").eq("dept_name", dept_name).execute()
    if not dept.data:
        raise HTTPException(status_code=500, detail=f"Department '{dept_name}' not found in database")
    dept = dept.data[0]

    assigned_role = CATEGORY_TO_ROLE.get(q["category"], "HOD")

    supabase.table("queries").update({
        "dept_id": dept["dept_id"],
        "assigned_role": assigned_role,
    }).eq("query_id", query_id).execute()

    return {"routed_to": dept_name, "assigned_role": assigned_role}


@app.post("/api/query/route")
def route_query(query_id: str, user=Depends(user_from_claims)):
    query_visible_to(query_id, user)
    return route_query_by_id(query_id)

@app.post("/api/test/run-escalation-check")
def run_escalation_check_manually(_user=Depends(allow("Admin"))):
    check_for_escalations()
    return {"status": "escalation check completed"}
@app.get("/api/queries")
def list_queries(status: str = None, _user=Depends(user_from_claims)):
    query = supabase.table("queries").select("*")
    if status:
        query = query.eq("status", status)
    result = query.execute()
    return result.data

@app.get("/api/analytics/departments")
def department_workload(_user=Depends(allow("Admin", "HOD"))):
    queries = supabase.table("queries").select("dept_id").execute().data
    departments = supabase.table("departments").select("dept_id, dept_name").execute().data
    dept_names = {d["dept_id"]: d["dept_name"] for d in departments}

    counts = {}
    for q in queries:
        name = dept_names.get(q["dept_id"], "Not routed")
        counts[name] = counts.get(name, 0) + 1

    return counts
scheduler = BackgroundScheduler()
scheduler.add_job(check_for_escalations, "interval", hours=1)
if os.getenv("GMAIL_POLL_ENABLED", "false").lower() == "true":
    scheduler.add_job(poll_gmail, "interval", minutes=int(os.getenv("GMAIL_POLL_MINUTES", "3")))
scheduler.start()

@app.patch("/api/queries/{query_id}/assign-role")
def reassign_role(query_id: str, payload: dict, _user=Depends(allow("Admin"))):
    new_role = payload.get("assigned_role")
    if new_role not in ["Department", "Instructor", "HOD", "Admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    supabase.table("queries").update({"assigned_role": new_role}).eq("query_id", query_id).execute()
    return {"status": "reassigned", "assigned_role": new_role}
