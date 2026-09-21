import reflex as rx

import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from app.api_runtime import (
    Depends,
    HTTPException,
    Query,
    Request,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Base

bearer = HTTPBearer(auto_error=False)
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=100000)]
PUBLIC_USER = (
    "id",
    "display_name",
    "role",
    "virtual_id",
    "institution_id",
    "organization",
    "department",
    "bio",
    "linkedin_url",
    "avatar_url",
    "created_at",
)


def now():
    return datetime.now(timezone.utc)


def fail(status: int, code: str, message: str):
    raise HTTPException(
        status_code=status, detail={"code": code, "message": message}
    )


def require(
    condition, message="You do not have permission to perform this action"
):
    if not condition:
        fail(403, "forbidden", message)


def transition(current: str, target: str, allowed: dict[str, set[str]]):
    if target not in allowed.get(current, set()):
        fail(
            409,
            "invalid_transition",
            f"Cannot transition from {current} to {target}",
        )


def serialize(value):
    if isinstance(value, dict):
        return {
            k: serialize(v)
            for k, v in value.items()
            if k
            not in {
                "password_hash",
                "token_digest",
                "storage_key",
                "proof_storage_key",
                "subject_hash",
            }
        }
    if isinstance(value, (list, tuple)):
        return [serialize(v) for v in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def result(value):
    return {"data": serialize(value)}


def public_user(user):
    return {k: user[k] for k in PUBLIC_USER if k in user}


async def rows(db, sql, params=None):
    return [
        dict(r)
        for r in (await db.execute(text(sql), params or {})).mappings().all()
    ]


async def one(db, sql, params=None, required=True):
    row = (await db.execute(text(sql), params or {})).mappings().first()
    if row is None and required:
        fail(404, "not_found", "Resource not found")
    return dict(row) if row else None


def columns(table: str):
    return ", ".join(Base.metadata.tables[table].c.keys())


async def get(db, table: str, identity: UUID, lock=False):
    suffix = " FOR UPDATE" if lock else ""
    return await one(
        db,
        f"SELECT {columns(table)} FROM {table} WHERE id=:id{suffix}",
        {"id": identity},
    )


async def insert(db, table: str, values: dict):
    assert table in Base.metadata.tables
    assert set(values).issubset(Base.metadata.tables[table].c.keys())
    names = ", ".join(values)
    binds = ", ".join(f":{k}" for k in values)
    return await one(
        db,
        f"INSERT INTO {table} ({names}) VALUES ({binds}) RETURNING {columns(table)}",
        values,
    )


async def update(db, table: str, identity: UUID, values: dict):
    assert table in Base.metadata.tables
    assert set(values).issubset(Base.metadata.tables[table].c.keys())
    assignments = ", ".join(f"{k}=:{k}" for k in values)
    return await one(
        db,
        f"UPDATE {table} SET {assignments}, updated_at=now() WHERE id=:_id RETURNING {columns(table)}",
        {**values, "_id": identity},
    )


async def page(db, sql, params, limit, offset):
    total = await one(
        db, f"SELECT count(*) AS total FROM ({sql}) AS counted", params
    )
    items = await rows(
        db,
        f"{sql} ORDER BY created_at DESC, id DESC LIMIT :limit OFFSET :offset",
        {**params, "limit": limit, "offset": offset},
    )
    return {
        "items": serialize(items),
        "total": total["total"],
        "limit": limit,
        "offset": offset,
    }


async def audit(db, actor, action, target=None, project=None):
    await insert(
        db,
        "api_audits",
        {"actor_id": actor, "action": action, "target_id": target},
    )
    if project:
        await insert(
            db,
            "project_activities",
            {
                "project_id": project,
                "actor_id": actor,
                "event_type": action,
                "description": action.replace(".", " "),
            },
        )


async def notify(db, recipient, actor, title, kind="system", project=None):
    if recipient != actor:
        await insert(
            db,
            "notifications",
            {
                "recipient_id": recipient,
                "actor_id": actor,
                "title": title,
                "kind": kind,
                "project_id": project,
            },
        )


async def notify_team(db, project, actor, title, kind="system"):
    await db.execute(
        text("""INSERT INTO notifications (recipient_id, actor_id, project_id, title, kind)
        SELECT m.user_id, :actor, p.id, :title, :kind FROM projects p
        JOIN team_memberships m ON m.team_id=p.team_id AND m.status='Member'
        WHERE p.id=:project AND m.user_id<>:actor"""),
        {"actor": actor, "project": project, "title": title, "kind": kind},
    )


async def transaction():
    try:
        async with rx.asession() as db:
            async with db.begin():
                yield db
    except IntegrityError as e:
        logging.exception(f"Error: {type(e).__name__}")
        fail(
            409,
            "conflict",
            "The operation conflicts with an existing record or validation rule",
        )
    except SQLAlchemyError as e:
        logging.exception(f"Error: {type(e).__name__}")
        fail(
            503,
            "database_unavailable",
            "The operation could not be completed; please retry",
        )


DB = Annotated[AsyncSession, Depends(transaction)]


async def authenticate(
    request: Request,
    db: DB,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer)
    ],
):
    if (
        not credentials
        or credentials.scheme.lower() != "bearer"
        or len(credentials.credentials) > 200
    ):
        fail(401, "unauthorized", "A valid bearer session is required")
    digest = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    user = await one(
        db,
        """SELECT u.id, u.email, u.display_name, u.role, u.virtual_id,
        u.institution_id, u.organization, u.department, u.bio, u.linkedin_url, u.avatar_url,
        u.created_at, s.id AS session_id FROM users u JOIN user_sessions s ON s.user_id=u.id
        WHERE s.token_digest=:digest AND s.revoked_at IS NULL AND s.expires_at>now()
        AND u.status='active' FOR SHARE OF u, s""",
        {"digest": digest},
        required=False,
    )
    if not user:
        fail(401, "unauthorized", "Session expired or invalid")
    request.state.actor_id = user["id"]
    return user


Actor = Annotated[dict, Depends(authenticate)]


async def project_access(
    db, identity, user, member=False, leader=False, faculty=False
):
    project = await get(db, "projects", identity, lock=True)
    team = await get(db, "teams", project["team_id"], lock=True)
    membership = await one(
        db,
        "SELECT id FROM team_memberships WHERE team_id=:team AND user_id=:user AND status='Member'",
        {"team": team["id"], "user": user["id"]},
        required=False,
    )
    assigned = await one(
        db,
        "SELECT id FROM mentor_assignments WHERE project_id=:project AND mentor_id=:user AND ended_at IS NULL",
        {"project": identity, "user": user["id"]},
        required=False,
    )
    is_faculty = (
        user["role"] == "faculty"
        and user["institution_id"] is not None
        and user["institution_id"] == project["institution_id"]
    )
    if leader:
        require(
            user["role"] == "student"
            and team["leader_id"] == user["id"]
            and membership
        )
    elif member:
        require(user["role"] == "student" and membership)
    elif faculty:
        require(is_faculty)
    else:
        require(
            membership
            or assigned
            or is_faculty
            or user["role"] in ("industry", "admin")
        )
    return project, team


async def active_student(db, identity):
    return await one(
        db,
        """SELECT u.id, u.institution_id, i.kind FROM users u JOIN institutions i ON i.id=u.institution_id
        WHERE u.id=:id AND u.role='student' AND u.status='active' AND i.is_active=true""",
        {"id": identity},
    )
