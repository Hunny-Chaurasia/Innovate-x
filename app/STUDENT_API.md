# InnovateX role API overlay · version 4

The student, faculty, industry, and public portfolio experiences use the API rather than browser demo records. The archive remains the source of the original branding, DM Sans typography, CSS variables, and shared role shells. Generated frontend files should not be edited as the source of truth: edit the versioned overlay templates instead.

## Local frontend development

Set `VITE_API_URL` to the API base URL **including `/api/v1`**. If omitted, requests use `/api/v1` on the frontend origin. This is a public browser setting, not a place for credentials or API secrets. Use an API origin permitted by the server's browser-origin policy.

From the restored `frontend` directory, install the package dependencies and run `npm run dev`. Run `npm run typecheck` for TypeScript validation and `npm run build` for the production frontend build. The preparation command uses the TypeScript AST to add `await` to retained legacy creation/provisioning handlers; both development and build scripts invoke it. No dependencies are downloaded or builds launched during Python app import.

The Reflex entry point continues to restore the archive on import. This change does not replace that entry point with a React hosting server. The generated React frontend still needs its normal Vite development or build process. Direct browser routes must be handled by the React host, including `/student/...` and `/u/...`.

## Authentication

- Login uses the user's email and password, not a demo role selector.
- Student signup uses the public active-institution chooser and the server-generated Virtual ID.
- First-administrator setup explicitly submits the administrator role. The backend rejects it after any account exists; the client cannot override that rule.
- A student cannot register until an administrator has added their institution.
- Role shells validate the session and redirect users to their actual role. Mentor accounts get an explicit unsupported-workspace screen instead of a redirect loop.
- The only persisted browser value added by this overlay is the session token. Passwords, identities, workflow records, and API response caches are not persisted in localStorage.
- Signing out clears the session even if the revocation request cannot reach the server. A failed offline revocation cannot guarantee remote token revocation; expiry and server revocation remain authoritative.
- Session expiry clears the student workspace; session network failures expose a retry instead of rendering demo data.

## Student workflows

The student dashboard, problem discovery, project/team creation, workspace progress, invitations, review replies, leader-only funding confirmation, proof links, portfolio sharing, and profile/security settings call the existing API. Create-project requests save the project, team and initial invitations atomically; there is no client-generated project identity. Invitations can only be answered by their recipient. Outgoing requests do not have a demo acceptance button.

Data reloads after successful writes, on window focus, and when the document becomes visible. Visible authenticated workspaces poll at 30-second intervals, skip overlapping loads or writes, enforce a 15-second minimum between automatic attempts, and pause after ten minutes without keyboard/pointer activity. Hidden and signed-out tabs do not poll. Focus, visibility, or user activity resumes the active window. This is bounded polling, not a WebSocket-based cross-role subscription. Empty views distinguish lack of records from loading and failed requests. Forms retain drafts on failure and block duplicate submissions while saving. Server authorization, membership state and transition validation remain authoritative, including when permissions change in another browser.

Funding amounts arrive as decimal strings in INR lakhs; the UI formats them for display. Confirmation explicitly requires a receipt checkbox and decline requires a reason. A saved decision is terminal. External opportunity applications are not available from the current API and are not represented as saved applications.

Portfolio sharing defaults private. Enabling and regenerating links use server-issued slugs. The shared-link viewer retrieves only the public portfolio endpoints. Disabling sharing revokes lookup of that portfolio, not files or copies already distributed.

## Evidence and file limits

The student evidence form submits external HTTP(S) links for repository pages, hosted images, and hosted videos. It persists backend proof entries and attachment metadata, not video bytes. It does **not** claim durable large-video-file storage. The backend's separate raw-upload endpoint retains its existing behavior, but this overlay does not expose a file-upload control or manufacture storage metadata. Data URLs, temporary blob URLs, and arbitrary browser file names are not treated as persistent evidence.

## Compatibility boundary

`workflow.ts` exports the archive's documented types and all documented facade names. `workflow.contract.ts` retains the original source solely as a TypeScript type contract; it is imported with `import type`, never evaluated by the integration. The live facade does not load, write, or migrate the former demo workflow localStorage key. Legacy creation/provisioning calls are asynchronous and are prepared by the AST adapter before development/build. Runtime mutations broadcast shared loading/error/update state and refetch server records.

## Industry and faculty workflows

Industry dashboard, discovery, publishing, review inbox, and CSR pages are maintained templates. Project discovery opens a server review visit before showing full details. Closing calls the guarded close endpoint: a structured review or follow-up created during that visit is mandatory. Navigating away does not erase the pending visit; opening the project resumes it. Structured reviews require assessment, flaws, and improvements; strengths are optional. Review authors can comment, request further changes after a student addresses a review, or resolve. Resolved threads are read-only.

Funding submission records an already-completed external transfer and requires an explicit checkbox, decimal amount, and transaction reference. Evidence uses an optional HTTP(S) URL, never a fabricated uploaded filename. History shows actual awaiting/confirmed/declined responses and decline notes. CSR figures come from the aggregate API and distinguish awaiting from confirmed amounts. No patents or startup metrics are invented. Mentor invitation and recipient decision controls use collaboration endpoints. Workshops are explicitly unavailable because there is no scheduling API.

Faculty dashboard and team views show school membership, chosen leader, progress, status and Virtual IDs. Problem briefs support text/domain/unread/shortlist/CSR filtering, server-recorded reads, and persistent shortlist toggles. Registration requires the student's real email and a user-supplied password; the returned Virtual ID is displayed only after server success. No invitation email or password-delivery service is claimed. Same-school formation chooses at least two students, a leader from that selection, a mentor, and a reason. Other compositions remain student-formed. Faculty cannot invite themselves as mentor; mentor acceptance is still required to activate a school-only team.

Institution change decisions are shown only for designated faculty and are validated on the server. Review panels show milestone states and evidence, accept feedback and optional scores, create milestones, and approve/request changes only from submitted state. Faculty access is restricted to their institution. The student workspace Milestones tab lets active members start/resume work and submit milestones for faculty review, and displays returned faculty feedback and scores.

Role forms await responses, keep drafts on validation/permission failures, and refetch collections after writes. If a write succeeds but its refresh fails, the UI explicitly warns not to resubmit. Backend authorization and state transitions remain authoritative if another role changes the record between reads and writes. Browser collections are transient views only, never persistence.

All listed faculty and industry pages, including archived review/action pages, are overlaid. The new industry review route is registered without replacing existing route paths or role shells. Faculty/industry signup routes no longer simulate privileged registration; they direct existing users to sign in and explain administrator provisioning. Legacy funding facade calls fail closed rather than manufacture consent. The facade returns promises and the compatibility adapter awaits all mutation exports. The old workflow contract remains a type-only, non-evaluated compatibility reference. Admin workflows are outside this release. Their archived demo mutation pages are replaced by an explicit unavailable notice inside the existing admin shell, so fake account changes and funding approvals cannot be mistaken for saved operations.

## Restoration guarantees and validation

Restoration validates archive paths, rejects symlinks, overlays from maintained source modules, and writes individual files atomically. The successful marker contains the overlay version and generated content hashes. Older markers do not suppress updates; missing or modified generated files are repaired. A failed restoration raises an error instead of silently leaving an apparently successful installation.

Run `python -m unittest app.test_frontend_restore app.test_role_api app.test_api app.test_models` for archive/overlay guardrails. The tests check restoration, idempotence, obsolete markers, repair, path traversal, facade exports, all role-page replacements, endpoint references, awaited forms, anonymous public requests, and polling guards. Focused backend tests cover faculty provisioning, same-school formation and leader selection, ownership of reviews/visits, mandatory engagement, pending funding, institution changes, panel decision transitions, CSR access, and disabled public shares. These are offline contract/authorization tests with mocked database operations, not a claim of a completed live end-to-end run. TypeScript and browser workflow checks require the frontend dependencies and a running API; they are separate from these Python tests. Before release, exercise separate faculty, industry, and student sessions: publish/shortlist a CSR brief; register students; form a school team; accept a mentor invitation; submit proof; open an industry review visit; submit a review; reply as a student; resolve as its author; record a transfer; confirm as the leader; inspect CSR; submit a milestone from the student workspace and decide it in the faculty panel; approve/decline institution changes; enable, regenerate and disable a public share. Verify public projects and proof metadata anonymously, reload all accounts, and verify persistence plus denied foreign-school, foreign-reviewer and non-leader writes. Neither the Python tests nor a static typecheck substitute for that end-to-end acceptance.
