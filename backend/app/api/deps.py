import hmac
import secrets

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User


def get_current_user(
    db: Session = Depends(get_db),
    access_cookie: str | None = Cookie(default=None, alias=settings.auth_cookie_name),
) -> User:
    if not access_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth cookie")
    payload = decode_token(access_cookie)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def csrf_guard(
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    csrf_cookie: str | None = Cookie(default=None, alias=settings.csrf_cookie_name),
) -> None:
    # Constant-time compare to avoid leaking the CSRF token via timing.
    if (
        not csrf_cookie
        or not csrf_header
        or not hmac.compare_digest(csrf_cookie, csrf_header)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)
