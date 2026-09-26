"""SQLite response cache. Unauthenticated GitHub allows 60 requests/hour, so repeat
questions must not cost a request. Entries keep their fetch time: fresh entries are
served normally, stale ones only as a fallback (rate-limited, offline, network down)."""
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CacheEntry:
    body: Any
    fetched_at: float

    def age(self) -> float:
        return time.time() - self.fetched_at


class ResponseCache:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, body TEXT NOT NULL, fetched_at REAL NOT NULL)"
            )
            self._db.commit()

    def get(self, key: str, max_age: float | None) -> CacheEntry | None:
        """max_age=None returns the entry however old it is."""
        with self._lock:
            row = self._db.execute("SELECT body, fetched_at FROM responses WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        entry = CacheEntry(json.loads(row[0]), row[1])
        if max_age is not None and entry.age() > max_age:
            return None
        return entry

    def set(self, key: str, body: Any, fetched_at: float | None = None) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO responses (key, body, fetched_at) VALUES (?, ?, ?)",
                (key, json.dumps(body), fetched_at if fetched_at is not None else time.time()),
            )
            self._db.commit()

    def keys(self) -> list[str]:
        with self._lock:
            return [r[0] for r in self._db.execute("SELECT key FROM responses ORDER BY key")]

    def clear(self) -> None:
        with self._lock:
            self._db.execute("DELETE FROM responses")
            self._db.commit()
