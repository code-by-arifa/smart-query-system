"""Gmail polling and reply delivery.  It is inert until GMAIL_TOKEN_JSON is set."""
import base64
import json
import os
from email.message import EmailMessage
from email.utils import parseaddr

try:
    from google.oauth2.credentials import Credentials  # type: ignore[import-not-found]
    from googleapiclient.discovery import build  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency may be absent at import time.
    Credentials = None
    build = None

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/gmail.send"]


def gmail_client():
    token_json = os.getenv("GMAIL_TOKEN_JSON")
    if not token_json:
        raise RuntimeError("GMAIL_TOKEN_JSON has not been configured")
    if Credentials is None or build is None:
        raise RuntimeError(
            "Google Gmail dependencies are not installed. Install google-auth and google-api-python-client."
        )
    credentials = Credentials.from_authorized_user_info(json.loads(token_json), GMAIL_SCOPES)
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _header(headers, name):
    return next((item["value"] for item in headers if item["name"].lower() == name.lower()), "")


def _plain_text(payload):
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"] + "===").decode("utf-8", "replace")
    for part in payload.get("parts", []):
        text = _plain_text(part)
        if text:
            return text
    return ""


BLOCKED_SENDERS = {"noreply-accounts@google.com"}

def unread_messages():
    service = gmail_client()
    items = service.users().messages().list(userId="me", q="is:unread -label:SENT", maxResults=25).execute().get("messages", [])
    for item in items:
        message = service.users().messages().get(userId="me", id=item["id"], format="full").execute()
        headers = message["payload"].get("headers", [])
        sender = parseaddr(_header(headers, "From"))

        if sender[1].lower() in BLOCKED_SENDERS:
            service.users().messages().modify(userId="me", id=message["id"], body={"removeLabelIds": ["UNREAD"]}).execute()
            continue

        yield {
            "gmail_message_id": message["id"], "gmail_thread_id": message["threadId"],
            "student_email": sender[1], "student_name": sender[0] or None,
            "subject": _header(headers, "Subject") or "No subject", "query_text": _plain_text(message["payload"]),
        }


def mark_read(message_id):
    gmail_client().users().messages().modify(userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}).execute()


def send_reply(to_email, subject, body, thread_id=None):
    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    message.set_content(body)
    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
    payload = {"raw": encoded}
    if thread_id:
        payload["threadId"] = thread_id
    return gmail_client().users().messages().send(userId="me", body=payload).execute()
