Build the frontend for "InnovateX" — a SaaS platform where school/college students 
build real projects, form cross-institution teams, get mentorship, and connect with 
industry for funding and deployment.

TECH: React + Tailwind CSS (component-based, responsive, mobile-first). Use a clean, 
modern SaaS aesthetic — think Linear/Notion energy, not a generic dashboard template. 
Rounded cards, soft shadows, a confident accent color (electric blue or violet), 
plenty of whitespace, no boilerplate gradients.

## ROLES (4 distinct dashboard experiences, shared auth/layout shell)
1. Student (school or college/university)
2. Industry Partner (Corporate)
3. Faculty Mentor
4. Admin

## GLOBAL SHELL
- Top nav: logo, role-aware nav links, notifications bell, profile avatar dropdown
- Sidebar (collapsible): role-specific nav items

## AUTH & REGISTRATION FLOWS (role-specific — this is not a generic signup form)

1. **Faculty Mentor Registration**
   - Fields: institutional email (must validate as ending in `.edu` or `.tech` domain — 
     show inline validation error otherwise), institution name, designation, 
     mandatory LinkedIn profile URL
   - On submission, show a "Registration submitted" confirmation state
   - System auto-generates a **Virtual ID**; faculty sets their own password via a 
     setup link sent to their registration email
   - Login screen for faculty: Virtual ID + Password fields

2. **Student Registration (first time)**
   - Students do NOT self-register freely — they need institution name + a 
     **Virtual ID provided by their faculty** to even start registration
   - Registration form: Institution Name, Virtual ID (issued by faculty), 
     mandatory LinkedIn profile URL
   - Student then sets their own password via a setup link sent to the registration 
     email that faculty entered while creating the student's account
   - Login screen for students: Virtual ID + Password fields (no email login)

3. **Student — Change Institution (returning/already-registered student)**
   - New action in Student Settings/Profile: **"Change Institution"**
   - Form: new Institution Name (searchable dropdown of registered institutions)
   - On submit, this creates a **pending approval request** — does NOT change the 
     institution immediately
   - Request is routed to **any one faculty member of the target institution** — 
     shown in that faculty's dashboard under a new **"Institution Change Requests"** 
     queue (see Faculty Experience below)
   - Student sees a status badge on their profile while pending: "Institution 
     Change Pending — awaiting approval from [Institution Name]"
   - On approval: institution updates on student profile, confirmation toast/email 
     state shown
   - On rejection: student sees a "Request declined" state, can re-submit or pick 
     a different institution
   - Student's Virtual ID does NOT change during this process — only the 
     institution field updates once approved

4. **Faculty → Student Provisioning** (Faculty Experience)
   - **"Register Student"** action: faculty enters student name + student's email, 
     system auto-generates a Virtual ID for that student, and sends a setup link to 
     the student's email to create their password
   - **"My Institution's Students"** table: list of all students registered under 
     this faculty's institution, with status (Invited / Active), searchable/filterable
   - **"Institution Change Requests"** queue: incoming requests from students 
     wanting to join this faculty's institution — each row shows student name, 
     current institution, Virtual ID, LinkedIn link, with Approve / Reject actions
   - Faculty can **proactively form teams**: search within their registered student 
     roster and send team-formation requests directly to students

5. **Industry/Corporate Registration**
   - Fields: company email (must validate as a recognized company domain format, 
     e.g. `@companyname.com`, not generic email providers), company name, 
     designation, mandatory LinkedIn profile URL
   - On approval, system auto-generates a Virtual ID + password setup flow, same 
     pattern as faculty
   - Login screen for industry: Virtual ID + Password fields

6. **Universal rule**: LinkedIn profile URL is a **mandatory field at registration 
   for every role** (Student, Faculty, Industry, Admin) — show it as a required 
   field with a LinkedIn icon prefix on the input

## STUDENT EXPERIENCE

1. **Discover Page** — Browse tab (Industry Problems | Community Ideas), filterable 
   by domain/institution type, card grid with problem title, industry logo, tags, 
   "Solve This" / "View" CTA

2. **Create Project Page** — Form: title, description, category, choose "solve an 
   existing problem" or "start from own idea"

3. **Team Formation** — Search/invite students across institutions, show 
   institution-type badges (School/College/University), mentor-requirement banner 
   that dynamically shows "Mentor Required" or "Mentor Optional" based on team 
   composition rules

4. **My Projects** (dedicated tab, separate from Portfolio) — the student's live 
   project feed:
   - Project cards show: title, current stage badge, last-updated timestamp, and 
     a "Proof of Work" activity indicator
   - Each time proof-of-work is uploaded, the card auto-updates with:
     - A small activity log entry ("New proof-of-work added — [date]")
     - Updated **Team Details panel**: avatars + names of all team members, their 
       institution badges (School/College/University), and role within the team 
       (Lead/Contributor)
   - **Request Mentor Collaboration** button on each project card/detail page:
     - Opens a mentor-request modal showing a searchable list of mentors, filtered 
       by the mentor rules:
       - College/University-only team → mentor list shown, marked "Optional"
       - Different-school team → mentor selection is **required before proceeding**, 
         request button disabled/highlighted until a mentor is selected
       - School + College team → mentor list shown, marked "Optional"
     - If team composition doesn't meet the minimum rule requirement, show an inline 
       warning banner instead of allowing submission ("This team requires a mentor — 
       please select one before requesting collaboration")
     - Once requested, show pending/accepted/declined status on the project card

5. **Project Workspace** — Tabs: Proposal, Milestones (checklist/timeline UI), 
   Proof-of-Work uploads (file/image grid), Feedback thread, Collaboration requests

6. **My Portfolio** — Grid of all projects with status badges (Ideation/Building/
   Funded/Deployed), a shareable public profile view

7. **Funding/Opportunities** — List of open funding calls, workshops, mentorship 
   slots to apply for

## INDUSTRY EXPERIENCE
1. **Post a Problem** — Form with title, description, domain, CSR tag toggle
2. **Discover Projects** — Card/table view of student projects tackling their 
   problems, filter by stage (Idea/Building/Prototype)
3. **Project Detail (Industry View)** — Progress timeline, milestone history, 
   team info, "Mentor This," "Fund This," "Invite to Workshop" actions
4. **CSR Impact Dashboard** — Stats cards (projects funded, students reached, 
   patents/startups incubated) + simple chart

## FACULTY MENTOR EXPERIENCE

1. **Dashboard Home** (landing view before My Teams):
   - Stats row: total projects mentored, active vs completed, students guided
   - **Graph: Projects Over Time** — line or bar chart showing number of projects 
     mentored per month/semester (mock time-series data)
   - **Graph: Projects by Stage** — pie/donut chart (Idea → Building → Funded → 
     Deployed breakdown) across all their mentored projects

2. **Register Student** — form + roster table (see Auth section #4 above)

3. **Institution Change Requests** — approval queue (see Auth section #4 above)

4. **My Teams** — List of assigned teams with quick status (shown below the 
   dashboard graphs as a secondary section); includes ability to proactively 
   create teams from their student roster

5. **Review Panel** — Proposal review, milestone approval, feedback composer

## ADMIN EXPERIENCE
1. **User Management Table** — Search/filter/suspend users, view registration type 
   (Faculty-provisioned vs Self-registered Industry/Faculty), and institution 
   change history per student
2. **Moderation Queue** — Flagged content/projects to approve/reject
3. **Platform Analytics** — Stats cards + charts (active users, projects by stage, 
   cross-institution team %, funding disbursed)

## LEADERBOARD (platform-wide page, visible to Students/Industry, plus in Admin)
- Two tabs: **Schools** | **Colleges & Universities**
- Ranked list/table showing:
  - Institution name + logo
  - Number of active projects
  - Number of students participating
  - Activity score (composite ranking metric — projects + milestones + 
    proof-of-work uploads — shown as a rank number, not a literal formula)
  - Rank badge for top 3 (gold/silver/bronze visual treatment)
- Filter/toggle for "This Month" vs "All Time"
- Highlight the logged-in user's own institution row if it appears (subtle 
  border/background tint)

## KEY VISUAL ELEMENTS TO GET RIGHT
- A visual "Project Journey" stepper component (Idea → Problem → Team → Proposal → 
  Build → Milestones → Feedback → Industry → Funding → Prototype → Deployment) used 
  on the project detail page as a horizontal progress tracker
- Institution-type badges (School / College / University) as small colored pills, 
  used throughout team/user displays
- Virtual ID display component — a distinct "credential card" look, shown on 
  profile pages and the post-registration confirmation screen
- Pending-approval status badges (used for both mentor collaboration requests and 
  institution change requests) — consistent visual treatment across both
- Empty states for Discover, Team search, and Portfolio — encouraging, not blank

## OUT OF SCOPE FOR THIS PASS
No backend/API wiring — use mock/static data (including mock email domain 
validation and mock Virtual ID generation). Focus entirely on layout, component 
structure, navigation, and visual polish across all 4 role dashboards.