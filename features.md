# trouble-library — features

Status legend: **done** (built + verified) · **in progress** · **planned** (designed, not built) · **maybe** (idea, no design/commitment).

## Data model / core

| Feature | Status | Description |
|---|---|---|
| SQLite storage, WAL mode | done | Single `library.db`, shared by admin + public processes. |
| FTS5 search index | done | `media_items_fts`, porter-tokenized, over title/author/series/publisher/description/category/subject. |
| `media_items` + `epub_metadata` tables | done | Core item record + epub-specific bibliographic fields (author, series, series_index, isbn, publisher, pub_date, language, cover_path). |
| Item `status` (pending / manual_review / active) | done | Drives review-queue visibility; public routes and search only ever see `active`. Existing rows migrate to `active` automatically. |
| Settings table | done | `organize_enabled`, `organize_copy_mode`, `path_template`, key/value. |

## Ingest (`app/ingest/epub.py`)

| Feature | Status | Description |
|---|---|---|
| OPF metadata parsing | done | title/author/series/series_index/isbn/publisher/pub_date/language/description via ebooklib, incl. calibre-prefixed-meta namespace workaround. |
| Cover extraction + normalization | done | Picks best cover candidate (declared cover → name-matched image → largest image), resizes/re-encodes to capped JPEG. |
| Write metadata back into the epub file | planned | New `epub_writer.py`: mutate via ebooklib, write to a sibling temp file, verify by re-parsing, atomic replace-only-on-success. Feeds "Apply in place" below. |

## Storage / organize (`app/storage.py`)

| Feature | Status | Description |
|---|---|---|
| Path templating (`{category}/{subject}/{author}/{series}/{title}`) | done | Empty tokens dropped automatically; segments sanitized. |
| Filename collision resolution | done | `Title (2).epub`-style suffixing. |
| Copy vs. move on first filing | done | "Copy instead of move" setting; re-organizing an already-filed item always relocates rather than duplicating. |
| Empty-directory pruning on re-organize | done | Fixed this session — re-filing a book no longer leaves orphaned empty folders behind in the library tree. |
| Generic move-into-dir helper (`move_file_into`) | done | Backs queue set-aside/remove; collision-safe, no-op if already there. |
| Filename-only rename (no directory move) | planned | Needed for "Apply in place" — reuse the path template's last segment only. |

## Review queue (`app/admin/queue.py`)

| Feature | Status | Description |
|---|---|---|
| Queue list (`/queue`) | done | Pending + manual_review items, oldest first, bulk-selectable. |
| Per-item review/editor (`/queue/{id}/review`) | done | Same metadata fields as the regular edit form (shared `_media_fields.html` include). |
| Apply & File | done | Saves metadata, marks `active`, files into `MEDIA_LIBRARY_ROOT` via the normal organize logic — always, regardless of the global organize-mode toggle. |
| Apply (DB only) | done | Saves metadata, marks `active`, file untouched. |
| Apply in place | planned | Save metadata + rename file in place + write metadata into the epub itself (see epub_writer above). Highest-risk piece, deliberately deferred. |
| Remove from queue | done | Deletes the tracking row; returns the file to the inbox if it isn't already there, so a rescan re-queues it. |
| Set aside for manual review | done | Single-item or bulk; moves the file to `MEDIA_MANUAL_REVIEW_DIR`, keeps it in the queue with the same actions available. Decouples review from the inbox so the inbox stays drainable. |
| External metadata lookup (Open Library, Google Books) | planned | Search by ISBN/LCCN or title+author; results rendered per-field. |
| Per-field "apply" from a lookup candidate | planned | htmx fragment swap — replaces one form input with the candidate's value, no page reload, no custom JS. |
| MARC record parsing | maybe | Considered and explicitly deprioritized in favor of the two JSON APIs above; would be more authoritative but substantially more work for likely marginal gain. |
| Amazon metadata lookup | not planned | No viable free/keyless API for a self-hosted personal tool (Product Advertising API needs an active affiliate/sales account). Ruled out. |
| Consistency/repair tool | maybe | Detect DB rows whose `file_path` no longer exists (or untracked files under a managed dir) and offer to relink by hash. Flagged as a future closer of a narrow, low-probability crash-window gap in the remove/set-aside actions — not built. |

## Admin app (`app/admin`)

| Feature | Status | Description |
|---|---|---|
| Scan inbox for new epubs | done | Dedup by sha256; inserts as `pending` into the review queue (no longer auto-catalogs). |
| Catalog listing (`/`) | done | Active items only. |
| Edit metadata (active items) | done | |
| Delete item | done | Removes the DB row; file is explicitly left on disk. |
| Settings page | done | Organize mode toggle, copy-mode toggle, path template. |
| Initialize library (wipe catalog) | done | Clears `media_items`/`epub_metadata`/FTS + resets id counter; settings and all files untouched. |
| Initialize settings (reset to defaults) | done | Catalog untouched. |
| Queue-count nav badge | done | | 
| Authentication / access control | maybe | Currently none — admin/public split is a port, not an ACL. No design yet; README calls this out explicitly as a known gap. |

## Public app (`app/public`)

| Feature | Status | Description |
|---|---|---|
| Search | done | Debounced live search via htmx, FTS5-backed, active-items-only. |
| Browse | done | Directory listing over `MEDIA_LIBRARY_ROOT`, breadcrumb nav; only meaningful with organize mode on. |
| Item detail page | done | |
| Download | done | |
| Cover image serving | done | |
| Direct-ID access blocked for unreviewed items | done | Detail/download/cover all explicitly check `status == 'active'` and 404 otherwise — closes the one path that bypassed FTS filtering. |

## Frontend / UI

| Feature | Status | Description |
|---|---|---|
| htmx-driven live search | done | Only current htmx usage; debounced `hx-get`. |
| Vendored `htmx.min.js` | done | So the app also works when run outside Docker (the Dockerfile still fetches its own pinned copy at build time). |
| Shared metadata-field partial | done | `_media_fields.html`, used by both the regular edit form and the queue review form. |
| Status badges / danger-zone button styling | done | Reused for queue status + the two "Initialize" actions. |
| Light/dark theme | done | `prefers-color-scheme`-based CSS custom properties. |

## Media types

| Feature | Status | Description |
|---|---|---|
| Epub | done | Only supported type currently. |
| Other formats (audiobooks, comics, etc.) | maybe | README's "mixed-media library" framing implies more are intended eventually; no concrete design yet. |

## Ops / dev tooling

| Feature | Status | Description |
|---|---|---|
| Docker Compose (admin + public + volumes) | done | Includes the manual-review volume mount. |
| `dev.sh` (start/stop/status/restart) | done | Local venv, no Docker required; owns its own `data/`/`inbox/`/`library/`/`manual_review/` dirs. |
| `.gitignore` coverage for local/dev artifacts | done | |
