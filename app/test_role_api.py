import reflex as rx

import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app import (
    api_auth as auth,
    api_projects as projects,
    api_workflows as workflows,
)
from app.api_contracts import (
    ChangeDecision,
    Decision,
    FundingInput,
    PanelInput,
    Registration,
    ReplyInput,
    Shortlist,
    TeamProject,
    ViewClose,
)
from app.api_runtime import HTTPException


class RoleAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_faculty_student_registration_scope_and_server_identity(self):
        institution = uuid4()
        actor = {
            "id": uuid4(),
            "role": "faculty",
            "institution_id": institution,
        }
        body = Registration(
            email="student@example.test",
            password="long-test-password",
            display_name="Student",
            institution_id=institution,
        )
        saved = {
            "id": uuid4(),
            "virtual_id": "STU-2026-0042",
            "display_name": "Student",
            "role": "student",
        }
        with patch.object(
            auth, "create_user", AsyncMock(return_value=saved)
        ) as create:
            response = await auth.add_user(body, None, actor)
            self.assertEqual(
                response["data"]["virtual_id"], saved["virtual_id"]
            )
            create.assert_awaited_once_with(None, body, actor["id"])
            for denied in (
                body.model_copy(update={"institution_id": uuid4()}),
                body.model_copy(update={"role": "faculty"}),
            ):
                with self.assertRaises(HTTPException) as error:
                    await auth.add_user(denied, None, actor)
                self.assertEqual(error.exception.status_code, 403)
            self.assertEqual(create.await_count, 1)

    async def test_faculty_formation_rejects_college_other_school_and_missing_mentor(
        self,
    ):
        institution, leader, member = uuid4(), uuid4(), uuid4()
        actor = {
            "id": uuid4(),
            "role": "faculty",
            "institution_id": institution,
        }
        body = TeamProject(
            name="Team",
            title="School project",
            description="A meaningful project",
            leader_id=leader,
            student_ids=[leader, member],
            mentor_id=uuid4(),
            reason="Please mentor this team",
        )
        for kind, school, mentor in (
            ("College", institution, body.mentor_id),
            ("School", uuid4(), body.mentor_id),
            ("School", institution, None),
        ):
            students = [
                {"id": identity, "kind": kind, "institution_id": school}
                for identity in (leader, member)
            ]
            with (
                patch.object(
                    projects, "composition", AsyncMock(return_value=students)
                ),
                patch.object(projects, "insert", AsyncMock()) as insert,
            ):
                with self.assertRaises(HTTPException):
                    await projects.create_project(
                        body.model_copy(update={"mentor_id": mentor}),
                        None,
                        actor,
                    )
                insert.assert_not_awaited()

    async def test_visit_requires_engagement_and_ownership(self):
        identity, actor_id, view_id = uuid4(), uuid4(), uuid4()
        actor = {"id": actor_id, "role": "industry"}
        visit = {
            "id": view_id,
            "project_id": identity,
            "actor_id": actor_id,
            "event_type": "view.opened",
            "created_at": "2026-01-01",
        }
        with (
            patch.object(projects, "project_access", AsyncMock()),
            patch.object(projects, "get", AsyncMock(return_value=visit)),
            patch.object(
                projects, "one", AsyncMock(return_value=None)
            ) as engagement,
            patch.object(projects, "audit", AsyncMock()) as audit,
        ):
            with self.assertRaises(HTTPException) as error:
                await projects.close_view(
                    identity, ViewClose(view_id=view_id), None, actor
                )
            self.assertEqual(error.exception.status_code, 409)
            audit.assert_not_awaited()
            engagement.return_value = {"id": uuid4()}
            self.assertTrue(
                (
                    await projects.close_view(
                        identity, ViewClose(view_id=view_id), None, actor
                    )
                )["data"]["closed"]
            )
            audit.assert_awaited_once()
            with self.assertRaises(HTTPException):
                await projects.close_view(
                    identity,
                    ViewClose(view_id=view_id),
                    None,
                    {"id": uuid4(), "role": "industry"},
                )
            self.assertEqual(audit.await_count, 1)

    async def test_open_visit_resumes_existing_audit(self):
        identity, view_id = uuid4(), uuid4()
        with (
            patch.object(
                projects, "project_access", AsyncMock(return_value=({}, {}))
            ),
            patch.object(
                projects, "one", AsyncMock(return_value={"id": view_id})
            ),
            patch.object(
                projects, "project_payload", AsyncMock(return_value={})
            ),
            patch.object(projects, "insert", AsyncMock()) as insert,
        ):
            response = await projects.open_view(
                identity, None, {"id": uuid4(), "role": "industry"}
            )
            self.assertEqual(response["data"]["view_id"], str(view_id))
            self.assertTrue(response["data"]["review_required"])
            insert.assert_not_awaited()

    async def test_funding_pending_and_inactive_team_block_writes(self):
        body = FundingInput(
            amount_lakh="1.25",
            txn_ref="bank-reference",
            transfer_confirmed=True,
            proof_url="https://example.test/receipt",
        )
        for team_status, latest in (
            ("forming", None),
            ("active", {"status": "awaiting_leader"}),
        ):
            with (
                patch.object(
                    workflows,
                    "project_access",
                    AsyncMock(return_value=({}, {"status": team_status})),
                ),
                patch.object(workflows, "one", AsyncMock(return_value=latest)),
                patch.object(workflows, "insert", AsyncMock()) as insert,
            ):
                with self.assertRaises(HTTPException):
                    await workflows.fund(
                        uuid4(), body, None, {"role": "industry", "id": uuid4()}
                    )
                insert.assert_not_awaited()

    async def test_only_original_reviewer_can_follow_up(self):
        review = {
            "id": uuid4(),
            "project_id": uuid4(),
            "reviewer_id": uuid4(),
            "status": "addressed",
        }
        with (
            patch.object(workflows, "get", AsyncMock(return_value=review)),
            patch.object(workflows, "project_access", AsyncMock()),
            patch.object(workflows, "insert", AsyncMock()) as insert,
        ):
            with self.assertRaises(HTTPException) as error:
                await workflows.reply(
                    review["id"],
                    ReplyInput(body="Follow-up", action="resolve"),
                    None,
                    {"id": uuid4(), "role": "industry"},
                )
            self.assertEqual(error.exception.status_code, 403)
            insert.assert_not_awaited()
        self.assertEqual(
            workflows.review_next("addressed", "request_changes", "industry"),
            "open",
        )
        self.assertEqual(
            workflows.review_next("addressed", "resolve", "industry"),
            "resolved",
        )
        with self.assertRaises(HTTPException):
            workflows.review_next("resolved", "comment", "industry")

    async def test_invitation_recipient_and_terminal_state(self):
        recipient, project_id, team_id = uuid4(), uuid4(), uuid4()
        invitation = {
            "project_id": project_id,
            "recipient_id": recipient,
            "status": "accepted",
        }

        async def lookup(db, table, identity, **kwargs):
            return {
                "projects": {"team_id": team_id},
                "teams": {"id": team_id},
                "collaboration_requests": invitation,
            }[table]

        with (
            patch.object(projects, "get", AsyncMock(side_effect=lookup)),
            patch.object(projects, "update", AsyncMock()) as update,
        ):
            for user_id, expected in ((uuid4(), 403), (recipient, 409)):
                with self.assertRaises(HTTPException) as error:
                    await projects.respond(
                        uuid4(),
                        Decision(status="accepted"),
                        None,
                        {"id": user_id, "role": "faculty"},
                    )
                self.assertEqual(error.exception.status_code, expected)
            update.assert_not_awaited()

    async def test_shortlist_role_and_explicit_toggle(self):
        with (
            patch.object(
                workflows,
                "get",
                AsyncMock(return_value={"status": "published"}),
            ),
            patch.object(
                workflows, "one", AsyncMock(return_value={"id": uuid4()})
            ) as one,
            patch.object(workflows, "audit", AsyncMock()),
        ):
            for enabled in (True, False):
                await workflows.shortlist(
                    uuid4(),
                    Shortlist(shortlisted=enabled),
                    None,
                    {"id": uuid4(), "role": "faculty"},
                )
                self.assertEqual(
                    one.await_args.args[2]["shortlisted"] is not None, enabled
                )
            with self.assertRaises(HTTPException):
                await workflows.shortlist(
                    uuid4(),
                    Shortlist(shortlisted=True),
                    None,
                    {"id": uuid4(), "role": "industry"},
                )
            self.assertEqual(one.await_count, 2)

    async def test_panel_decisions_require_submitted_matching_milestone(self):
        project_id, milestone_id = uuid4(), uuid4()
        actor = {"id": uuid4(), "role": "faculty"}
        with (
            patch.object(workflows, "project_access", AsyncMock()) as access,
            patch.object(workflows, "get", AsyncMock()) as get,
            patch.object(workflows, "update", AsyncMock()) as update,
            patch.object(
                workflows, "insert", AsyncMock(return_value={"id": uuid4()})
            ) as insert,
            patch.object(workflows, "audit", AsyncMock()),
            patch.object(workflows, "notify_team", AsyncMock()),
        ):
            with self.assertRaises(HTTPException) as error:
                await workflows.panel_feedback(
                    project_id,
                    PanelInput(body="Approve", decision="approved"),
                    None,
                    actor,
                )
            self.assertEqual(error.exception.status_code, 422)
            for status, owner in (
                ("pending", project_id),
                ("approved", project_id),
                ("submitted", uuid4()),
            ):
                get.return_value = {"project_id": owner, "status": status}
                with self.assertRaises(HTTPException):
                    await workflows.panel_feedback(
                        project_id,
                        PanelInput(
                            body="Decision",
                            decision="approved",
                            milestone_id=milestone_id,
                        ),
                        None,
                        actor,
                    )
            insert.assert_not_awaited()
            update.assert_not_awaited()
            for decision in ("approved", "changes_requested"):
                get.return_value = {
                    "project_id": project_id,
                    "status": "submitted",
                }
                await workflows.panel_feedback(
                    project_id,
                    PanelInput(
                        body="Evidence assessment",
                        decision=decision,
                        milestone_id=milestone_id,
                        score="82.50",
                    ),
                    None,
                    actor,
                )
                self.assertEqual(update.await_args.args[3]["status"], decision)
            access.assert_awaited_with(None, project_id, actor, faculty=True)

    async def test_institution_change_requires_destination_faculty_and_no_memberships(
        self,
    ):
        institution, faculty_id = uuid4(), uuid4()
        change = {
            "faculty_id": faculty_id,
            "to_institution_id": institution,
            "from_institution_id": uuid4(),
            "student_id": uuid4(),
            "status": "pending",
        }

        async def lookup(db, table, identity, **kwargs):
            return {
                "institution_change_requests": change,
                "users": {
                    "id": change["student_id"],
                    "institution_id": change["from_institution_id"],
                },
                "institutions": {"is_active": True},
            }[table]

        with (
            patch.object(workflows, "get", AsyncMock(side_effect=lookup)),
            patch.object(
                workflows, "one", AsyncMock(return_value={"id": uuid4()})
            ),
            patch.object(workflows, "update", AsyncMock()) as update,
        ):
            for actor_id, expected in ((uuid4(), 403), (faculty_id, 409)):
                with self.assertRaises(HTTPException) as error:
                    await workflows.change_response(
                        uuid4(),
                        ChangeDecision(status="approved"),
                        None,
                        {
                            "id": actor_id,
                            "role": "faculty",
                            "institution_id": institution,
                        },
                    )
                self.assertEqual(error.exception.status_code, expected)
            update.assert_not_awaited()

    async def test_csr_restricted_and_team_list_institution_scoped(self):
        with self.assertRaises(HTTPException):
            await workflows.csr(None, {"role": "faculty"})
        actor = {"id": uuid4(), "role": "faculty", "institution_id": uuid4()}
        with patch.object(
            projects, "page", AsyncMock(return_value={"items": []})
        ) as page:
            await projects.teams(None, actor, 25, 0)
            self.assertIn(
                "t.institution_id=:institution", page.await_args.args[1]
            )
            self.assertEqual(
                page.await_args.args[2]["institution"], actor["institution_id"]
            )


if __name__ == "__main__":
    unittest.main()
