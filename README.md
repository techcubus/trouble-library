# trouble-library

Self-hosted, mixed-media library. Catalogs media and lets you search/download —
playback and rendering are left to whatever tool you normally use to open the
file. Epub is the first supported media type.

## Run it

```
docker compose up --build
```

- Public search/download UI: http://localhost:8000
- Admin UI (import, edit metadata, settings): http://localhost:8001 (bound to
  127.0.0.1 by default — not reachable off the host unless you change the
  port mapping in `docker-compose.yml`)

Drop `.epub` files into `./media/inbox`, then on the admin UI click
"Scan inbox for new epubs". Metadata (title, author, series, ISBN, publisher,
date, language, description, cover) is parsed from each epub's OPF. Scanned
files land in the **review queue** (see below) — they're not added to the
catalog or visible to the public UI until reviewed.

## Review queue

Scanning the inbox doesn't catalog files immediately — each new epub becomes
a pending item in the admin Queue (`/queue`), invisible to the public search/
browse/download UI until it's been reviewed. Opening a queue item shows the
same metadata fields as editing a regular catalog item, plus one of:

- **Apply & File** — save the metadata and file the book into
  `./media/library` per the path template below, same as organize mode's
  filing, regardless of whether organize mode is globally on.
- **Apply (DB only)** — save the metadata, add the item to the catalog, but
  leave the file exactly where it is.
- **Remove from queue** — forget this item; if its file isn't already in the
  inbox (e.g. it was set aside), it's moved back there so a future scan
  picks it up again.

There's also **Set aside for manual review**, available per-item or in bulk
from the queue list: moves the file into `./media/manual_review` and keeps
it in the queue with the same options, so you can fully clear the inbox
without having to make a filing decision on every item right away.

## Organize mode

Off by default. Toggle it under Settings in the admin UI. When on, editing
an already-catalogued item's metadata moves the file into `./media/library`
according to the configured path template (default:
`{category}/{subject}/{author}/{series}/{title}`). Empty tokens (e.g. no
series, no subject) are dropped from the path automatically. `category` and
`subject` are free-text fields you set per item — there's no fixed
vocabulary; use whatever top-level sections and topics make sense for your
collection. Filing a queue item via "Apply & File" always happens,
independent of this toggle — see Review queue above.

When organize mode is off, catalog edits don't move files — they stay
wherever they were filed.

There's also a "copy instead of move" toggle: when on, the source file (e.g.
in the inbox) is left in place the first time it's filed into the library —
a copy is made instead. Later re-organizing the same item (from a metadata
edit) still relocates that library copy rather than making another one, so
edits don't pile up duplicates.

## Config (env vars)

| Var | Default | Meaning |
|---|---|---|
| `DATA_DIR` | `/data` | SQLite DB + extracted covers |
| `MEDIA_INBOX_DIR` | `/media/inbox` | Where new files are scanned from |
| `MEDIA_LIBRARY_ROOT` | `/media/library` | Organize-mode destination root |
| `MEDIA_MANUAL_REVIEW_DIR` | `/media/manual_review` | Where queue items set aside for later live |
| `ADMIN_PORT` | `8001` | Admin app port |
| `PUBLIC_PORT` | `8000` | Public search/download app port |

## Notes

- No authentication yet. The admin/public split is a separate port, not an
  ACL — don't expose the admin port beyond your own machine/network.
- SQLite in WAL mode, shared by both processes in the same container.
- Search is SQLite FTS5 (prefix match per word) over title/author/series/
  publisher/description/category/subject. Only reviewed (catalog) items are
  searchable, browsable, or downloadable publicly — queue items are admin-only
  until applied.
- The public UI also has a Browse view, a directory listing over
  `MEDIA_LIBRARY_ROOT` (only meaningful with organize mode on, since that's
  what actually populates that tree) with breadcrumb navigation.
