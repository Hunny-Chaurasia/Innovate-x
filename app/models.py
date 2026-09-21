"""Managed PostgreSQL schema; importing this module performs no database I/O.

Display names, request direction, and the Funded display stage are derived from
related records, not copied into workflow rows. Latest funding is ordered by
(created_at, id); only its confirmed status makes a project display as Funded.

Checks validate row snapshots, not transitions. The future transaction layer must
lock workflow rows, enforce allowed transitions/actor roles, team composition,
leader membership, school mentors, attachment counts, and mandatory view reviews.
It must update updated_at for bulk SQL (ORM updates do this automatically).
"""

import reflex as rx

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def choice(name: str, *values: str) -> Enum:
    return Enum(
        *values,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )


def reference(table: str, *, optional: bool = False):
    # Required references have no fabricated sentinel identity.
    return mapped_column(
        Uuid,
        ForeignKey(f"{table}.id", ondelete="RESTRICT"),
        nullable=optional,
        default=None,
        index=True,
    )


class AuditColumns:
    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Institution(AuditColumns, Base):
    __tablename__ = "institutions"
    name: Mapped[str] = mapped_column(
        String(240), default="", server_default=""
    )
    kind: Mapped[str] = mapped_column(
        choice("institution_kind", "School", "College"),
        default="College",
        server_default="College",
    )
    code: Mapped[str | None] = mapped_column(
        String(64), unique=True, default=None
    )
    city: Mapped[str] = mapped_column(
        String(120), default="", server_default=""
    )
    region: Mapped[str] = mapped_column(
        String(120), default="", server_default=""
    )
    country_code: Mapped[str] = mapped_column(
        String(2), default="IN", server_default="IN"
    )
    website_url: Mapped[str | None] = mapped_column(Text, default=None)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    users: Mapped[list["User"]] = relationship(back_populates="institution")
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_required"),
        Index("ix_institutions_name", "name"),
    )


class User(AuditColumns, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(
        String(320), default="", server_default=""
    )
    password_hash: Mapped[str | None] = mapped_column(Text, default=None)
    display_name: Mapped[str] = mapped_column(
        String(200), default="", server_default=""
    )
    role: Mapped[str] = mapped_column(
        choice(
            "user_role", "student", "faculty", "industry", "mentor", "admin"
        ),
        default="student",
        server_default="student",
    )
    virtual_id: Mapped[str | None] = mapped_column(
        String(40), unique=True, default=None
    )
    virtual_id_year: Mapped[int | None] = mapped_column(Integer, default=None)
    virtual_id_sequence: Mapped[int | None] = mapped_column(
        BigInteger, default=None
    )
    institution_id: Mapped[UUID | None] = reference(
        "institutions", optional=True
    )
    registered_by_id: Mapped[UUID | None] = reference("users", optional=True)
    organization: Mapped[str] = mapped_column(
        String(240), default="", server_default=""
    )
    department: Mapped[str] = mapped_column(
        String(160), default="", server_default=""
    )
    bio: Mapped[str] = mapped_column(Text, default="", server_default="")
    linkedin_url: Mapped[str | None] = mapped_column(Text, default=None)
    avatar_url: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(
        choice("user_status", "invited", "active", "suspended", "deleted"),
        default="invited",
        server_default="invited",
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    deletion_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    institution: Mapped[Institution | None] = relationship(
        back_populates="users"
    )
    registered_by: Mapped["User | None"] = relationship(
        remote_side="User.id", foreign_keys=[registered_by_id]
    )
    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user")
    __table_args__ = (
        Index("uq_users_email_normalized", func.lower(email), unique=True),
        UniqueConstraint("role", "virtual_id_sequence"),
        CheckConstraint(
            "email = lower(trim(email)) AND email LIKE '%_@_%._%'",
            name="email_normalized",
        ),
        CheckConstraint(
            "length(trim(display_name)) > 0", name="display_name_required"
        ),
        CheckConstraint(
            "(virtual_id IS NULL AND virtual_id_year IS NULL AND virtual_id_sequence IS NULL) OR (virtual_id IS NOT NULL AND virtual_id_year BETWEEN 1000 AND 9999 AND virtual_id_sequence > 0 AND virtual_id = (CASE role WHEN 'student' THEN 'STU' WHEN 'faculty' THEN 'FAC' WHEN 'industry' THEN 'IND' WHEN 'mentor' THEN 'MEN' ELSE 'ADM' END) || '-' || virtual_id_year::text || '-' || lpad(virtual_id_sequence::text, greatest(4, length(virtual_id_sequence::text)), '0'))",
            name="virtual_identity",
        ),
        CheckConstraint(
            "status <> 'active' OR (virtual_id IS NOT NULL AND password_hash IS NOT NULL)",
            name="active_identity",
        ),
    )


class UserSession(AuditColumns, Base):
    __tablename__ = "user_sessions"
    user_id: Mapped[UUID] = reference("users")
    token_digest: Mapped[str | None] = mapped_column(
        String(128), unique=True, default=None
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, index=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    user_agent: Mapped[str] = mapped_column(
        String(512), default="", server_default=""
    )
    user: Mapped[User] = relationship(back_populates="sessions")
    __table_args__ = (
        CheckConstraint(
            "token_digest IS NOT NULL AND length(token_digest) >= 64",
            name="digest_required",
        ),
        CheckConstraint(
            "expires_at IS NOT NULL AND expires_at > created_at",
            name="expiry_required",
        ),
    )


class Problem(AuditColumns, Base):
    __tablename__ = "problems"
    publisher_id: Mapped[UUID] = reference("users")
    title: Mapped[str] = mapped_column(
        String(240), default="", server_default=""
    )
    description: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    domain: Mapped[str] = mapped_column(
        choice(
            "problem_domain",
            "Technology",
            "Healthcare",
            "Education",
            "Environment",
            "Finance",
            "Agriculture",
            "Logistics",
        ),
        default="Technology",
        server_default="Technology",
        index=True,
    )
    source: Mapped[str] = mapped_column(
        choice("problem_source", "industry", "community"),
        default="industry",
        server_default="industry",
    )
    csr: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), index=True
    )
    status: Mapped[str] = mapped_column(
        choice("problem_status", "draft", "published", "closed", "archived"),
        default="draft",
        server_default="draft",
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    publisher: Mapped[User] = relationship()
    tags: Mapped[list["ProblemTag"]] = relationship(back_populates="problem")
    projects: Mapped[list["Project"]] = relationship(back_populates="problem")
    __table_args__ = (
        CheckConstraint(
            "status = 'draft' OR (length(trim(title)) >= 3 AND length(trim(description)) >= 10 AND published_at IS NOT NULL)",
            name="published_brief",
        ),
    )


class ProblemTag(AuditColumns, Base):
    __tablename__ = "problem_tags"
    problem_id: Mapped[UUID] = reference("problems")
    label: Mapped[str] = mapped_column(
        String(80), default="", server_default=""
    )
    problem: Mapped[Problem] = relationship(back_populates="tags")
    __table_args__ = (
        UniqueConstraint("problem_id", "label"),
        CheckConstraint(
            "length(trim(label)) > 0 AND label = lower(trim(label))",
            name="normalized_label",
        ),
    )


class Team(AuditColumns, Base):
    __tablename__ = "teams"
    name: Mapped[str] = mapped_column(
        String(200), default="", server_default=""
    )
    leader_id: Mapped[UUID] = reference("users")
    created_by_id: Mapped[UUID] = reference("users")
    formed_by: Mapped[str] = mapped_column(
        choice("team_formed_by", "student", "faculty"),
        default="student",
        server_default="student",
    )
    institution_id: Mapped[UUID | None] = reference(
        "institutions", optional=True
    )
    status: Mapped[str] = mapped_column(
        choice("team_status", "forming", "active", "archived"),
        default="forming",
        server_default="forming",
    )
    leader: Mapped[User] = relationship(foreign_keys=[leader_id])
    creator: Mapped[User] = relationship(foreign_keys=[created_by_id])
    institution: Mapped[Institution | None] = relationship()
    memberships: Mapped[list["TeamMembership"]] = relationship(
        back_populates="team"
    )
    projects: Mapped[list["Project"]] = relationship(back_populates="team")
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="team_name"),
        CheckConstraint(
            "formed_by <> 'student' OR leader_id = created_by_id",
            name="student_creator_leader",
        ),
        CheckConstraint(
            "formed_by <> 'faculty' OR institution_id IS NOT NULL",
            name="faculty_institution",
        ),
    )


class TeamMembership(AuditColumns, Base):
    __tablename__ = "team_memberships"
    team_id: Mapped[UUID] = reference("teams")
    user_id: Mapped[UUID] = reference("users")
    invited_by_id: Mapped[UUID | None] = reference("users", optional=True)
    status: Mapped[str] = mapped_column(
        choice(
            "membership_status",
            "Invited",
            "Member",
            "Declined",
            "Left",
            "Removed",
        ),
        default="Invited",
        server_default="Invited",
        index=True,
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    team: Mapped[Team] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    __table_args__ = (
        UniqueConstraint("team_id", "user_id"),
        CheckConstraint(
            "status <> 'Member' OR (joined_at IS NOT NULL AND ended_at IS NULL)",
            name="member_dates",
        ),
        CheckConstraint(
            "ended_at IS NULL OR joined_at IS NULL OR ended_at >= joined_at",
            name="membership_chronology",
        ),
    )


class Project(AuditColumns, Base):
    __tablename__ = "projects"
    team_id: Mapped[UUID] = reference("teams")
    problem_id: Mapped[UUID | None] = reference("problems", optional=True)
    created_by_id: Mapped[UUID] = reference("users")
    institution_id: Mapped[UUID | None] = reference(
        "institutions", optional=True
    )
    title: Mapped[str] = mapped_column(
        String(240), default="", server_default=""
    )
    description: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    category: Mapped[str] = mapped_column(
        String(100),
        default="Technology",
        server_default="Technology",
        index=True,
    )
    stage: Mapped[str] = mapped_column(
        choice(
            "project_stage", "Ideation", "Building", "Prototype", "Completed"
        ),
        default="Ideation",
        server_default="Ideation",
        index=True,
    )
    status: Mapped[str] = mapped_column(
        choice("project_status", "active", "completed", "archived"),
        default="active",
        server_default="active",
    )
    progress: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    cover_url: Mapped[str | None] = mapped_column(Text, default=None)
    repository_url: Mapped[str | None] = mapped_column(Text, default=None)
    demo_url: Mapped[str | None] = mapped_column(Text, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    team: Mapped[Team] = relationship(back_populates="projects")
    problem: Mapped[Problem | None] = relationship(back_populates="projects")
    proofs: Mapped[list["ProofEntry"]] = relationship(back_populates="project")
    reviews: Mapped[list["Review"]] = relationship(back_populates="project")
    funding_records: Mapped[list["FundingRecord"]] = relationship(
        back_populates="project"
    )
    __table_args__ = (
        CheckConstraint(
            "length(trim(title)) >= 3 AND length(trim(description)) >= 10",
            name="project_brief",
        ),
        CheckConstraint("progress BETWEEN 0 AND 100", name="progress_range"),
    )


class CollaborationRequest(AuditColumns, Base):
    __tablename__ = "collaboration_requests"
    project_id: Mapped[UUID] = reference("projects")
    sender_id: Mapped[UUID] = reference("users")
    recipient_id: Mapped[UUID] = reference("users")
    kind: Mapped[str] = mapped_column(
        choice("collaboration_kind", "member", "mentor"),
        default="member",
        server_default="member",
    )
    reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(
        choice("collaboration_status", "pending", "accepted", "declined"),
        default="pending",
        server_default="pending",
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    response_note: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    project: Mapped[Project] = relationship()
    sender: Mapped[User] = relationship(foreign_keys=[sender_id])
    recipient: Mapped[User] = relationship(foreign_keys=[recipient_id])
    __table_args__ = (
        CheckConstraint("sender_id <> recipient_id", name="different_parties"),
        CheckConstraint("length(trim(reason)) >= 10", name="reason_length"),
        CheckConstraint(
            "(status = 'pending' AND responded_at IS NULL) OR (status <> 'pending' AND responded_at IS NOT NULL AND responded_at >= created_at)",
            name="response_state",
        ),
        Index(
            "uq_collaboration_pending",
            "project_id",
            "recipient_id",
            "kind",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_collaboration_inbox", "recipient_id", "status", "created_at"),
    )


class MentorAssignment(AuditColumns, Base):
    __tablename__ = "mentor_assignments"
    project_id: Mapped[UUID] = reference("projects")
    mentor_id: Mapped[UUID] = reference("users")
    assigned_by_id: Mapped[UUID] = reference("users")
    request_id: Mapped[UUID | None] = reference(
        "collaboration_requests", optional=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    project: Mapped[Project] = relationship()
    mentor: Mapped[User] = relationship(foreign_keys=[mentor_id])
    request: Mapped[CollaborationRequest | None] = relationship()
    __table_args__ = (
        UniqueConstraint("request_id"),
        Index(
            "uq_mentor_current_project",
            "project_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="assignment_dates",
        ),
    )


class ProofEntry(AuditColumns, Base):
    __tablename__ = "proof_entries"
    project_id: Mapped[UUID] = reference("projects")
    author_id: Mapped[UUID] = reference("users")
    title: Mapped[str] = mapped_column(
        String(240), default="", server_default=""
    )
    description: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    project: Mapped[Project] = relationship(back_populates="proofs")
    author: Mapped[User] = relationship()
    attachments: Mapped[list["ProofAttachment"]] = relationship(
        back_populates="entry"
    )
    __table_args__ = (
        CheckConstraint("length(trim(title)) >= 3", name="proof_title"),
        Index("ix_proof_project_created", "project_id", "created_at"),
    )


class ProofAttachment(AuditColumns, Base):
    __tablename__ = "proof_attachments"
    entry_id: Mapped[UUID] = reference("proof_entries")
    kind: Mapped[str] = mapped_column(
        choice("attachment_kind", "image", "link", "video"),
        default="link",
        server_default="link",
    )
    source: Mapped[str] = mapped_column(
        choice("attachment_source", "upload", "external"),
        default="external",
        server_default="external",
    )
    url: Mapped[str] = mapped_column(Text, default="", server_default="")
    name: Mapped[str] = mapped_column(
        String(255), default="", server_default=""
    )
    storage_key: Mapped[str | None] = mapped_column(
        Text, default=None, unique=True
    )
    mime_type: Mapped[str | None] = mapped_column(String(127), default=None)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, default=None)
    checksum_sha256: Mapped[str | None] = mapped_column(
        String(64), default=None
    )
    position: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    entry: Mapped[ProofEntry] = relationship(back_populates="attachments")
    __table_args__ = (
        CheckConstraint(
            "url ~ '^https?://[^[:space:]/]+[^[:space:]]*$' OR (source = 'upload' AND url LIKE '/_upload/%')",
            name="attachment_url",
        ),
        CheckConstraint(
            "position >= 0 AND (size_bytes IS NULL OR size_bytes >= 0)",
            name="attachment_numbers",
        ),
        CheckConstraint(
            "source <> 'upload' OR (storage_key IS NOT NULL AND length(storage_key) > 0 AND mime_type IS NOT NULL AND size_bytes IS NOT NULL AND ((kind = 'image' AND mime_type LIKE 'image/%' AND size_bytes <= 2097152) OR (kind = 'video' AND mime_type LIKE 'video/%' AND size_bytes <= 104857600)))",
            name="upload_limits",
        ),
        CheckConstraint(
            "checksum_sha256 IS NULL OR checksum_sha256 ~ '^[0-9a-f]{64}$'",
            name="checksum_format",
        ),
    )


class Review(AuditColumns, Base):
    __tablename__ = "reviews"
    project_id: Mapped[UUID] = reference("projects")
    reviewer_id: Mapped[UUID] = reference("users")
    summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    strengths: Mapped[str] = mapped_column(Text, default="", server_default="")
    flaws: Mapped[str] = mapped_column(Text, default="", server_default="")
    improvements: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    status: Mapped[str] = mapped_column(
        choice("review_status", "open", "addressed", "resolved"),
        default="open",
        server_default="open",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    resolved_by_id: Mapped[UUID | None] = reference("users", optional=True)
    project: Mapped[Project] = relationship(back_populates="reviews")
    reviewer: Mapped[User] = relationship(foreign_keys=[reviewer_id])
    replies: Mapped[list["ReviewReply"]] = relationship(
        back_populates="review",
        order_by="(ReviewReply.created_at, ReviewReply.id)",
    )
    __table_args__ = (
        CheckConstraint(
            "length(trim(summary)) >= 10 AND length(trim(flaws)) >= 10 AND length(trim(improvements)) >= 10",
            name="review_lengths",
        ),
        CheckConstraint(
            "(status = 'resolved' AND resolved_at IS NOT NULL AND resolved_by_id = reviewer_id) OR (status <> 'resolved' AND resolved_at IS NULL AND resolved_by_id IS NULL)",
            name="resolution_state",
        ),
        Index("ix_review_project_status", "project_id", "status", "created_at"),
    )


class ReviewReply(AuditColumns, Base):
    __tablename__ = "review_replies"
    review_id: Mapped[UUID] = reference("reviews")
    author_id: Mapped[UUID] = reference("users")
    author_role: Mapped[str] = mapped_column(
        choice("reply_author_role", "student", "industry"),
        default="student",
        server_default="student",
    )
    body: Mapped[str] = mapped_column(Text, default="", server_default="")
    action: Mapped[str] = mapped_column(
        choice(
            "reply_action",
            "comment",
            "changes_done",
            "request_changes",
            "resolve",
        ),
        default="comment",
        server_default="comment",
    )
    review: Mapped[Review] = relationship(back_populates="replies")
    author: Mapped[User] = relationship()
    __table_args__ = (
        CheckConstraint("length(trim(body)) > 0", name="reply_required"),
        CheckConstraint(
            "action = 'comment' OR (action = 'changes_done' AND author_role = 'student') OR (action IN ('request_changes', 'resolve') AND author_role = 'industry')",
            name="reply_action_role",
        ),
    )


class FundingRecord(AuditColumns, Base):
    __tablename__ = "funding_records"
    project_id: Mapped[UUID] = reference("projects")
    leader_id: Mapped[UUID] = reference("users")
    funder_id: Mapped[UUID] = reference("users")
    responded_by_id: Mapped[UUID | None] = reference("users", optional=True)
    amount_lakh: Mapped[Decimal] = mapped_column(
        Numeric(16, 6), default=Decimal("0"), server_default="0"
    )
    currency: Mapped[str] = mapped_column(
        String(3), default="INR", server_default="INR"
    )
    txn_ref: Mapped[str] = mapped_column(
        String(240), default="", server_default=""
    )
    proof_file_name: Mapped[str] = mapped_column(
        String(255), default="", server_default=""
    )
    proof_url: Mapped[str | None] = mapped_column(Text, default=None)
    proof_storage_key: Mapped[str | None] = mapped_column(Text, default=None)
    proof_mime_type: Mapped[str | None] = mapped_column(
        String(127), default=None
    )
    proof_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger, default=None
    )
    transfer_confirmed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    receipt_confirmed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    status: Mapped[str] = mapped_column(
        choice("funding_status", "awaiting_leader", "confirmed", "declined"),
        default="awaiting_leader",
        server_default="awaiting_leader",
    )
    decline_note: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    verification_status: Mapped[str] = mapped_column(
        choice("funding_verification", "unverified", "verified", "rejected"),
        default="unverified",
        server_default="unverified",
    )
    verified_by_id: Mapped[UUID | None] = reference("users", optional=True)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    verification_note: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    project: Mapped[Project] = relationship(back_populates="funding_records")
    funder: Mapped[User] = relationship(foreign_keys=[funder_id])
    leader: Mapped[User] = relationship(foreign_keys=[leader_id])
    __table_args__ = (
        CheckConstraint(
            "amount_lakh > 0 AND currency = 'INR'", name="funding_amount"
        ),
        CheckConstraint(
            "length(trim(txn_ref)) > 0 AND transfer_confirmed",
            name="transfer_proof",
        ),
        CheckConstraint(
            "(status = 'awaiting_leader' AND responded_at IS NULL AND responded_by_id IS NULL AND NOT receipt_confirmed AND decline_note = '') OR (status = 'confirmed' AND responded_at IS NOT NULL AND responded_by_id IS NOT NULL AND responded_by_id = leader_id AND receipt_confirmed AND decline_note = '') OR (status = 'declined' AND responded_at IS NOT NULL AND responded_by_id IS NOT NULL AND responded_by_id = leader_id AND NOT receipt_confirmed AND length(trim(decline_note)) >= 5)",
            name="funding_decision",
        ),
        CheckConstraint(
            "responded_at IS NULL OR responded_at >= created_at",
            name="funding_dates",
        ),
        CheckConstraint(
            "proof_size_bytes IS NULL OR proof_size_bytes >= 0",
            name="proof_size",
        ),
        CheckConstraint(
            "(verification_status = 'unverified' AND verified_at IS NULL AND verified_by_id IS NULL) OR (verification_status <> 'unverified' AND verified_at IS NOT NULL AND verified_by_id IS NOT NULL)",
            name="verification_state",
        ),
        Index("ix_funding_latest", "project_id", "created_at", "id"),
        Index("ix_funding_leader_pending", "leader_id", "status"),
    )


class FacultyProblemShortlist(AuditColumns, Base):
    __tablename__ = "faculty_problem_shortlists"
    faculty_id: Mapped[UUID] = reference("users")
    problem_id: Mapped[UUID] = reference("problems")
    seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    shortlisted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    faculty: Mapped[User] = relationship()
    problem: Mapped[Problem] = relationship()
    __table_args__ = (UniqueConstraint("faculty_id", "problem_id"),)


class PortfolioShare(AuditColumns, Base):
    __tablename__ = "portfolio_shares"
    owner_id: Mapped[UUID] = reference("users")
    slug: Mapped[str | None] = mapped_column(
        String(200), unique=True, default=None
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    view_count: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0"
    )
    owner: Mapped[User] = relationship()
    __table_args__ = (
        CheckConstraint(
            "slug IS NOT NULL AND slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'",
            name="share_slug",
        ),
        CheckConstraint(
            "NOT enabled OR revoked_at IS NULL", name="revoked_is_private"
        ),
        CheckConstraint("view_count >= 0", name="view_count"),
        Index(
            "uq_portfolio_current_owner",
            "owner_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )


class InstitutionChangeRequest(AuditColumns, Base):
    __tablename__ = "institution_change_requests"
    student_id: Mapped[UUID] = reference("users")
    from_institution_id: Mapped[UUID] = reference("institutions")
    to_institution_id: Mapped[UUID] = reference("institutions")
    faculty_id: Mapped[UUID] = reference("users")
    reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(
        choice("institution_change_status", "pending", "approved", "declined"),
        default="pending",
        server_default="pending",
    )
    responded_by_id: Mapped[UUID | None] = reference("users", optional=True)
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    response_note: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    student: Mapped[User] = relationship(foreign_keys=[student_id])
    faculty: Mapped[User] = relationship(foreign_keys=[faculty_id])
    from_institution: Mapped[Institution] = relationship(
        foreign_keys=[from_institution_id]
    )
    to_institution: Mapped[Institution] = relationship(
        foreign_keys=[to_institution_id]
    )
    __table_args__ = (
        CheckConstraint(
            "from_institution_id <> to_institution_id",
            name="different_institutions",
        ),
        CheckConstraint(
            "(status = 'pending' AND responded_at IS NULL AND responded_by_id IS NULL) OR (status <> 'pending' AND responded_at IS NOT NULL AND responded_by_id IS NOT NULL AND responded_by_id = faculty_id)",
            name="change_response",
        ),
        Index(
            "uq_student_pending_change",
            "student_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )


class Milestone(AuditColumns, Base):
    __tablename__ = "milestones"
    project_id: Mapped[UUID] = reference("projects")
    created_by_id: Mapped[UUID] = reference("users")
    title: Mapped[str] = mapped_column(
        String(240), default="", server_default=""
    )
    description: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    position: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    status: Mapped[str] = mapped_column(
        choice(
            "milestone_status",
            "pending",
            "in_progress",
            "submitted",
            "changes_requested",
            "approved",
        ),
        default="pending",
        server_default="pending",
    )
    approved_by_id: Mapped[UUID | None] = reference("users", optional=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    project: Mapped[Project] = relationship()
    feedback: Mapped[list["ReviewPanelFeedback"]] = relationship(
        back_populates="milestone"
    )
    __table_args__ = (
        CheckConstraint(
            "length(trim(title)) > 0 AND position >= 0", name="milestone_fields"
        ),
        CheckConstraint(
            "(status = 'approved' AND approved_by_id IS NOT NULL AND approved_at IS NOT NULL) OR (status <> 'approved' AND approved_by_id IS NULL AND approved_at IS NULL)",
            name="milestone_approval",
        ),
    )


class ReviewPanelFeedback(AuditColumns, Base):
    __tablename__ = "review_panel_feedback"
    project_id: Mapped[UUID] = reference("projects")
    milestone_id: Mapped[UUID | None] = reference("milestones", optional=True)
    faculty_id: Mapped[UUID] = reference("users")
    body: Mapped[str] = mapped_column(Text, default="", server_default="")
    decision: Mapped[str] = mapped_column(
        choice("panel_decision", "feedback", "changes_requested", "approved"),
        default="feedback",
        server_default="feedback",
    )
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), default=None)
    project: Mapped[Project] = relationship()
    milestone: Mapped[Milestone | None] = relationship(
        back_populates="feedback"
    )
    faculty: Mapped[User] = relationship()
    __table_args__ = (
        CheckConstraint(
            "length(trim(body)) > 0", name="panel_feedback_required"
        ),
        CheckConstraint(
            "score IS NULL OR score BETWEEN 0 AND 100", name="panel_score"
        ),
    )


class Notification(AuditColumns, Base):
    __tablename__ = "notifications"
    recipient_id: Mapped[UUID] = reference("users")
    actor_id: Mapped[UUID | None] = reference("users", optional=True)
    project_id: Mapped[UUID | None] = reference("projects", optional=True)
    collaboration_request_id: Mapped[UUID | None] = reference(
        "collaboration_requests", optional=True
    )
    funding_record_id: Mapped[UUID | None] = reference(
        "funding_records", optional=True
    )
    review_id: Mapped[UUID | None] = reference("reviews", optional=True)
    change_request_id: Mapped[UUID | None] = reference(
        "institution_change_requests", optional=True
    )
    kind: Mapped[str] = mapped_column(
        choice(
            "notification_kind",
            "collaboration",
            "funding",
            "review",
            "institution_change",
            "milestone",
            "system",
        ),
        default="system",
        server_default="system",
    )
    title: Mapped[str] = mapped_column(
        String(240), default="", server_default=""
    )
    body: Mapped[str] = mapped_column(Text, default="", server_default="")
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    deduplication_key: Mapped[str | None] = mapped_column(
        String(240), default=None
    )
    recipient: Mapped[User] = relationship(foreign_keys=[recipient_id])
    __table_args__ = (
        UniqueConstraint("recipient_id", "deduplication_key"),
        CheckConstraint("length(trim(title)) > 0", name="notification_title"),
        Index(
            "ix_notification_unread",
            "recipient_id",
            "created_at",
            postgresql_where=text("read_at IS NULL"),
        ),
    )


class ApiAudit(AuditColumns, Base):
    __tablename__ = "api_audits"
    actor_id: Mapped[UUID | None] = reference("users", optional=True)
    action: Mapped[str] = mapped_column(
        String(100), default="", server_default="", index=True
    )
    target_id: Mapped[UUID | None] = mapped_column(Uuid, default=None)
    subject_hash: Mapped[str | None] = mapped_column(
        String(64), default=None, index=True
    )
    __table_args__ = (
        Index("ix_api_audit_subject_time", "subject_hash", "created_at"),
    )


class ProjectActivity(AuditColumns, Base):
    __tablename__ = "project_activities"
    project_id: Mapped[UUID] = reference("projects")
    actor_id: Mapped[UUID | None] = reference("users", optional=True)
    event_type: Mapped[str] = mapped_column(
        String(80), default="note", server_default="note"
    )
    description: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    project: Mapped[Project] = relationship()
    actor: Mapped[User | None] = relationship()
    __table_args__ = (
        Index("ix_activity_project_created", "project_id", "created_at"),
    )
