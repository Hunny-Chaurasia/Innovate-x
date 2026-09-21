# InnovateX: Workflow Features

Adds the missing cross-role workflows to the InnovateX platform (student, industry, faculty):
team formation, collaboration requests, leader-approved funding, mandatory industry reviews,
proof of work, a shareable public portfolio, role-based Virtual IDs and a faculty problem-statement portal.

Stack: React + TypeScript + React Router. No backend required yet (see [Data and persistence](#data-and-persistence)).

---

## Features

| # | Feature | Where |
|---|---|---|
| 1 | **New Project**: Form Team, Find Mentor, Send Collaboration Request, Contact List, Reason to join | `pages/student/NewProject.tsx` |
| 2 | **Public portfolio link**: generate, copy, switch public/private, regenerate | `pages/student/Portfolio.tsx`, `pages/public/PublicPortfolio.tsx` |
| 3 | **Role-based Virtual IDs** (`STU-`, `FAC-`, `IND-`, `MEN-`, `ADM-`) | `utils/virtualId.ts`, used in `pages/faculty/Students.tsx` |
| 4 | **Funding approved by the team leader** before a project counts as Funded | `components/FundModal.tsx`, `components/FundingApprovalCard.tsx` |
| 5 | **Team formation rules** (school vs college / university / cross-institution) | `store/workflow.ts` (`teamFormationRule`), `components/FormTeamModal.tsx` |
| 6 | **Mandatory industry review** on every project view, with student replies | `components/ProjectReviewModal.tsx`, `pages/student/Review.tsx` |
| 7 | **Faculty portal for incoming problem statements** | `pages/faculty/ProblemStatements.tsx` |
| 8 | **Proof of Work** with images, links and videos | `components/ProofOfWork.tsx` |
| 9 | **Action Center** for everything waiting on a student | `pages/student/StudentActions.tsx` |

---

## Folder structure

```
src/
├── store/
│   └── workflow.ts                 shared store + demo identities + all actions
├── utils/
│   └── virtualId.ts                role-based Virtual ID generator
├── components/
│   ├── FundModal.tsx               industry funding flow (amount, then proof)
│   ├── FundingApprovalCard.tsx     team-leader approve / decline card
│   ├── ProjectReviewModal.tsx      mandatory review modal + reusable ReviewThread
│   ├── ProofOfWork.tsx             images / links / videos section
│   ├── FormTeamModal.tsx           faculty "Form Team" (school-only)
│   └── PortfolioGrid.tsx           portfolio cards, stage filter, detail modal
└── pages/
    ├── student/
    │   ├── NewProject.tsx          NEW (was comments only)
    │   ├── Review.tsx              NEW (was empty)
    │   ├── StudentActions.tsx      NEW (was empty)
    │   ├── Portfolio.tsx           rewritten
    │   ├── Funding.tsx             patched: incoming funding section
    │   ├── MyProjects.tsx          patched: Proof of Work tab, New Project button
    │   └── Discover.tsx            patched: shows industry-posted problems
    ├── industry/
    │   ├── IndustryDashboard.tsx   rewritten: leader-aware funding, review status
    │   ├── DiscoverProjects.tsx    rewritten: same funding + review flow
    │   └── PostProblem.tsx         patched: Publish really saves
    ├── faculty/
    │   ├── ProblemStatements.tsx   NEW
    │   ├── FacultyDashboard.tsx    patched: Form Team, PS banner, Virtual ID
    │   └── Students.tsx            patched: real Virtual ID + persisted registration
    └── public/
        └── PublicPortfolio.tsx     NEW (no layout, no login)
```

Files not touched: `CSRImpact`, `ChangeRequests`, `ReviewPanel`, `StudentDashboard`, `StudentSettings`.

---

## Installation

1. Copy `src/` from this package over your project's `src/` (paths mirror your project).
2. Register the routes below.
3. Add sidebar links for the new pages.

No new npm packages are needed.

### 1. Routes

Wrap each page in the same shell your other routes use. `FacultyShell` is the assumed name; use whatever your faculty layout is called.

```tsx
import NewProject from './pages/student/NewProject';
import Review from './pages/student/Review';
import StudentActions from './pages/student/StudentActions';
import ProblemStatements from './pages/faculty/ProblemStatements';
import PublicPortfolio from './pages/public/PublicPortfolio';

<Routes>
  {/* ...your existing routes... */}

  {/* Student */}
  <Route path="/student/new-project" element={<StudentShell><NewProject /></StudentShell>} />
  <Route path="/student/reviews"     element={<StudentShell><Review /></StudentShell>} />
  <Route path="/student/actions"     element={<StudentShell><StudentActions /></StudentShell>} />

  {/* Faculty */}
  <Route path="/faculty/problems"    element={<FacultyShell><ProblemStatements /></FacultyShell>} />

  {/* Public: no shell, no login guard, so the shared link opens for anyone */}
  <Route path="/u/:slug"             element={<PublicPortfolio />} />
</Routes>
```

Inside `<Routes>` use `{/* comments */}`. A plain `//` comment there is a syntax error.

If your route names differ, change these `navigate(...)` calls:

| File | Navigates to |
|---|---|
| `MyProjects.tsx` | `/student/new-project` |
| `NewProject.tsx` | `/student/actions` |
| `StudentActions.tsx` | `/student/reviews` |
| `FacultyDashboard.tsx` | `/faculty/problems` |

### 2. Sidebar links

Add entries for **Reviews** (`/student/reviews`), **Actions** (`/student/actions`) and **Problem Statements** (`/faculty/problems`).

### 3. Deployment note

The public link uses `/u/:slug`. With `BrowserRouter`, your host must serve `index.html` for unknown paths, otherwise opening a shared link directly returns a 404. Vite's dev server already does this. With `HashRouter` the generated link becomes `/#/u/:slug` automatically.

---

## How each flow works

### Funding: the team leader must approve

1. Industry clicks **Fund**, enters an amount, then transaction reference and confirmation.
2. A funding record is created with status `awaiting_leader`. The project stays at its current stage and the row shows "awaiting {leader}".
3. The team leader sees it in **Action Center** and in **Funding > Funding from industry partners**. They tick the receipt confirmation and click **Approve funding**, or **Decline** with a reason (minimum 5 characters).
4. On approval the status becomes `confirmed` and the project shows **Funded** on the industry dashboard and Discover page.
5. On decline the funder sees the reason and can click **Fund again**.
6. Team members who are not the leader see "Only the team leader can approve this funding".

### Industry review: required on every view

1. Industry clicks **View & review** (dashboard) or **View** (Discover).
2. The modal asks for **Overall assessment**, **Flaws** and **Improvements needed** (at least 10 characters each) plus optional **What works**.
3. The modal cannot be closed until a review is submitted. Trying to close shows a warning.
4. Students see the review in **Reviews** and reply. **Send reply** keeps it open; **Reply · changes done** marks it as addressed.
5. Industry can **Request more changes** or **Mark resolved** from the same modal. Following up in an existing thread also counts as the review for that visit.

Review status: `open` (changes requested), `addressed` (student replied), `resolved`.

### Team formation rules

| Situation | Who forms the team |
|---|---|
| All members from the **same school** | That school's **faculty** (`FormTeamModal`) |
| College or university students | **Students** (`NewProject`) |
| Members from **different institutions** (any mix) | **Students**, no faculty involvement |

- Faculty at a college or university do not form teams. The Form Team button explains the rule instead.
- A school-only team of different schools requires a **mentor** in `NewProject` (same rule as `MyProjects`).
- The student who creates a team through `NewProject` is the **team leader**. Faculty choose the leader when forming a school team.

### New Project wizard

1. **Project**: title, description, category.
2. **Team**: search and filter the contact list (All / My institution / Other institutions / Schools), invite people, write the required **Reason to join**.
3. **Mentor**: pick one (required only for school-only teams).
4. **Send**: review, then send collaboration requests. Track them in Action Center.

Invitees appear in the team as `Invited` until they accept. Accepting an incoming invite (Action Center) creates the project for the invited student.

### Proof of Work

Add a title, description and any mix of:

- **Images**: uploaded from disk, max 2 MB each, stored as data URLs.
- **Links**: validated, `https://` added if missing, optional label.
- **Videos**: YouTube, Vimeo and Google Drive links play inline; direct `.mp4/.webm/.mov` links use a video player. Video **file uploads** (max 100 MB) last for the current session only, so use a link for permanent proof.

Proof of work shows in **My Projects > Proof of Work** and read-only in the portfolio detail view.

### Public portfolio

**Portfolio > Share Public Profile** generates `/u/{name}-{4 random chars}`. You can copy it, open a preview, switch it private (link stops working, not deleted), or create a new link (old link stops working).

### Virtual IDs

Format: `{ROLE}-{YEAR}-{SEQ}`

| Role | Prefix | Example |
|---|---|---|
| Student | `STU` | `STU-2026-0090` |
| Faculty | `FAC` | `FAC-2026-0008` |
| Industry | `IND` | `IND-2026-0004` |
| Mentor | `MEN` | `MEN-2026-0002` |
| Admin | `ADM` | `ADM-2026-0001` |

```ts
import { generateVirtualId } from '../utils/virtualId';
const id = generateVirtualId('faculty', existingFacultyIds); // max existing sequence + 1
```

Call it wherever an account is created (faculty registering a student, sign-up for faculty / industry / mentor, admin invites). `parseVirtualId(id)` returns `{ role, year, seq }`.

### Faculty problem-statement portal

Lists every problem industry publishes (plus your existing ones) with search, domain filter and tabs **All / New / Shortlisted / CSR**. Opening a brief marks it as seen. Faculty can shortlist problems for their students. The Faculty Dashboard shows a banner with the number of new problems.

---

## Data and persistence

All shared state lives in `src/store/workflow.ts`.

- It uses `useSyncExternalStore`, so no provider or `App.tsx` change is needed.
- It is saved to `localStorage` under `innovatex.workflow.v1` and syncs across browser tabs, so you can demo two roles side by side.
- **Public portfolio links only work in the browser that created them** until you add a backend.
- To reset demo data, clear that localStorage key.

`useWorkflow()` returns the whole state object. Filter or map inside components with `useMemo`.

### Replacing it with an API

Components only call the exported functions. Swap their bodies for API calls:

| Area | Functions |
|---|---|
| Funding | `submitFunding`, `respondFunding`, `latestFunding` |
| Reviews | `addReview`, `addReply` |
| Proof of work | `addProof`, `removeProof` |
| Problems | `publishProblem`, `markProblemSeen`, `toggleShortlist`, `useAllProblems` |
| Teams | `createProject`, `addRequests`, `respondCollab`, `teamFormationRule` |
| Portfolio | `ensureProfile`, `setProfileEnabled`, `regenerateSlug`, `publicProfileUrl` |
| Faculty | `registerStudent` |

Enforce the same rules on the server: only the team leader may confirm funding, and only industry may create reviews.

### Demo identities (replace with real auth)

In `workflow.ts`:

| Constant | Demo value |
|---|---|
| `CURRENT_STUDENT` | Arjun Mehta, `STU-2024-0042`, IIT Bombay (College) |
| `CURRENT_FACULTY` | Dr. Priya Sharma, `FAC-2024-0007`, Delhi Technological University (College) |
| `CURRENT_INDUSTRY` | Rohan Kapoor, `IND-2024-0003`, Infosys |
| `CONTACTS` | Demo student directory (colleges and schools) |
| `TEAM_DIRECTORY` | Team Nova: leader Arjun. Team Echo: leader Karan Malhotra (Arjun is a member) |

---

## Try it: demo walkthrough

Open two tabs (state syncs between them).

**Funding approval**
1. Tab A (industry): Dashboard, **Fund** on Team Nova, complete both steps. The row shows "awaiting Arjun".
2. Tab B (student): **Actions**, tick the confirmation, **Approve funding**.
3. Tab A: the project now shows **Funded**.
4. Fund Team Echo. In Tab B (**Funding** page) Arjun sees it is read-only because Karan is the leader.

**Review loop**
1. Tab A: **View & review** on a project. Try closing first to see the requirement, then submit.
2. Tab B: **Reviews**, reply with **Reply · changes done**.
3. Tab A: open the project again and **Mark resolved**.

**Faculty form team**
1. In `workflow.ts` set `CURRENT_FACULTY.institution = 'Delhi Public School, R.K. Puram'` and `institutionType = 'School'`.
2. Faculty Dashboard, **+ Form Team**, pick 2+ students, choose a leader, create.

**Other**
- Industry **Post Problem** then Faculty **Problem Statements** and student **Discover**.
- Student **Portfolio > Share Public Profile**, then open the link.
- Student **New Project**, then **Actions** (use "Demo: mark accepted" to simulate an invitee replying).

---

## Testing

The flows were verified with 17 integration tests (Vitest, jsdom, Testing Library) covering Virtual IDs, team rules, leader-only funding approval and decline, mandatory review and reply loop, proof of work (image, link, YouTube), share link and public page, the New Project wizard, faculty problem portal, student registration IDs and the faculty Form Team modal. The tests ran against stand-in versions of `components/ui`, `components/Toast` and `data/mock`, so they are not included in this package.

---

## Known limitations

- No authentication or authorization on the server yet; the leader-only rules are enforced in the UI.
- Collaboration requests to other users cannot be answered by them until real accounts exist. Action Center has a clearly labelled **Demo: mark accepted** button for outgoing requests.
- Video files uploaded from disk are not persisted across reloads.
- Images are stored inline in localStorage (about 5 MB browser limit in total); use a backend file store in production.
- Reviews and funding are keyed by team name through `TEAM_DIRECTORY`; with a backend, key them by real project and team IDs.
- Types were inferred from how your existing files use `components/ui` and `data/mock`; if your prop types are stricter, a couple of small type adjustments may be needed.
