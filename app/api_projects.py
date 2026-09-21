import reflex as rx

from uuid import UUID
from app.api_runtime import APIRouter
from sqlalchemy import text, bindparam

from app.api_contracts import (
    ProblemInput,
    ProblemStatus,
    TeamProject,
    ProjectUpdate,
    Invite,
    Decision,
    MembershipDecision,
    ProofInput,
    ReviewInput,
    ViewClose,
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
    require,
    result,
    rows,
    transition,
    update,
)

router = APIRouter(prefix="/api/v1", tags=["Projects"])


async def composition(db, student_ids):
    query = text("""SELECT u.id, u.institution_id, i.kind FROM users u JOIN institutions i ON i.id=u.institution_id
        WHERE u.id IN :ids AND u.role='student' AND u.status='active' AND i.is_active=true ORDER BY u.id FOR SHARE OF u""").bindparams(
        bindparam("ids", expanding=True)
    )
    students = [
        dict(r)
        for r in (await db.execute(query, {"ids": student_ids})).mappings()
    ]
    require(
        len(students) == len(student_ids),
        "All team members must be active students with institutions",
    )
    return students


def formation_rule(students):
    schools = all(s["kind"] == "School" for s in students)
    same = len({s["institution_id"] for s in students}) == 1
    return ("faculty" if schools and same else "student"), schools


async def refresh_team(db, project, team):
    summary = await one(
        db,
        """SELECT count(*) AS n, bool_and(i.kind='School') AS school_only,
        count(DISTINCT u.institution_id) AS institutions FROM team_memberships m
        JOIN users u ON u.id=m.user_id JOIN institutions i ON i.id=u.institution_id
        WHERE m.team_id=:team AND m.status='Member' """,
        {"team": team["id"]},
    )
    mentor = await one(
        db,
        "SELECT id FROM mentor_assignments WHERE project_id=:project AND ended_at IS NULL",
        {"project": project["id"]},
        required=False,
    )
    ready = summary["n"] >= 2 and (not summary["school_only"] or mentor)
    if (
        team["formed_by"] == "student"
        and summary["school_only"]
        and summary["institutions"] == 1
    ):
        ready = False
    await update(
        db, "teams", team["id"], {"status": "active" if ready else "forming"}
    )


async def send_invite(db, project, team, actor, recipient, kind, reason):
    require(actor["id"] != recipient, "You cannot invite yourself")
    target = await get(db, "users", recipient)
    require(target["status"] == "active", "Recipient is not active")
    if kind == "member":
        require(target["role"] == "student")
        planned = await rows(
            db,
            "SELECT user_id FROM team_memberships WHERE team_id=:team AND status IN ('Invited','Member') LIMIT 51",
            {"team": team["id"]},
        )
        ids = [m["user_id"] for m in planned]
        require(
            recipient not in ids and len(ids) < 50,
            "Student is already on the team or the team is full",
        )
        members = await composition(db, [*ids, recipient])
        formed_by, school_only = formation_rule(members)
        require(
            formed_by == team["formed_by"],
            "Invitation would violate team formation rules",
        )
        if formed_by == "faculty":
            require(target["institution_id"] == team["institution_id"])
        if school_only:
            mentor = await one(
                db,
                "SELECT id FROM mentor_assignments WHERE project_id=:p AND ended_at IS NULL UNION ALL SELECT id FROM collaboration_requests WHERE project_id=:p AND kind='mentor' AND status='pending' LIMIT 1",
                {"p": project["id"]},
                required=False,
            )
            require(
                mentor, "Select a mentor before inviting a school-only team"
            )
        await db.execute(
            text("""INSERT INTO team_memberships (team_id, user_id, invited_by_id, status)
            VALUES (:team,:recipient,:actor,'Invited') ON CONFLICT (team_id,user_id)
            DO UPDATE SET status='Invited', invited_by_id=:actor, joined_at=NULL, ended_at=NULL, updated_at=now()"""),
            {"team": team["id"], "recipient": recipient, "actor": actor["id"]},
        )
    else:
        require(
            target["role"] in ("mentor", "industry", "faculty"),
            "Recipient must be a mentor, industry partner or faculty member",
        )
        existing = await one(
            db,
            "SELECT id FROM mentor_assignments WHERE project_id=:p AND ended_at IS NULL UNION ALL SELECT id FROM collaboration_requests WHERE project_id=:p AND kind='mentor' AND status='pending' LIMIT 1",
            {"p": project["id"]},
            required=False,
        )
        require(not existing, "A mentor is already assigned or requested")
    saved = await insert(
        db,
        "collaboration_requests",
        {
            "project_id": project["id"],
            "sender_id": actor["id"],
            "recipient_id": recipient,
            "kind": kind,
            "reason": reason,
        },
    )
    await notify(
        db,
        recipient,
        actor["id"],
        f"{kind.title()} invitation received",
        "collaboration",
        project["id"],
    )
    await audit(
        db, actor["id"], "collaboration.created", saved["id"], project["id"]
    )
    return saved


@router.get("/problems", response_model=Page)
async def problems(
    db: DB,
    user: Actor,
    q: str = "",
    domain: str = "",
    source: str = "",
    view: str = "all",
    limit: Limit = 25,
    offset: Offset = 0,
):
    if view in ("new", "shortlisted"):
        require(user["role"] == "faculty")
    return await page(
        db,
        """SELECT p.id, p.publisher_id, p.title, p.description, p.domain, p.source, p.csr, p.status,
        p.deadline, p.created_at, COALESCE((SELECT json_agg(t.label ORDER BY t.label) FROM problem_tags t WHERE t.problem_id=p.id),'[]') AS tags,
        s.seen_at, s.shortlisted_at FROM problems p LEFT JOIN faculty_problem_shortlists s ON s.problem_id=p.id AND s.faculty_id=:user
        WHERE (p.status='published' OR p.publisher_id=:user OR :admin)
        AND (p.title ILIKE :q OR p.description ILIKE :q) AND (:domain='' OR p.domain=:domain)
        AND (:source='' OR p.source=:source) AND (:view<>'csr' OR p.csr)
        AND (:view<>'new' OR s.seen_at IS NULL) AND (:view<>'shortlisted' OR s.shortlisted_at IS NOT NULL)""",
        {
            "user": user["id"],
            "admin": user["role"] == "admin",
            "q": f"%{q[:200]}%",
            "domain": domain,
            "source": source,
            "view": view,
        },
        limit,
        offset,
    )


@router.post("/problems", response_model=Result, status_code=201)
async def publish(body: ProblemInput, db: DB, user: Actor):
    require(user["role"] == "industry")
    problem = await insert(
        db,
        "problems",
        {
            **body.model_dump(exclude={"tags"}),
            "publisher_id": user["id"],
            "published_at": now() if body.status == "published" else None,
        },
    )
    if body.tags:
        await db.execute(
            text(
                "INSERT INTO problem_tags (problem_id,label) VALUES (:problem,:label)"
            ),
            [{"problem": problem["id"], "label": tag} for tag in body.tags],
        )
    await audit(db, user["id"], "problem.created", problem["id"])
    return result({**problem, "tags": body.tags})


@router.get("/problems/{identity}", response_model=Result)
async def problem_detail(identity: UUID, db: DB, user: Actor):
    problem = await get(db, "problems", identity)
    require(
        problem["status"] == "published"
        or problem["publisher_id"] == user["id"]
        or user["role"] == "admin"
    )
    tags = await rows(
        db,
        "SELECT label FROM problem_tags WHERE problem_id=:id ORDER BY label LIMIT 20",
        {"id": identity},
    )
    if user["role"] == "faculty":
        await db.execute(
            text("""INSERT INTO faculty_problem_shortlists (faculty_id,problem_id,seen_at) VALUES (:user,:id,now())
            ON CONFLICT (faculty_id,problem_id) DO UPDATE SET seen_at=now(), updated_at=now()"""),
            {"user": user["id"], "id": identity},
        )
    return result({**problem, "tags": [t["label"] for t in tags]})


@router.post("/problems/{identity}/status", response_model=Result)
async def problem_status(
    identity: UUID, body: ProblemStatus, db: DB, user: Actor
):
    problem = await get(db, "problems", identity, lock=True)
    require(
        user["role"] == "industry" and problem["publisher_id"] == user["id"]
    )
    transition(
        problem["status"],
        body.status,
        {
            "draft": {"published"},
            "published": {"closed", "archived"},
            "closed": {"archived"},
        },
    )
    saved = await update(
        db,
        "problems",
        identity,
        {
            "status": body.status,
            "published_at": problem["published_at"] or now(),
        },
    )
    await audit(db, user["id"], "problem.status_changed", identity)
    return result(saved)


@router.post("/projects", response_model=Result, status_code=201)
async def create_project(body: TeamProject, db: DB, user: Actor):
    require(user["role"] in ("student", "faculty"))
    require(body.leader_id in body.student_ids, "Leader must be a team member")
    students = await composition(db, body.student_ids)
    formed_by, school_only = formation_rule(students)
    require(
        user["role"] == formed_by,
        "Same-school teams are faculty-formed; all other teams are student-formed",
    )
    institution = next(
        s["institution_id"] for s in students if s["id"] == body.leader_id
    )
    if formed_by == "student":
        require(body.leader_id == user["id"], "The creator must be the leader")
    else:
        require(
            user["institution_id"] == institution,
            "Faculty may form teams only for their own school",
        )
    require(
        not school_only or body.mentor_id is not None,
        "School-only teams require a selected mentor",
    )
    if body.problem_id:
        problem = await get(db, "problems", body.problem_id)
        require(problem["status"] == "published", "Problem is not published")
    team = await insert(
        db,
        "teams",
        {
            "name": body.name,
            "leader_id": body.leader_id,
            "created_by_id": user["id"],
            "formed_by": formed_by,
            "institution_id": institution,
        },
    )
    project = await insert(
        db,
        "projects",
        {
            "team_id": team["id"],
            "problem_id": body.problem_id,
            "created_by_id": user["id"],
            "institution_id": institution,
            "title": body.title,
            "description": body.description,
            "category": body.category,
        },
    )
    await insert(
        db,
        "team_memberships",
        {
            "team_id": team["id"],
            "user_id": body.leader_id,
            "invited_by_id": user["id"],
            "status": "Member",
            "joined_at": now(),
        },
    )
    if body.mentor_id:
        await send_invite(
            db, project, team, user, body.mentor_id, "mentor", body.reason
        )
    # All initial members are validated as a set; sequential invites must not change that set's formation rule.
    for student in students:
        if student["id"] == body.leader_id:
            continue
        status = "Member" if formed_by == "faculty" else "Invited"
        await insert(
            db,
            "team_memberships",
            {
                "team_id": team["id"],
                "user_id": student["id"],
                "invited_by_id": user["id"],
                "status": status,
                "joined_at": now() if status == "Member" else None,
            },
        )
        if status == "Invited":
            await insert(
                db,
                "collaboration_requests",
                {
                    "project_id": project["id"],
                    "sender_id": user["id"],
                    "recipient_id": student["id"],
                    "kind": "member",
                    "reason": body.reason,
                },
            )
        await notify(
            db,
            student["id"],
            user["id"],
            "Team invitation received"
            if status == "Invited"
            else "You were added to a school team",
            "collaboration",
            project["id"],
        )
    await refresh_team(db, project, team)
    await audit(db, user["id"], "project.created", project["id"], project["id"])
    return result(project)


PROJECT_LIST = """SELECT p.id,p.team_id,p.problem_id,p.title,p.category,p.stage,p.status,p.progress,p.institution_id,p.created_at,
    t.name AS team_name,t.leader_id,t.formed_by,t.status AS team_status,
    CASE WHEN (SELECT f.status FROM funding_records f WHERE f.project_id=p.id ORDER BY f.created_at DESC,f.id DESC LIMIT 1)='confirmed' THEN 'Funded' ELSE p.stage END AS display_stage
    FROM projects p JOIN teams t ON t.id=p.team_id
    WHERE (EXISTS (SELECT 1 FROM team_memberships m WHERE m.team_id=t.id AND m.user_id=:user AND m.status IN ('Member','Invited'))
    OR :role IN ('industry','admin') OR (:role='faculty' AND p.institution_id=:institution)
    OR EXISTS (SELECT 1 FROM mentor_assignments a WHERE a.project_id=p.id AND a.mentor_id=:user AND a.ended_at IS NULL))"""


@router.get("/projects", response_model=Page)
async def projects(
    db: DB,
    user: Actor,
    q: str = "",
    stage: str = "",
    limit: Limit = 25,
    offset: Offset = 0,
):
    return await page(
        db,
        f"SELECT * FROM ({PROJECT_LIST}) AS accessible WHERE title ILIKE :q AND (:stage='' OR display_stage=:stage)",
        {
            "user": user["id"],
            "role": user["role"],
            "institution": user["institution_id"],
            "q": f"%{q[:200]}%",
            "stage": stage,
        },
        limit,
        offset,
    )


async def project_payload(db, project, team):
    members = await rows(
        db,
        """SELECT m.id,m.user_id,m.status,u.display_name,u.virtual_id,m.created_at FROM team_memberships m JOIN users u ON u.id=m.user_id
        WHERE m.team_id=:team ORDER BY m.created_at,m.id LIMIT 100""",
        {"team": team["id"]},
    )
    mentor = await one(
        db,
        "SELECT mentor_id FROM mentor_assignments WHERE project_id=:p AND ended_at IS NULL",
        {"p": project["id"]},
        required=False,
    )
    return {
        **project,
        "team": team,
        "memberships": members,
        "mentor_id": mentor["mentor_id"] if mentor else None,
    }


@router.get("/projects/{identity}", response_model=Result)
async def detail(identity: UUID, db: DB, user: Actor):
    project, team = await project_access(db, identity, user)
    require(
        user["role"] != "industry",
        "Industry must open a review visit to view project details",
    )
    return result(await project_payload(db, project, team))


@router.post(
    "/projects/{identity}/views", response_model=Result, status_code=201
)
async def open_view(identity: UUID, db: DB, user: Actor):
    require(user["role"] == "industry")
    project, team = await project_access(db, identity, user)
    pending = await one(
        db,
        """SELECT a.id,a.created_at FROM project_activities a WHERE a.project_id=:p AND a.actor_id=:u AND a.event_type='view.opened'
        AND NOT EXISTS (SELECT 1 FROM api_audits c WHERE c.target_id=a.id AND c.action='view.closed') ORDER BY a.created_at DESC LIMIT 1""",
        {"p": identity, "u": user["id"]},
        required=False,
    )
    if not pending:
        pending = await insert(
            db,
            "project_activities",
            {
                "project_id": identity,
                "actor_id": user["id"],
                "event_type": "view.opened",
                "description": "Review visit opened",
            },
        )
    return result(
        {
            "view_id": pending["id"],
            "review_required": True,
            "project": await project_payload(db, project, team),
        }
    )


@router.post("/projects/{identity}/views/close", response_model=Result)
async def close_view(identity: UUID, body: ViewClose, db: DB, user: Actor):
    require(user["role"] == "industry")
    await project_access(db, identity, user)
    visit = await get(db, "project_activities", body.view_id, lock=True)
    require(
        visit["project_id"] == identity
        and visit["actor_id"] == user["id"]
        and visit["event_type"] == "view.opened"
    )
    engaged = await one(
        db,
        """SELECT id FROM reviews WHERE project_id=:p AND reviewer_id=:u AND created_at>=:opened
        UNION ALL SELECT r.id FROM review_replies r JOIN reviews v ON v.id=r.review_id
        WHERE v.project_id=:p AND r.author_id=:u AND v.reviewer_id=:u AND r.created_at>=:opened LIMIT 1""",
        {"p": identity, "u": user["id"], "opened": visit["created_at"]},
        required=False,
    )
    if not engaged:
        fail(
            409,
            "review_required",
            "Submit a structured review or follow-up before closing this visit",
        )
    await audit(db, user["id"], "view.closed", visit["id"])
    return result({"closed": True})


@router.patch("/projects/{identity}", response_model=Result)
async def edit_project(
    identity: UUID, body: ProjectUpdate, db: DB, user: Actor
):
    project, team = await project_access(db, identity, user, leader=True)
    require(team["status"] == "active", "Team formation must be complete")
    if project["stage"] != body.stage:
        transition(
            project["stage"],
            body.stage,
            {
                "Ideation": {"Building"},
                "Building": {"Prototype"},
                "Prototype": {"Completed"},
            },
        )
    require(
        body.stage != "Completed" or body.progress == 100,
        "Completed projects require 100% progress",
    )
    saved = await update(
        db,
        "projects",
        identity,
        {
            **body.model_dump(),
            "status": "completed" if body.stage == "Completed" else "active",
            "completed_at": now() if body.stage == "Completed" else None,
        },
    )
    await audit(db, user["id"], "project.updated", identity, identity)
    return result(saved)


@router.get("/teams", response_model=Page)
async def teams(db: DB, user: Actor, limit: Limit = 25, offset: Offset = 0):
    return await page(
        db,
        """SELECT t.id,t.name,t.leader_id,t.formed_by,t.institution_id,t.status,t.created_at FROM teams t
        WHERE t.created_by_id=:u OR EXISTS (SELECT 1 FROM team_memberships m WHERE m.team_id=t.id AND m.user_id=:u AND m.status IN ('Member','Invited'))""",
        {"u": user["id"]},
        limit,
        offset,
    )


@router.get("/teams/{identity}/memberships", response_model=Page)
async def memberships(
    identity: UUID, db: DB, user: Actor, limit: Limit = 25, offset: Offset = 0
):
    project = await one(
        db,
        "SELECT id FROM projects WHERE team_id=:team LIMIT 1",
        {"team": identity},
    )
    await project_access(db, project["id"], user)
    return await page(
        db,
        "SELECT id,team_id,user_id,status,joined_at,ended_at,created_at FROM team_memberships WHERE team_id=:team",
        {"team": identity},
        limit,
        offset,
    )


@router.post(
    "/projects/{identity}/requests", response_model=Result, status_code=201
)
async def invite(identity: UUID, body: Invite, db: DB, user: Actor):
    project, team = await project_access(db, identity, user)
    require(
        (user["role"] == "student" and team["leader_id"] == user["id"])
        or (user["role"] == "faculty" and team["created_by_id"] == user["id"])
        or (user["role"] == "industry" and body.kind == "mentor")
    )
    return result(
        await send_invite(
            db, project, team, user, body.recipient_id, body.kind, body.reason
        )
    )


@router.get("/requests", response_model=Page)
async def requests(
    db: DB,
    user: Actor,
    status: str = "",
    direction: str = "",
    limit: Limit = 25,
    offset: Offset = 0,
):
    return await page(
        db,
        """SELECT id,project_id,sender_id,recipient_id,kind,reason,status,response_note,responded_at,created_at FROM collaboration_requests
        WHERE (sender_id=:u OR recipient_id=:u) AND (:status='' OR status=:status)
        AND (:direction<>'incoming' OR recipient_id=:u) AND (:direction<>'outgoing' OR sender_id=:u)""",
        {"u": user["id"], "status": status, "direction": direction},
        limit,
        offset,
    )


@router.post("/requests/{identity}/respond", response_model=Result)
async def respond(identity: UUID, body: Decision, db: DB, user: Actor):
    initial = await get(db, "collaboration_requests", identity)
    project = await get(db, "projects", initial["project_id"], lock=True)
    team = await get(db, "teams", project["team_id"], lock=True)
    request = await get(db, "collaboration_requests", identity, lock=True)
    require(request["recipient_id"] == user["id"])
    transition(
        request["status"], body.status, {"pending": {"accepted", "declined"}}
    )
    if request["kind"] == "member":
        require(user["role"] == "student")
        membership = await one(
            db,
            "SELECT id,status FROM team_memberships WHERE team_id=:t AND user_id=:u FOR UPDATE",
            {"t": team["id"], "u": user["id"]},
        )
        require(membership["status"] == "Invited")
        await update(
            db,
            "team_memberships",
            membership["id"],
            {
                "status": "Member" if body.status == "accepted" else "Declined",
                "joined_at": now() if body.status == "accepted" else None,
            },
        )
    elif body.status == "accepted":
        require(user["role"] in ("mentor", "industry", "faculty"))
        await insert(
            db,
            "mentor_assignments",
            {
                "project_id": project["id"],
                "mentor_id": user["id"],
                "assigned_by_id": request["sender_id"],
                "request_id": identity,
            },
        )
    saved = await update(
        db,
        "collaboration_requests",
        identity,
        {
            "status": body.status,
            "response_note": body.note,
            "responded_at": now(),
        },
    )
    await refresh_team(db, project, team)
    await notify(
        db,
        request["sender_id"],
        user["id"],
        f"Invitation {body.status}",
        "collaboration",
        project["id"],
    )
    await audit(
        db, user["id"], "collaboration.responded", identity, project["id"]
    )
    return result(saved)


@router.post("/memberships/{identity}/status", response_model=Result)
async def membership_status(
    identity: UUID, body: MembershipDecision, db: DB, user: Actor
):
    initial = await get(db, "team_memberships", identity)
    project = await one(
        db,
        "SELECT id FROM projects WHERE team_id=:t LIMIT 1",
        {"t": initial["team_id"]},
    )
    project, team = await project_access(db, project["id"], user)
    membership = await get(db, "team_memberships", identity, lock=True)
    require(
        membership["user_id"] != team["leader_id"],
        "The leader cannot leave or be removed",
    )
    require(
        (body.status == "Left" and membership["user_id"] == user["id"])
        or (body.status == "Removed" and user["id"] == team["leader_id"])
    )
    transition(
        membership["status"], body.status, {"Member": {"Left", "Removed"}}
    )
    saved = await update(
        db,
        "team_memberships",
        identity,
        {"status": body.status, "ended_at": now()},
    )
    await refresh_team(db, project, team)
    await notify(
        db,
        membership["user_id"],
        user["id"],
        "Team membership changed",
        "collaboration",
        project["id"],
    )
    await audit(db, user["id"], "membership.changed", identity, project["id"])
    return result(saved)


@router.post(
    "/projects/{identity}/proofs", response_model=Result, status_code=201
)
async def add_proof(identity: UUID, body: ProofInput, db: DB, user: Actor):
    project, team = await project_access(db, identity, user, member=True)
    require(team["status"] == "active", "Team formation must be complete")
    proof = await insert(
        db,
        "proof_entries",
        {
            "project_id": identity,
            "author_id": user["id"],
            "title": body.title,
            "description": body.description,
        },
    )
    attachments = []
    for position, attachment in enumerate(body.attachments):
        attachments.append(
            await insert(
                db,
                "proof_attachments",
                {
                    **attachment.model_dump(),
                    "entry_id": proof["id"],
                    "position": position,
                },
            )
        )
    await audit(db, user["id"], "proof.created", proof["id"], identity)
    return result({**proof, "attachments": attachments})


@router.get("/projects/{identity}/proofs", response_model=Page)
async def proofs(
    identity: UUID, db: DB, user: Actor, limit: Limit = 25, offset: Offset = 0
):
    await project_access(db, identity, user)
    return await page(
        db,
        """SELECT e.id,e.project_id,e.author_id,e.title,e.description,e.created_at,
        COALESCE((SELECT json_agg(json_build_object('id',a.id,'kind',a.kind,'url',a.url,'name',a.name) ORDER BY a.position) FROM proof_attachments a WHERE a.entry_id=e.id),'[]') AS attachments
        FROM proof_entries e WHERE e.project_id=:p AND e.deleted_at IS NULL""",
        {"p": identity},
        limit,
        offset,
    )


@router.delete("/proofs/{identity}", response_model=Result)
async def remove_proof(identity: UUID, db: DB, user: Actor):
    proof = await get(db, "proof_entries", identity)
    await project_access(db, proof["project_id"], user, member=True)
    require(
        proof["author_id"] == user["id"],
        "Only the author may remove a proof entry",
    )
    await update(db, "proof_entries", identity, {"deleted_at": now()})
    await audit(db, user["id"], "proof.deleted", identity, proof["project_id"])
    return result({"deleted": True})


@router.get("/projects/{identity}/activity", response_model=Page)
async def activity(
    identity: UUID, db: DB, user: Actor, limit: Limit = 25, offset: Offset = 0
):
    await project_access(db, identity, user)
    return await page(
        db,
        "SELECT id,actor_id,event_type,description,created_at FROM project_activities WHERE project_id=:p AND event_type<>'view.opened'",
        {"p": identity},
        limit,
        offset,
    )
