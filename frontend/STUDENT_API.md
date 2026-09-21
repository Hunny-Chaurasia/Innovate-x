# Student API overlay

The student experience uses the authenticated API rather than browser demo records. The archive remains the source of the original branding, DM Sans typography, CSS variables, shared role shells, and non-student workflow pages. Generated frontend files should not be edited as the source of truth: edit the versioned overlay templates instead.

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

Data reloads after successful writes and on window focus. There is no claim of a WebSocket-based cross-role subscription. Empty views distinguish lack of records from loading and failed requests. Forms retain drafts on failure and block duplicate submissions while saving. Server authorization, membership state and transition validation remain authoritative, including when permissions change in another browser.

Funding amounts arrive as decimal strings in INR lakhs; the UI formats them for display. Confirmation explicitly requires a receipt checkbox and decline requires a reason. A saved decision is terminal. External opportunity applications are not available from the current API and are not represented as saved applications.

Portfolio sharing defaults private. Enabling and regenerating links use server-issued slugs. The shared-link viewer retrieves only the public portfolio endpoints. Disabling sharing revokes lookup of that portfolio, not files or copies already distributed.

## Evidence and file limits

The student evidence form submits external HTTP(S) links for repository pages, hosted images, and hosted videos. It persists backend proof entries and attachment metadata, not video bytes. It does **not** claim durable large-video-file storage. The backend's separate raw-upload endpoint retains its existing behavior, but this overlay does not expose a file-upload control or manufacture storage metadata. Data URLs, temporary blob URLs, and arbitrary browser file names are not treated as persistent evidence.

## Compatibility boundary

`workflow.ts` exports the archive's documented types and all documented facade names. `workflow.contract.ts` retains the original source solely as a TypeScript type contract; it is imported with `import type`, never evaluated by the integration. The live facade does not load, write, or migrate the former demo workflow localStorage key. Legacy creation/provisioning calls are asynchronous and are prepared by the AST adapter before development/build. Runtime mutations broadcast shared loading/error/update state and refetch server records.

Industry and faculty workflow pages remain archive-owned in this phase. Their shared facade no longer performs local demo mutations; complete role-specific form validation, payload adaptation and workflow UX for those pages remain the next checklist item. In particular, legacy faculty registration forms must supply the real email/password registration contract before they can provision users successfully. No default credentials are invented for them. Admin workflow pages also remain archive-owned; first-admin registration is not a claim that those admin pages have been integrated.

## Restoration guarantees and validation

Restoration validates archive paths, rejects symlinks, overlays from maintained source modules, and writes individual files atomically. The successful marker contains the overlay version and generated content hashes. Older markers do not suppress updates; missing or modified generated files are repaired. A failed restoration raises an error instead of silently leaving an apparently successful installation.

Run `python -m unittest app.test_frontend_restore` for archive/overlay guardrails. The tests check restoration, idempotence, obsolete markers, repair, path traversal, exports and scope preservation. TypeScript and browser workflow checks require the frontend dependencies and a running API; they are separate from these Python tests. Before release, exercise two student sessions through invitation acceptance, active-team proof submission, review replies and funding confirmation, then reload each account and verify persistence and denied cross-user writes. Neither the Python tests nor a static typecheck substitute for that end-to-end acceptance.
