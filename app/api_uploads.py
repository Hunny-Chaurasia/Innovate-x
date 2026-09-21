import reflex as rx

import asyncio
import hashlib
import logging
import secrets
from pathlib import Path
from uuid import UUID

from app.api_runtime import APIRouter, Query, Request

from app.api_contracts import Result
from app.api_core import (
    Actor,
    DB,
    audit,
    fail,
    get,
    insert,
    project_access,
    require,
    result,
)

router = APIRouter(prefix="/api/v1", tags=["Proof uploads"])

MEDIA = {
    "image/jpeg": ("image", ".jpg", 2097152),
    "image/png": ("image", ".png", 2097152),
    "image/gif": ("image", ".gif", 2097152),
    "image/webp": ("image", ".webp", 2097152),
    "video/mp4": ("video", ".mp4", 104857600),
    "video/quicktime": ("video", ".mov", 104857600),
    "video/webm": ("video", ".webm", 104857600),
    "video/ogg": ("video", ".ogg", 104857600),
}


def signature_matches(mime: str, header: bytes) -> bool:
    match mime:
        case "image/jpeg":
            return header.startswith(b"\xff\xd8\xff")
        case "image/png":
            return header.startswith(b"\x89PNG\r\n\x1a\n")
        case "image/gif":
            return header.startswith((b"GIF87a", b"GIF89a"))
        case "image/webp":
            return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
        case "video/mp4" | "video/quicktime":
            return header[4:8] == b"ftyp"
        case "video/webm":
            return header.startswith(b"\x1aE\xdf\xa3")
        case "video/ogg":
            return header.startswith(b"OggS")
        case _:
            return False


async def write_upload(request: Request):
    mime = request.headers.get("content-type", "").split(";")[0].lower()
    if mime not in MEDIA:
        fail(
            415,
            "unsupported_media",
            "Use a supported image or video content type",
        )
    kind, extension, maximum = MEDIA[mime]
    name = f"{secrets.token_hex(32)}{extension}"
    path = rx.get_upload_dir() / name
    size = 0
    header = b""
    checksum = hashlib.sha256()
    handle = None
    try:
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        handle = await asyncio.to_thread(path.open, "xb")
        async for chunk in request.stream():
            size += len(chunk)
            if size > maximum:
                fail(
                    413,
                    "upload_too_large",
                    "Images are limited to 2 MB and videos to 100 MB",
                )
            if len(header) < 32:
                header = b"".join((header, chunk[: 32 - len(header)]))
            checksum.update(chunk)
            await asyncio.to_thread(handle.write, chunk)
        await asyncio.to_thread(handle.close)
        handle = None
        if not size or not signature_matches(mime, header):
            fail(
                422,
                "invalid_media",
                "File contents do not match the declared media type",
            )
        return path, {
            "kind": kind,
            "source": "upload",
            "url": f"/_upload/{name}",
            "storage_key": name,
            "mime_type": mime,
            "size_bytes": size,
            "checksum_sha256": checksum.hexdigest(),
        }
    except Exception as e:
        logging.exception(f"Error: {type(e).__name__}")
        if handle:
            await asyncio.to_thread(handle.close)
        await asyncio.to_thread(path.unlink, missing_ok=True)
        raise


@router.post(
    "/projects/{identity}/proofs/upload", response_model=Result, status_code=201
)
async def upload_proof(
    identity: UUID,
    request: Request,
    db: DB,
    user: Actor,
    title: str = Query(min_length=3, max_length=240),
    description: str = Query(default="", max_length=10000),
    filename: str = Query(default="Attachment", max_length=255),
):
    project, team = await project_access(db, identity, user, member=True)
    require(team["status"] == "active")
    if len(title.strip()) < 3:
        fail(422, "invalid_title", "Proof titles require at least 3 characters")
    path, metadata = await write_upload(request)
    try:
        proof = await insert(
            db,
            "proof_entries",
            {
                "project_id": identity,
                "author_id": user["id"],
                "title": title.strip(),
                "description": description.strip(),
            },
        )
        attachment = await insert(
            db,
            "proof_attachments",
            {**metadata, "entry_id": proof["id"], "name": Path(filename).name},
        )
        await audit(db, user["id"], "proof.uploaded", proof["id"], identity)
        return result({**proof, "attachments": [attachment]})
    except Exception as e:
        logging.exception(f"Error: {type(e).__name__}")
        await asyncio.to_thread(path.unlink, missing_ok=True)
        raise
