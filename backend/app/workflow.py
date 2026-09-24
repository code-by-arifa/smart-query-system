"""Protected role-aware API used by all dashboard views."""
from datetime import datetime, timezone
from typing import Literal
import io

try:
    from fastapi import APIRouter, Depends, HTTPException  # pyright: ignore[reportMissingImports]
    from fastapi.responses import StreamingResponse  # pyright: ignore[reportMissingImports]
except ImportError:  # pragma: no cover
    class APIRouter:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def get(self, *args, **kwargs):
            del args, kwargs
            def decorator(func):
                return func
            return decorator

        def post(self, *args, **kwargs):
            del args, kwargs
            def decorator(func):
                return func
            return decorator

        def patch(self, *args, **kwargs):
            del args, kwargs
            def decorator(func):
                return func
            return decorator

        def delete(self, *args, **kwargs):
            del args, kwargs
            def decorator(func):
                return func
            return decorator

    def Depends(dependency=None):
        return dependency

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str | None = None):
            self.status_code = status_code
            self.detail = detail

    class StreamingResponse:
        def __init__(self, content, media_type=None, headers=None):
            self.body_iterator = content
            self.media_type = media_type
            self.headers = headers or {}

try:
    from fpdf import FPDF  # pyright: ignore[reportMissingImports]
except ImportError:  # pragma: no cover
    class FPDF:
        def __init__(self):
            self._lines = []

        def add_page(self):
            pass

        def set_font(self, *args, **kwargs):
            del args, kwargs

        def cell(self, *args, **kwargs):
            if len(args) > 2:
                self._lines.append(str(args[2]))

        def ln(self, *args, **kwargs):
            del args, kwargs

        def multi_cell(self, *args, **kwargs):
            if len(args) > 2:
                self._lines.append(str(args[2]))

        def output(self):
            return ("\n".join(self._lines)).encode()

try:
    from pydantic import BaseModel, EmailStr  # pyright: ignore[reportMissingImports]
except ImportError:  # pragma: no cover
    class BaseModel:
        def model_dump(self, *_args, **_kwargs):
            return self.__dict__.copy()

    class EmailStr(str):
        pass

from .security import current_user

router = APIRouter(prefix="/api", tags=["dashboard"])

class Assignment(BaseModel): user_id: str
class StatusChange(BaseModel): status: Literal["Pending", "In Progress", "Resolved", "Escalated"]
class UserInput(BaseModel):
    name: str
    email: EmailStr
    role: Literal["Admin", "Instructor", "HOD", "Department"]
    dept_id: str | None = None
    is_active: bool = True
class ReassignInput(BaseModel):
    target: str
    comment: str


# These names are the routing departments defined by the application. Keeping
# the rule on the server prevents clients from assigning a role to a department
# that cannot receive that role's work.
FIXED_ROLE_DEPARTMENTS = {
    "Admin": "Admin",
    "HOD": "HOD",
    "Instructor": "Academic",
}
DEPARTMENT_STAFF_DEPARTMENTS = {"Finance", "Exam", "Registrar", "IT Support"}

def db():
    from .main import supabase
    return supabase

def user_from_claims(claims=Depends(current_user)):
    result = db().table("users").select("*").eq("user_id", claims["sub"]).execute()
    if not result.data or not result.data[0].get("is_active", True): raise HTTPException(401, "User is not active")
    return result.data[0]

def allow(*roles):
    def check(user=Depends(user_from_claims)):
        if user["role"] not in roles: raise HTTPException(403, "Permission denied")
        return user
    return check

def log(user_id, action): db().table("activity_log").insert({"user_id": user_id, "action": action}).execute()
def one(query_id):
    found = db().table("queries").select("*").eq("query_id", query_id).execute()
    if not found.data: raise HTTPException(404, "Query not found")
    return found.data[0]

def one_user(user_id):
    found = db().table("users").select("*").eq("user_id", user_id).execute()
    if not found.data:
        raise HTTPException(404, "User not found")
    return found.data[0]


def user_values(payload: UserInput):
    """Return validated staff data with the role's correct department set."""
    values = payload.model_dump()
    required_department = FIXED_ROLE_DEPARTMENTS.get(values["role"])

    if required_department:
        result = db().table("departments").select("dept_id").eq(
            "dept_name", required_department
        ).execute()
        if not result.data:
            raise HTTPException(
                500,
                f"Required department '{required_department}' is missing from the database",
            )
        values["dept_id"] = result.data[0]["dept_id"]
        return values

    if not values["dept_id"]:
        raise HTTPException(400, "A department is required for Department staff")

    result = db().table("departments").select("dept_name").eq(
        "dept_id", values["dept_id"]
    ).execute()
    if not result.data or result.data[0]["dept_name"] not in DEPARTMENT_STAFF_DEPARTMENTS:
        allowed = ", ".join(sorted(DEPARTMENT_STAFF_DEPARTMENTS))
        raise HTTPException(400, f"Department staff must belong to one of: {allowed}")
    return values

def can_view(row, user):
    if user["role"] == "Admin":
        return True
    if row.get("status") == "Escalated" and row.get("escalated_to_role") == user["role"]:
        return True
    if user["role"] in ("Department", "Instructor"):
        return row.get("dept_id") == user.get("dept_id")
    return False
@router.get("/auth/profile")
def profile(user=Depends(user_from_claims)): return user

@router.get("/queries")
def queries(status: str | None = None, search: str | None = None, user=Depends(user_from_claims)):
    rows = [q for q in db().table("queries").select("*").order("created_at", desc=True).execute().data if can_view(q, user)]
    if status: rows = [q for q in rows if q["status"] == status]
    if search:
        needle = search.lower(); rows = [q for q in rows if needle in q["subject"].lower() or needle in q["student_email"].lower()]
    return rows

@router.get("/query/{query_id}")
def query_detail(query_id: str, user=Depends(user_from_claims)):
    row = one(query_id)
    if not can_view(row, user): raise HTTPException(403, "Query is outside your scope")
    row["attachments"] = db().table("query_attachments").select("*").eq("query_id", query_id).execute().data
    row["classification_history"] = db().table("ai_classification_log").select("*").eq("query_id", query_id).execute().data
    row["reply_history"] = db().table("reply_history").select("*").eq("query_id", query_id).execute().data
    return row

@router.patch("/queries/{query_id}/status")
def change_status(query_id: str, payload: StatusChange, user=Depends(user_from_claims)):
    row = one(query_id)
    if not can_view(row, user): raise HTTPException(403, "Query is outside your scope")
    update = {"status": payload.status, "updated_at": datetime.now(timezone.utc).isoformat()}
    if payload.status == "Resolved": update["resolved_at"] = datetime.now(timezone.utc).isoformat()
    db().table("queries").update(update).eq("query_id", query_id).execute(); log(user["user_id"], f"Set {query_id} to {payload.status}")
    return one(query_id)

@router.post("/queries/{query_id}/assign")
def assign(query_id: str, payload: Assignment, user=Depends(allow("Admin", "HOD", "Department"))):
    row = one(query_id)
    if user["role"] == "Department" and row.get("dept_id") != user.get("dept_id"): raise HTTPException(403, "Outside your department")
    staff = db().table("users").select("*").eq("user_id", payload.user_id).execute()
    if not staff.data or staff.data[0].get("dept_id") != row.get("dept_id"): raise HTTPException(400, "Assignee must be in this department")
    db().table("queries").update({"assigned_to":payload.user_id, "status":"In Progress", "updated_at":datetime.now(timezone.utc).isoformat()}).eq("query_id", query_id).execute(); log(user["user_id"], f"Assigned {query_id}")
    return one(query_id)

@router.post("/queries/{query_id}/escalate")
def escalate(query_id: str, escalated_to_role: str = "HOD", user=Depends(user_from_claims)):
    if escalated_to_role not in ("HOD", "Admin"):
        raise HTTPException(400, "Invalid escalation target")
    row = one(query_id)
    if not can_view(row, user):
        raise HTTPException(403, "Query is outside your scope")
    db().table("queries").update({
        "status": "Escalated",
        "escalated_to_role": escalated_to_role,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("query_id", query_id).execute()
    db().table("escalation_record").insert({
        "query_id": query_id,
        "reason": f"Escalated by staff to {escalated_to_role}",
    }).execute()
    log(user["user_id"], f"Escalated {query_id} to {escalated_to_role}")
    return {"status": "Escalated", "escalated_to_role": escalated_to_role}

@router.post("/queries/{query_id}/return")
def return_to_staff(query_id: str, user=Depends(allow("Admin", "HOD"))):
    db().table("queries").update({"status":"In Progress", "updated_at":datetime.now(timezone.utc).isoformat()}).eq("query_id", query_id).execute(); log(user["user_id"], f"Returned {query_id}")
    return one(query_id)

@router.get("/dashboard/stats")
def stats(user=Depends(user_from_claims)):
    rows = [q for q in db().table("queries").select("*").execute().data if can_view(q, user)]
    today = datetime.now(timezone.utc).date().isoformat()
    return {
        "total": len(rows),
        "pending": sum(q["status"] == "Pending" for q in rows),
        "in_progress": sum(q["status"] == "In Progress" for q in rows),
        "escalated": sum(q["status"] == "Escalated" for q in rows),
        "reassigned": sum(q["status"] == "Reassigned by HOD" for q in rows),
        "resolved_today": sum(q["status"] == "Resolved" and str(q.get("resolved_at", "")).startswith(today) for q in rows),
    }

@router.get("/analytics")
def analytics(_user=Depends(allow("Admin", "HOD"))):
    if not _user:
        raise HTTPException(401, "User is not active")
    categories, statuses = {}, {}
    for q in db().table("queries").select("*").execute().data:
        categories[q.get("category") or "Unclassified"] = categories.get(q.get("category") or "Unclassified", 0) + 1; statuses[q["status"]] = statuses.get(q["status"], 0) + 1
    return {"by_category":categories, "by_status":statuses}

@router.get("/reassigned")
def reassigned(user=Depends(user_from_claims)):
    rows = [q for q in db().table("queries").select("*").execute().data
            if q.get("status") == "Reassigned by HOD" and can_view(q, user)]
    return rows

@router.get("/escalations")
def escalations(target: str | None = None, user=Depends(user_from_claims)):
    rows = [q for q in db().table("queries").select("*").eq("status", "Escalated").execute().data if can_view(q, user)]
    if target:
        rows = [q for q in rows if q.get("escalated_to_role") == target]
    return rows

@router.get("/users")
def users(_user=Depends(allow("Admin"))):
    if not _user:
        raise HTTPException(401, "User is not active")
    return db().table("users").select("*").execute().data

@router.post("/users")
def add_user(payload: UserInput, user=Depends(allow("Admin"))):
    item = db().table("users").insert(user_values(payload)).execute().data[0]; log(user["user_id"], f"Created user {payload.email}"); return item
@router.patch("/users/{user_id}")
def edit_user(user_id: str, payload: UserInput, user=Depends(allow("Admin"))):
    item = db().table("users").update(user_values(payload)).eq("user_id", user_id).execute().data[0]; log(user["user_id"], f"Updated user {user_id}"); return item
@router.post("/users/{user_id}/activate")
def activate_user(user_id: str, user=Depends(allow("Admin"))):
    db().table("users").update({"is_active": True}).eq("user_id", user_id).execute()
    log(user["user_id"], f"Activated user {user_id}")
    return {"status": "activated"}

@router.post("/users/{user_id}/deactivate")
def deactivate_user(user_id: str, user=Depends(allow("Admin"))):
    target = one_user(user_id)
    if target["role"] == "Admin":
        raise HTTPException(400, "Admin accounts cannot be deactivated.")
    db().table("users").update({"is_active": False}).eq("user_id", user_id).execute()
    log(user["user_id"], f"Deactivated user {user_id}")
    return {"status": "deactivated"}

@router.delete("/users/{user_id}")
def delete_user(user_id: str, user=Depends(allow("Admin"))):
    target = one_user(user_id)
    if target["role"] == "Admin":
        raise HTTPException(400, "Admin accounts cannot be deleted.")
    db().table("users").delete().eq("user_id", user_id).execute()
    log(user["user_id"], f"Deleted user {user_id}")
    return {"status": "deleted"}

class RoleAssignment(BaseModel):
    assigned_role: Literal["Department", "Instructor", "HOD", "Admin"]

class DeptAssignment(BaseModel):
    dept_id: str

@router.patch("/queries/{query_id}/assign-role")
def reassign_role(query_id: str, payload: RoleAssignment, user=Depends(allow("Admin"))):
    one(query_id)
    db().table("queries").update({"assigned_role": payload.assigned_role}).eq("query_id", query_id).execute()
    log(user["user_id"], f"Reassigned {query_id} to {payload.assigned_role}")
    return one(query_id)

@router.patch("/queries/{query_id}/assign-department")
def reroute_query(query_id: str, payload: DeptAssignment, user=Depends(allow("Admin"))):
    one(query_id)
    db().table("queries").update({
        "dept_id": payload.dept_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("query_id", query_id).execute()
    log(user["user_id"], f"Rerouted {query_id} to department {payload.dept_id}")
    return one(query_id)

@router.get("/departments")
def list_departments(user=Depends(user_from_claims)):
    return db().table("departments").select("*").execute().data

@router.get("/reports/daily")
def daily_report(user=Depends(allow("Admin", "HOD"))):
    today = datetime.now(timezone.utc).date().isoformat()
    rows = [q for q in db().table("queries").select("*").execute().data
            if str(q.get("created_at", ""))[:10] == today]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Daily Queries Report - {today}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(4)
    for q in rows:
        line = f"{q.get('subject', '')[:50]} | {q.get('student_email', '')} | {q.get('category') or 'N/A'} | {q.get('status')}"
        pdf.multi_cell(0, 7, line)
    pdf.ln(4)
    pdf.cell(0, 10, f"Total queries today: {len(rows)}", ln=True)

    buf = io.BytesIO(bytes(pdf.output()))
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="daily_report_{today}.pdf"'},
    )


@router.post("/queries/{query_id}/reassign")
def reassign_by_hod(query_id: str, payload: ReassignInput, user=Depends(allow("HOD"))):
    one(query_id)
    update = {
        "status": "Reassigned by HOD",
        "escalated_to_role": None,
        "hod_comment": payload.comment,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    update["dept_id"] = None if payload.target == "ADMIN" else payload.target
    db().table("queries").update(update).eq("query_id", query_id).execute()
    log(user["user_id"], f"Reassigned {query_id} to {payload.target}")
    return one(query_id)
