from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException
from jose import JWTError, jwt

from app.config import get_settings
from app.models.schemas import RegisterRequest, RegisterResponse, UserInfo

router = APIRouter(prefix="/api", tags=["auth"])

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

_DB_DIR = Path(__file__).resolve().parents[1].parent / "data"
_DB_PATH = _DB_DIR / "users.db"

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_HOURS = 24


async def _get_db() -> aiosqlite.Connection:
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(_DB_PATH))
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            company TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    await db.commit()
    return db


def _create_token(user_id: str, email: str) -> str:
    settings = get_settings()
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=_JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

async def get_current_user(authorization: str = Header(...)) -> UserInfo:
    """Extract and validate the JWT from the Authorization Bearer header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    payload = _decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT name, email, company FROM users WHERE id = ?", (user_id,)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    if row is None:
        raise HTTPException(status_code=401, detail="User not found")

    return UserInfo(name=row[0], email=row[1], company=row[2])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=RegisterResponse)
async def register(body: RegisterRequest) -> RegisterResponse:
    db = await _get_db()
    try:
        # Check if user already exists by email
        cursor = await db.execute(
            "SELECT id FROM users WHERE email = ?", (body.email,)
        )
        existing = await cursor.fetchone()

        if existing:
            user_id = existing[0]
        else:
            user_id = uuid.uuid4().hex
            await db.execute(
                "INSERT INTO users (id, name, email, company, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    user_id, body.name, body.email,
                    body.company, datetime.now(timezone.utc).isoformat(),
                ),
            )
            await db.commit()
    finally:
        await db.close()

    token = _create_token(user_id, body.email)
    return RegisterResponse(session_id=user_id, token=token)


@router.get("/session", response_model=UserInfo)
async def session(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    return user
