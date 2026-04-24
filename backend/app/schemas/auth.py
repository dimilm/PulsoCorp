from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    username: str
    role: str
    csrf_token: str


class MeResponse(BaseModel):
    username: str
    role: str
    # Tokens are only handed out on /login and /refresh now. The cookie itself
    # is the source of truth for in-flight requests.
    csrf_token: str | None = None
