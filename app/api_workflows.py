import reflex as rx

import secrets
from uuid import UUID

from app.api_runtime import APIRouter
from sqlalchemy import text

from app.api_contracts import (
    ReviewInput,
    ReplyInput,
    FundingInput,
    FundingDecision,
    Verification,
    Shortlist,
    ShareInput,
    ChangeInput,
    ChangeDecision,
    MilestoneInput,
    MilestoneStatus,
    PanelInput,
    Result,
    Page,
)
from app.api_core import (
    Actor,
    DB,
    Limit,
    Offset,
    audit,
    columns,
    fail,
    get,
    insert,
    notify,
    notify_team,
    now,
    one,
    page,
    project_access,
    public_user,
    require,
    result,
    rows,
    transition,
    update,
)

router = APIRouter(prefix="/api/v1", tags=["Workflows"])


def review_next(status: str, action: str, role: str) -> str:
    if status == "resolved":
        fail(409, "invalid_transition", "Resolved reviews are read-only")
    if action == "comment":
        return status
    if action == "changes_done":
        require(role == "student")
        transition(status, "addressed", {"open": {"addressed"}})
        return "addressed"
    require(role == "industry")
    target = "open" if action == "request_changes" else "resolved"
    transition(
        status,
        target,
        {"open": {"resolved"}, "addressed": {"open", "resolved"}},
    )
    return target


@router.post(
    "/projects/{identity}/reviews", response_model=Result, status_code=201
)
async def add_review(identity: UUID, body: ReviewInput, db: DB, user: Actor):
    require(user["role"] == "industry")
    await project_access(db, identity, user)
    saved = await insert(
        db,
        "reviews",
        {
            **body.model_dump(),
            "project_id": identity,
            "reviewer_id": user["id"],
        },
    )
    await audit(db, user["id"], "review.created", saved["id"], identity)
    await notify_team(db, identity, user["id"], "New industry review", "review")
    return result(saved)


@router.get("/projects/{identity}/reviews", response_model=Page)
async def reviews(
    identity: UUID,
    db: DB,
    user: Actor,
    status: str = "",
    limit: Limit = 25,
    offset: Offset = 0,
):
    await project_access(db, identity, user)
    return await page(
        db,
        f"SELECT {columns('reviews')} FROM reviews WHERE project_id=:p AND (:status='' OR status=:status)",
        {"p": identity, "status": status},
        limit,
        offset,
    )


@router.get("/reviews", response_model=Page)
async def review_inbox(
    db: DB, user: Actor, status: str = "", limit: Limit = 25, offset: Offset = 0
):
    return await page(
        db,
        """SELECT r.id,r.project_id,r.reviewer_id,r.summary,r.status,r.created_at FROM reviews r JOIN projects p ON p.id=r.project_id
        WHERE (r.reviewer_id=:u OR EXISTS (SELECT 1 FROM team_memberships m WHERE m.team_id=p.team_id AND m.user_id=:u AND m.status='Member'))
        AND (:status='' OR r.status=:status)""",
        {"u": user["id"], "status": status},
        limit,
        offset,
    )


@router.get("/reviews/{identity}/replies", response_model=Page)
async def replies(
    identity: UUID, db: DB, user: Actor, limit: Limit = 25, offset: Offset = 0
):
    review = await get(db, "reviews", identity)
    await project_access(db, review["project_id"], user)
    return await page(
        db,
        "SELECT id,review_id,author_id,author_role,body,action,created_at FROM review_replies WHERE review_id=:r",
        {"r": identity},
        limit,
        offset,
    )


@router.post(
    "/reviews/{identity}/replies", response_model=Result, status_code=201
)
async def reply(identity: UUID, body: ReplyInput, db: DB, user: Actor):
    initial = await get(db, "reviews", identity)
    await project_access(
        db, initial["project_id"], user, member=user["role"] == "student"
    )
    review = await get(db, "reviews", identity, lock=True)
    require(
        user["role"] == "student"
        or (user["role"] == "industry" and user["id"] == review["reviewer_id"])
    )
    status = review_next(review["status"], body.action, user["role"])
    saved = await insert(
        db,
        "review_replies",
        {
            **body.model_dump(),
            "review_id": identity,
            "author_id": user["id"],
            "author_role": user["role"],
        },
    )
    await update(
        db,
        "reviews",
        identity,
        {
            "status": status,
            "resolved_at": now() if status == "resolved" else None,
            "resolved_by_id": user["id"] if status == "resolved" else None,
        },
    )
    await notify_team(
        db, review["project_id"], user["id"], "Review thread updated", "review"
    )
    await notify(
        db,
        review["reviewer_id"],
        user["id"],
        "Student replied to your review",
        "review",
        review["project_id"],
    )
    await audit(
        db, user["id"], "review.replied", saved["id"], review["project_id"]
    )
    return result({"reply": saved, "status": status})


@router.post(
    "/projects/{identity}/funding", response_model=Result, status_code=201
)
async def fund(identity: UUID, body: FundingInput, db: DB, user: Actor):
    require(user["role"] == "industry")
    project, team = await project_access(db, identity, user)
    require(team["status"] == "active", "Funding requires an active team")
    latest = await one(
        db,
        "SELECT status FROM funding_records WHERE project_id=:p ORDER BY created_at DESC,id DESC LIMIT 1",
        {"p": identity},
        required=False,
    )
    if latest and latest["status"] == "awaiting_leader":
        fail(
            409,
            "pending_funding",
            "The previous funding record is awaiting the leader",
        )
    record = await insert(
        db,
        "funding_records",
        {
            **body.model_dump(),
            "project_id": identity,
            "leader_id": team["leader_id"],
            "funder_id": user["id"],
        },
    )
    await notify_team(
        db,
        identity,
        user["id"],
        "Funding awaits team leader confirmation",
        "funding",
    )
    await audit(db, user["id"], "funding.submitted", record["id"], identity)
    return result(record)


@router.get("/funding", response_model=Page)
async def funding_inbox(
    db: DB,
    user: Actor,
    status: str = "",
    project_id: UUID | None = None,
    limit: Limit = 25,
    offset: Offset = 0,
):
    return await page(
        db,
        """SELECT f.id,f.project_id,f.leader_id,f.funder_id,f.amount_lakh,f.currency,f.txn_ref,f.proof_file_name,f.proof_url,
        f.status,f.decline_note,f.receipt_confirmed,f.responded_at,f.verification_status,f.verification_note,f.created_at
        FROM funding_records f JOIN projects p ON p.id=f.project_id WHERE
        (f.funder_id=:u OR :admin OR EXISTS (SELECT 1 FROM team_memberships m WHERE m.team_id=p.team_id AND m.user_id=:u AND m.status='Member'))
        AND (:status='' OR f.status=:status) AND (CAST(:p AS uuid) IS NULL OR f.project_id=:p)""",
        {
            "u": user["id"],
            "admin": user["role"] == "admin",
            "status": status,
            "p": project_id,
        },
        limit,
        offset,
    )


@router.post("/funding/{identity}/respond", response_model=Result)
async def funding_response(
    identity: UUID, body: FundingDecision, db: DB, user: Actor
):
    initial = await get(db, "funding_records", identity)
    project, team = await project_access(
        db, initial["project_id"], user, leader=True
    )
    record = await get(db, "funding_records", identity, lock=True)
    require(
        record["leader_id"] == user["id"],
        "Only the designated team leader may respond",
    )
    transition(
        record["status"],
        body.status,
        {"awaiting_leader": {"confirmed", "declined"}},
    )
    saved = await update(
        db,
        "funding_records",
        identity,
        {
            **body.model_dump(),
            "responded_by_id": user["id"],
            "responded_at": now(),
        },
    )
    await notify(
        db,
        record["funder_id"],
        user["id"],
        f"Funding {body.status}",
        "funding",
        project["id"],
    )
    await notify_team(
        db, project["id"], user["id"], f"Funding {body.status}", "funding"
    )
    await audit(db, user["id"], "funding.responded", identity, project["id"])
    return result(saved)


@router.post("/admin/funding/{identity}/verify", response_model=Result)
async def verify_funding(
    identity: UUID, body: Verification, db: DB, user: Actor
):
    require(user["role"] == "admin")
    initial = await get(db, "funding_records", identity)
    await project_access(db, initial["project_id"], user)
    record = await get(db, "funding_records", identity, lock=True)
    transition(
        record["verification_status"],
        body.status,
        {"unverified": {"verified", "rejected"}},
    )
    require(
        record["status"] == "confirmed",
        "Only leader-confirmed funding can be verified",
    )
    saved = await update(
        db,
        "funding_records",
        identity,
        {
            "verification_status": body.status,
            "verified_by_id": user["id"],
            "verified_at": now(),
            "verification_note": body.note,
        },
    )
    await audit(
        db, user["id"], "funding.verified", identity, record["project_id"]
    )
    await notify(
        db,
        record["funder_id"],
        user["id"],
        "Funding verification completed",
        "funding",
        record["project_id"],
    )
    await notify(
        db,
        record["leader_id"],
        user["id"],
        "Funding verification completed",
        "funding",
        record["project_id"],
    )
    return result(saved)


@router.put("/problems/{identity}/shortlist", response_model=Result)
async def shortlist(identity: UUID, body: Shortlist, db: DB, user: Actor):
    require(user["role"] == "faculty")
    problem = await get(db, "problems", identity)
    require(problem["status"] == "published")
    saved = await one(
        db,
        """INSERT INTO faculty_problem_shortlists (faculty_id,problem_id,seen_at,shortlisted_at)
        VALUES (:u,:p,now(),:shortlisted) ON CONFLICT (faculty_id,problem_id)
        DO UPDATE SET seen_at=now(),shortlisted_at=:shortlisted,updated_at=now() RETURNING id,problem_id,faculty_id,seen_at,shortlisted_at""",
        {
            "u": user["id"],
            "p": identity,
            "shortlisted": now() if body.shortlisted else None,
        },
    )
    await audit(db, user["id"], "problem.shortlist_changed", identity)
    return result(saved)


@router.get("/portfolio/share", response_model=Result)
async def get_share(db: DB, user: Actor):
    require(user["role"] == "student")
    share = await one(
        db,
        "SELECT id,slug,enabled,view_count,created_at FROM portfolio_shares WHERE owner_id=:u AND revoked_at IS NULL",
        {"u": user["id"]},
        required=False,
    )
    return result(share)


@router.put("/portfolio/share", response_model=Result)
async def share(body: ShareInput, db: DB, user: Actor):
    require(user["role"] == "student")
    await get(db, "users", user["id"], lock=True)
    current = await one(
        db,
        "SELECT id,slug FROM portfolio_shares WHERE owner_id=:u AND revoked_at IS NULL FOR UPDATE",
        {"u": user["id"]},
        required=False,
    )
    if current and body.regenerate:
        await update(
            db,
            "portfolio_shares",
            current["id"],
            {"enabled": False, "revoked_at": now()},
        )
        current = None
    if current:
        saved = await update(
            db, "portfolio_shares", current["id"], {"enabled": body.enabled}
        )
    else:
        saved = await insert(
            db,
            "portfolio_shares",
            {
                "owner_id": user["id"],
                "slug": secrets.token_hex(24),
                "enabled": body.enabled,
            },
        )
    await audit(db, user["id"], "portfolio.share_changed", saved["id"])
    return result(saved)


@router.get("/public/portfolios/{slug}", response_model=Result)
async def public_portfolio(
    slug: str, db: DB, limit: Limit = 25, offset: Offset = 0
):
    if len(slug) > 200:
        fail(404, "not_found", "Portfolio is not available")
    share = await one(
        db,
        """SELECT s.id,s.owner_id,u.display_name,u.bio,u.linkedin_url,u.avatar_url,i.name AS institution
        FROM portfolio_shares s JOIN users u ON u.id=s.owner_id LEFT JOIN institutions i ON i.id=u.institution_id
        WHERE s.slug=:slug AND s.enabled=true AND s.revoked_at IS NULL AND u.status='active' FOR SHARE OF s""",
        {"slug": slug},
        required=False,
    )
    if not share:
        fail(404, "not_found", "Portfolio is not available")
    projects = await page(
        db,
        """SELECT p.id,p.title,p.description,p.category,p.stage,p.progress,p.created_at,
        CASE WHEN (SELECT f.status FROM funding_records f WHERE f.project_id=p.id ORDER BY f.created_at DESC,f.id DESC LIMIT 1)='confirmed' THEN 'Funded' ELSE p.stage END AS display_stage
        FROM projects p WHERE p.status<>'archived' AND EXISTS (SELECT 1 FROM team_memberships m WHERE m.team_id=p.team_id AND m.user_id=:u AND m.status='Member')""",
        {"u": share["owner_id"]},
        limit,
        offset,
    )
    await db.execute(
        text(
            "UPDATE portfolio_shares SET view_count=view_count+1,updated_at=now() WHERE id=:id"
        ),
        {"id": share["id"]},
    )
    return result(
        {
            "profile": {
                k: share[k]
                for k in (
                    "display_name",
                    "bio",
                    "linkedin_url",
                    "avatar_url",
                    "institution",
                )
            },
            "projects": projects,
        }
    )


@router.get(
    "/public/portfolios/{slug}/projects/{identity}/proofs", response_model=Page
)
async def public_proofs(
    slug: str, identity: UUID, db: DB, limit: Limit = 25, offset: Offset = 0
):
    available = await one(
        db,
        """SELECT s.id FROM portfolio_shares s JOIN users u ON u.id=s.owner_id
        JOIN team_memberships m ON m.user_id=u.id AND m.status='Member' JOIN projects p ON p.team_id=m.team_id
        WHERE s.slug=:slug AND s.enabled=true AND s.revoked_at IS NULL AND u.status='active' AND p.id=:p AND p.status<>'archived' LIMIT 1""",
        {"slug": slug[:201], "p": identity},
        required=False,
    )
    if not available:
        fail(404, "not_found", "Portfolio is not available")
    return await page(
        db,
        """SELECT e.id,e.title,e.description,e.created_at,
        COALESCE((SELECT json_agg(json_build_object('kind',a.kind,'url',a.url,'name',a.name) ORDER BY a.position) FROM proof_attachments a WHERE a.entry_id=e.id),'[]') AS attachments
        FROM proof_entries e WHERE e.project_id=:p AND e.deleted_at IS NULL""",
        {"p": identity},
        limit,
        offset,
    )


@router.get("/notifications", response_model=Page)
async def notifications(
    db: DB,
    user: Actor,
    unread: bool = False,
    limit: Limit = 25,
    offset: Offset = 0,
):
    return await page(
        db,
        """SELECT id,kind,title,body,project_id,read_at,created_at FROM notifications
        WHERE recipient_id=:u AND (NOT :unread OR read_at IS NULL)""",
        {"u": user["id"], "unread": unread},
        limit,
        offset,
    )


@router.post("/notifications/read-all", response_model=Result)
async def read_all(db: DB, user: Actor):
    await db.execute(
        text(
            "UPDATE notifications SET read_at=now(),updated_at=now() WHERE recipient_id=:u AND read_at IS NULL"
        ),
        {"u": user["id"]},
    )
    return result({"read": True})


@router.post("/notifications/{identity}/read", response_model=Result)
async def read_notification(identity: UUID, db: DB, user: Actor):
    notification = await get(db, "notifications", identity)
    require(notification["recipient_id"] == user["id"])
    return result(
        await update(
            db,
            "notifications",
            identity,
            {"read_at": notification["read_at"] or now()},
        )
    )


@router.post("/institution-changes", response_model=Result, status_code=201)
async def change_institution(body: ChangeInput, db: DB, user: Actor):
    require(
        user["role"] == "student"
        and user["institution_id"]
        and user["institution_id"] != body.to_institution_id
    )
    institution = await get(db, "institutions", body.to_institution_id)
    faculty = await get(db, "users", body.faculty_id)
    require(
        institution["is_active"]
        and faculty["status"] == "active"
        and faculty["role"] == "faculty"
        and faculty["institution_id"] == body.to_institution_id,
        "Select active faculty at the destination institution",
    )
    saved = await insert(
        db,
        "institution_change_requests",
        {
            **body.model_dump(),
            "student_id": user["id"],
            "from_institution_id": user["institution_id"],
        },
    )
    await audit(db, user["id"], "institution_change.created", saved["id"])
    await notify(
        db,
        body.faculty_id,
        user["id"],
        "Institution change approval requested",
        "institution_change",
    )
    return result(saved)


@router.get("/institution-changes", response_model=Page)
async def changes(
    db: DB, user: Actor, status: str = "", limit: Limit = 25, offset: Offset = 0
):
    return await page(
        db,
        f"SELECT {columns('institution_change_requests')} FROM institution_change_requests WHERE (student_id=:u OR faculty_id=:u) AND (:status='' OR status=:status)",
        {"u": user["id"], "status": status},
        limit,
        offset,
    )


@router.post("/institution-changes/{identity}/respond", response_model=Result)
async def change_response(
    identity: UUID, body: ChangeDecision, db: DB, user: Actor
):
    change = await get(db, "institution_change_requests", identity, lock=True)
    require(
        user["role"] == "faculty"
        and change["faculty_id"] == user["id"]
        and user["institution_id"] == change["to_institution_id"]
    )
    transition(
        change["status"], body.status, {"pending": {"approved", "declined"}}
    )
    student = await get(db, "users", change["student_id"], lock=True)
    require(
        student["institution_id"] == change["from_institution_id"],
        "Student institution has changed",
    )
    if body.status == "approved":
        destination = await get(db, "institutions", change["to_institution_id"])
        require(destination["is_active"])
        # Do not silently change the formation basis of an existing team.
        active = await one(
            db,
            "SELECT id FROM team_memberships WHERE user_id=:u AND status IN ('Member','Invited') LIMIT 1",
            {"u": student["id"]},
            required=False,
        )
        if active:
            fail(
                409,
                "active_memberships",
                "Resolve existing team memberships before changing institution",
            )
        await update(
            db,
            "users",
            student["id"],
            {"institution_id": change["to_institution_id"]},
        )
    saved = await update(
        db,
        "institution_change_requests",
        identity,
        {
            "status": body.status,
            "response_note": body.note,
            "responded_by_id": user["id"],
            "responded_at": now(),
        },
    )
    await notify(
        db,
        student["id"],
        user["id"],
        f"Institution change {body.status}",
        "institution_change",
    )
    await audit(db, user["id"], "institution_change.responded", identity)
    return result(saved)


@router.post(
    "/projects/{identity}/milestones", response_model=Result, status_code=201
)
async def milestone(identity: UUID, body: MilestoneInput, db: DB, user: Actor):
    if user["role"] == "faculty":
        await project_access(db, identity, user, faculty=True)
    else:
        await project_access(db, identity, user, leader=True)
    saved = await insert(
        db,
        "milestones",
        {
            **body.model_dump(),
            "project_id": identity,
            "created_by_id": user["id"],
        },
    )
    await audit(db, user["id"], "milestone.created", saved["id"], identity)
    await notify_team(
        db, identity, user["id"], "Milestone created", "milestone"
    )
    return result(saved)


@router.get("/projects/{identity}/milestones", response_model=Page)
async def milestones(
    identity: UUID, db: DB, user: Actor, limit: Limit = 25, offset: Offset = 0
):
    await project_access(db, identity, user)
    return await page(
        db,
        f"SELECT {columns('milestones')} FROM milestones WHERE project_id=:p",
        {"p": identity},
        limit,
        offset,
    )


@router.post("/milestones/{identity}/status", response_model=Result)
async def milestone_status(
    identity: UUID, body: MilestoneStatus, db: DB, user: Actor
):
    initial = await get(db, "milestones", identity)
    project, team = await project_access(
        db, initial["project_id"], user, member=True
    )
    require(team["status"] == "active")
    milestone = await get(db, "milestones", identity, lock=True)
    transition(
        milestone["status"],
        body.status,
        {
            "pending": {"in_progress"},
            "in_progress": {"submitted"},
            "changes_requested": {"in_progress", "submitted"},
        },
    )
    saved = await update(
        db,
        "milestones",
        identity,
        {
            "status": body.status,
            "submitted_at": now() if body.status == "submitted" else None,
        },
    )
    await audit(
        db, user["id"], "milestone.status_changed", identity, project["id"]
    )
    await notify_team(
        db, project["id"], user["id"], "Milestone updated", "milestone"
    )
    return result(saved)


@router.post(
    "/projects/{identity}/panel-feedback",
    response_model=Result,
    status_code=201,
)
async def panel_feedback(identity: UUID, body: PanelInput, db: DB, user: Actor):
    await project_access(db, identity, user, faculty=True)
    if body.decision != "feedback" and not body.milestone_id:
        fail(
            422,
            "milestone_required",
            "A milestone is required for an approval or change request",
        )
    if body.milestone_id:
        milestone = await get(db, "milestones", body.milestone_id, lock=True)
        require(milestone["project_id"] == identity)
        if body.decision != "feedback":
            transition(
                milestone["status"],
                body.decision,
                {"submitted": {"approved", "changes_requested"}},
            )
            await update(
                db,
                "milestones",
                body.milestone_id,
                {
                    "status": body.decision,
                    "approved_by_id": user["id"]
                    if body.decision == "approved"
                    else None,
                    "approved_at": now()
                    if body.decision == "approved"
                    else None,
                },
            )
    saved = await insert(
        db,
        "review_panel_feedback",
        {**body.model_dump(), "project_id": identity, "faculty_id": user["id"]},
    )
    await audit(db, user["id"], "panel.feedback_created", saved["id"], identity)
    await notify_team(
        db,
        identity,
        user["id"],
        "Faculty review panel feedback received",
        "milestone",
    )
    return result(saved)


@router.get("/projects/{identity}/panel-feedback", response_model=Page)
async def feedback(
    identity: UUID, db: DB, user: Actor, limit: Limit = 25, offset: Offset = 0
):
    await project_access(db, identity, user)
    return await page(
        db,
        f"SELECT {columns('review_panel_feedback')} FROM review_panel_feedback WHERE project_id=:p",
        {"p": identity},
        limit,
        offset,
    )


@router.get("/csr/summary", response_model=Result)
async def csr(db: DB, user: Actor):
    require(user["role"] in ("industry", "admin"))
    summary = await one(
        db,
        """WITH eligible AS (
        SELECT f.project_id,f.amount_lakh,f.status FROM funding_records f JOIN projects p ON p.id=f.project_id
        JOIN problems b ON b.id=p.problem_id WHERE b.csr=true AND (f.funder_id=:u OR :admin)
        ), funded AS (SELECT DISTINCT project_id FROM eligible WHERE status='confirmed')
        SELECT (SELECT count(*) FROM funded) AS projects_funded,
        (SELECT COALESCE(sum(amount_lakh),0) FROM eligible WHERE status='confirmed') AS confirmed_amount_lakh,
        (SELECT COALESCE(sum(amount_lakh),0) FROM eligible WHERE status='awaiting_leader') AS awaiting_amount_lakh,
        (SELECT count(DISTINCT m.user_id) FROM funded f JOIN projects p ON p.id=f.project_id
            JOIN team_memberships m ON m.team_id=p.team_id WHERE m.status='Member') AS students_reached""",
        {"u": user["id"], "admin": user["role"] == "admin"},
    )
    return result(
        {**summary, "patents_incubated": None, "startups_spun_off": None}
    )


@router.get("/admin/audit", response_model=Page)
async def audit_log(
    db: DB, user: Actor, action: str = "", limit: Limit = 25, offset: Offset = 0
):
    require(user["role"] == "admin")
    return await page(
        db,
        "SELECT id,actor_id,action,target_id,created_at FROM api_audits WHERE action<>'auth.attempt' AND (:action='' OR action=:action)",
        {"action": action},
        limit,
        offset,
    )
