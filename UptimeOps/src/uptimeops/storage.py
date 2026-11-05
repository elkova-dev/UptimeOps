"""SQLite persistence, migrations and incident lifecycle."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS monitors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    interval_seconds INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    last_checked TEXT,
                    last_status TEXT NOT NULL DEFAULT 'pending',
                    last_latency_ms INTEGER,
                    last_http_code INTEGER,
                    last_error TEXT
                );
                CREATE TABLE IF NOT EXISTS checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    monitor_id INTEGER NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
                    checked_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    latency_ms INTEGER,
                    http_code INTEGER,
                    error TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_checks_monitor_date ON checks(monitor_id, id DESC);
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    monitor_id INTEGER NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
                    opened_at TEXT NOT NULL,
                    resolved_at TEXT,
                    reason TEXT NOT NULL,
                    failure_type TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_incidents_monitor ON incidents(monitor_id, id DESC);
            ''')
            for table, additions in {
                'monitors': {'contract_enabled':'INTEGER NOT NULL DEFAULT 0', 'contract_path':"TEXT NOT NULL DEFAULT ''",
                    'contract_operator':"TEXT NOT NULL DEFAULT 'equals'", 'contract_expected':"TEXT NOT NULL DEFAULT ''",
                    'last_failure_type':'TEXT'},
                'checks': {'failure_type':'TEXT'},
            }.items():
                existing = {row[1] for row in db.execute(f'PRAGMA table_info({table})')}
                for col, column_type in additions.items():
                    if col not in existing:
                        db.execute(f'ALTER TABLE {table} ADD COLUMN {col} {column_type}')

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=10000')
        return db

    def add(self, name: str, url: str, seconds: int, contract_enabled: bool = False,
            contract_path: str = '', contract_operator: str = 'equals', contract_expected: str = '') -> dict[str, Any]:
        with self.connect() as db:
            cursor = db.execute('''INSERT INTO monitors
                (name,url,interval_seconds,created_at,contract_enabled,contract_path,contract_operator,contract_expected)
                VALUES(?,?,?,?,?,?,?,?)''',
                (name, url, seconds, utcnow(), int(contract_enabled),contract_path,contract_operator,contract_expected))
            key = cursor.lastrowid
        return self.get(int(key))  # type: ignore[return-value]

    def get(self, key: int) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute('SELECT * FROM monitors WHERE id=?', (key,)).fetchone()
        return dict(row) if row else None

    def list_monitors(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM monitors ORDER BY id DESC').fetchall()]

    def update(self, key: int, name: str, url: str, seconds: int,
               contract_enabled: bool = False, contract_path: str = '',
               contract_operator: str = 'equals', contract_expected: str = '') -> dict[str, Any] | None:
        with self.connect() as db:
            cursor = db.execute("""UPDATE monitors SET name=?,url=?,interval_seconds=?,
                contract_enabled=?,contract_path=?,contract_operator=?,contract_expected=?,
                last_checked=NULL,last_status='pending',last_latency_ms=NULL,
                last_http_code=NULL,last_error=NULL,last_failure_type=NULL WHERE id=?""",
                (name,url,seconds,int(contract_enabled),contract_path,contract_operator,contract_expected,key))
            if cursor.rowcount:
                db.execute('UPDATE incidents SET resolved_at=? WHERE monitor_id=? AND resolved_at IS NULL', (utcnow(),key))
        return self.get(key) if cursor.rowcount else None

    def count_open_incidents(self) -> int:
        with self.connect() as db:
            return int(db.execute('SELECT COUNT(*) FROM incidents WHERE resolved_at IS NULL').fetchone()[0])

    def delete(self, key: int) -> bool:
        with self.connect() as db:
            cursor = db.execute('DELETE FROM monitors WHERE id=?', (key,))
            return cursor.rowcount > 0

    def save_check(self, key: int, status: str, latency_ms: int | None, http_code: int | None,
                   error: str | None, failure_type: str | None = None) -> None:
        now = utcnow()
        with self.connect() as db:
            monitor = db.execute('SELECT last_status FROM monitors WHERE id=?', (key,)).fetchone()
            if monitor is None:
                return
            db.execute('''INSERT INTO checks (monitor_id,checked_at,status,latency_ms,http_code,error,failure_type)
                VALUES(?,?,?,?,?,?,?)''', (key,now,status,latency_ms,http_code,error,failure_type))
            db.execute('''UPDATE monitors SET last_checked=?,last_status=?,last_latency_ms=?,
                last_http_code=?,last_error=?,last_failure_type=? WHERE id=?''',
                (now,status,latency_ms,http_code,error,failure_type,key))
            open_incident = db.execute('SELECT id FROM incidents WHERE monitor_id=? AND resolved_at IS NULL ORDER BY id DESC LIMIT 1', (key,)).fetchone()
            if status == 'down' and open_incident is None:
                db.execute('INSERT INTO incidents(monitor_id,opened_at,reason,failure_type) VALUES (?,?,?,?)',
                           (key,now,(error or 'Endpoint unavailable')[:240], failure_type or 'http'))
            if status == 'up' and open_incident is not None:
                db.execute('UPDATE incidents SET resolved_at=? WHERE id=?', (now,open_incident['id']))

    def checks(self, key: int, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM checks WHERE monitor_id=? ORDER BY id DESC LIMIT ?', (key,min(max(limit,1),500))).fetchall()]

    def incidents(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [dict(row) for row in db.execute('''SELECT incidents.*, monitors.name AS monitor_name, monitors.url AS monitor_url
                FROM incidents JOIN monitors ON monitors.id=incidents.monitor_id
                ORDER BY incidents.id DESC LIMIT ?''', (min(max(limit,1),200),)).fetchall()]

    def total_checks(self) -> int:
        with self.connect() as db:
            return int(db.execute('SELECT COUNT(*) FROM checks').fetchone()[0])

    def uptime(self, key: int, limit: int = 100) -> dict[str, Any]:
        with self.connect() as db:
            rows = db.execute('SELECT status, latency_ms FROM checks WHERE monitor_id=? ORDER BY id DESC LIMIT ?', (key,limit)).fetchall()
        count = len(rows)
        up = sum(row['status']=='up' for row in rows)
        latencies = [row['latency_ms'] for row in rows if row['latency_ms'] is not None]
        return {'sample_size': count, 'uptime_percent': round(up/count*100,1) if count else None,
                'avg_latency_ms': round(sum(latencies)/len(latencies)) if latencies else None}
