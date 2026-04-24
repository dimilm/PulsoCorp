from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, new_csrf_token
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookies(response: Response, access_token: str, csrf_token: str) -> None:
    """Write the auth + CSRF cookies with consistent security flags.

    `cookie_secure` defaults to True so deployments behind HTTPS get a Secure
    cookie out of the box; tests and local HTTP setups can opt out via env.
    The CSRF cookie is intentionally readable from JS (httponly=False) since
    the SPA needs to echo it back as `X-CSRF-Token` (double-submit pattern).
    """
    secure = settings.cookie_secure
    samesite = settings.cookie_samesite
    response.set_cookie(
        settings.auth_cookie_name,
        access_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        httponly=False,
        secure=secure,
        samesite=samesite,
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(settings.auth_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.get(User, payload.username)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.username)
    csrf_token = new_csrf_token()
    _set_session_cookies(response, token, csrf_token)
    return LoginResponse(username=user.username, role=user.role, csrf_token=csrf_token)


@router.post("/logout")
def logout(response: Response) -> dict:
    _clear_session_cookies(response)
    return {"ok": True}


@router.post("/refresh", response_model=LoginResponse)
def refresh(response: Response, user: User = Depends(get_current_user)) -> LoginResponse:
    token = create_access_token(user.username)
    csrf_token = new_csrf_token()
    _set_session_cookies(response, token, csrf_token)
    return LoginResponse(username=user.username, role=user.role, csrf_token=csrf_token)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> MeResponse:
    # GET /me must be a pure read. Rotating the CSRF token here would break
    # any in-flight requests on other tabs that already captured the previous
    # token. Token rotation is exclusive to /login and /refresh.
    return MeResponse(username=user.username, role=user.role)
