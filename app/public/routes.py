from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app import config, db, storage
from app.templating import templates

router = APIRouter()


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _resolve_library_subpath(subpath: str) -> Path:
    root = config.MEDIA_LIBRARY_ROOT.resolve()
    parts = [p for p in subpath.split("/") if p]
    if any(p in (".", "..") for p in parts):
        raise HTTPException(status_code=404)
    candidate = root.joinpath(*parts).resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=404)
    return candidate


def _build_match_query(raw: str) -> str:
    terms = raw.split()
    if not terms:
        return ""
    escaped = ['"{}"*'.format(term.replace('"', '""')) for term in terms]
    return " ".join(escaped)


def _search(q: str) -> list:
    if not q.strip():
        return []
    match_query = _build_match_query(q)
    if not match_query:
        return []
    with db.db_session() as conn:
        return db.search_media_items(conn, match_query)


@router.get("/")
def search_page(request: Request, q: str = ""):
    results = _search(q)
    return templates.TemplateResponse(
        "public_search.html", {"request": request, "results": results, "query": q}
    )


@router.get("/search")
def search_fragment(request: Request, q: str = ""):
    results = _search(q)
    return templates.TemplateResponse(
        "public_results.html", {"request": request, "results": results, "query": q}
    )


@router.get("/browse")
@router.get("/browse/{subpath:path}")
def browse(request: Request, subpath: str = ""):
    target = _resolve_library_subpath(subpath)
    if not target.is_dir():
        raise HTTPException(status_code=404)

    crumb_parts = [p for p in subpath.split("/") if p]
    breadcrumbs = [
        {"name": part, "path": "/".join(crumb_parts[: i + 1])}
        for i, part in enumerate(crumb_parts)
    ]

    directories = []
    files = []
    with db.db_session() as conn:
        for entry in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            if entry.is_dir():
                item_count = sum(1 for _ in entry.iterdir())
                directories.append({
                    "name": entry.name,
                    "path": "/".join(crumb_parts + [entry.name]),
                    "item_count": item_count,
                })
            elif entry.is_file():
                row = db.get_media_item_by_file_path(conn, str(entry))
                stat = entry.stat()
                added_at = row["added_at"] if row else datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat()
                files.append({
                    "name": entry.name,
                    "row": row,
                    "size": _human_size(stat.st_size),
                    "added_at": added_at,
                })

    return templates.TemplateResponse(
        "public_browse.html",
        {
            "request": request,
            "breadcrumbs": breadcrumbs,
            "directories": directories,
            "files": files,
        },
    )


@router.get("/media/{media_item_id}")
def detail(request: Request, media_item_id: int):
    with db.db_session() as conn:
        item = db.get_media_item(conn, media_item_id)
    if item is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("public_detail.html", {"request": request, "item": item})


@router.get("/media/{media_item_id}/download")
def download(media_item_id: int):
    with db.db_session() as conn:
        item = db.get_media_item(conn, media_item_id)
    if item is None:
        raise HTTPException(status_code=404)
    filename = f"{storage.sanitize_segment(item['title']) or 'untitled'}.{item['format']}"
    return FileResponse(item["file_path"], filename=filename)


@router.get("/media/{media_item_id}/cover")
def cover(media_item_id: int):
    with db.db_session() as conn:
        item = db.get_media_item(conn, media_item_id)
    if item is None or not item["cover_path"]:
        raise HTTPException(status_code=404)
    return FileResponse(item["cover_path"])
