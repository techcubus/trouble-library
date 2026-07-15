import sqlite3
from dataclasses import dataclass


@dataclass
class PathTokens:
    """Fields a path template can reference when organize mode renders
    a target location for a media item on disk."""

    category: str = ""
    subject: str = ""
    author: str = ""
    series: str = ""
    series_index: str = ""
    title: str = ""

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "PathTokens":
        keys = row.keys()
        return cls(
            category=row["category"] or "",
            subject=row["subject"] or "",
            author=(row["author"] or "") if "author" in keys else "",
            series=(row["series"] or "") if "series" in keys else "",
            series_index=(row["series_index"] or "") if "series_index" in keys else "",
            title=row["title"] or "",
        )
