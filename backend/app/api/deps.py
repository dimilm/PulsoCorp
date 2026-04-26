import hmac
import secrets
from functools import lru_cache

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models.settings import AppSettings
from app.models.user import User
from app.providers.ai.base import AIProvider
from app.providers.market.base import MarketProvider
from app.providers.market.yfinance_provider import YFinanceProvider
from app.services.provider_factory import build_ai_provider


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


# ---------------------------------------------------------------------------
# Provider dependencies
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _default_market_provider() -> MarketProvider:
    """Singleton YFinance provider shared across requests.

    The provider is stateless and cheap to construct, but caching avoids
    redundant allocations on every endpoint hit and makes it trivial to
    swap via `app.dependency_overrides[get_market_provider]` in tests.
    """
    return YFinanceProvider()


def get_market_provider() -> MarketProvider:
    return _default_market_provider()


def get_ai_provider(db: Session = Depends(get_db)) -> AIProvider:
    """Resolve the currently configured AI provider per request.

    Reads `AppSettings` (provider/model/api-key) at request-time because the
    user can change those values via the Settings page; tests override this
    dependency through `app.dependency_overrides[get_ai_provider]`.
    """
    row = db.get(AppSettings, 1) or AppSettings(id=1)
    return build_ai_provider(row)
