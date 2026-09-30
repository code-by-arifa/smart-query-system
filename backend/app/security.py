import os
from datetime import datetime, timedelta, timezone

import jwt  # type: ignore[import-not-found]
from dotenv import load_dotenv  # type: ignore[import-not-found]
from fastapi import Depends, HTTPException  # type: ignore[import-not-found]
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer  # type: ignore[import-not-found]

load_dotenv()

bearer = HTTPBearer()
SECRET = os.getenv("JWT_SECRET")
if not SECRET or len(SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be set to a random value of at least 32 characters.")

def issue_session(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=8)}, SECRET, algorithm="HS256")


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        return jwt.decode(credentials.credentials, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc
