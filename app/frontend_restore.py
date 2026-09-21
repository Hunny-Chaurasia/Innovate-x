import reflex as rx

import hashlib
import json
import logging
import zipfile
from pathlib import Path, PurePosixPath

from app.frontend_overlay import OVERLAY_VERSION, overlay_sources


_EXCLUDED_PARTS = {
    "node_modules",
    "dist",
    "build",
    ".git",
    ".cache",
    "coverage",
}


def restore_frontend(root: Path | None = None) -> None:
    root = root or Path(__file__).resolve().parent.parent
    archive = root / "assets" / "InnovateX-main (2).zip"
    destination = root / "frontend"
    marker = destination / ".innovatex-source-restored"
    try:
        if not archive.is_file():
            raise FileNotFoundError(
                "The approved frontend archive is unavailable"
            )
        original: dict[str, bytes] = {}
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                path = PurePosixPath(member.filename)
                parts = path.parts
                if (
                    member.is_dir()
                    or not parts
                    or any(p in _EXCLUDED_PARTS for p in parts)
                ):
                    continue
                if (
                    path.is_absolute()
                    or ".." in parts
                    or "\\" in member.filename
                ):
                    raise ValueError("Unsafe archive member")
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Archive symlinks are not supported")
                relative = PurePosixPath(*parts[1:]) if len(parts) > 1 else path
                name = relative.as_posix()
                if name in original:
                    raise ValueError("Duplicate archive member")
                original[name] = package.read(member)
        files = overlay_sources(original)
        manifest = {
            name: hashlib.sha256(content).hexdigest()
            for name, content in files.items()
        }
        marker_text = json.dumps(
            {"version": OVERLAY_VERSION, "files": manifest}, sort_keys=True
        )
        # Legacy markers never suppress an updated overlay. Missing or changed files repair themselves.
        if (
            marker.is_file()
            and marker.read_text(encoding="utf-8") == marker_text
        ):
            intact = all(
                (destination / name).is_file()
                and hashlib.sha256(
                    (destination / name).read_bytes()
                ).hexdigest()
                == digest
                for name, digest in manifest.items()
            )
            if intact:
                return
        destination.mkdir(parents=True, exist_ok=True)
        if marker.exists():
            marker.unlink()
        for name, content in files.items():
            target = destination / name
            if destination.resolve() not in target.resolve().parents:
                raise ValueError("Unsafe frontend destination")
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.is_file() or target.read_bytes() != content:
                temporary = target.with_name(f".{target.name}.overlay-tmp")
                temporary.write_bytes(content)
                temporary.replace(target)
        temporary_marker = marker.with_suffix(".tmp")
        temporary_marker.write_text(marker_text, encoding="utf-8")
        temporary_marker.replace(marker)
    except zipfile.BadZipFile as e:
        logging.exception(f"Error: {e}")
        return
    except (OSError, ValueError) as e:
        logging.exception(f"Error: {e}")
        raise RuntimeError(
            "Frontend restoration failed; no successful overlay marker was written"
        ) from e
