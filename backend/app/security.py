import os
from datetime import datetime, timedelta, timezone

import jwt  # type: ignore[import-not-found]
from fastapi import Depends, HTTPException  # type: ignore[import-not-found]
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer  # type: ignore[import-not-found]

bearer = HTTPBearer()
SECRET = os.getenv("JWT_SECRET", "change-this-development-secret")


def issue_session(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=8)}, SECRET, algorithm="HS256")


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        return jwt.decode(credentials.credentials, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc
