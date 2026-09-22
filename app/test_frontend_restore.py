import reflex as rx

import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from app.frontend_restore import (
    VERSION,
    PAGES,
    INDUSTRY_PAGES,
    FACULTY_PAGES,
    restore_frontend,
)
from app.frontend_compat import (
    EXPORTS,
    archive_exports,
    await_workflow_calls,
    patch_shells,
)


class RestorationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "assets").mkdir()
        self.archive = self.root / "assets" / "InnovateX-main (2).zip"

    def bundle(
        self,
        extras: dict[str, str] | None = None,
        omitted: tuple[str, ...] = (),
    ):
        with zipfile.ZipFile(self.archive, "w") as bundle:
            for name, content in {
                "original/package.json": '{"name":"fixture"}',
                "original/src/App.tsx": "\n".join(
                    [
                        'import { MOCK_USERS } from "./data/mock";',
                        "export default function App() { return null; }",
                        *[
                            f'function {role.title()}Shell() {{ return <Shell role="{role}" user={{MOCK_USERS.{role}}} />; }}'
                            for role in (
                                "student",
                                "faculty",
                                "industry",
                                "admin",
                            )
                        ],
                    ]
                ),
                "original/src/store/workflow.ts": "\n".join(
                    f"export const {name} = {{}};" for name in sorted(EXPORTS)
                ),
                **{
                    f"original/src/pages/student/{name}.tsx": f"export default function {name}() {{return null;}}"
                    for name in PAGES
                },
                "original/src/pages/student/StudentDashboard.tsx": "export default function StudentDashboard() {return null;}",
                **{
                    f"original/src/pages/{role}/{name}.tsx": f"export default function {name}() {{return null;}}"
                    for role, pages in (
                        ("industry", INDUSTRY_PAGES),
                        ("faculty", FACULTY_PAGES),
                    )
                    for name in pages
                },
                "original/src/layouts/StudentShell.tsx": "archive-owned-shell",
                "original/public/logo.svg": "original-artwork",
                "original/node_modules/unused/index.js": "excluded",
                "original/dist/index.html": "excluded",
                **(extras or {}),
            }.items():
                if name not in omitted:
                    bundle.writestr(name, content)

    def test_idempotent_and_preserves_archive_assets_and_shells(self):
        self.bundle()
        original_hash = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        target = restore_frontend(self.root)
        before = {
            str(p.relative_to(target)): p.stat().st_mtime_ns
            for p in target.rglob("*")
            if p.is_file() and p.name != ".restore.lock"
        }
        restore_frontend(self.root)
        after = {
            str(p.relative_to(target)): p.stat().st_mtime_ns
            for p in target.rglob("*")
            if p.is_file() and p.name != ".restore.lock"
        }
        self.assertEqual(before, after)
        self.assertEqual(
            original_hash, hashlib.sha256(self.archive.read_bytes()).hexdigest()
        )
        self.assertEqual(
            (target / "public/logo.svg").read_text(), "original-artwork"
        )
        self.assertEqual(
            (target / "src/layouts/StudentShell.tsx").read_text(),
            "archive-owned-shell",
        )
        for role, pages in (
            ("industry", INDUSTRY_PAGES),
            ("faculty", FACULTY_PAGES),
        ):
            for name in pages:
                self.assertIn(
                    f"{role.title()}Page",
                    (target / f"src/pages/{role}/{name}.tsx").read_text(),
                )
        self.assertIn(
            "StudentPage",
            (target / "src/pages/student/StudentDashboard.tsx").read_text(),
        )
        self.assertFalse((target / "node_modules").exists())
        self.assertFalse((target / "dist").exists())
        manifest = json.loads((target / ".restore-manifest.json").read_text())
        self.assertEqual(manifest["version"], VERSION)
        for relative, digest in manifest["files"].items():
            self.assertEqual(
                hashlib.sha256((target / relative).read_bytes()).hexdigest(),
                digest,
            )

    def test_repairs_managed_files_and_preserves_contract(self):
        self.bundle()
        target = restore_frontend(self.root)
        facade = target / "src/store/workflow.ts"
        contract = target / "src/store/workflow.contract.ts"
        self.assertEqual(archive_exports(contract.read_text()), EXPORTS)
        self.assertNotIn("localStorage", facade.read_text())
        self.assertNotIn("MOCK_", facade.read_text())
        self.assertIn("import type * as Contract", facade.read_text())
        self.assertNotIn(
            "MOCK_USERS", (target / "src/App.archive.tsx").read_text()
        )
        self.assertIn(
            'currentShellUser("student")',
            (target / "src/App.archive.tsx").read_text(),
        )
        manifest = json.loads((target / ".restore-manifest.json").read_text())
        self.assertEqual(manifest["workflow_exports"], sorted(EXPORTS))
        self.assertEqual(len(manifest["student_pages_replaced"]), 9)

        self.assertEqual(len(manifest["industry_pages_replaced"]), 5)
        self.assertEqual(len(manifest["faculty_pages_replaced"]), 6)
        for role, stem, label in (
            ("industry", "Review", "Industry Reviews"),
            ("faculty", "StudentActions", "Faculty Actions"),
        ):
            relative = f"src/pages/{role}/{stem}.tsx"
            self.assertIn(relative, manifest[f"{role}_pages_replaced"])
            self.assertIn(
                f"page={json.dumps(label)}", (target / relative).read_text()
            )
        self.assertIn("30 seconds", manifest["refresh_policy"])
        self.assertEqual(
            json.loads((target / "tsconfig.student.json").read_text())[
                "include"
            ],
            ["src/**/*"],
        )
        expected = facade.read_bytes()
        facade.write_text("corrupted generated file")
        restore_frontend(self.root)
        self.assertEqual(facade.read_bytes(), expected)

    def test_rejects_changed_archive_contracts(self):
        self.bundle(
            {"original/src/store/workflow.ts": "export const unexpected = 1;"}
        )
        with self.assertRaisesRegex(ValueError, "export contract"):
            restore_frontend(self.root)
        self.bundle(
            {
                "original/src/App.tsx": "export default function App() {return null;}"
            }
        )
        with self.assertRaisesRegex(ValueError, "MOCK_USERS import"):
            restore_frontend(self.root)

    def test_named_export_role_pages_are_overlaid(self):
        for role, pages in (
            ("industry", INDUSTRY_PAGES),
            ("faculty", FACULTY_PAGES),
        ):
            for stem, label in pages.items():
                with self.subTest(role=role, stem=stem):
                    relative = f"src/pages/{role}/{stem}.tsx"
                    original = f"export function {stem}() {{ return null; }}"
                    self.bundle({f"original/{relative}": original})
                    target = restore_frontend(self.root)
                    expected = (
                        'import React from "react";\n'
                        f'import {{ {role.title()}Page }} from "../../live/{role}";\n'
                        f"export default function {stem}() {{ return <{role.title()}Page page={json.dumps(label)} />; }}\n"
                    )
                    self.assertEqual((target / relative).read_text(), expected)
                    manifest = json.loads(
                        (target / ".restore-manifest.json").read_text()
                    )
                    self.assertIn(relative, manifest[f"{role}_pages_replaced"])
                    self.assertEqual(
                        manifest["files"][relative],
                        hashlib.sha256(expected.encode()).hexdigest(),
                    )
                    with zipfile.ZipFile(self.archive) as bundle:
                        self.assertEqual(
                            bundle.read(f"original/{relative}").decode(),
                            original,
                        )

    def test_missing_role_pages_fail_clearly(self):
        for role, pages in (
            ("industry", INDUSTRY_PAGES),
            ("faculty", FACULTY_PAGES),
        ):
            for stem in pages:
                with self.subTest(role=role, stem=stem):
                    self.bundle(
                        omitted=(f"original/src/pages/{role}/{stem}.tsx",)
                    )
                    with self.assertRaisesRegex(
                        ValueError,
                        f"Archive {role} page contract changed: missing or unexpected pages",
                    ):
                        restore_frontend(self.root)

    def test_extra_role_pages_fail_clearly(self):
        for role in ("faculty", "industry"):
            self.bundle(
                {
                    f"original/src/pages/{role}/Unexpected.tsx": "export default function Extra() {}"
                }
            )
            with self.assertRaisesRegex(
                ValueError, f"Archive {role} page contract changed"
            ):
                restore_frontend(self.root)

    def test_async_compatibility_transform_is_idempotent(self):
        source = 'import {createProject} from "../store/workflow"; const save = () => { const id = createProject(project); navigate(id); };'
        updated = await_workflow_calls(source)
        self.assertIn("async () =>", updated)
        self.assertIn("await createProject(project)", updated)
        self.assertEqual(await_workflow_calls(updated), updated)

    def test_real_archive_contract_when_available(self):
        archive = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "InnovateX-main (2).zip"
        )
        if not archive.exists():
            self.skipTest(
                "Original archive is not installed in this test environment"
            )
        with zipfile.ZipFile(archive) as bundle:
            names = [n for n in bundle.namelist() if "node_modules" not in n]
            workflow = next(
                n for n in names if n.endswith("/src/store/workflow.ts")
            )
            app = next(n for n in names if n.endswith("/src/App.tsx"))
            self.assertEqual(
                archive_exports(bundle.read(workflow).decode()), EXPORTS
            )
            original = bundle.read(app).decode()
            patched, _ = patch_shells(original)
            import re

            self.assertEqual(
                re.findall(r"<Route[^>]+", original),
                re.findall(r"<Route[^>]+", patched),
            )
            for stem in PAGES:
                self.assertTrue(
                    any(
                        n.endswith(f"/src/pages/student/{stem}.tsx")
                        for n in names
                    )
                )

            for role, pages in (
                ("industry", INDUSTRY_PAGES),
                ("faculty", FACULTY_PAGES),
            ):
                prefix = f"{Path(app).parent.as_posix()}/pages/{role}/"
                actual = {
                    n[len(prefix) :]
                    for n in names
                    if n.startswith(prefix) and n.endswith(".tsx")
                }
                self.assertEqual(actual, {f"{stem}.tsx" for stem in pages})

    def test_rejects_traversal_before_extracting(self):
        self.bundle({"original/../../escape.txt": "unsafe"})
        with self.assertRaises(ValueError):
            restore_frontend(self.root)
        self.assertFalse((self.root / "escape.txt").exists())
        self.assertFalse((self.root / "frontend/src/App.tsx").exists())

    def test_rejects_archive_symlink(self):
        self.bundle()
        with zipfile.ZipFile(self.archive, "a") as bundle:
            entry = zipfile.ZipInfo("original/public/link")
            entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            bundle.writestr(entry, "../../outside")
        with self.assertRaises(ValueError):
            restore_frontend(self.root)

    def test_rejects_destination_symlink(self):
        self.bundle()
        destination = self.root / "frontend"
        destination.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (destination / "src").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            restore_frontend(self.root)
        self.assertFalse((outside / "App.tsx").exists())

    def test_no_install_or_build_side_effect(self):
        self.bundle()
        with (
            patch(
                "subprocess.run",
                side_effect=AssertionError("Unexpected process"),
            ),
            patch(
                "subprocess.Popen",
                side_effect=AssertionError("Unexpected process"),
            ),
        ):
            restore_frontend(self.root)

    def test_ignores_private_environment_file(self):
        self.bundle({"original/.env.local": "PRIVATE=not-for-restoration"})
        destination = restore_frontend(self.root)
        self.assertFalse((destination / ".env.local").exists())
        self.assertEqual(
            (destination / ".env.example").read_text(), "VITE_API_URL=/api/v1\n"
        )


class StudentTemplateContracts(unittest.TestCase):
    def test_safety_contracts(self):
        directory = Path(__file__).parent
        api = (directory / "frontend_api.txt").read_text()
        self.assertIn("VITE_API_URL", api)
        self.assertIn("credentials: 'omit'", api)
        self.assertIn("redirect: 'error'", api)
        self.assertIn("AbortController", api)
        self.assertIn("options.public ? null : session()", api)
        self.assertNotIn("localStorage", api)
        student = (directory / "frontend_student.txt").read_text()
        self.assertNotIn("MOCK_", student)
        self.assertNotIn("localStorage", student)
        self.assertNotIn("/proofs/upload", student)
        for field in (
            "receipt_confirmed",
            "decline_note",
            "student_ids",
            "leader_id",
            "to_institution_id",
            "faculty_id",
            "changes_done",
        ):
            self.assertIn(field, student)

    def test_identity_and_public_routes(self):
        directory = Path(__file__).parent
        api = (directory / "frontend_api.txt").read_text()
        gate = (directory / "frontend_app.txt").read_text()
        student = (directory / "frontend_student.txt").read_text()
        self.assertIn("setShellUser(value.user)", api)
        self.assertIn("setShellUser();", api)
        self.assertIn("validateSession().then", gate)
        self.assertLess(
            gate.index("if (publicSlug) return <PublicPortfolio"),
            gate.index("if (!user) return"),
        )
        self.assertIn("offset=${offset}`, true)", student)
        self.assertIn("route(prefix)", gate)
        workflow = (directory / "frontend_workflow.txt").read_text()
        for name in EXPORTS:
            self.assertIn(name, workflow)
        self.assertIn("innovatex:workflow", workflow)
        self.assertIn("pending", workflow)
        self.assertIn("error", workflow)
        self.assertNotIn("localStorage", workflow)
        self.assertNotIn("MOCK_PROBLEMS", workflow)

    def test_role_templates_and_refresh(self):
        directory = Path(__file__).parent
        industry = (directory / "frontend_industry.txt").read_text()
        faculty = (directory / "frontend_faculty.txt").read_text()
        import re

        for source in (industry, faculty):
            self.assertNotIn("localStorage", source)
            self.assertNotIn("MOCK_", source)
            self.assertNotIn("store/workflow", source)
            for match in re.finditer(r"\bwrite(?:<[^>]+>)?\(", source):
                self.assertTrue(
                    source[: match.start()].rstrip().endswith("await")
                )
        for endpoint in (
            "/views`",
            "/views/close",
            "/reviews",
            "/replies",
            "/funding",
            "/problems",
            "/csr/summary",
            "/respond",
        ):
            self.assertIn(endpoint, industry)
        for endpoint in (
            "/shortlist",
            "/users",
            "/projects",
            "/institution-changes/",
            "/milestones",
            "/panel-feedback",
            "/respond",
        ):
            self.assertIn(endpoint, faculty)
        self.assertIn(
            "transfer_confirmed: f.get('confirmed') === 'on'", industry
        )
        self.assertIn("virtual_id", faculty)
        self.assertIn(
            "page === 'Industry Reviews' ? <Records<Review> path=\"/reviews\" render={r => <IndustryThread review={r} user={user}/>}/>",
            industry,
        )
        self.assertIn(
            "page === 'Faculty Actions' ? <Invitations user={user}/>",
            faculty,
        )
        ui = (directory / "frontend_ui.txt").read_text()
        for term in (
            "30000",
            "120000",
            "visibilitychange",
            "document.visibilityState === 'visible'",
            "clearInterval",
            "busy.current",
            "await onSubmit(data)",
            "previousKey",
        ):
            self.assertIn(term, ui)
        self.assertIn(
            "useActivityRefresh();",
            (directory / "frontend_app.txt").read_text(),
        )

    def test_backend_request_contracts_remain_valid(self):
        from app.api_contracts import (
            FundingDecision,
            Attachment,
            ReplyInput,
            ShareInput,
        )

        self.assertTrue(
            FundingDecision(
                status="confirmed", receipt_confirmed=True
            ).receipt_confirmed
        )
        self.assertEqual(
            FundingDecision(
                status="declined", decline_note="Not received"
            ).status,
            "declined",
        )
        self.assertEqual(
            Attachment(
                kind="link", url="https://example.org/proof", source="external"
            ).source,
            "external",
        )
        self.assertEqual(
            ReplyInput(
                body="Changes are documented", action="changes_done"
            ).action,
            "changes_done",
        )
        self.assertTrue(ShareInput(enabled=True, regenerate=True).regenerate)


if __name__ == "__main__":
    unittest.main()
