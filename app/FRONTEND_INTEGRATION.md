# Role integration: restoration and maintained templates

## Checklist items three and four: implemented

The maintained student integration connects authentication, all nine student pages, and public portfolios to the API while retaining InnovateX’s existing role shells and route registration. The shared workflow entry point is now an API-backed compatibility facade, not the archive’s browser-persisted demo store. The maintained industry and faculty experiences now replace every existing business route page with a thin role-page wrapper. Existing route declarations and navigation shells remain intact, with DM Sans, dark compact panels, amber industry accents and emerald faculty accents.

The facade preserves the exact 49-name archive export contract, including the original types through type-only imports. It broadcasts refresh, pending and error state, uses API reads and writes, and never imports mock problems or reads, migrates or writes workflow localStorage. Original workflow source is preserved in `workflow.contract.ts` exclusively for compile-time compatibility.

## Restoration

`restore_frontend()` runs before Reflex app construction. It reads the original ZIP and maintained text templates, restores source into `frontend/`, and writes a versioned checksum manifest. No npm command, dependency installation, JavaScript process, or build runs during import.

Run restoration explicitly with `python -m app.frontend_restore`. Keep source edits in these maintained templates, not generated files:

- `frontend_api.txt`: transport, wire types, session operations and safe external links.
- `frontend_ui.txt`: async resources, forms, pagination and feedback.
- `frontend_student.txt`: student pages, project workspaces, proof links, and public portfolios.
- `frontend_industry.txt`: audited project discovery, structured reviews, transfer recording, problem publishing, invitations and CSR metrics; shared role summary, invitation and project header components.
- `frontend_faculty.txt`: institution dashboard, student registration, school formation, problem shortlists, institution decisions, milestone review and panel feedback.
- `frontend_app.txt`: authentication gate around the archive's App and its existing shells.
- `frontend_workflow.txt`: maintained API-backed workflow facade and original export surface.
- `frontend_compat.py`: exact archive export guard, shell identity replacement, and deterministic async caller adaptation.

Restoration preserves original assets, installs the API-backed workflow module, preserves its original source as `src/store/workflow.contract.ts`, and retains route registration in `src/App.archive.tsx`. It explicitly replaces the known `MOCK_USERS` import and all four shell uses with authenticated shell-user lookups. Changed imports, unrecognized identity uses, changed workflow exports, or missing student overlays fail restoration rather than silently retaining demo behavior. Shell identity carries display name, Virtual ID, institution, role and avatar fields; login, registration and session validation set it, and logout clears it.

All nine default-export student pages are required. Version three also requires the exact four industry and five faculty page paths and a default export in each. Missing, additional or non-default-export role pages fail clearly before managed files are written. The checksum manifest records per-role overlays, refresh policy, exports, adapted callers, identity mode and full-source typecheck scope. The ZIP is never modified. Repeated restoration preserves unchanged modification times and repairs modified managed files.

Archive entries are validated before extraction: absolute/traversal/backslash paths, symlinks, duplicate destinations and oversized source archives are rejected. Dependency/build/cache folders and private developer environment files are excluded. Destination symlinks are rejected. An interprocess lock serializes restoration; individual file writes are atomic. The version manifest is written last. This is file-level atomicity, not a transactional directory swap. Stop serving the frontend while upgrading templates. The working directory is assumed to be operator-controlled, not writable by untrusted users.

## React development

The React frontend remains a separate Vite application. Restoration does not make Reflex serve the Vite development server or its build, and the existing Reflex index is not the React UI.

After restoration, install the archive's dependencies explicitly using its package manager and inspect its scripts. Do not copy archived node_modules into a real installation. Use a supported Node version compatible with the restored package's requirements.

The generated `.env.example` contains `VITE_API_URL=/api/v1`. This value is a public API base address, not a credential. Use the same-origin `/api/v1` path when your development environment forwards API traffic; otherwise set the public API base URL including `/api/v1` in your local Vite environment. A changed Vite environment value requires restarting Vite. No secrets should be placed in any VITE variable.

After installing dependencies, run `npx tsc -p tsconfig.student.json`. Despite its retained filename, this configuration includes the entire generated `src`, including retained pages, shells, the archive type contract, and maintained overlays. It uses bundler resolution, React JSX and compile-safe settings for the supplied project. Run the archive’s production build as well. The original role roots are `/student`, `/faculty`, `/industry` and `/admin`; continuation links use the actual role root, not an invented dashboard route. Public `/u/:slug` lookup precedes the authentication gate, supports the router URL convention and deliberately omits bearer credentials.

## Implemented client behaviors

- JSON `/api/v1` transport with typed wire records, 20-second timeout, omitted cookies, rejected HTTP redirects, structured backend errors and field messages.
- Only bearer token and expiry persist in tab-scoped sessionStorage, with memory fallback if storage is unavailable. Profile/project data do not persist in these templates.
- Login, student registration, explicit first-admin bootstrap, logout, session validation, expiry checks and role gating. Admin/mentor workspaces display a truthful unsupported-workspace state instead of a demo dashboard.
- Public institution and portfolio calls deliberately omit bearer headers and do not clear a private session on public errors.
- Student Dashboard, Discover, My Projects/workspace, New Project, Action Center, Reviews, Funding, Portfolio and Settings are backed by API reads/writes. Project creation uses one atomic backend request for the project, team and initial invitations.
- Membership changes, member/mentor requests, recipient-only decisions, leader-only funding receipt decisions, structured review replies, external evidence, profile/password changes, institution-change requests, account-deletion requests, notification reads, public/private sharing and link regeneration.
- Resources reload after writes and on focus/visibility return. One page-level 30-second timer refreshes while visible and active within the last two minutes (pointer, keyboard or scroll activity). It stops doing work while hidden or idle and is cleaned up on unmount. This is bounded polling, not WebSockets.
- Background refresh keeps already-loaded components mounted, preserving form drafts and current errors. Changed resource keys load fresh data. Forms await returned writes, retain inputs after failure, block in-flight duplicates and disable repeated successful submissions until an input changes. Structured permission, validation and conflict messages remain visible. Writes are never automatically retried; a timed-out write may have committed.
- Industry project detail is opened only by an explicit audited visit. Closing awaits server verification of a structured review or follow-up during the visit; navigating away does not fabricate a close. Reopening resumes an outstanding visit. Review actions respect author ownership and terminal states. Funding requires a checked transfer confirmation, reference and durable HTTP(S) proof URL; the leader still confirms receipt separately.
- Faculty student creation requires actual email/password input and displays the returned Virtual ID. Same-school formation selects 2–50 students, a selected student leader, a mentor and an optional published problem. The server remains authoritative for formation and institution scope. Institution team lists now include all teams at the faculty institution, not only teams created by that faculty.
- Faculty problem reads explicitly mark the brief read; shortlist actions send the desired boolean. Panel decisions target submitted milestones; project-wide feedback cannot approve a milestone. Scores and feedback are API-backed. CSR metrics distinguish leader-confirmed and awaiting amounts; unsupported patent/startup metrics are not fabricated.
- List views provide server-side pagination; contact search supports paginated student/faculty selection. The workflow compatibility facade follows paginated API lists rather than seeding demo records.

## Evidence and public links

Only external HTTP(S) image, repository and video links plus backend metadata are submitted by these templates. No data URLs, object URLs or large binary video persistence are claimed. Evidence renders as safe external links, without third-party iframe execution. Public portfolio lookup is server-backed; private and revoked slugs are unavailable. Disabling sharing cannot retract evidence URLs already copied elsewhere.

## Validation

Run `python -m unittest app.test_api app.test_models app.test_frontend_restore app.test_role_api` in the application environment, followed by the full-source TypeScript check and frontend build. Restoration tests cover archive exports, all nine overlays, shell identity replacement, unchanged route declarations, type-only contract preservation, absence of live workflow demo persistence, public unauthenticated portfolio behavior, async adaptation, idempotent repair, traversal and symlink protection. They inspect the supplied archive when it is present in the test environment. Role template contracts assert awaited writes, endpoint paths, refresh bounds, and absence of mock/localStorage workflows. Additional backend unit tests cover registration scope, server Virtual ID forwarding, school formation restrictions, visit ownership and review requirements, pending funding, reviewer ownership, invitation terminal states, shortlist toggles, milestone decisions, institution-change membership conflicts and institution team scoping. Database collaborators are mocked in these unit tests; they do not replace live end-to-end acceptance.

These are executable regression checks, not a claim that browser tests or TypeScript compilation ran during this edit. Browser acceptance should exercise two-account collaboration, leader-only funding, review replies, session expiration, and public-link revocation. Also check industry open → evidence → structured review → close, student changes-done → industry resolve, faculty registration → school formation → mentor acceptance, student milestone submission → faculty decision, and institution-change approval/conflict. Verify the other visible active account refreshes within 30 seconds; hidden/idle tabs resume on focus/visibility. Keep a draft open during refresh and failed submissions to confirm it survives. The remaining delivery boundaries are the separately hosted Vite UI and linked external evidence described above. No database schema changes are included.
