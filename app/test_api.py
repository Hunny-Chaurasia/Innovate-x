import reflex as rx

import asyncio
import json as json_module
import unittest
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlsplit
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.api_runtime import (
    API,
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
)
from pydantic import ValidationError

from app.api import api
from app.api_auth import hash_password, verify_password
from app.api_contracts import (
    Credentials,
    FundingDecision,
    FundingInput,
    ProofInput,
    ReviewInput,
    TeamProject,
)
from app.api_core import public_user, serialize, transaction, transition
from app.api_projects import formation_rule
from app.api_uploads import signature_matches
from app.api_workflows import funding_response, review_next

import logging


class ContractTests(unittest.TestCase):
    def test_email_normalization_and_password_preservation(self):
        credentials = Credentials(
            email=" Student@Example.com ", password="  a-long-password  "
        )
        self.assertEqual(credentials.email, "student@example.com")
        self.assertEqual(credentials.password, "  a-long-password  ")

    def test_salted_scrypt(self):
        first = hash_password("sufficiently-long-password")
        second = hash_password("sufficiently-long-password")
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password("sufficiently-long-password", first))
        self.assertFalse(verify_password("incorrect-password", first))
        self.assertFalse(verify_password("sufficiently-long-password", None))

    def test_private_fields_not_serialized(self):
        data = public_user(
            {
                "id": uuid4(),
                "display_name": "Example",
                "email": "private@example.com",
                "password_hash": "secret",
                "session_id": uuid4(),
                "role": "student",
            }
        )
        self.assertNotIn("email", data)
        self.assertNotIn("password_hash", data)
        self.assertNotIn("session_id", data)
        self.assertEqual(
            serialize({"amount": Decimal("1.250000")}), {"amount": "1.250000"}
        )
        self.assertEqual(
            serialize({"nested": {"token_digest": "secret"}}), {"nested": {}}
        )

    def test_funding_validation(self):
        for amount in ["0", "-1", "NaN", "Infinity", "0.0000001"]:
            with (
                self.subTest(amount=amount),
                self.assertRaises(ValidationError),
            ):
                FundingInput(
                    amount_lakh=amount,
                    txn_ref="receipt",
                    transfer_confirmed=True,
                )
        with self.assertRaises(ValidationError):
            FundingInput(amount_lakh="1", txn_ref=" ", transfer_confirmed=True)
        with self.assertRaises(ValidationError):
            FundingDecision(status="confirmed", receipt_confirmed=False)
        with self.assertRaises(ValidationError):
            FundingDecision(status="declined", decline_note="no")
        self.assertTrue(
            FundingDecision(
                status="confirmed", receipt_confirmed=True
            ).receipt_confirmed
        )

    def test_review_and_proof_lengths(self):
        with self.assertRaises(ValidationError):
            ReviewInput(
                summary="short",
                flaws="long enough flaws",
                improvements="long enough improvements",
            )
        with self.assertRaises(ValidationError):
            ProofInput(title="Proof", attachments=[])
        with self.assertRaises(ValidationError):
            ProofInput(
                title="Proof", attachments=[{"url": "javascript://alert(1)"}]
            )
        with self.assertRaises(ValidationError):
            ProofInput(
                title="Proof",
                attachments=[
                    {"source": "upload", "url": "/_upload/someone-elses-file"}
                ],
            )
        proof = ProofInput(
            title="Proof", attachments=[{"url": "example.org/demo"}]
        )
        self.assertEqual(proof.attachments[0].url, "https://example.org/demo")

    def test_formation_matrix(self):
        self.assertEqual(
            formation_rule(
                [
                    {"kind": "School", "institution_id": "a"},
                    {"kind": "School", "institution_id": "a"},
                ]
            ),
            ("faculty", True),
        )
        self.assertEqual(
            formation_rule(
                [
                    {"kind": "School", "institution_id": "a"},
                    {"kind": "School", "institution_id": "b"},
                ]
            ),
            ("student", True),
        )
        self.assertEqual(
            formation_rule(
                [
                    {"kind": "School", "institution_id": "a"},
                    {"kind": "College", "institution_id": "b"},
                ]
            ),
            ("student", False),
        )

    def test_duplicate_members_rejected(self):
        identity = uuid4()
        with self.assertRaises(ValidationError):
            TeamProject(
                name="Team",
                title="Project",
                description="Project description",
                leader_id=identity,
                student_ids=[identity, identity],
                reason="Join our project",
            )

    def test_review_state_machine(self):
        self.assertEqual(
            review_next("open", "changes_done", "student"), "addressed"
        )
        self.assertEqual(
            review_next("addressed", "request_changes", "industry"), "open"
        )
        self.assertEqual(
            review_next("addressed", "resolve", "industry"), "resolved"
        )
        for current, action, role in [
            ("resolved", "comment", "industry"),
            ("open", "resolve", "student"),
            ("open", "changes_done", "industry"),
            ("addressed", "changes_done", "student"),
        ]:
            with (
                self.subTest(current=current, action=action),
                self.assertRaises(HTTPException),
            ):
                review_next(current, action, role)

    def test_terminal_funding(self):
        with self.assertRaises(HTTPException) as raised:
            transition(
                "confirmed",
                "declined",
                {"awaiting_leader": {"confirmed", "declined"}},
            )
        self.assertEqual(raised.exception.status_code, 409)

    def test_upload_signatures(self):
        self.assertTrue(signature_matches("image/png", b"\x89PNG\r\n\x1a\n"))
        self.assertFalse(
            signature_matches("image/png", b"<script>alert(1)</script>")
        )
        self.assertFalse(signature_matches("image/svg+xml", b"<svg></svg>"))


class AuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_designated_leader_cannot_confirm(self):
        actor = {"id": uuid4(), "role": "student"}
        record = {
            "id": uuid4(),
            "leader_id": uuid4(),
            "project_id": uuid4(),
            "status": "awaiting_leader",
        }
        with (
            patch("app.api_workflows.get", AsyncMock(return_value=record)),
            patch(
                "app.api_workflows.project_access",
                AsyncMock(
                    return_value=(
                        {"id": record["project_id"]},
                        {"leader_id": actor["id"]},
                    )
                ),
            ),
            patch("app.api_workflows.update", AsyncMock()) as write,
        ):
            with self.assertRaises(HTTPException) as raised:
                await funding_response(
                    record["id"],
                    FundingDecision(status="confirmed", receipt_confirmed=True),
                    None,
                    actor,
                )
            self.assertEqual(raised.exception.status_code, 403)
            write.assert_not_awaited()

    async def test_double_confirmation_does_not_write(self):
        actor = {"id": uuid4(), "role": "student"}
        record = {
            "id": uuid4(),
            "leader_id": actor["id"],
            "project_id": uuid4(),
            "status": "confirmed",
        }
        with (
            patch("app.api_workflows.get", AsyncMock(return_value=record)),
            patch(
                "app.api_workflows.project_access",
                AsyncMock(return_value=({"id": record["project_id"]}, {})),
            ),
            patch("app.api_workflows.update", AsyncMock()) as write,
        ):
            with self.assertRaises(HTTPException) as raised:
                await funding_response(
                    record["id"],
                    FundingDecision(status="confirmed", receipt_confirmed=True),
                    None,
                    actor,
                )
            self.assertEqual(raised.exception.status_code, 409)
            write.assert_not_awaited()


class TestResponse:
    def __init__(self, messages):
        start = next(m for m in messages if m["type"] == "http.response.start")
        self.status_code = start["status"]
        self.headers = {k.decode(): v.decode() for k, v in start["headers"]}
        self.text = b"".join(
            m.get("body", b"")
            for m in messages
            if m["type"] == "http.response.body"
        ).decode()

    def json(self):
        return json_module.loads(self.text)


class TestClient:
    """Direct ASGI harness; no HTTP framework or optional client package."""

    def __init__(self, application):
        self.application = application

    async def exchange(
        self, method, path, headers=None, json=None, chunks=None
    ):
        parsed = urlsplit(path)
        headers = {k.lower(): v for k, v in (headers or {}).items()}
        if json is not None:
            headers.setdefault("content-type", "application/json")
            chunks = [json_module.dumps(json).encode()]
        chunks = chunks or [b""]
        events = [
            {
                "type": "http.request",
                "body": chunk,
                "more_body": i < len(chunks) - 1,
            }
            for i, chunk in enumerate(chunks)
        ]
        messages = []

        async def receive():
            return events.pop(0) if events else {"type": "http.disconnect"}

        async def send(message):
            messages.append(message)

        await self.application(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "method": method,
                "path": parsed.path,
                "query_string": parsed.query.encode(),
                "headers": [
                    (k.encode(), v.encode()) for k, v in headers.items()
                ],
                "client": ("127.0.0.1", 1234),
            },
            receive,
            send,
        )
        return TestResponse(messages)

    def request(self, method, path, **kwargs):
        return asyncio.run(self.exchange(method, path, **kwargs))

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def options(self, path, **kwargs):
        return self.request("OPTIONS", path, **kwargs)

    def close(self):
        pass


class TransportTests(unittest.TestCase):
    def setUp(self):
        async def no_database():
            yield None

        api.dependency_overrides[transaction] = no_database
        self.client = TestClient(api)

    def tearDown(self):
        self.client.close()
        api.dependency_overrides.clear()

    def test_protected_routes_require_bearer(self):
        for path in [
            "/auth/me",
            "/users",
            "/projects",
            "/funding",
            "/notifications",
            "/admin/audit",
        ]:
            with self.subTest(path=path):
                response = self.client.get(f"/api/v1{path}")
                self.assertEqual(response.status_code, 401)
                self.assertEqual(
                    response.json()["error"]["code"], "unauthorized"
                )
                self.assertEqual(response.headers["cache-control"], "no-store")

    def test_validation_does_not_echo_password(self):
        password = "sensitive-but-short"
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "bad", "password": password, "unexpected": "secret"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(password, response.text)
        self.assertNotIn("secret", response.text)

    def test_openapi_registered(self):
        schema = self.client.get("/api/openapi.json").json()
        for path in [
            "/api/v1/auth/register",
            "/api/v1/projects/{identity}/requests",
            "/api/v1/funding/{identity}/respond",
            "/api/v1/public/portfolios/{slug}",
            "/api/v1/projects/{identity}/proofs/upload",
        ]:
            self.assertIn(path, schema["paths"])

    def test_invalid_parameters(self):
        for path in [
            "/api/v1/users?limit=0",
            "/api/v1/users?limit=101",
            "/api/v1/users?offset=-1",
            "/api/v1/users?offset=100001",
            "/api/v1/users?institution_id=invalid",
            "/api/v1/notifications?unread=invalid",
            "/api/v1/projects/not-a-uuid",
            "/api/v1/projects/not-a-uuid/proofs/upload",
        ]:
            with self.subTest(path=path):
                response = (
                    self.client.get(path)
                    if not path.endswith("upload")
                    else self.client.post(path)
                )
                self.assertEqual(response.status_code, 422)

    def test_malformed_body_and_limits(self):
        for chunks, headers, expected in [
            ([b"{"], {}, 422),
            ([b"x" * 600000, b"x" * 600000], {}, 413),
            ([b"{}"], {"Content-Length": "invalid"}, 400),
            ([b"{}"], {"Content-Length": "1048577"}, 413),
            ([b"{}"], {"Content-Type": "text/plain"}, 415),
        ]:
            response = self.client.post(
                "/api/v1/auth/login", chunks=chunks, headers=headers
            )
            self.assertEqual(response.status_code, expected)
            self.assertEqual(
                response.headers["x-content-type-options"], "nosniff"
            )
            self.assertEqual(
                response.json()["request_id"], response.headers["x-request-id"]
            )

    def test_missing_route_and_wrong_method(self):
        self.assertEqual(self.client.get("/api/v1/unknown").status_code, 404)
        response = self.client.request("DELETE", "/api/v1/auth/login")
        self.assertEqual(response.status_code, 405)
        self.assertIn("POST", response.headers["allow"])

    def test_cors_denied(self):
        response = self.client.options(
            "/api/v1/projects",
            headers={
                "Origin": "https://untrusted.invalid",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)
        response = self.client.options(
            "/api/v1/projects",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-unapproved",
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_cors_preflight(self):
        response = self.client.options(
            "/api/v1/projects",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )


class BootstrapTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = AsyncMock()
        self.count = 0
        self.writes = []

        async def database():
            yield self.db

        async def read(db, sql, params=None):
            self.assertIs(db, self.db)
            if sql == "SELECT count(*) AS n FROM users":
                lock = self.db.execute.await_args_list[-1]
                self.assertIn("pg_advisory_xact_lock", str(lock.args[0]))
                self.assertEqual(
                    lock.args[1], {"key": "auth:first-account-bootstrap"}
                )
                return {"n": self.count}
            self.assertIn("max(virtual_id_sequence)", sql)
            return {"n": 1}

        async def write(db, table, values):
            self.assertIs(db, self.db)
            self.writes.append((table, values))
            if table == "users":
                self.count += 1
            return {"id": uuid4(), **values}

        api.dependency_overrides[transaction] = database
        self.addCleanup(api.dependency_overrides.clear)
        for target, replacement in [
            ("app.api_auth.throttle", AsyncMock()),
            ("app.api_auth.one", AsyncMock(side_effect=read)),
            ("app.api_auth.insert", AsyncMock(side_effect=write)),
            ("app.api_auth.audit", AsyncMock()),
            ("app.api_auth.hash_password", MagicMock(return_value="hashed")),
            ("app.api_auth.get", AsyncMock(return_value={"is_active": True})),
        ]:
            patcher = patch(target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(api)

    async def signup(self, role, institution=None):
        return await self.client.exchange(
            "POST",
            "/api/v1/auth/register",
            json={
                "email": "registration@example.test",
                "password": "sufficiently-long-password",
                "display_name": "Registration test",
                "role": role,
                "institution_id": institution,
            },
        )

    async def test_first_admin_returns_normal_session_and_adm_id(self):
        response = await self.signup("admin")
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["user"]["role"], "admin")
        self.assertIsNone(data["user"]["institution_id"])
        self.assertRegex(data["user"]["virtual_id"], r"^ADM-\d{4}-0001$")
        self.assertEqual(data["token_type"], "bearer")
        self.assertTrue(data["access_token"])
        self.assertTrue(data["expires_at"])
        self.assertEqual(
            [table for table, _ in self.writes], ["users", "user_sessions"]
        )
        self.assertNotIn("password_hash", data["user"])
        self.assertEqual((await self.signup("admin")).status_code, 403)
        self.assertEqual(self.count, 1)

    async def test_wrong_first_roles_rejected_without_writes(self):
        for role in ("student", "faculty", "industry", "mentor"):
            with self.subTest(role=role):
                response = await self.signup(role, str(uuid4()))
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["error"]["code"], "forbidden")
                self.assertIn(
                    "first account", response.json()["error"]["message"]
                )
        self.assertEqual(self.writes, [])

    async def test_post_bootstrap_privileged_roles_rejected(self):
        self.count = 1
        for role in ("admin", "faculty", "industry", "mentor"):
            with self.subTest(role=role):
                response = await self.signup(role)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["error"]["code"], "forbidden")
        self.assertEqual(self.writes, [])

    async def test_post_bootstrap_student_requires_institution(self):
        self.count = 1
        response = await self.signup("student")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["error"]["message"], "An institution is required"
        )
        self.assertEqual(self.writes, [])
        response = await self.signup("student", str(uuid4()))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["user"]["role"], "student")


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_expected_http_error_unwinds_transaction_without_logging(
        self,
    ):
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        boundary = AsyncMock()
        boundary.__aexit__.return_value = False
        session.begin.return_value = boundary
        failure = HTTPException(403, {"code": "forbidden", "message": "Denied"})
        with (
            patch("app.api_core.rx.asession", return_value=session),
            patch("app.api_core.logging.exception") as log,
        ):
            with self.assertRaises(HTTPException) as raised:
                async with asynccontextmanager(transaction)() as db:
                    self.assertIs(db, session)
                    raise failure
            self.assertIs(raised.exception, failure)
            boundary.__aexit__.assert_awaited_once()
            exit_args = boundary.__aexit__.await_args.args
            self.assertIs(exit_args[0], HTTPException)
            self.assertIs(exit_args[1], failure)
            self.assertIsNotNone(exit_args[2])
            session.__aexit__.assert_awaited_once()
            log.assert_not_called()

    async def test_dependency_lifecycle_and_commit_failure(self):
        application = API("test", "1", [])
        router = APIRouter(prefix="/api")
        events = []
        commit_failure = False

        async def unit_of_work():
            events.append("begin")
            try:
                yield object()
                if commit_failure:
                    raise HTTPException(
                        503,
                        {"code": "database_unavailable", "message": "Retry"},
                    )
                events.append("commit")
            except Exception:
                logging.exception("Unexpected error")
                events.append("rollback")
                raise
            finally:
                events.append("close")

        async def nested(db: Annotated[object, Depends(unit_of_work)]):
            return db

        @router.post("/transaction", status_code=201)
        async def handler(
            db: Annotated[object, Depends(unit_of_work)],
            other: Annotated[object, Depends(nested)],
            fail: bool = False,
        ):
            self.assertIs(db, other)
            if fail:
                raise HTTPException(409, "Conflict")
            return {"data": "ok"}

        application.include_router(router)
        client = TestClient(application)
        response = await client.exchange("POST", "/api/transaction")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(events, ["begin", "commit", "close"])
        events.clear()
        response = await client.exchange("POST", "/api/transaction?fail=true")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(events, ["begin", "rollback", "close"])
        events.clear()
        commit_failure = True
        response = await client.exchange("POST", "/api/transaction")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(events, ["begin", "rollback", "close"])

    async def test_transformer_preserves_reflex_scopes(self):
        scopes = []

        async def fallback(scope, receive, send):
            scopes.append(scope)

        wrapped = api(fallback)
        for scope in [
            {"type": "http", "path": "/ping"},
            {"type": "http", "path": "/_upload/file"},
            {"type": "websocket", "path": "/_event"},
            {"type": "lifespan"},
        ]:
            await wrapped(scope, AsyncMock(), AsyncMock())
        self.assertEqual(len(scopes), 4)
        response = await TestClient(wrapped).exchange(
            "GET", "/api/openapi.json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(scopes), 4)

    async def test_stream_and_query_defaults(self):
        application = API("test", "1", [])
        router = APIRouter(prefix="/api")

        @router.post("/stream")
        async def stream(
            request: Request,
            title: str = Query(min_length=3),
            count: int = Query(default=25, ge=1, le=100),
        ):
            data = bytearray()
            async for chunk in request.stream():
                data.extend(chunk)
            return {
                "data": {"title": title, "count": count, "bytes": len(data)}
            }

        application.include_router(router)
        client = TestClient(application)
        response = await client.exchange(
            "POST", "/api/stream?title=Proof", chunks=[b"abc", b"def"]
        )
        self.assertEqual(
            response.json()["data"], {"title": "Proof", "count": 25, "bytes": 6}
        )
        self.assertEqual(
            (await client.exchange("POST", "/api/stream")).status_code, 422
        )
        self.assertEqual(
            (
                await client.exchange(
                    "POST", "/api/stream?title=Proof&count=101"
                )
            ).status_code,
            422,
        )

    async def test_static_precedence_and_safe_server_errors(self):
        application = API("test", "1", ["http://localhost:5173"])
        router = APIRouter(prefix="/api")

        @router.get("/items/{identity}")
        async def dynamic(identity: str):
            return {"data": identity}

        @router.get("/items/current")
        async def current():
            return {"data": "static"}

        @router.get("/broken")
        async def broken():
            raise RuntimeError("private error text")

        application.include_router(router)
        client = TestClient(application)
        self.assertEqual(
            (await client.exchange("GET", "/api/items/current")).json()["data"],
            "static",
        )
        response = await client.exchange(
            "GET", "/api/broken", headers={"Origin": "http://localhost:5173"}
        )
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private error text", response.text)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )


if __name__ == "__main__":
    unittest.main()
