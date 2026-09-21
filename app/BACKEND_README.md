# InnovateX backend API

This phase supplies the API only. The existing page and React frontend are unchanged. A self-contained API catalog viewer is at `/api/docs`; the machine-readable OpenAPI 3.1 request/response catalog is `/api/openapi.json`. The viewer requires no external scripts and does not submit authenticated requests. All business routes below begin with `/api/v1`.

## HTTP compatibility

The HTTP layer uses an app-owned ASGI runtime, with Python's standard library and the existing Pydantic contracts. It does not import FastAPI or Starlette. Reflex remains responsible for its own transitive HTTP dependencies; there is no explicit Starlette version pin. This removes the incompatible FastAPI constraint rather than downgrading Reflex's required dependencies. The PostgreSQL driver remains necessary for the existing database transactions.

The runtime is both a three-argument ASGI callable and a synchronous callable transformer accepted by Reflex. API requests are handled by the existing endpoint functions. Other HTTP routes, WebSockets and lifespan events pass through unchanged to the wrapped application. No UI, schema or migration changes are part of this repair.

Routing preserves GET, POST, PUT, PATCH and DELETE registrations and their success codes. Static paths take precedence over parameterized paths. UUID path/query values, booleans, pagination bounds, required upload query fields and JSON bodies are validated through Pydantic. Repeated scalar query parameters use the last value. Missing routes return 404; unsupported methods return 405 with an Allow header. JSON endpoints accept application/json and application/*+json; incompatible media types return 415. Malformed JSON returns a sanitized 422 error.

Dependencies are cached per request: authentication and the endpoint share one transaction. Async dependency contexts remain open through handler execution, response validation and JSON encoding. They commit before any success response is sent; handler, authorization, serialization and commit failures unwind the contexts before returning an error. Existing database conflict/unavailability mappings and the separately committed authentication throttle are retained.

Request size checks apply to both declared lengths and actual streamed bytes: normal bodies are limited to 1 MiB, raw proof uploads to 100 MiB, with the existing stricter per-media upload limits retained. Interrupted streams fail rather than accepting partial evidence. Security headers and exact-origin CORS apply to errors as well as successes, including denied preflights and unexpected exceptions. Validation responses omit submitted values and validator contexts.

After updating dependencies, use a clean environment or reinstall from the requirements and check dependency consistency. An old environment retaining incompatible packages is not repaired merely by editing a requirements file.

## Client contract

- Send JSON with `Content-Type: application/json`, except the raw-file upload route.
- Authenticated calls require `Authorization: Bearer <access_token>`. No cookie authentication is used.
- Successful single-resource operations return `{ "data": ... }`. Lists return `{ "items": [...], "total": 0, "limit": 25, "offset": 0 }`.
- UUIDs are strings; timestamps are ISO 8601 UTC strings. Money and decimal scores are decimal **strings**, avoiding financial precision loss in JavaScript. Funding units are INR lakhs, not rupees.
- List routes accept `limit` (1–100, default 25) and `offset` (0–100000). Ordering is newest first, with ID as a deterministic tie-breaker. Filters are applied before pagination/counting.
- Unknown input fields are rejected. Treat workflow status strings as case-sensitive literals. Request schemas and accepted enum values are enumerated in OpenAPI.
- Errors have `{ "error": { "code": "...", "message": "...", "details": [] }, "request_id": "..." }`. Validation details contain field paths, messages and error types, never submitted values.
- Status codes: 401 missing/expired session; 403 forbidden role/ownership; 404 missing resource; 409 conflict or invalid transition; 413 oversized body; 415 unsupported media; 422 invalid input; 429 authentication throttling; 503 temporary database failure.
- API responses are `no-store`. `X-Request-ID` supports support-ticket correlation. A 401 includes a Bearer authentication challenge; a 429 includes `Retry-After`.
- Browser CORS is an exact-origin allowlist, including standard Vite local development origins. Wildcard origins and credentialed cookies are not enabled. Non-browser callers must still authenticate; CORS is not authorization.

## Authentication and identities

| Method | Route | Contract / access |
|---|---|---|
| POST | `/auth/register` | First account must explicitly request role=admin; no institution required. After any user exists, public registration is student-only with institution_id required. Returns token, expiry and current user. |
| POST | `/auth/login` | Email/password; returns access_token, token_type, expires_at and user. |
| GET | `/auth/me` | Current public profile plus the caller's own email. |
| POST | `/auth/logout` | Revoke this session. |
| POST | `/auth/logout-all` | Revoke all caller sessions. |
| POST | `/auth/password` | current_password, new_password; revokes all sessions, requiring login again. |
| GET | `/users` | Authenticated contact directory; q, role and institution_id filters. Does not expose emails. |
| GET | `/users/{id}` | Safe directory profile. |
| POST | `/users` | Admin registers any role. Faculty registers students only in their own institution. Uses registration fields. No automatically returned session for another user. |
| PATCH | `/users/me` | display_name, bio, department, linkedin_url. Does not permit role/institution mutation. |
| POST | `/users/me/deletion-request` | Records a request, not immediate irreversible deletion. |
| PATCH | `/users/{id}/status` | Admin: active/suspended, cannot suspend self; suspension revokes sessions. |
| GET | `/institutions` | Public active institution chooser; q filter. |
| POST | `/institutions` | Admin creates an institution. |
| PATCH | `/institutions/{id}` | Admin updates details, not the institution type. |

Passwords are 12–128 characters and are never trimmed. Emails are trimmed and lowercased before uniqueness checks. Password derivation uses standard-library scrypt with a new 32-byte salt for every password. Opaque session tokens have 48 random bytes; only their SHA-256 digest is retained. Sessions expire after 12 hours and are checked for revocation and active account status on every authenticated request. Authentication attempts consume a durable 15-minute rate allowance, including failed logins. Invalid login responses do not distinguish nonexistent users from incorrect passwords.

Virtual IDs use `STU/FAC/IND/MEN/ADM-YYYY-NNNN`. Each role's sequence is the maximum existing sequence plus one, independently of year. Concurrent allocations are serialized. On an empty database, public registration accepts only an explicit admin role and returns an ADM Virtual ID and the normal session response. A transaction-scoped PostgreSQL advisory lock serializes the user count check and account/session creation through commit or rollback, preventing simultaneous public signups from both becoming the first administrator. Once any user exists, public signup is student-only and requires an institution; admin/faculty controlled provisioning is unchanged. There is no default account. Expected HTTP errors still unwind and roll back transactions without being logged as unexpected transaction failures. Email verification, forgotten-password email delivery and identity-provider integration are not claimed by these endpoints.

## Problems, projects, teams and invitations

| Method | Route | Contract / access |
|---|---|---|
| GET | `/problems` | q, domain, source and view=all/new/shortlisted/csr; faculty-only new/shortlisted views. Drafts are visible only to their publisher/admin. |
| POST | `/problems` | Industry: title, description, domain, source, csr, tags, status=draft/published, deadline. Tags are normalized and deduplicated. |
| GET | `/problems/{id}` | Brief with tags; faculty reads mark the problem seen. |
| POST | `/problems/{id}/status` | Publisher: draft→published→closed/archived; closed→archived. |
| PUT | `/problems/{id}/shortlist` | Faculty: shortlisted boolean; idempotently keeps seen/shortlist timestamps. |
| POST | `/projects` | Atomic project + team creation. name, title, description, category, problem_id?, leader_id, student_ids, mentor_id?, reason. student_ids includes leader and contains 2–50 distinct students. |
| GET | `/projects` | Accessible project summaries; q and stage (including Funded) filters. |
| GET | `/projects/{id}` | Member/assigned mentor/institution faculty/admin workspace. Industry uses review visits instead. |
| PATCH | `/projects/{id}` | Student leader: title, description, stage, progress. Forward stage transitions only; completed requires progress 100. |
| GET | `/teams` | Teams created by or joined/invited to the caller. |
| GET | `/teams/{id}/memberships` | Authorized workspace membership list. |
| POST | `/memberships/{id}/status` | Self leave or leader removal: status=Left/Removed. Leader cannot leave/be removed. |
| POST | `/projects/{id}/requests` | Leader or team-forming faculty invites members/mentors. Industry may request a mentor. recipient_id, kind=member/mentor, reason. |
| GET | `/requests` | Caller inbox/outbox; status and direction=incoming/outgoing filters. |
| POST | `/requests/{id}/respond` | Recipient only: accepted/declined plus optional note. Accept creates membership/mentor assignment atomically. |
| GET | `/projects/{id}/activity` | Authorized paginated activity history. |

Same-school teams can only be formed by that school's faculty. College teams and cross-institution teams are student-formed, and their creator must be leader. Faculty school formation directly enrolls the chosen students; student-created teams issue invitations. School-only teams must select a mentor. A selected mentor receives a request and is not silently treated as consenting.

Teams remain `forming` until at least two students are members, actual membership obeys the formation rule, and school-only teams have an accepted mentor. A declined invitation or member departure can return a team to forming. Project progression, proof submission, milestone submission and funding require an active team. A declined mentor request can be replaced with another request. Pending/member duplicates, duplicate mentor requests and non-student member invites are rejected.

## Reviews and mandatory review visits

| Method | Route | Contract / access |
|---|---|---|
| POST | `/projects/{id}/views` | Industry opens a durable review visit; returns view_id, review_required and project details. Reuses an unclosed visit. |
| POST | `/projects/{id}/views/close` | Industry supplies view_id; rejected until that reviewer adds a review/follow-up after opening the visit. |
| POST | `/projects/{id}/reviews` | Industry: summary, flaws, improvements (minimum 10 each), optional strengths. |
| GET | `/projects/{id}/reviews` | Authorized project reviews; status filter. |
| GET | `/reviews` | Reviewer's or student's review inbox; status filter. |
| GET | `/reviews/{id}/replies` | Authorized paginated thread; newest first. |
| POST | `/reviews/{id}/replies` | body and action=comment/changes_done/request_changes/resolve. |

A team student may comment or mark open→addressed. Only the original industry reviewer may follow up, request addressed→open or resolve open/addressed→resolved. Resolved threads are terminal/read-only; a new visit can submit a new review. Every reply requires nonempty text. Clients must use the visit-close endpoint before dismissing their view. The API enforces closure but cannot prevent a browser tab from being terminated; an abandoned visit remains outstanding.

## Proof of work and attachments

| Method | Route | Contract / access |
|---|---|---|
| POST | `/projects/{id}/proofs` | Active-team students: title, description, 1–30 external attachment objects. Each has kind=image/link/video, url, optional name, source=external. |
| POST | `/projects/{id}/proofs/upload` | Active-team students: raw binary request with actual media Content-Type and query parameters title, description?, filename?. Creates a proof and its uploaded attachment. No multipart wrapper. |
| GET | `/projects/{id}/proofs` | Authorized proof list with safe attachment metadata. |
| DELETE | `/proofs/{id}` | Current member who authored the proof; soft deletion. |

Proof titles require three characters. External HTTP(S) links are normalized, with HTTPS added when omitted; credentials and non-HTTP protocols are rejected. Arbitrary client claims about uploaded files are not trusted. Upload metadata (storage identity, checksum, actual byte count and MIME type) is generated by the upload endpoint. Images are capped at 2 MB and videos at 100 MB, including streamed requests. Supported image types are JPEG, PNG, GIF and WebP; video types are MP4, QuickTime, WebM and Ogg. Headers are checked against signatures; SVG/executable payloads are not accepted. URLs are returned for rendering, with storage keys omitted from responses.

These checks are not a malware scanning service. Upload cancellation or a commit failure may require operational orphan-file cleanup; deleted proofs do not immediately erase bytes shared by an existing URL. A public portfolio toggle revokes portfolio lookup, not copies or previously distributed attachment URLs. Clients should not upload confidential material as public project evidence.

## Funding

| Method | Route | Contract / access |
|---|---|---|
| POST | `/projects/{id}/funding` | Industry: amount_lakh decimal string, txn_ref, transfer_confirmed=true, proof_file_name?, proof_url?. Creates awaiting_leader. |
| GET | `/funding` | Funder, current team members or admin; status/project_id filters. Transaction references are not in the public portfolio. |
| POST | `/funding/{id}/respond` | Designated current student leader only: status=confirmed/declined, receipt_confirmed, decline_note. |
| POST | `/admin/funding/{id}/verify` | Admin: status=verified/rejected and note (minimum five characters); leader-confirmed records only. |

Amounts must be finite, greater than zero and have at most six fractional digits. Transfer reference and transfer confirmation are mandatory. Receipt confirmation is mandatory for approval; decline requires at least five characters and no receipt confirmation. Both decisions are terminal. Admin verification never substitutes for the student's receipt decision. A new funding record cannot overtake one awaiting leader approval. The displayed Funded stage derives from the **latest** funding record by timestamp/ID, and never overwrites the project's actual development stage.

## Faculty, portfolio, notifications and reporting

| Method | Route | Contract / access |
|---|---|---|
| POST | `/institution-changes` | Student: to_institution_id, faculty_id, reason. Faculty must belong to destination institution. |
| GET | `/institution-changes` | Student or assigned faculty; status filter. |
| POST | `/institution-changes/{id}/respond` | Assigned destination faculty: approved/declined, note. |
| POST | `/projects/{id}/milestones` | Leader or same-institution faculty: title, description, position, due_at. |
| GET | `/projects/{id}/milestones` | Authorized workspace. |
| POST | `/milestones/{id}/status` | Team student: in_progress/submitted. pending→in_progress→submitted; changes_requested→in_progress/submitted. |
| POST | `/projects/{id}/panel-feedback` | Same-institution faculty: body, milestone_id?, decision=feedback/changes_requested/approved, score?. Decisions require a submitted milestone in that project. |
| GET | `/projects/{id}/panel-feedback` | Authorized workspace. |
| GET | `/portfolio/share` | Student's current share settings or null. |
| PUT | `/portfolio/share` | Student: enabled, regenerate=false. Regeneration revokes the prior URL. |
| GET | `/public/portfolios/{slug}` | No login; only enabled, unrevoked shares of active owners. Safe profile and paginated projects. |
| GET | `/public/portfolios/{slug}/projects/{id}/proofs` | No login; validates share and owner membership before returning proof metadata. |
| GET | `/notifications` | Recipient only; unread boolean filter. |
| POST | `/notifications/{id}/read` | Recipient-only idempotent read. |
| POST | `/notifications/read-all` | Marks caller's unread notifications read. |
| GET | `/csr/summary` | Industry's own CSR funding or aggregate for admin. |
| GET | `/admin/audit` | Admin-only event history; optional action filter. |

Institution changes do not silently rewrite the composition of existing teams. Approval is blocked while the student has invited/member memberships; resolving those memberships is required first. Leadership transfer and team archival are not included in this phase, so a leader's institution change needs a later administrative resolution workflow rather than bypassing this guard.

Portfolio sharing defaults private. Responses never expose emails, password hashes, sessions, transaction references, private review discussions or other members' personal contact information. Private, revoked and unknown slugs all yield an unavailable response.

Notifications accompany invitation responses, review discussions, funding decisions, institution changes and milestones. They are durable in-app notifications; email/push delivery is not included. CSR counts and amounts are computed from actual CSR-linked funding records. Patents and startups return null because no supported source records exist; the API does not fabricate those metrics.

## Validation and test coverage

`app/test_api.py` includes offline password hashing, validation, formation-matrix, review-transition, funding authorization, upload signature, route registration, unauthenticated-access and CORS tests. Its direct ASGI harness uses no FastAPI/Starlette test client or optional HTTP client dependency. Transport coverage includes malformed JSON, streamed body limits, UUID/query validation, required upload parameters, method errors, static route precedence, error sanitization and denied preflights. Runtime tests cover shared dependency identity, commit/rollback/cleanup ordering, commit failures, raw streaming and pass-through of Reflex HTTP/WebSocket/lifespan scopes. `app/test_models.py` retains the schema guardrails. Run the unittest modules in the application's Python environment.

Focused bootstrap tests cover first-admin identity/session responses, lock-before-count ordering, wrong-first-role rejection, subsequent privileged-role rejection, and the continuing student institution requirement. A transaction regression test checks expected HTTP exception propagation and context unwinding without unexpected-error logging. These tests use mocked database operations and are not a claim of live database/concurrency certification. Before production release, integration acceptance should exercise simultaneous per-role registrations, duplicate emails, competing funding responses, invitation races, share regeneration, rollback/notification atomicity, expiry/revocation, cross-user authorization and actual upload limits against a disposable managed test database. No test or application route initializes tables or runs migrations.
