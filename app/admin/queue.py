import sqlite3
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app import config, db, storage
from app.templating import templates

router = APIRouter()


def _apply_metadata(
    conn: sqlite3.Connection,
    media_item_id: int,
    *,
    title: str,
    category: str,
    subject: str,
    description: str,
    author: str,
    series: str,
    series_index: str,
    isbn: str,
    publisher: str,
    pub_date: str,
    language: str,
) -> None:
    db.update_media_item_fields(
        conn, media_item_id,
        {
            "title": title, "category": category, "subject": subject,
            "description": description, "status": "active",
        },
    )
    row = db.get_media_item(conn, media_item_id)
    existing_cover_path = row["cover_path"] if row else ""
    db.upsert_epub_metadata(
        conn, media_item_id,
        author=author, series=series, series_index=series_index,
        isbn=isbn, publisher=publisher, pub_date=pub_date, language=language,
        cover_path=existing_cover_path or "",
    )


@router.get("/queue")
def queue_list(request: Request):
    with db.db_session() as conn:
        items = db.list_queue_items(conn)
    return templates.TemplateResponse("admin_queue.html", {"request": request, "items": items})


@router.get("/queue/{media_item_id}/review")
def queue_review(request: Request, media_item_id: int):
    with db.db_session() as conn:
        item = db.get_media_item(conn, media_item_id)
    return templates.TemplateResponse("admin_queue_review.html", {"request": request, "item": item})


@router.post("/queue/{media_item_id}/apply-file")
def apply_file(
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
        _apply_metadata(
            conn, media_item_id,
            title=title, category=category, subject=subject, description=description,
            author=author, series=series, series_index=series_index, isbn=isbn,
            publisher=publisher, pub_date=pub_date, language=language,
        )
        organize_copy_mode = db.get_setting(conn, "organize_copy_mode") == "1"
        path_template = db.get_setting(conn, "path_template") or config.DEFAULT_PATH_TEMPLATE
        storage.organize_file(
            conn, media_item_id, config.MEDIA_LIBRARY_ROOT, path_template, copy=organize_copy_mode
        )
    return RedirectResponse(url="/queue", status_code=303)


@router.post("/queue/{media_item_id}/apply-db-only")
def apply_db_only(
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
        _apply_metadata(
            conn, media_item_id,
            title=title, category=category, subject=subject, description=description,
            author=author, series=series, series_index=series_index, isbn=isbn,
            publisher=publisher, pub_date=pub_date, language=language,
        )
    return RedirectResponse(url="/queue", status_code=303)


@router.post("/queue/{media_item_id}/remove")
def remove_from_queue(media_item_id: int):
    with db.db_session() as conn:
        row = db.get_media_item(conn, media_item_id)
        if row is not None:
            current_path = Path(row["file_path"])
            if current_path.exists() and not storage.is_within(current_path, config.MEDIA_INBOX_DIR):
                storage.move_file_into(current_path, config.MEDIA_INBOX_DIR)
            db.delete_media_item(conn, media_item_id)
    return RedirectResponse(url="/queue", status_code=303)


@router.post("/queue/set-aside")
def set_aside(ids: list[int] = Form([])):
    with db.db_session() as conn:
        for media_item_id in ids:
            row = db.get_media_item(conn, media_item_id)
            if row is None:
                continue
            current_path = Path(row["file_path"])
            if current_path.exists():
                new_path = storage.move_file_into(current_path, config.MEDIA_MANUAL_REVIEW_DIR)
                db.update_media_item_file_path(conn, media_item_id, str(new_path))
            db.update_media_item_fields(conn, media_item_id, {"status": "manual_review"})
    return RedirectResponse(url="/queue", status_code=303)
