from typing import Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app import config, db, storage
from app.ingest import epub as epub_ingest
from app.templating import templates

router = APIRouter()


def _scan_inbox() -> int:
    imported = 0
    with db.db_session() as conn:
        for file_path in sorted(config.MEDIA_INBOX_DIR.rglob("*")):
            if not file_path.is_file() or file_path.suffix.lower() not in config.SUPPORTED_EPUB_EXTENSIONS:
                continue

            file_hash = storage.hash_file(file_path)
            if db.get_media_item_by_hash(conn, file_hash) is not None:
                continue

            metadata = epub_ingest.parse_epub(file_path)
            media_item_id = db.insert_media_item(
                conn,
                media_type="epub",
                title=metadata.title,
                category="",
                subject="",
                description=metadata.description,
                file_path=str(file_path),
                file_hash=file_hash,
                file_size=file_path.stat().st_size,
                format="epub",
                status="pending",
            )

            cover_path = ""
            if metadata.cover_bytes:
                cover_path = epub_ingest.save_cover(config.COVERS_DIR, media_item_id, metadata.cover_bytes)

            db.upsert_epub_metadata(
                conn,
                media_item_id,
                author=metadata.author,
                series=metadata.series,
                series_index=metadata.series_index,
                isbn=metadata.isbn,
                publisher=metadata.publisher,
                pub_date=metadata.pub_date,
                language=metadata.language,
                cover_path=cover_path,
            )

            imported += 1
    return imported


@router.get("/")
def index(request: Request, scanned: Optional[int] = None):
    with db.db_session() as conn:
        items = db.list_media_items(conn)
        organize_enabled = db.get_setting(conn, "organize_enabled") == "1"
        queue_count = len(db.list_queue_items(conn))
    return templates.TemplateResponse(
        "admin_index.html",
        {
            "request": request, "items": items, "scanned": scanned,
            "organize_enabled": organize_enabled, "queue_count": queue_count,
        },
    )


@router.post("/import/scan")
def import_scan():
    imported = _scan_inbox()
    return RedirectResponse(url=f"/?scanned={imported}", status_code=303)


@router.post("/library/reset")
def reset_library():
    with db.db_session() as conn:
        db.reset_library(conn)
    return RedirectResponse(url="/", status_code=303)


@router.get("/media/{media_item_id}/edit")
def edit_form(request: Request, media_item_id: int):
    with db.db_session() as conn:
        item = db.get_media_item(conn, media_item_id)
    return templates.TemplateResponse("admin_edit.html", {"request": request, "item": item})


@router.post("/media/{media_item_id}")
def update_media_item(
    media_item_id: int,
    title: str = Form(...),
    category: str = Form(""),
    subject: str = Form(""),
    description: str = Form(""),
    author: str = Form(""),
    series: str = Form(""),
    series_index: str = Form(""),
    isbn: str = Form(""),
    publisher: str = Form(""),
    pub_date: str = Form(""),
    language: str = Form(""),
):
    with db.db_session() as conn:
        db.update_media_item_fields(
            conn, media_item_id,
            {"title": title, "category": category, "subject": subject, "description": description},
        )
        row = db.get_media_item(conn, media_item_id)
        existing_cover_path = row["cover_path"] if row else ""
        db.upsert_epub_metadata(
            conn, media_item_id,
            author=author, series=series, series_index=series_index,
            isbn=isbn, publisher=publisher, pub_date=pub_date, language=language,
            cover_path=existing_cover_path or "",
        )

        organize_enabled = db.get_setting(conn, "organize_enabled") == "1"
        if organize_enabled:
            path_template = db.get_setting(conn, "path_template") or config.DEFAULT_PATH_TEMPLATE
            organize_copy_mode = db.get_setting(conn, "organize_copy_mode") == "1"
            storage.organize_file(
                conn, media_item_id, config.MEDIA_LIBRARY_ROOT, path_template, copy=organize_copy_mode
            )

    return RedirectResponse(url="/", status_code=303)


@router.post("/media/{media_item_id}/delete")
def delete_media_item(media_item_id: int):
    with db.db_session() as conn:
        db.delete_media_item(conn, media_item_id)
    return RedirectResponse(url="/", status_code=303)


@router.get("/settings")
def settings_form(request: Request):
    with db.db_session() as conn:
        organize_enabled = db.get_setting(conn, "organize_enabled") == "1"
        organize_copy_mode = db.get_setting(conn, "organize_copy_mode") == "1"
        path_template = db.get_setting(conn, "path_template") or config.DEFAULT_PATH_TEMPLATE
    return templates.TemplateResponse(
        "admin_settings.html",
        {
            "request": request,
            "organize_enabled": organize_enabled,
            "organize_copy_mode": organize_copy_mode,
            "path_template": path_template,
        },
    )


@router.post("/settings")
def update_settings(
    organize_enabled: bool = Form(False),
    organize_copy_mode: bool = Form(False),
    path_template: str = Form(config.DEFAULT_PATH_TEMPLATE),
):
    with db.db_session() as conn:
        db.set_setting(conn, "organize_enabled", "1" if organize_enabled else "0")
        db.set_setting(conn, "organize_copy_mode", "1" if organize_copy_mode else "0")
        db.set_setting(conn, "path_template", path_template.strip() or config.DEFAULT_PATH_TEMPLATE)
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/settings/reset")
def reset_settings():
    with db.db_session() as conn:
        db.reset_settings(conn)
    return RedirectResponse(url="/settings", status_code=303)
