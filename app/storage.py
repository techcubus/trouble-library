import hashlib
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Optional

from app import db
from app.models import PathTokens

_INVALID_CHARS = re.compile(r'[\/\\:*?"<>|\x00-\x1f]')
_MAX_SEGMENT_LENGTH = 120


def sanitize_segment(value: str) -> str:
    value = _INVALID_CHARS.sub("", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value[:_MAX_SEGMENT_LENGTH].strip()


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


def render_path_segments(template: str, tokens: PathTokens) -> list[str]:
    token_map = _SafeDict(
        category=tokens.category,
        subject=tokens.subject,
        author=tokens.author,
        series=tokens.series,
        series_index=tokens.series_index,
        title=tokens.title,
    )
    segments = []
    for raw_segment in template.split("/"):
        rendered = raw_segment.format_map(token_map)
        sanitized = sanitize_segment(rendered)
        if sanitized:
            segments.append(sanitized)
    return segments


def resolve_collision(target_path: Path, keep_if_same_as: Optional[Path] = None) -> Path:
    if keep_if_same_as is not None and target_path.resolve() == keep_if_same_as.resolve():
        return target_path
    if not target_path.exists():
        return target_path
    stem, suffix, parent = target_path.stem, target_path.suffix, target_path.parent
    n = 2
    while True:
        candidate = parent / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def compute_target_path(
    library_root: Path, template: str, tokens: PathTokens, extension: str
) -> Path:
    segments = render_path_segments(template, tokens)
    if not segments:
        segments = ["untitled"]
    path = library_root
    for part in segments[:-1]:
        path = path / part
    filename = f"{segments[-1]}{extension}"
    return path / filename


def prune_empty_dirs(start: Path, library_root: Path) -> None:
    """Remove start and any now-empty ancestor directories, stopping at
    (and never removing) library_root itself."""
    root = library_root.resolve()
    current = start.resolve()
    if current != root and root not in current.parents:
        return
    while current != root and current.is_dir() and not any(current.iterdir()):
        parent = current.parent
        current.rmdir()
        current = parent


def hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def organize_file(
    conn: sqlite3.Connection,
    media_item_id: int,
    library_root: Path,
    path_template: str,
    copy: bool = False,
) -> Optional[Path]:
    """File a media item's file to match its current metadata, per the
    configured path template. No-op if the computed path is unchanged.

    When copy=True, the source is only ever copied - never deleted - the
    first time it's filed into the library (e.g. straight out of the
    inbox). Once a copy already lives in the library tree, later
    re-organizing (from a metadata edit) moves that library copy to its
    new location rather than copying again, so re-edits don't pile up
    duplicate copies inside library_root.
    """
    row = db.get_media_item(conn, media_item_id)
    if row is None:
        return None
    current_path = Path(row["file_path"])
    extension = current_path.suffix
    tokens = PathTokens.from_row(row)
    target_path = compute_target_path(library_root, path_template, tokens, extension)

    if target_path.resolve() == current_path.resolve():
        return current_path

    target_path = resolve_collision(target_path, keep_if_same_as=current_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    root = library_root.resolve()
    source_already_in_library = root == current_path.resolve() or root in current_path.resolve().parents
    if copy and not source_already_in_library:
        shutil.copy2(str(current_path), str(target_path))
    else:
        old_parent = current_path.resolve().parent
        shutil.move(str(current_path), str(target_path))
        if source_already_in_library:
            prune_empty_dirs(old_parent, library_root)
    db.update_media_item_file_path(conn, media_item_id, str(target_path))
    return target_path
