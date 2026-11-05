from pathlib import Path
from uptimeops.storage import Store


def test_incident_open_once_and_auto_recover(tmp_path: Path):
    store = Store(tmp_path / 'test.sqlite3')
    monitor = store.add('My health API', 'https://example.com/health', 60,True,'status','equals','ok')
    assert monitor['contract_enabled'] == 1
    key = monitor['id']
    store.save_check(key,'up',12,200,None,None)
    store.save_check(key,'down',14,200,'Expected status = ok','contract')
    store.save_check(key,'down',16,200,'Expected status = ok','contract')
    items = store.incidents()
    assert len(items) == 1
    assert items[0]['resolved_at'] is None
    assert items[0]['failure_type'] == 'contract'
    store.save_check(key,'up',9,200,None,None)
    assert store.incidents()[0]['resolved_at'] is not None
    assert len(store.checks(key)) == 4
    assert store.uptime(key)['uptime_percent'] == 50.0
    assert store.total_checks() == 4
    assert store.delete(key)
    assert store.incidents() == []
    assert store.checks(key) == []


def test_migration_of_previous_preview_database(tmp_path: Path):
    import sqlite3
    db_path = tmp_path / 'old.sqlite3'
    with sqlite3.connect(db_path) as db:
        db.execute('''CREATE TABLE monitors (
          id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,url TEXT NOT NULL,
          interval_seconds INTEGER NOT NULL,created_at TEXT NOT NULL,last_checked TEXT,
          last_status TEXT NOT NULL DEFAULT 'pending',last_latency_ms INTEGER,last_http_code INTEGER,last_error TEXT)''')
        db.execute('''CREATE TABLE checks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,monitor_id INTEGER NOT NULL,
          checked_at TEXT NOT NULL,status TEXT NOT NULL,latency_ms INTEGER,http_code INTEGER,error TEXT)''')
        db.execute("INSERT INTO monitors(name,url,interval_seconds,created_at) VALUES('Old','https://example.com',60,'2026-10-29T10:00:00+00:00')")
    store = Store(db_path)
    assert store.list_monitors()[0]['contract_enabled'] == 0
    assert store.list_monitors()[0]['last_failure_type'] is None
    assert store.incidents() == []
