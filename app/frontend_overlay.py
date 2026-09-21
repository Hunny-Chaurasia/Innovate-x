import reflex as rx

import json
from pathlib import Path

OVERLAY_VERSION = "role-api-4.0.0"
TEMPLATES = {
    "student_api.txt": "src/integration/api.ts",
    "student_records.txt": "src/integration/records.ts",
    "student_auth.txt": "src/integration/auth.tsx",
    "student_experience.txt": "src/integration/StudentExperience.tsx",
    "student_workflow.txt": "src/store/workflow.ts",
    "student_shared_portfolio.txt": "src/integration/SharedPortfolio.tsx",
    "student_build.txt": "scripts/student-compat.mjs",
    "industry_experience.txt": "src/integration/IndustryExperience.tsx",
    "faculty_experience.txt": "src/integration/FacultyExperience.tsx",
    "role_shared.txt": "src/integration/RoleShared.tsx",
    "student_milestones.txt": "src/integration/StudentMilestones.tsx",
}
STUDENT_PAGES = (
    "StudentDashboard",
    "Discover",
    "MyProjects",
    "NewProject",
    "StudentActions",
    "Review",
    "Funding",
    "Portfolio",
    "StudentSettings",
)


ROLE_PAGES = {
    "industry": {
        "IndustryDashboard": "dashboard",
        "DiscoverProjects": "discover",
        "PostProblem": "post",
        "Review": "reviews",
        "CSRImpact": "csr",
    },
    "faculty": {
        "FacultyDashboard": "dashboard",
        "Students": "students",
        "ProblemStatements": "problems",
        "ChangeRequests": "changes",
        "ReviewPanel": "panel",
        "StudentActions": "actions",
    },
}


def overlay_sources(original: dict[str, bytes]) -> dict[str, bytes]:
    """Compose versioned role pages over the approved visual shell and assets."""
    files = dict(original)
    required = ("src/App.tsx", "src/store/workflow.ts", "package.json")
    missing = [name for name in required if name not in files]
    if missing:
        raise ValueError(
            "The frontend archive is missing required source files"
        )
    directory = Path(__file__).resolve().parent
    files["src/store/workflow.contract.ts"] = files["src/store/workflow.ts"]
    for source, destination in TEMPLATES.items():
        files[destination] = (directory / source).read_bytes()
    page_modes = {
        "StudentDashboard": "student",
        "Discover": "discover",
        "MyProjects": "projects",
        "NewProject": "new-project",
        "StudentActions": "actions",
        "Review": "reviews",
        "Funding": "funding",
        "Portfolio": "portfolio",
        "StudentSettings": "settings",
    }
    for page in STUDENT_PAGES:
        mode = page_modes[page]
        files[f"src/pages/student/{page}.tsx"] = (
            "import StudentExperience from '../../integration/StudentExperience';\n"
            f'export default function {page}() {{ return <StudentExperience page="{mode}" />; }}\n'
        ).encode()
    for role, pages in ROLE_PAGES.items():
        component = f"{role.title()}Experience"
        for page, mode in pages.items():
            files[f"src/pages/{role}/{page}.tsx"] = (
                f"import {component} from '../../integration/{component}';\n"
                f'export default function {page}() {{ return <{component} page="{mode}" />; }}\n'
            ).encode()
    # Retire demo-only mutation surfaces; administration is not implemented by this release.
    for name in tuple(files):
        if name.startswith("src/pages/admin/") and name.endswith(".tsx"):
            files[name] = (
                'export default function AdministrationUnavailable() { return <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 text-[var(--foreground)]"><h1 className="text-xl font-semibold">Administration</h1><p className="text-sm text-[var(--muted-foreground)] mt-3">Administrative workflow controls are not connected in this release. Demo approvals and account changes are disabled. No changes have been saved.</p></section>; }\n'
            ).encode()
    for page in ("FacultyRegister", "IndustryRegister"):
        files[f"src/pages/auth/{page}.tsx"] = (
            "import { AuthPage } from '../../integration/auth';\n"
            f'export default function {page}() {{ return <><p className="p-4 text-sm text-amber-300 bg-[var(--background)]">Faculty and industry accounts must be provisioned by an administrator. Sign in with your existing account.</p><AuthPage /></>; }}\n'
        ).encode()
    files["src/pages/auth/Login.tsx"] = (
        "export { AuthPage as default } from '../../integration/auth';\n"
    ).encode()
    files["src/pages/auth/StudentRegister.tsx"] = (
        "import { AuthPage } from '../../integration/auth';\n"
        "export default function StudentRegister() { return <AuthPage registration />; }\n"
    ).encode()
    files["src/pages/public/PublicPortfolio.tsx"] = (
        "export { default } from '../../integration/SharedPortfolio';\n"
    ).encode()
    app = files["src/App.tsx"].decode("utf-8")
    for role in ("student", "faculty", "industry", "admin"):
        before = f'<Shell role="{role}" user={{MOCK_USERS.{role}}}>{{children}}</Shell>'
        after = f'<AuthShell role="{role}">{{children}}</AuthShell>'
        if app.count(before) != 1:
            raise ValueError(
                "The archive role-shell contract changed; update the overlay explicitly"
            )
        app = app.replace(before, after)
    app = app.replace("import Shell from './components/Shell';\n", "")
    app = app.replace("import { MOCK_USERS } from './data/mock';\n", "")
    app = (
        f"import {{ AuthShell, MentorHome }} from './integration/auth';\n{app}"
    )
    if "<Routes>" not in app:
        raise ValueError("The archive routing contract changed")
    app = app.replace(
        "<Routes>",
        '<Routes>\n          <Route path="/mentor" element={<MentorHome />} />',
        1,
    )
    if 'path="/industry/reviews"' not in app:
        app = app.replace(
            "<Routes>",
            '<Routes>\n          <Route path="/industry/reviews" element={<IndustryShell><IndustryReview /></IndustryShell>} />',
            1,
        )
        app = f"import IndustryReview from './pages/industry/Review';\n{app}"
    files["src/App.tsx"] = app.encode()
    package = json.loads(files["package.json"])
    scripts = package.setdefault("scripts", {})
    # Explicit preparation makes API-return values safe in retained legacy handlers.
    scripts["student:prepare"] = "node scripts/student-compat.mjs"
    scripts["typecheck"] = (
        "npm run student:prepare && tsc -p tsconfig.student.json"
    )
    scripts["build"] = "npm run typecheck && vite build"
    scripts["predev"] = "npm run student:prepare"
    files["package.json"] = (json.dumps(package, indent=2) + "\n").encode()
    files["tsconfig.student.json"] = (
        json.dumps(
            {
                "compilerOptions": {
                    "target": "ES2022",
                    "lib": ["ES2022", "DOM", "DOM.Iterable"],
                    "module": "ESNext",
                    "moduleResolution": "Bundler",
                    "jsx": "react-jsx",
                    "allowImportingTsExtensions": True,
                    "resolveJsonModule": True,
                    "esModuleInterop": True,
                    "skipLibCheck": True,
                    "noEmit": True,
                    "strict": False,
                    "types": ["vite/client"],
                },
                "include": ["src"],
            },
            indent=2,
        )
        + "\n"
    ).encode()
    files["src/integration/env.d.ts"] = (
        b'/// <reference types="vite/client" />\n'
    )
    files["STUDENT_API.md"] = (directory / "STUDENT_API.md").read_bytes()
    return files
