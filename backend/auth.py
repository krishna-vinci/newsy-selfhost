"""
Authentication and user account endpoints for Newsy.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import pytz
from fastapi import APIRouter, HTTPException, Path, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend import database
from backend.config import Config
from backend.timezone_catalog import DEFAULT_TIMEZONE, normalize_timezone

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

JWT_ALGORITHM = "HS256"
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,31}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RESERVED_USERNAMES = {
    "api",
    "auth",
    "bootstrap",
    "feeds",
    "login",
    "logout",
    "newsy",
    "reports",
    "settings",
    "signup",
}
PUBLIC_API_ENDPOINTS = {
    ("GET", "/api/auth/config"),
    ("GET", "/api/auth/providers"),
    ("GET", "/api/timezones"),
    ("POST", "/api/auth/sign-in"),
    ("POST", "/api/auth/refresh"),
    ("POST", "/api/auth/sign-out"),
    ("POST", "/api/users"),
    ("POST", "/api/users/bootstrap"),
}


class AuthConfigResponse(BaseModel):
    bootstrap_required: bool
    allow_public_signup: bool


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=12, max_length=128)
    timezone: str | None = Field(default=None, max_length=128)


class SignInRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class ApiTokenCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)

    def normalized_name(self) -> str:
        return self.name.strip()


class ApiTokenResponse(BaseModel):
    id: int
    name: str
    created_at: str
    last_used_at: str | None = None
    expires_at: str | None = None
    revoked_at: str | None = None


class ApiTokenCreateResponse(ApiTokenResponse):
    token: str


class ExpiredTokenError(Exception):
    pass


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_secret_bytes() -> bytes:
    return Config.AUTH_SECRET_KEY.encode("utf-8")


def _hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _hash_api_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64
    )
    return f"scrypt$16384$8$1${_b64url_encode(salt)}${_b64url_encode(digest)}"


_DUMMY_PASSWORD_HASH = _hash_password("newsy-auth-dummy-password")


def _verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        password_hash = _DUMMY_PASSWORD_HASH

    try:
        algorithm, n_value, r_value, p_value, salt_b64, digest_b64 = (
            password_hash.split("$", 5)
        )
        if algorithm != "scrypt":
            return False

        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_b64url_decode(salt_b64),
            n=int(n_value),
            r=int(r_value),
            p=int(p_value),
            dklen=len(_b64url_decode(digest_b64)),
        )
        return hmac.compare_digest(digest, _b64url_decode(digest_b64))
    except Exception:
        # Preserve a constant-ish path for bad/missing hashes.
        hmac.compare_digest(
            _b64url_decode(_DUMMY_PASSWORD_HASH.split("$", 5)[-1]),
            _b64url_decode(_DUMMY_PASSWORD_HASH.split("$", 5)[-1]),
        )
        return False


def _create_access_token(*, user_id: int, role: str, session_id: int) -> str:
    now = _utcnow()
    payload = {
        "sub": str(user_id),
        "role": role,
        "sid": session_id,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(minutes=Config.AUTH_ACCESS_TTL_MINUTES)).timestamp()
        ),
    }
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    encoded_header = _b64url_encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    encoded_payload = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = hmac.new(_get_secret_bytes(), signing_input, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64url_encode(signature)}"


def _decode_access_token(token: str) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".", 2)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token"
        ) from exc

    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    expected_signature = hmac.new(
        _get_secret_bytes(), signing_input, hashlib.sha256
    ).digest()
    try:
        actual_signature = _b64url_decode(encoded_signature)
        payload = json.loads(_b64url_decode(encoded_payload))
    except (ValueError, json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token"
        ) from exc

    if not hmac.compare_digest(expected_signature, actual_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token"
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token"
        )

    if int(payload.get("exp", 0)) <= int(_utcnow().timestamp()):
        raise ExpiredTokenError()

    return payload


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_timezone_value(timezone_name: str | None) -> str:
    if not timezone_name:
        return DEFAULT_TIMEZONE

    try:
        pytz.timezone(timezone_name)
    except pytz.UnknownTimeZoneError as exc:
        raise HTTPException(status_code=400, detail="Invalid timezone value") from exc
    return timezone_name


def _validate_new_user_payload(payload: UserCreateRequest) -> tuple[str, str, str, str]:
    username = _normalize_username(payload.username)
    email = _normalize_email(payload.email)
    password = payload.password
    timezone_name = _validate_timezone_value(payload.timezone)

    if not USERNAME_PATTERN.fullmatch(username):
        raise HTTPException(
            status_code=400,
            detail="Username must be 3-32 characters and use letters, numbers, dots, dashes, or underscores",
        )
    if username in RESERVED_USERNAMES:
        raise HTTPException(status_code=400, detail="That username is reserved")
    if not EMAIL_PATTERN.fullmatch(email):
        raise HTTPException(
            status_code=400, detail="Please provide a valid email address"
        )
    if len(password) < 12:
        raise HTTPException(
            status_code=400, detail="Password must be at least 12 characters long"
        )

    return username, email, password, timezone_name


def _serialize_user(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
        "is_active": row["is_active"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "last_login_at": row["last_login_at"].isoformat()
        if row["last_login_at"]
        else None,
    }


def _serialize_api_token(row: Any) -> ApiTokenResponse:
    return ApiTokenResponse(
        id=row["id"],
        name=row["name"],
        created_at=row["created_at"].isoformat(),
        last_used_at=row["last_used_at"].isoformat() if row["last_used_at"] else None,
        expires_at=row["expires_at"].isoformat() if row["expires_at"] else None,
        revoked_at=row["revoked_at"].isoformat() if row["revoked_at"] else None,
    )


def _get_request_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


def _set_no_store_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def set_auth_cookies(
    response: Response, *, access_token: str, refresh_token: str | None = None
) -> None:
    access_max_age = Config.AUTH_ACCESS_TTL_MINUTES * 60
    refresh_max_age = Config.AUTH_REFRESH_TTL_DAYS * 24 * 60 * 60

    response.set_cookie(
        key=Config.AUTH_ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=Config.AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
        max_age=access_max_age,
    )

    if refresh_token is not None:
        response.set_cookie(
            key=Config.AUTH_REFRESH_COOKIE_NAME,
            value=refresh_token,
            httponly=True,
            secure=Config.AUTH_COOKIE_SECURE,
            samesite="lax",
            path="/",
            max_age=refresh_max_age,
        )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(Config.AUTH_ACCESS_COOKIE_NAME, path="/", samesite="lax")
    response.delete_cookie(Config.AUTH_REFRESH_COOKIE_NAME, path="/", samesite="lax")


async def _ensure_user_preferences(
    conn: Any, user_id: int, timezone_name: str = DEFAULT_TIMEZONE
) -> None:
    await conn.execute(
        """
        INSERT INTO user_preferences (user_id, timezone, default_view)
        VALUES ($1, $2, 'card')
        ON CONFLICT (user_id) DO NOTHING
        """,
        user_id,
        normalize_timezone(timezone_name, fallback=DEFAULT_TIMEZONE),
    )


async def _backfill_legacy_data_for_user(conn: Any, user_id: int) -> None:
    await database.migrate_legacy_user_owned_data(conn)

    legacy_timezone = await conn.fetchval(
        "SELECT value FROM user_settings WHERE key = 'timezone'"
    )
    legacy_default_view = await conn.fetchval(
        "SELECT value FROM user_settings WHERE key = 'default_view'"
    )

    await conn.execute(
        """
        UPDATE user_preferences
        SET timezone = COALESCE($2, timezone),
            default_view = CASE WHEN $3 IN ('card', 'headline', 'column') THEN $3 ELSE default_view END,
            updated_at = NOW()
        WHERE user_id = $1
        """,
        user_id,
        legacy_timezone,
        legacy_default_view,
    )

    legacy_owner_user_id = await database.get_legacy_owner_user_id(conn)
    if legacy_owner_user_id == user_id:
        legacy_rows = await conn.fetch(
            "SELECT article_link, is_read, read_at FROM user_article_status"
        )
        for row in legacy_rows:
            article_id = await conn.fetchval(
                "SELECT id FROM articles WHERE user_id = $1 AND link = $2 LIMIT 1",
                user_id,
                row["article_link"],
            )
            await conn.execute(
                """
                INSERT INTO user_article_state (user_id, article_id, article_link, is_read, read_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id, article_link)
                DO UPDATE SET article_id = EXCLUDED.article_id, is_read = EXCLUDED.is_read, read_at = EXCLUDED.read_at
                """,
                user_id,
                article_id,
                row["article_link"],
                row["is_read"],
                row["read_at"],
            )

    await database.populate_default_feeds_for_user(conn, user_id)


async def _create_refresh_session(
    conn: Any, *, user_id: int, request: Request
) -> tuple[int, str]:
    refresh_token = secrets.token_urlsafe(48)
    refresh_hash = _hash_refresh_token(refresh_token)
    expires_at = _utcnow() + timedelta(days=Config.AUTH_REFRESH_TTL_DAYS)
    session_id = await conn.fetchval(
        """
        INSERT INTO refresh_sessions (
            user_id,
            refresh_token_hash,
            expires_at,
            last_seen_at,
            ip_address,
            user_agent,
            device_label
        )
        VALUES ($1, $2, $3, NOW(), $4, $5, $6)
        RETURNING id
        """,
        user_id,
        refresh_hash,
        expires_at,
        _get_request_ip(request),
        request.headers.get("user-agent"),
        request.headers.get("x-device-label") or "browser",
    )
    return session_id, refresh_token


async def _issue_auth_response(
    conn: Any, *, user_row: Any, request: Request
) -> JSONResponse:
    session_id, refresh_token = await _create_refresh_session(
        conn, user_id=user_row["id"], request=request
    )
    access_token = _create_access_token(
        user_id=user_row["id"], role=user_row["role"], session_id=session_id
    )
    response = JSONResponse(
        {
            "user": _serialize_user(user_row),
            "expires_in": Config.AUTH_ACCESS_TTL_MINUTES * 60,
        }
    )
    set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    _set_no_store_headers(response)
    return response


async def _get_user_by_id(conn: Any, user_id: int) -> Any:
    return await conn.fetchrow(
        """
        SELECT id, username, email, role, is_active, created_at, last_login_at
        FROM users
        WHERE id = $1
        """,
        user_id,
    )


async def _get_user_by_identifier(conn: Any, identifier: str) -> Any:
    normalized = identifier.strip().lower()
    return await conn.fetchrow(
        """
        SELECT id, username, email, password_hash, role, is_active, created_at, last_login_at
        FROM users
        WHERE LOWER(username) = $1 OR LOWER(email) = $1
        LIMIT 1
        """,
        normalized,
    )


def _is_session_active(session_row: Any) -> bool:
    return bool(
        session_row
        and session_row["revoked_at"] is None
        and session_row["expires_at"] > _utcnow()
    )


async def authenticate_request(
    request: Request, *, touch_api_token_last_used: bool = True
) -> dict[str, Any] | None:
    authorization = request.headers.get("authorization")
    bearer_token = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer_token = authorization.split(" ", 1)[1].strip()

    if bearer_token:
        user = await _authenticate_access_token(bearer_token)
        if user:
            request.state.auth_method = "access_token"
            return user
        user = await _authenticate_api_token(
            bearer_token, touch_last_used=touch_api_token_last_used
        )
        if user:
            request.state.auth_method = "api_token"
        return user

    token = request.cookies.get(Config.AUTH_ACCESS_COOKIE_NAME)
    if not token:
        return None

    user = await _authenticate_access_token(token)
    if user:
        request.state.auth_method = "session_cookie"
    return user


async def _authenticate_access_token(token: str) -> dict[str, Any] | None:

    try:
        payload = _decode_access_token(token)
    except ExpiredTokenError:
        return None
    except HTTPException:
        return None

    try:
        user_id = int(payload["sub"])
        session_id = int(payload["sid"])
    except (KeyError, TypeError, ValueError):
        return None

    conn = await database.get_db_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.username, u.email, u.role, u.is_active, u.created_at, u.last_login_at,
                   rs.id AS session_id, rs.expires_at, rs.revoked_at
            FROM users u
            JOIN refresh_sessions rs ON rs.user_id = u.id
            WHERE u.id = $1 AND rs.id = $2
            LIMIT 1
            """,
            user_id,
            session_id,
        )
        if not row or not row["is_active"] or not _is_session_active(row):
            return None
        return _serialize_user(row)
    finally:
        await database.release_db_connection(conn)


async def _authenticate_api_token(
    token: str, *, touch_last_used: bool = True
) -> dict[str, Any] | None:
    conn = await database.get_db_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.username, u.email, u.role, u.is_active, u.created_at, u.last_login_at,
                   at.id AS api_token_id, at.expires_at, at.revoked_at
            FROM api_tokens at
            JOIN users u ON u.id = at.user_id
            WHERE at.token_hash = $1
            LIMIT 1
            """,
            _hash_api_token(token),
        )
        if not row or not row["is_active"]:
            return None
        if row["revoked_at"] is not None:
            return None
        if row["expires_at"] is not None and row["expires_at"] <= _utcnow():
            return None

        if touch_last_used:
            await conn.execute(
                "UPDATE api_tokens SET last_used_at = NOW() WHERE id = $1",
                row["api_token_id"],
            )
        return _serialize_user(row)
    finally:
        await database.release_db_connection(conn)


def require_request_user(request: Request) -> dict[str, Any]:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    return user


def require_session_user(request: Request) -> dict[str, Any]:
    user = require_request_user(request)
    if getattr(request.state, "auth_method", None) == "api_token":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API tokens cannot manage other API tokens",
        )
    return user


def is_public_api_path(path: str, method: str) -> bool:
    return (method.upper(), path) in PUBLIC_API_ENDPOINTS


def is_admin_only_api_request(path: str, method: str) -> bool:
    method = method.upper()

    if path.startswith("/api/backups"):
        return True
    if path == "/api/queue/status":
        return True
    return False


def validate_internal_api_key(request: Request) -> bool:
    configured_key = Config.INTERNAL_API_KEY
    provided_key = request.headers.get("x-internal-api-key")
    return bool(
        configured_key
        and provided_key
        and hmac.compare_digest(configured_key, provided_key)
    )


@router.get("/api/auth/config", response_model=AuthConfigResponse)
async def get_auth_config() -> AuthConfigResponse:
    conn = await database.get_db_connection()
    try:
        user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        return AuthConfigResponse(
            bootstrap_required=(user_count == 0),
            allow_public_signup=Config.AUTH_ALLOW_PUBLIC_SIGNUP,
        )
    finally:
        await database.release_db_connection(conn)


@router.get("/api/auth/providers")
async def get_auth_providers() -> JSONResponse:
    response = JSONResponse([])
    _set_no_store_headers(response)
    return response


@router.post("/api/users/bootstrap")
async def bootstrap_first_user(
    payload: UserCreateRequest, request: Request
) -> JSONResponse:
    username, email, password, timezone_name = _validate_new_user_payload(payload)
    conn = await database.get_db_connection()

    try:
        async with conn.transaction():
            user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
            if user_count > 0:
                raise HTTPException(
                    status_code=409, detail="Bootstrap is already complete"
                )

            user_row = await conn.fetchrow(
                """
                INSERT INTO users (username, email, password_hash, role, is_active, created_at, updated_at, last_login_at)
                VALUES ($1, $2, $3, 'admin', true, NOW(), NOW(), NOW())
                RETURNING id, username, email, role, is_active, created_at, last_login_at
                """,
                username,
                email,
                _hash_password(password),
            )
            await _ensure_user_preferences(conn, user_row["id"], timezone_name)
            await _backfill_legacy_data_for_user(conn, user_row["id"])
            return await _issue_auth_response(conn, user_row=user_row, request=request)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to bootstrap first user")
        if "idx_users_username_lower" in str(exc) or "username" in str(exc).lower():
            raise HTTPException(
                status_code=409, detail="That username is already taken"
            ) from exc
        if "idx_users_email_lower" in str(exc) or "email" in str(exc).lower():
            raise HTTPException(
                status_code=409, detail="That email is already in use"
            ) from exc
        raise HTTPException(
            status_code=500, detail="Failed to create bootstrap user"
        ) from exc
    finally:
        await database.release_db_connection(conn)


@router.post("/api/users")
async def create_user(payload: UserCreateRequest, request: Request) -> JSONResponse:
    username, email, password, timezone_name = _validate_new_user_payload(payload)

    if not Config.AUTH_ALLOW_PUBLIC_SIGNUP:
        raise HTTPException(status_code=403, detail="Public sign-up is disabled")

    conn = await database.get_db_connection()
    try:
        async with conn.transaction():
            user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
            if user_count == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Bootstrap must be completed before public sign-up",
                )

            user_row = await conn.fetchrow(
                """
                INSERT INTO users (username, email, password_hash, role, is_active, created_at, updated_at, last_login_at)
                VALUES ($1, $2, $3, 'user', true, NOW(), NOW(), NOW())
                RETURNING id, username, email, role, is_active, created_at, last_login_at
                """,
                username,
                email,
                _hash_password(password),
            )
            await _ensure_user_preferences(conn, user_row["id"], timezone_name)
            return await _issue_auth_response(conn, user_row=user_row, request=request)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to create user")
        if "idx_users_username_lower" in str(exc) or "username" in str(exc).lower():
            raise HTTPException(
                status_code=409, detail="That username is already taken"
            ) from exc
        if "idx_users_email_lower" in str(exc) or "email" in str(exc).lower():
            raise HTTPException(
                status_code=409, detail="That email is already in use"
            ) from exc
        raise HTTPException(status_code=500, detail="Failed to create user") from exc
    finally:
        await database.release_db_connection(conn)


@router.post("/api/auth/sign-in")
async def sign_in(payload: SignInRequest, request: Request) -> JSONResponse:
    conn = await database.get_db_connection()
    try:
        user_row = await _get_user_by_identifier(conn, payload.identifier)
        password_hash = user_row["password_hash"] if user_row else None
        password_valid = _verify_password(payload.password, password_hash)

        if not user_row or not password_valid or not user_row["is_active"]:
            raise HTTPException(
                status_code=401, detail="Invalid username/email or password"
            )

        await conn.execute(
            "UPDATE users SET last_login_at = NOW(), updated_at = NOW() WHERE id = $1",
            user_row["id"],
        )
        fresh_user_row = await _get_user_by_id(conn, user_row["id"])
        return await _issue_auth_response(
            conn, user_row=fresh_user_row, request=request
        )
    finally:
        await database.release_db_connection(conn)


@router.post("/api/auth/refresh")
async def refresh_session(request: Request) -> JSONResponse:
    refresh_token = request.cookies.get(Config.AUTH_REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token is missing")

    conn = await database.get_db_connection()
    try:
        async with conn.transaction():
            session_row = await conn.fetchrow(
                """
                SELECT rs.id, rs.user_id, rs.expires_at, rs.revoked_at,
                       u.id AS user_id_ref, u.username, u.email, u.role, u.is_active, u.created_at, u.last_login_at
                FROM refresh_sessions rs
                JOIN users u ON u.id = rs.user_id
                WHERE rs.refresh_token_hash = $1
                LIMIT 1
                """,
                _hash_refresh_token(refresh_token),
            )
            if (
                not session_row
                or session_row["revoked_at"] is not None
                or session_row["expires_at"] <= _utcnow()
                or not session_row["is_active"]
            ):
                raise HTTPException(
                    status_code=401, detail="Refresh token is invalid or expired"
                )

            await conn.execute(
                "UPDATE refresh_sessions SET revoked_at = NOW() WHERE id = $1",
                session_row["id"],
            )
            user_row = {
                "id": session_row["user_id_ref"],
                "username": session_row["username"],
                "email": session_row["email"],
                "role": session_row["role"],
                "is_active": session_row["is_active"],
                "created_at": session_row["created_at"],
                "last_login_at": session_row["last_login_at"],
            }
            response = await _issue_auth_response(
                conn, user_row=user_row, request=request
            )
            return response
    finally:
        await database.release_db_connection(conn)


@router.post("/api/auth/sign-out")
async def sign_out(request: Request) -> JSONResponse:
    refresh_token = request.cookies.get(Config.AUTH_REFRESH_COOKIE_NAME)
    response = JSONResponse({"message": "Signed out"})

    if refresh_token:
        conn = await database.get_db_connection()
        try:
            await conn.execute(
                "UPDATE refresh_sessions SET revoked_at = NOW() WHERE refresh_token_hash = $1 AND revoked_at IS NULL",
                _hash_refresh_token(refresh_token),
            )
        finally:
            await database.release_db_connection(conn)

    clear_auth_cookies(response)
    _set_no_store_headers(response)
    return response


@router.get("/api/auth/api-tokens", response_model=list[ApiTokenResponse])
async def list_api_tokens(request: Request) -> JSONResponse:
    user = require_session_user(request)
    conn = await database.get_db_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT id, name, created_at, last_used_at, expires_at, revoked_at
            FROM api_tokens
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user["id"],
        )
        response = JSONResponse(
            [_serialize_api_token(row).model_dump() for row in rows]
        )
        _set_no_store_headers(response)
        return response
    finally:
        await database.release_db_connection(conn)


@router.post("/api/auth/api-tokens", response_model=ApiTokenCreateResponse)
async def create_api_token(
    payload: ApiTokenCreateRequest, request: Request
) -> JSONResponse:
    user = require_session_user(request)
    token_name = payload.normalized_name()
    if not token_name:
        raise HTTPException(status_code=400, detail="API token name is required")

    token = f"nsy_{secrets.token_urlsafe(32)}"
    expires_at = (
        _utcnow() + timedelta(days=payload.expires_in_days)
        if payload.expires_in_days is not None
        else None
    )

    conn = await database.get_db_connection()
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO api_tokens (user_id, name, token_hash, expires_at)
            VALUES ($1, $2, $3, $4)
            RETURNING id, name, created_at, last_used_at, expires_at, revoked_at
            """,
            user["id"],
            token_name,
            _hash_api_token(token),
            expires_at,
        )
        response = JSONResponse(
            ApiTokenCreateResponse(
                **_serialize_api_token(row).model_dump(), token=token
            ).model_dump()
        )
        _set_no_store_headers(response)
        return response
    finally:
        await database.release_db_connection(conn)


@router.delete("/api/auth/api-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_token(request: Request, token_id: int = Path(..., ge=1)) -> Response:
    user = require_session_user(request)
    conn = await database.get_db_connection()
    try:
        result = await conn.execute(
            """
            UPDATE api_tokens
            SET revoked_at = NOW()
            WHERE id = $1 AND user_id = $2 AND revoked_at IS NULL
            """,
            token_id,
            user["id"],
        )
        updated_count = int(result.split()[-1]) if result else 0
        if updated_count == 0:
            existing = await conn.fetchval(
                "SELECT 1 FROM api_tokens WHERE id = $1 AND user_id = $2",
                token_id,
                user["id"],
            )
            if not existing:
                raise HTTPException(status_code=404, detail="API token not found")

        return Response(status_code=status.HTTP_204_NO_CONTENT)
    finally:
        await database.release_db_connection(conn)


@router.get("/api/auth/me")
async def get_current_user(request: Request) -> JSONResponse:
    user = await authenticate_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    response = JSONResponse(user)
    _set_no_store_headers(response)
    return response
