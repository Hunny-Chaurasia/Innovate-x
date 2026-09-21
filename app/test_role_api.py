import reflex as rx

import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app import api_auth, api_core, api_projects, api_workflows
from app.api_contracts import (
    ChangeDecision,
    FundingInput,
    PanelInput,
    ProblemInput,
    Registration,
    ReplyInput,
    ReviewInput,
    Shortlist,
    TeamProject,
    ViewClose,
)
from app.api_runtime import HTTPException


class ConnectedRoleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = {
            "id": uuid4(),
            "role": "faculty",
            "institution_id": uuid4(),
        }
        self.project = {
            "id": uuid4(),
            "team_id": uuid4(),
            "institution_id": self.user["institution_id"],
        }
        self.team = {
            "id": self.project["team_id"],
            "leader_id": uuid4(),
            "status": "active",
        }
        self.db = AsyncMock()

    async def test_faculty_provisioning_only_own_school_students(self):
        for role, institution, allowed in [
            ("student", self.user["institution_id"], True),
            ("faculty", self.user["institution_id"], False),
            ("industry", self.user["institution_id"], False),
            ("student", uuid4(), False),
        ]:
            body = Registration(
                email="student@example.test",
                password="a-user-chosen-password",
                display_name="Student",
                role=role,
                institution_id=institution,
            )
            with patch.object(
                api_auth,
                "create_user",
                AsyncMock(
                    return_value={
                        "id": uuid4(),
                        "virtual_id": "STU-server-issued",
                    }
                ),
            ) as create:
                if allowed:
                    result = await api_auth.add_user(body, self.db, self.user)
                    self.assertEqual(
                        result["data"]["virtual_id"], "STU-server-issued"
                    )
                    create.assert_awaited_once_with(
                        self.db, body, self.user["id"]
                    )
                else:
                    with self.assertRaises(HTTPException) as raised:
                        await api_auth.add_user(body, self.db, self.user)
                    self.assertEqual(raised.exception.status_code, 403)
                    create.assert_not_awaited()

    async def test_project_faculty_access_requires_same_institution(self):
        with (
            patch.object(
                api_core,
                "get",
                AsyncMock(side_effect=[self.project, self.team] * 3),
            ),
            patch.object(api_core, "one", AsyncMock(return_value=None)),
        ):
            for role, institution, allowed in [
                ("faculty", self.user["institution_id"], True),
                ("faculty", uuid4(), False),
                ("industry", self.user["institution_id"], False),
            ]:
                actor = {
                    **self.user,
                    "role": role,
                    "institution_id": institution,
                }
                if allowed:
                    await api_core.project_access(
                        self.db, self.project["id"], actor, faculty=True
                    )
                else:
                    with self.assertRaises(HTTPException):
                        await api_core.project_access(
                            self.db, self.project["id"], actor, faculty=True
                        )

    async def test_faculty_formation_rejects_cross_school_and_wrong_leader(
        self,
    ):
        students = [uuid4(), uuid4()]
        body = TeamProject(
            name="School team",
            title="School project",
            description="A meaningful project",
            leader_id=students[0],
            student_ids=students,
            mentor_id=uuid4(),
            reason="Please mentor this team",
        )
        for institution, kind in [
            (uuid4(), "School"),
            (self.user["institution_id"], "College"),
        ]:
            members = [
                {"id": identity, "institution_id": institution, "kind": kind}
                for identity in students
            ]
            with (
                patch.object(
                    api_projects, "composition", AsyncMock(return_value=members)
                ),
                patch.object(api_projects, "insert", AsyncMock()) as write,
            ):
                with self.assertRaises(HTTPException):
                    await api_projects.create_project(body, self.db, self.user)
                write.assert_not_awaited()
        body.leader_id = uuid4()
        with patch.object(
            api_projects, "composition", AsyncMock()
        ) as composition:
            with self.assertRaises(HTTPException):
                await api_projects.create_project(body, self.db, self.user)
            composition.assert_not_awaited()

    async def test_faculty_formation_assigns_chosen_leader_and_real_members(
        self,
    ):
        ids = [uuid4(), uuid4()]
        body = TeamProject(
            name="School team",
            title="School project",
            description="A meaningful project",
            leader_id=ids[1],
            student_ids=ids,
            mentor_id=uuid4(),
            reason="Please mentor this team",
        )
        writes = []

        async def insert(db, table, values):
            writes.append((table, values))
            return {"id": uuid4(), **values}

        with (
            patch.object(
                api_projects,
                "composition",
                AsyncMock(
                    return_value=[
                        {
                            "id": i,
                            "institution_id": self.user["institution_id"],
                            "kind": "School",
                        }
                        for i in ids
                    ]
                ),
            ),
            patch.object(api_projects, "insert", AsyncMock(side_effect=insert)),
            patch.object(api_projects, "send_invite", AsyncMock()) as invite,
            patch.object(api_projects, "refresh_team", AsyncMock()),
            patch.object(api_projects, "notify", AsyncMock()),
            patch.object(api_projects, "audit", AsyncMock()),
        ):
            await api_projects.create_project(body, self.db, self.user)
        self.assertEqual(writes[0][1]["leader_id"], ids[1])
        members = [v for t, v in writes if t == "team_memberships"]
        self.assertEqual({m["user_id"] for m in members}, set(ids))
        self.assertTrue(all(m["status"] == "Member" for m in members))
        invite.assert_awaited_once()
        self.assertEqual(
            invite.await_args.args[4:6], (body.mentor_id, "mentor")
        )

    async def test_publish_and_shortlist_role_guards(self):
        body = ProblemInput(
            title="Useful challenge",
            description="A clear description",
            tags=["Climate", "climate"],
            csr=True,
        )
        self.assertEqual(body.tags, ["climate"])
        with patch.object(api_projects, "insert", AsyncMock()) as write:
            with self.assertRaises(HTTPException):
                await api_projects.publish(body, self.db, self.user)
            write.assert_not_awaited()
        with patch.object(api_workflows, "one", AsyncMock()) as write:
            with self.assertRaises(HTTPException):
                await api_workflows.shortlist(
                    uuid4(),
                    Shortlist(shortlisted=True),
                    self.db,
                    {**self.user, "role": "industry"},
                )
            write.assert_not_awaited()
        with (
            patch.object(
                api_workflows,
                "get",
                AsyncMock(return_value={"status": "closed"}),
            ),
            patch.object(api_workflows, "one", AsyncMock()) as write,
        ):
            with self.assertRaises(HTTPException):
                await api_workflows.shortlist(
                    uuid4(), Shortlist(shortlisted=True), self.db, self.user
                )
            write.assert_not_awaited()

    async def test_mandatory_review_visit_cannot_close_without_engagement(self):
        actor = {**self.user, "role": "industry"}
        visit = {
            "id": uuid4(),
            "project_id": self.project["id"],
            "actor_id": actor["id"],
            "event_type": "view.opened",
            "created_at": api_core.now(),
        }
        with (
            patch.object(api_projects, "project_access", AsyncMock()),
            patch.object(api_projects, "get", AsyncMock(return_value=visit)),
            patch.object(api_projects, "one", AsyncMock(return_value=None)),
            patch.object(api_projects, "audit", AsyncMock()) as audit,
        ):
            with self.assertRaises(HTTPException) as raised:
                await api_projects.close_view(
                    self.project["id"],
                    ViewClose(view_id=visit["id"]),
                    self.db,
                    actor,
                )
            self.assertEqual(raised.exception.detail["code"], "review_required")
            audit.assert_not_awaited()
        with (
            patch.object(api_projects, "project_access", AsyncMock()),
            patch.object(api_projects, "get", AsyncMock(return_value=visit)),
            patch.object(
                api_projects, "one", AsyncMock(return_value={"id": uuid4()})
            ),
            patch.object(api_projects, "audit", AsyncMock()) as audit,
        ):
            result = await api_projects.close_view(
                self.project["id"],
                ViewClose(view_id=visit["id"]),
                self.db,
                actor,
            )
            self.assertTrue(result["data"]["closed"])
            audit.assert_awaited_once()

    async def test_other_industry_cannot_reply_or_close_visit(self):
        actor = {**self.user, "role": "industry"}
        review = {
            "project_id": self.project["id"],
            "reviewer_id": uuid4(),
            "status": "open",
        }
        with (
            patch.object(api_workflows, "get", AsyncMock(return_value=review)),
            patch.object(api_workflows, "project_access", AsyncMock()),
            patch.object(api_workflows, "insert", AsyncMock()) as write,
        ):
            with self.assertRaises(HTTPException):
                await api_workflows.reply(
                    uuid4(),
                    ReplyInput(body="A response", action="resolve"),
                    self.db,
                    actor,
                )
            write.assert_not_awaited()
        visit = {
            "project_id": self.project["id"],
            "actor_id": uuid4(),
            "event_type": "view.opened",
        }
        with (
            patch.object(api_projects, "project_access", AsyncMock()),
            patch.object(api_projects, "get", AsyncMock(return_value=visit)),
            patch.object(api_projects, "audit", AsyncMock()) as audit,
        ):
            with self.assertRaises(HTTPException):
                await api_projects.close_view(
                    self.project["id"],
                    ViewClose(view_id=uuid4()),
                    self.db,
                    actor,
                )
            audit.assert_not_awaited()

    async def test_funding_blocks_forming_team_and_pending_transfer(self):
        body = FundingInput(
            amount_lakh="1.25",
            txn_ref="external-reference",
            transfer_confirmed=True,
        )
        for team_status, previous in [
            ("forming", None),
            ("active", {"status": "awaiting_leader"}),
        ]:
            with (
                patch.object(
                    api_workflows,
                    "project_access",
                    AsyncMock(
                        return_value=(
                            self.project,
                            {**self.team, "status": team_status},
                        )
                    ),
                ),
                patch.object(
                    api_workflows, "one", AsyncMock(return_value=previous)
                ),
                patch.object(api_workflows, "insert", AsyncMock()) as write,
            ):
                with self.assertRaises(HTTPException):
                    await api_workflows.fund(
                        self.project["id"],
                        body,
                        self.db,
                        {**self.user, "role": "industry"},
                    )
                write.assert_not_awaited()

    async def test_change_decisions_enforce_assignment_and_terminal_state(self):
        change = {
            "faculty_id": self.user["id"],
            "to_institution_id": self.user["institution_id"],
            "status": "pending",
        }
        for altered, status in [
            ({**change, "faculty_id": uuid4()}, 403),
            ({**change, "status": "approved"}, 409),
            ({**change, "to_institution_id": uuid4()}, 403),
        ]:
            with (
                patch.object(
                    api_workflows, "get", AsyncMock(return_value=altered)
                ),
                patch.object(api_workflows, "update", AsyncMock()) as write,
            ):
                with self.assertRaises(HTTPException) as raised:
                    await api_workflows.change_response(
                        uuid4(),
                        ChangeDecision(status="declined"),
                        self.db,
                        self.user,
                    )
                self.assertEqual(raised.exception.status_code, status)
                write.assert_not_awaited()

    async def test_change_approval_blocks_active_membership(self):
        origin = uuid4()
        change = {
            "faculty_id": self.user["id"],
            "to_institution_id": self.user["institution_id"],
            "from_institution_id": origin,
            "student_id": uuid4(),
            "status": "pending",
        }
        with (
            patch.object(
                api_workflows,
                "get",
                AsyncMock(
                    side_effect=[
                        change,
                        {"id": change["student_id"], "institution_id": origin},
                        {"is_active": True},
                    ]
                ),
            ),
            patch.object(
                api_workflows, "one", AsyncMock(return_value={"id": uuid4()})
            ),
            patch.object(api_workflows, "update", AsyncMock()) as write,
        ):
            with self.assertRaises(HTTPException) as raised:
                await api_workflows.change_response(
                    uuid4(),
                    ChangeDecision(status="approved"),
                    self.db,
                    self.user,
                )
            self.assertEqual(
                raised.exception.detail["code"], "active_memberships"
            )
            write.assert_not_awaited()

    async def test_panel_milestone_decision_matrix(self):
        for status in (
            "pending",
            "in_progress",
            "changes_requested",
            "approved",
            "submitted",
        ):
            for decision in ("approved", "changes_requested"):
                body = PanelInput(
                    milestone_id=uuid4(),
                    body="Evidence reviewed",
                    decision=decision,
                    score="82.25",
                )
                with (
                    patch.object(
                        api_workflows, "project_access", AsyncMock()
                    ) as access,
                    patch.object(
                        api_workflows,
                        "get",
                        AsyncMock(
                            return_value={
                                "project_id": self.project["id"],
                                "status": status,
                            }
                        ),
                    ),
                    patch.object(
                        api_workflows, "update", AsyncMock()
                    ) as update,
                    patch.object(
                        api_workflows,
                        "insert",
                        AsyncMock(return_value={"id": uuid4()}),
                    ) as insert,
                    patch.object(api_workflows, "audit", AsyncMock()),
                    patch.object(api_workflows, "notify_team", AsyncMock()),
                ):
                    if status == "submitted":
                        await api_workflows.panel_feedback(
                            self.project["id"], body, self.db, self.user
                        )
                        update.assert_awaited_once()
                        insert.assert_awaited_once()
                    else:
                        with self.assertRaises(HTTPException):
                            await api_workflows.panel_feedback(
                                self.project["id"], body, self.db, self.user
                            )
                        update.assert_not_awaited()
                        insert.assert_not_awaited()
                    access.assert_awaited_once_with(
                        self.db, self.project["id"], self.user, faculty=True
                    )

    async def test_panel_rejects_missing_or_foreign_milestone(self):
        for milestone in (None, uuid4()):
            with (
                patch.object(api_workflows, "project_access", AsyncMock()),
                patch.object(
                    api_workflows,
                    "get",
                    AsyncMock(return_value={"project_id": uuid4()}),
                ),
                patch.object(api_workflows, "insert", AsyncMock()) as write,
            ):
                with self.assertRaises(HTTPException):
                    await api_workflows.panel_feedback(
                        self.project["id"],
                        PanelInput(
                            milestone_id=milestone,
                            body="Review feedback",
                            decision="approved",
                        ),
                        self.db,
                        self.user,
                    )
                write.assert_not_awaited()

    async def test_public_slug_and_proofs_fail_closed_without_share(self):
        for function, args in [
            (api_workflows.public_portfolio, ("disabled-slug", self.db)),
            (api_workflows.public_proofs, ("disabled-slug", uuid4(), self.db)),
        ]:
            with (
                patch.object(
                    api_workflows, "one", AsyncMock(return_value=None)
                ) as read,
                patch.object(api_workflows, "page", AsyncMock()) as page,
            ):
                with self.assertRaises(HTTPException) as raised:
                    await function(*args)
                self.assertEqual(raised.exception.status_code, 404)
                query = read.await_args.args[1]
                for guard in (
                    "s.enabled=true",
                    "s.revoked_at IS NULL",
                    "u.status='active'",
                ):
                    self.assertIn(guard, query)
                page.assert_not_awaited()

    async def test_csr_denies_faculty_and_students(self):
        for role in ("faculty", "student", "mentor"):
            with patch.object(api_workflows, "one", AsyncMock()) as read:
                with self.assertRaises(HTTPException):
                    await api_workflows.csr(
                        self.db, {**self.user, "role": role}
                    )
                read.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
