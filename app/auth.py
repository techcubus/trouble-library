"""No-op auth dependency. Replace with real accounts/groups/ACLs later
without touching route signatures that depend on `get_current_user`.
"""


def get_current_user() -> None:
    return None
