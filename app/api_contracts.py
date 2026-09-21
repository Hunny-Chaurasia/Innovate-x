import reflex as rx

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

Role = Literal["student", "faculty", "industry", "mentor", "admin"]
Domain = Literal[
    "Technology",
    "Healthcare",
    "Education",
    "Environment",
    "Finance",
    "Agriculture",
    "Logistics",
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Result(BaseModel):
    data: JsonValue


class Page(BaseModel):
    items: list[JsonValue]
    total: int
    limit: int
    offset: int


class Credentials(Input):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        import re

        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("password", mode="before")
    @classmethod
    def preserve_password(cls, value: str) -> str:
        # Passwords are not stripped by the model string configuration.
        return value

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class Registration(Credentials):
    display_name: str = Field(min_length=1, max_length=200)
    role: Role = "student"
    institution_id: UUID | None = None
    organization: str = Field(default="", max_length=240)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name is required")
        return value.strip()


class Profile(Input):
    display_name: str = Field(min_length=1, max_length=200)
    bio: str = Field(default="", max_length=5000)
    department: str = Field(default="", max_length=160)
    linkedin_url: str | None = None

    @field_validator("linkedin_url")
    @classmethod
    def profile_url(cls, value: str | None) -> str | None:
        return safe_url(value) if value else None


class PasswordChange(Input):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class UserStatus(Input):
    status: Literal["active", "suspended"]


class InstitutionInput(Input):
    name: str = Field(min_length=1, max_length=240)
    kind: Literal["School", "College"]
    code: str | None = Field(default=None, max_length=64)
    city: str = Field(default="", max_length=120)
    region: str = Field(default="", max_length=120)
    country_code: str = Field(default="IN", pattern=r"^[A-Z]{2}$")


class ProblemInput(Input):
    title: str = Field(min_length=3, max_length=240)
    description: str = Field(min_length=10, max_length=30000)
    domain: Domain = "Technology"
    source: Literal["industry", "community"] = "industry"
    csr: bool = False
    tags: list[str] = Field(default_factory=list, max_length=20)
    status: Literal["draft", "published"] = "published"
    deadline: datetime | None = None

    @field_validator("tags")
    @classmethod
    def tags_normalized(cls, values: list[str]) -> list[str]:
        values = sorted(set(v.strip().lower() for v in values))
        if any(not v or len(v) > 80 for v in values):
            raise ValueError("Tags must contain 1–80 characters")
        return values


class ProblemStatus(Input):
    status: Literal["published", "closed", "archived"]


class TeamProject(Input):
    name: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=3, max_length=240)
    description: str = Field(min_length=10, max_length=30000)
    category: Domain = "Technology"
    problem_id: UUID | None = None
    leader_id: UUID
    student_ids: list[UUID] = Field(min_length=2, max_length=50)
    mentor_id: UUID | None = None
    reason: str = Field(min_length=10, max_length=5000)

    @field_validator("student_ids")
    @classmethod
    def unique_students(cls, values: list[UUID]) -> list[UUID]:
        if len(values) != len(set(values)):
            raise ValueError("Duplicate students are not allowed")
        return values


class ProjectUpdate(Input):
    title: str = Field(min_length=3, max_length=240)
    description: str = Field(min_length=10, max_length=30000)
    stage: Literal["Ideation", "Building", "Prototype", "Completed"]
    progress: int = Field(ge=0, le=100)


class Invite(Input):
    recipient_id: UUID
    kind: Literal["member", "mentor"] = "member"
    reason: str = Field(min_length=10, max_length=5000)


class Decision(Input):
    status: Literal["accepted", "declined"]
    note: str = Field(default="", max_length=5000)


class MembershipDecision(Input):
    status: Literal["Left", "Removed"]


def safe_url(value: str) -> str:
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ("https", "http")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or any(c.isspace() for c in value)
    ):
        raise ValueError("Only valid HTTP(S) URLs are accepted")
    return value


class Attachment(Input):
    kind: Literal["image", "link", "video"] = "link"
    url: str = Field(max_length=4000)
    name: str = Field(default="", max_length=255)
    source: Literal["external"] = "external"

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return safe_url(value)


class ProofInput(Input):
    title: str = Field(min_length=3, max_length=240)
    description: str = Field(default="", max_length=30000)
    attachments: list[Attachment] = Field(min_length=1, max_length=30)


class ReviewInput(Input):
    summary: str = Field(min_length=10, max_length=10000)
    strengths: str = Field(default="", max_length=10000)
    flaws: str = Field(min_length=10, max_length=10000)
    improvements: str = Field(min_length=10, max_length=10000)


class ReplyInput(Input):
    body: str = Field(min_length=1, max_length=10000)
    action: Literal["comment", "changes_done", "request_changes", "resolve"] = (
        "comment"
    )


class FundingInput(Input):
    amount_lakh: Decimal = Field(
        gt=0, max_digits=16, decimal_places=6, allow_inf_nan=False
    )
    txn_ref: str = Field(min_length=1, max_length=240)
    transfer_confirmed: Literal[True]
    proof_file_name: str = Field(default="", max_length=255)
    proof_url: str | None = None

    @field_validator("proof_url")
    @classmethod
    def funding_url(cls, value: str | None) -> str | None:
        return safe_url(value) if value else None


class FundingDecision(Input):
    status: Literal["confirmed", "declined"]
    receipt_confirmed: bool = False
    decline_note: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def check_decision(self):
        if self.status == "confirmed" and (
            not self.receipt_confirmed or self.decline_note
        ):
            raise ValueError(
                "Confirmation requires receipt confirmation and no decline note"
            )
        if self.status == "declined" and (
            self.receipt_confirmed or len(self.decline_note) < 5
        ):
            raise ValueError(
                "Decline requires a reason of at least 5 characters and no receipt confirmation"
            )
        return self


class Verification(Input):
    status: Literal["verified", "rejected"]
    note: str = Field(min_length=5, max_length=5000)


class Shortlist(Input):
    shortlisted: bool


class ShareInput(Input):
    enabled: bool
    regenerate: bool = False


class ChangeInput(Input):
    to_institution_id: UUID
    faculty_id: UUID
    reason: str = Field(min_length=10, max_length=5000)


class ChangeDecision(Input):
    status: Literal["approved", "declined"]
    note: str = Field(default="", max_length=5000)


class MilestoneInput(Input):
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=10000)
    position: int = Field(default=0, ge=0)
    due_at: datetime | None = None


class MilestoneStatus(Input):
    status: Literal["in_progress", "submitted"]


class PanelInput(Input):
    milestone_id: UUID | None = None
    body: str = Field(min_length=1, max_length=10000)
    decision: Literal["feedback", "changes_requested", "approved"] = "feedback"
    score: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)


class ViewClose(Input):
    view_id: UUID
