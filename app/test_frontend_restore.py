import reflex as rx

import json
import logging
import runpy
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from app.frontend_overlay import (
    OVERLAY_VERSION,
    TEMPLATES,
    ROLE_PAGES,
    overlay_sources,
)
from app.frontend_restore import restore_frontend


class FrontendRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.archive = self.root / "assets" / "InnovateX-main (2).zip"
        try:
            self.archive.parent.mkdir()
            source = (
                Path(__file__).resolve().parent.parent
                / "assets"
                / self.archive.name
            )
            shutil.copyfile(source, self.archive)
        except OSError as e:
            logging.exception(f"Error: {e}")
            raise

    def test_entrypoint_restores_before_app_construction_without_commands(self):
        def construct_app(**kwargs):
            trigger.assert_called_once_with()
            self.assertTrue(
                (self.root / "frontend/.innovatex-source-restored").is_file()
            )
            self.assertTrue(
                (self.root / "frontend/src/store/workflow.ts").is_file()
            )
            return app_instance

        from unittest.mock import Mock

        app_instance = Mock()
        with (
            patch(
                "app.frontend_restore.restore_frontend",
                side_effect=lambda: restore_frontend(self.root),
            ) as trigger,
            patch.object(rx, "App", side_effect=construct_app) as constructor,
            patch("subprocess.Popen") as process,
            patch("os.system") as system,
        ):
            runpy.run_path(str(Path(__file__).with_name("app.py")))
        trigger.assert_called_once_with()
        constructor.assert_called_once()
        app_instance.add_page.assert_called_once()
        process.assert_not_called()
        system.assert_not_called()

    def test_restoration_idempotence_and_repair(self):
        restore_frontend(self.root)
        frontend = self.root / "frontend"
        marker = frontend / ".innovatex-source-restored"
        payload = json.loads(marker.read_text())
        self.assertEqual(payload["version"], OVERLAY_VERSION)
        current = (frontend / "src/integration/api.ts").read_bytes()
        stamp = marker.stat().st_mtime_ns
        restore_frontend(self.root)
        self.assertEqual(stamp, marker.stat().st_mtime_ns)
        (frontend / "src/integration/api.ts").write_text("obsolete")
        restore_frontend(self.root)
        self.assertEqual(
            current, (frontend / "src/integration/api.ts").read_bytes()
        )

    def test_older_marker_never_suppresses_overlay(self):
        frontend = self.root / "frontend"
        frontend.mkdir()
        (frontend / ".innovatex-source-restored").write_text(
            "Restored from the approved InnovateX source archive.\n"
        )
        restore_frontend(self.root)
        for destination in TEMPLATES.values():
            self.assertTrue((frontend / destination).is_file(), destination)
        app = (frontend / "src/App.tsx").read_text()
        self.assertNotIn("user={MOCK_USERS.", app)
        self.assertEqual(app.count('<AuthShell role="'), 4)

    def test_live_facade_exports_and_no_local_persistence(self):
        restore_frontend(self.root)
        frontend = self.root / "frontend"
        facade = (frontend / "src/store/workflow.ts").read_text()
        names = (
            "CONTACTS CURRENT_FACULTY CURRENT_INDUSTRY CURRENT_STUDENT TEAM_DIRECTORY "
            "useWorkflow useAllProblems submitFunding respondFunding latestFunding addReview addReply "
            "addProof removeProof publishProblem markProblemSeen toggleShortlist createProject "
            "addRequests respondCollab teamFormationRule ensureProfile setProfileEnabled regenerateSlug "
            "publicProfileUrl registerStudent getTeamLeader isMemberOf slugify timeAgo"
        ).split()
        for name in names:
            self.assertRegex(
                facade, rf"export (?:async )?(?:function|const|let) {name}\b"
            )
        self.assertNotIn("localStorage", facade)
        self.assertNotIn("MOCK_PROBLEMS", facade)
        self.assertIn("import type * as Legacy", facade)
        self.assertEqual(
            facade.count(
                "CURRENT_INDUSTRY = identity() as unknown as typeof Legacy.CURRENT_INDUSTRY;"
            ),
            2,
        )
        experience = (
            frontend / "src/integration/StudentExperience.tsx"
        ).read_text()
        self.assertNotIn("localStorage", experience)
        self.assertNotIn("Demo: mark accepted", experience)
        self.assertIn("receipt_confirmed", experience)
        self.assertIn("source: 'external'", experience)

    def test_all_role_and_public_pages_are_overlaid(self):
        restore_frontend(self.root)
        source = self.root / "frontend/src"
        for role, pages in ROLE_PAGES.items():
            for page, mode in pages.items():
                content = (source / f"pages/{role}/{page}.tsx").read_text()
                self.assertIn(f"{role.title()}Experience", content)
                self.assertIn(f'page="{mode}"', content)
                self.assertNotIn("data/mock", content)
                self.assertNotIn("localStorage", content)
        self.assertIn(
            "SharedPortfolio",
            (source / "pages/public/PublicPortfolio.tsx").read_text(),
        )
        routes = (source / "App.tsx").read_text()
        self.assertIn('path="/u/:slug"', routes)
        self.assertIn('path="/industry/reviews"', routes)
        self.assertEqual(routes.count('<AuthShell role="'), 4)

    def test_role_contracts_await_server_mutations(self):
        restore_frontend(self.root)
        source = self.root / "frontend/src/integration"
        industry = (source / "IndustryExperience.tsx").read_text()
        faculty = (source / "FacultyExperience.tsx").read_text()
        for endpoint in (
            "/views",
            "/views/close",
            "/reviews",
            "/replies",
            "/funding",
            "/problems",
            "/requests",
        ):
            self.assertIn(endpoint, industry)
        for endpoint in (
            "/users",
            "/projects",
            "/institution-changes/",
            "/shortlist",
            "/milestones",
            "/panel-feedback",
        ):
            self.assertIn(endpoint, faculty)
        self.assertIn("await mutate<Visit>", industry)
        self.assertIn("await mutate<User>", faculty)
        self.assertIn("await mutate<Project>", faculty)
        self.assertIn("f.get('transferred') === 'on'", industry)
        self.assertIn("String(f.get('password'))", faculty)
        for name in (
            "IndustryExperience.tsx",
            "FacultyExperience.tsx",
            "RoleShared.tsx",
        ):
            content = (source / name).read_text()
            self.assertNotIn("localStorage", content)
            self.assertNotIn("data/mock", content)
            self.assertNotIn("Demo: mark accepted", content)
            self.assertNotIn("void mutate", content)
        shared = (source / "StudentExperience.tsx").read_text()
        self.assertIn("await action(new FormData(form))", shared)
        records = (source / "records.ts").read_text()
        for value in (
            "/csr/summary",
            "visibilitychange",
            "30_000",
            "activeUntil",
            "document.hidden",
            "await refresh()",
        ):
            self.assertIn(value, records)
        facade = (source.parent / "store/workflow.ts").read_text()
        self.assertNotIn("void mutate", facade)
        self.assertNotIn("transfer_confirmed: true", facade)
        public = (source / "SharedPortfolio.tsx").read_text()
        self.assertIn("/public/portfolios/", public)
        self.assertNotIn("useSession", public)
        self.assertNotIn("AuthShell", public)
        self.assertIn(
            "!path.startsWith('/public/')", (source / "api.ts").read_text()
        )

    def test_unsafe_archive_fails_without_marker(self):
        with zipfile.ZipFile(self.archive, "a") as archive:
            archive.writestr("InnovateX-main/../../escape.txt", "invalid")
        with (
            patch("app.frontend_restore.logging.exception"),
            self.assertRaises(RuntimeError),
        ):
            restore_frontend(self.root)
        self.assertFalse((self.root / "escape.txt").exists())
        self.assertFalse(
            (self.root / "frontend/.innovatex-source-restored").exists()
        )

    def test_incompatible_archive_contract_fails_explicitly(self):
        with self.assertRaises(ValueError):
            overlay_sources(
                {
                    "src/App.tsx": b"invalid",
                    "src/store/workflow.ts": b"",
                    "package.json": b"{}",
                }
            )


if __name__ == "__main__":
    unittest.main()
