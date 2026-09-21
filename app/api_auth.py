import reflex as rx

import asyncio
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta
from uuid import UUID

from app.api_runtime import APIRouter, Request
from sqlalchemy import text

from app.api_contracts import (
    Credentials,
    Registration,
    Profile,
    PasswordChange,
    UserStatus,
    InstitutionInput,
    Result,
    Page,
)
from app.api_core import (
    Actor,
    DB,
    Limit,
    Offset,
    audit,
    fail,
    get,
    insert,
    now,
    one,
    page,
    public_user,
    require,
    result,
    update,
)

router = APIRouter(prefix="/api/v1", tags=["Identity"])
PREFIXES = {
    "student": "STU",
    "faculty": "FAC",
    "industry": "IND",
    "mentor": "MEN",
    "admin": "ADM",
}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(32)
    derived = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=32768,
        r=8,
        p=1,
        dklen=64,
        maxmem=64 * 1024 * 1024,
    )
    return f"scrypt$32768$8$1${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        parts = (encoded or "").split("$")
        valid = len(parts) == 6 and parts[:4] == ["scrypt", "32768", "8", "1"]
        salt = bytes.fromhex(parts[4]) if valid else bytes(32)
        expected = bytes.fromhex(parts[5]) if valid else bytes(64)
        if len(salt) != 32 or len(expected) != 64:
            return False
        actual = hashlib.scrypt(
            password.encode(),
            salt=salt,
            n=32768,
            r=8,
            p=1,
            dklen=64,
            maxmem=64 * 1024 * 1024,
        )
        return valid and hmac.compare_digest(actual, expected)
    except (ValueError, TypeError) as e:
        logging.exception(f"Error: {type(e).__name__}")
        return False


async def throttle(request: Request, email: str):
    # Committed separately so failed authentication also consumes its allowance.
    address = request.client.host if request.client else "unknown"
    subjects = sorted(
        [
            hashlib.sha256(f"email:{email}".encode()).hexdigest(),
            hashlib.sha256(f"ip:{address}".encode()).hexdigest(),
        ]
    )
    try:
        async with rx.asession() as db:
            async with db.begin():
                for subject in subjects:
                    await db.execute(
                        text(
                            "SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"
                        ),
                        {"key": subject},
                    )
                    count = await one(
                        db,
                        "SELECT count(*) AS n FROM api_audits WHERE action='auth.attempt' AND subject_hash=:key AND created_at>now()-interval '15 minutes'",
                        {"key": subject},
                    )
                    if count["n"] >= 30:
                        fail(
                            429,
                            "rate_limited",
                            "Too many attempts; try again in 15 minutes",
                        )
                for subject in subjects:
                    await insert(
                        db,
                        "api_audits",
                        {"action": "auth.attempt", "subject_hash": subject},
                    )
    except Exception as e:
        from app.api_runtime import HTTPException

        if isinstance(e, HTTPException):
            raise
        logging.exception(f"Error: {type(e).__name__}")
        fail(503, "unavailable", "Authentication is temporarily unavailable")


async def create_user(db, body, creator=None):
    if body.role in ("student", "faculty"):
        require(body.institution_id is not None, "An institution is required")
    if body.institution_id:
        institution = await get(db, "institutions", body.institution_id)
        require(institution["is_active"], "Institution is inactive")
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:role, 0))"),
        {"role": f"virtual-id:{body.role}"},
    )
    sequence = await one(
        db,
        "SELECT COALESCE(max(virtual_id_sequence),0)+1 AS n FROM users WHERE role=:role",
        {"role": body.role},
    )
    year = now().year
    password_hash = await asyncio.to_thread(hash_password, body.password)
    user = await insert(
        db,
        "users",
        {
            "email": body.email,
            "password_hash": password_hash,
            "display_name": body.display_name,
            "role": body.role,
            "institution_id": body.institution_id,
            "organization": body.organization,
            "registered_by_id": creator,
            "status": "active",
            "password_changed_at": now(),
            "virtual_id_year": year,
            "virtual_id_sequence": sequence["n"],
            "virtual_id": f"{PREFIXES[body.role]}-{year}-{sequence['n']:04d}",
        },
    )
    await audit(db, creator or user["id"], "user.registered", user["id"])
    return user


async def session_response(db, user, request):
    token = secrets.token_urlsafe(48)
    expiry = now() + timedelta(hours=12)
    await insert(
        db,
        "user_sessions",
        {
            "user_id": user["id"],
            "token_digest": hashlib.sha256(token.encode()).hexdigest(),
            "expires_at": expiry,
            "last_seen_at": now(),
            "user_agent": request.headers.get("user-agent", "")[:512],
        },
    )
    await audit(db, user["id"], "session.created", user["id"])
    return result(
        {
            "access_token": token,
            "token_type": "bearer",
            "expires_at": expiry,
            "user": {**public_user(user), "email": user["email"]},
        }
    )


@router.post("/auth/register", response_model=Result, status_code=201)
async def register(body: Registration, request: Request, db: DB):
    await throttle(request, body.email)
    # Hold through user/session creation and transaction commit or rollback.
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": "auth:first-account-bootstrap"},
    )
    count = await one(db, "SELECT count(*) AS n FROM users")
    if count["n"] == 0:
        require(
            body.role == "admin", "The first account must be an administrator"
        )
    else:
        require(
            body.role == "student",
            "Privileged roles must be registered by an administrator",
        )
    user = await create_user(db, body)
    return await session_response(db, user, request)


@router.post("/auth/login", response_model=Result)
async def login(body: Credentials, request: Request, db: DB):
    await throttle(request, body.email)
    user = await one(
        db,
        "SELECT id, email, password_hash, display_name, role, virtual_id, institution_id, organization, department, bio, linkedin_url, avatar_url, created_at, status FROM users WHERE email=:email",
        {"email": body.email},
        required=False,
    )
    valid = await asyncio.to_thread(
        verify_password, body.password, user["password_hash"] if user else None
    )
    if not valid or not user or user["status"] != "active":
        fail(401, "invalid_credentials", "Email or password is incorrect")
    return await session_response(db, user, request)


@router.get("/auth/me", response_model=Result)
async def me(user: Actor):
    return result({**public_user(user), "email": user["email"]})


@router.post("/auth/logout", response_model=Result)
async def logout(db: DB, user: Actor):
    await update(db, "user_sessions", user["session_id"], {"revoked_at": now()})
    await audit(db, user["id"], "session.revoked", user["session_id"])
    return result({"logged_out": True})


@router.post("/auth/logout-all", response_model=Result)
async def logout_all(db: DB, user: Actor):
    await db.execute(
        text(
            "UPDATE user_sessions SET revoked_at=now(), updated_at=now() WHERE user_id=:id AND revoked_at IS NULL"
        ),
        {"id": user["id"]},
    )
    await audit(db, user["id"], "sessions.revoked", user["id"])
    return result({"logged_out": True})


@router.post("/auth/password", response_model=Result)
async def password(body: PasswordChange, db: DB, user: Actor):
    current = await get(db, "users", user["id"], lock=True)
    require(
        await asyncio.to_thread(
            verify_password, body.current_password, current["password_hash"]
        ),
        "Current password is incorrect",
    )
    hashed = await asyncio.to_thread(hash_password, body.new_password)
    await update(
        db,
        "users",
        user["id"],
        {"password_hash": hashed, "password_changed_at": now()},
    )
    return await logout_all(db, user)


@router.patch("/users/me", response_model=Result)
async def profile(body: Profile, db: DB, user: Actor):
    saved = await update(db, "users", user["id"], body.model_dump())
    await audit(db, user["id"], "user.profile_updated", user["id"])
    return result(public_user(saved))


@router.post("/users/me/deletion-request", response_model=Result)
async def deletion_request(db: DB, user: Actor):
    await update(db, "users", user["id"], {"deletion_requested_at": now()})
    await audit(db, user["id"], "user.deletion_requested", user["id"])
    return result({"requested": True})


@router.post("/users", response_model=Result, status_code=201)
async def add_user(body: Registration, db: DB, user: Actor):
    require(
        user["role"] == "admin"
        or (
            user["role"] == "faculty"
            and body.role == "student"
            and body.institution_id == user["institution_id"]
        )
    )
    return result(public_user(await create_user(db, body, user["id"])))


@router.patch("/users/{identity}/status", response_model=Result)
async def user_status(identity: UUID, body: UserStatus, db: DB, user: Actor):
    require(user["role"] == "admin" and identity != user["id"])
    target = await get(db, "users", identity, lock=True)
    require(target["status"] in ("active", "suspended"))
    saved = await update(db, "users", identity, {"status": body.status})
    if body.status == "suspended":
        await db.execute(
            text(
                "UPDATE user_sessions SET revoked_at=now(), updated_at=now() WHERE user_id=:id AND revoked_at IS NULL"
            ),
            {"id": identity},
        )
    await audit(db, user["id"], "user.status_changed", identity)
    return result(public_user(saved))


@router.get("/users", response_model=Page)
async def users(
    db: DB,
    user: Actor,
    q: str = "",
    role: str = "",
    institution_id: UUID | None = None,
    limit: Limit = 25,
    offset: Offset = 0,
):
    return await page(
        db,
        """SELECT id, display_name, role, virtual_id, institution_id, organization, created_at FROM users
        WHERE status='active' AND (:q='' OR display_name ILIKE :search OR virtual_id ILIKE :search)
        AND (:role='' OR role=:role) AND (CAST(:institution AS uuid) IS NULL OR institution_id=:institution)""",
        {
            "q": q[:200],
            "search": f"%{q[:200]}%",
            "role": role,
            "institution": institution_id,
        },
        limit,
        offset,
    )


@router.get("/users/{identity}", response_model=Result)
async def user_detail(identity: UUID, db: DB, user: Actor):
    target = await get(db, "users", identity)
    require(target["status"] == "active" or user["role"] == "admin")
    return result(public_user(target))


@router.get("/institutions", response_model=Page)
async def institutions(
    db: DB, q: str = "", limit: Limit = 25, offset: Offset = 0
):
    return await page(
        db,
        "SELECT id, name, kind, city, region, country_code, created_at FROM institutions WHERE is_active=true AND name ILIKE :q",
        {"q": f"%{q[:200]}%"},
        limit,
        offset,
    )


@router.post("/institutions", response_model=Result, status_code=201)
async def institution(body: InstitutionInput, db: DB, user: Actor):
    require(user["role"] == "admin")
    saved = await insert(db, "institutions", body.model_dump())
    await audit(db, user["id"], "institution.created", saved["id"])
    return result(saved)


@router.patch("/institutions/{identity}", response_model=Result)
async def edit_institution(
    identity: UUID, body: InstitutionInput, db: DB, user: Actor
):
    require(user["role"] == "admin")
    previous = await get(db, "institutions", identity, lock=True)
    require(
        previous["kind"] == body.kind,
        "Institution type cannot be changed after creation",
    )
    saved = await update(db, "institutions", identity, body.model_dump())
    await audit(db, user["id"], "institution.updated", identity)
    return result(saved)
