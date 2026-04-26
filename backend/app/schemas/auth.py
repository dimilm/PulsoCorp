from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    username: str
    role: str
    csrf_token: str


class MeResponse(BaseModel):
    """Returned by `GET /auth/me`.

    Tokens are only ever rotated on `/login` and `/refresh`; everything in
    flight reads the CSRF cookie directly. We deliberately do not expose
    the token here so a stale tab cannot resurrect itself with a fresh
    token via a GET (which is supposed to be safe / idempotent).
    """

    username: str
    role: str
