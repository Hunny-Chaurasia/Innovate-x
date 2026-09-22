import reflex as rx

import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile
import fcntl

from app.frontend_compat import (
    EXPORTS,
    archive_exports,
    await_workflow_calls,
    patch_shells,
)

VERSION = 3
EXCLUDED = {
    "node_modules",
    "dist",
    "build",
    ".git",
    ".vite",
    "coverage",
    "__MACOSX",
    ".next",
}
PAGES = {
    "StudentDashboard": "Dashboard",
    "Discover": "Discover",
    "MyProjects": "My Projects",
    "NewProject": "New Project",
    "StudentActions": "Action Center",
    "Review": "Reviews",
    "Funding": "Funding",
    "Portfolio": "Portfolio",
    "StudentSettings": "Settings",
}


INDUSTRY_PAGES = {
    "IndustryDashboard": "Industry Dashboard",
    "PostProblem": "Post Problem",
    "DiscoverProjects": "Discover Projects",
    "CSRImpact": "CSR Impact",
    "Review": "Industry Reviews",
}
FACULTY_PAGES = {
    "FacultyDashboard": "Faculty Dashboard",
    "Students": "Students",
    "ChangeRequests": "Change Requests",
    "ReviewPanel": "Review Panel",
    "ProblemStatements": "Problem Statements",
    "StudentActions": "Faculty Actions",
}


def _safe_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        "\\" in name
        or path.is_absolute()
        or ".." in path.parts
        or any(":" in p for p in path.parts)
    ):
        raise ValueError("Unsafe archive path")
    return path


def _write(root: Path, relative: str, content: bytes) -> None:
    target = root.joinpath(*_safe_path(relative).parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Destination escapes frontend directory")
    cursor = target
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError("Symlinks are not allowed in managed paths")
        cursor = cursor.parent
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() == content:
        return
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
    try:
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def restore_frontend(root: Path | None = None) -> Path:
    """Restore archive-owned files and maintained overlays, without executing JS tooling."""
    root = (root or Path(__file__).resolve().parents[1]).resolve()
    destination = root / "frontend"
    try:
        if destination.is_symlink():
            raise ValueError("Frontend destination must not be a symlink")
        destination.mkdir(parents=True, exist_ok=True)
        lock = destination / ".restore.lock"
        if lock.is_symlink():
            raise ValueError("Invalid restoration lock")
        with lock.open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            return _restore_locked(root, destination)
    except Exception as e:
        logging.exception(f"Error: {e}")
        raise


def _restore_locked(root: Path, destination: Path) -> Path:
    archive = root / "assets" / "InnovateX-main (2).zip"
    try:
        if not archive.is_file() or not zipfile.is_zipfile(archive):
            logging.warning(
                "Skipping frontend restoration: archive is unavailable or invalid"
            )
            return destination
    except Exception as e:
        logging.exception(f"Error: {e}")
        return destination
    templates = Path(__file__).resolve().parent
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(archive) as bundle:
        candidates: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
        total = 0
        for info in bundle.infolist():
            path = _safe_path(info.filename)
            if EXCLUDED.intersection(path.parts) or info.is_dir():
                continue
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError("Archive symlinks are not supported")
            if info.file_size > 64 * 1024 * 1024:
                raise ValueError(
                    "Archive source entry exceeds restoration limit"
                )
            total += info.file_size
            if total > 512 * 1024 * 1024:
                raise ValueError("Archive source exceeds restoration limit")
            candidates.append((info, path))
        roots = [
            p.parent
            for _, p in candidates
            if p.name == "package.json"
            and (p.parent / "src" / "App.tsx") in {q for _, q in candidates}
        ]
        if len(roots) != 1:
            raise ValueError(
                "Expected one React package containing src/App.tsx"
            )
        prefix = roots[0]
        for info, path in candidates:
            if not path.is_relative_to(prefix):
                continue
            relative = path.relative_to(prefix).as_posix()
            if relative in files:
                raise ValueError("Duplicate archive destination")
            # Do not restore potentially private developer environment files.
            if path.name.startswith(".env") and path.name not in {
                ".env.example",
                ".env.sample",
            }:
                continue
            files[relative] = bundle.read(info)
    if "src/App.archive.tsx" in files:
        raise ValueError("Archive uses a reserved overlay name")
    workflow_path = "src/store/workflow.ts"
    if workflow_path not in files or "src/store/workflow.contract.ts" in files:
        raise ValueError(
            "Archive workflow contract missing or reserved name occupied"
        )
    original_workflow = files[workflow_path].decode()
    actual_exports = archive_exports(original_workflow)
    if actual_exports != EXPORTS:
        raise ValueError("Archive workflow export contract changed")
    files["src/store/workflow.contract.ts"] = files[workflow_path]
    patched_app, shell_contract = patch_shells(files["src/App.tsx"].decode())
    files["src/App.archive.tsx"] = patched_app.encode()
    files["src/live/shell.contract.ts"] = shell_contract.encode()
    adapted = []
    for name, content in list(files.items()):
        if (
            name.startswith("src/")
            and name.endswith((".ts", ".tsx"))
            and name not in {workflow_path, "src/store/workflow.contract.ts"}
            and not name.startswith(
                (
                    "src/pages/student/",
                    "src/pages/industry/",
                    "src/pages/faculty/",
                )
            )
        ):
            updated = await_workflow_calls(content.decode())
            if updated.encode() != content:
                files[name] = updated.encode()
                adapted.append(name)
    for target, source in {
        "src/store/workflow.ts": "frontend_workflow.txt",
        "src/live/api.ts": "frontend_api.txt",
        "src/live/ui.tsx": "frontend_ui.txt",
        "src/live/student.tsx": "frontend_student.txt",
        "src/live/industry.tsx": "frontend_industry.txt",
        "src/live/faculty.tsx": "frontend_faculty.txt",
        "src/App.tsx": "frontend_app.txt",
    }.items():
        files[target] = (templates / source).read_bytes()
    replaced = []
    for stem, label in PAGES.items():
        path = f"src/pages/student/{stem}.tsx"
        if path not in files:
            raise ValueError(f"Archive student page contract changed: {stem}")
        if path in files:
            files[path] = (
                f'import React from "react";\nimport {{ StudentPage }} from "../../live/student";\nexport default function {stem}() {{ return <StudentPage page={json.dumps(label)} />; }}\n'.encode()
            )
            replaced.append(path)
    role_pages: dict[str, list[str]] = {}
    for role, pages in (
        ("industry", INDUSTRY_PAGES),
        ("faculty", FACULTY_PAGES),
    ):
        expected = {f"src/pages/{role}/{stem}.tsx" for stem in pages}
        actual = {
            name
            for name in files
            if name.startswith(f"src/pages/{role}/") and name.endswith(".tsx")
        }
        if actual != expected:
            raise ValueError(
                f"Archive {role} page contract changed: missing or unexpected pages"
            )
        role_pages[role] = []
        for stem, label in pages.items():
            path = f"src/pages/{role}/{stem}.tsx"
            component = f"{role.title()}Page"
            files[path] = (
                f'import React from "react";\nimport {{ {component} }} from "../../live/{role}";\nexport default function {stem}() {{ return <{component} page={json.dumps(label)} />; }}\n'.encode()
            )
            role_pages[role].append(path)
    files[".env.example"] = b"VITE_API_URL=/api/v1\n"
    files["tsconfig.student.json"] = json.dumps(
        {
            "compilerOptions": {
                "target": "ES2022",
                "lib": ["ES2022", "DOM", "DOM.Iterable"],
                "module": "ESNext",
                "moduleResolution": "Bundler",
                "jsx": "react-jsx",
                "strict": False,
                "noUnusedLocals": False,
                "noUnusedParameters": False,
                "allowImportingTsExtensions": True,
                "resolveJsonModule": True,
                "esModuleInterop": True,
                "forceConsistentCasingInFileNames": True,
                "skipLibCheck": True,
                "noEmit": True,
                "allowSyntheticDefaultImports": True,
                "types": ["vite/client"],
            },
            "include": ["src/**/*"],
        },
        indent=2,
    ).encode()
    with archive.open("rb") as handle:
        archive_sha256 = hashlib.file_digest(handle, "sha256").hexdigest()
    manifest = {
        "version": VERSION,
        "archive_sha256": archive_sha256,
        "files": {
            name: hashlib.sha256(data).hexdigest()
            for name, data in sorted(files.items())
        },
        "student_pages_replaced": replaced,
        "industry_pages_replaced": role_pages["industry"],
        "faculty_pages_replaced": role_pages["faculty"],
        "refresh_policy": "30 seconds while visible and active within 120 seconds; focus and visibility refresh",
        "role_page_contract": "exact page set with maintained default-export wrappers",
        "workflow_exports": sorted(actual_exports),
        "workflow_contract": "src/store/workflow.contract.ts",
        "typecheck_scope": "src/**/*",
        "async_callers_adapted": sorted(adapted),
        "shell_identity": "authenticated-api-user",
        "public_portfolio": "unauthenticated",
        "compatibility_status": "API workflow facade and shell identity installed",
    }
    for name, content in files.items():
        _write(destination, name, content)
    _write(
        destination,
        ".restore-manifest.json",
        json.dumps(manifest, indent=2).encode(),
    )
    return destination


if __name__ == "__main__":
    restore_frontend()
