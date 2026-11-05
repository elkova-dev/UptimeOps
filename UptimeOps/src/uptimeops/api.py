"""Local-only FastAPI service, scheduler, monitoring API and report export."""
from __future__ import annotations

import asyncio
import csv
import io
import os
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from .monitor import probe, validate_target
from .storage import Store

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get('UPTIMEOPS_DATA_DIR', str(ROOT / 'data'))).expanduser()
store = Store(DATA_DIR / 'monitors.sqlite3')
_locks: dict[int, asyncio.Lock] = {}


class NewMonitor(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    url: HttpUrl
    interval_seconds: int = Field(default=60, ge=30, le=86400)
    contract_enabled: bool = False
    contract_path: str = Field(default='', max_length=120)
    contract_operator: str = Field(default='equals')
    contract_expected: str = Field(default='', max_length=160)

    @field_validator('name')
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Name must contain at least 2 characters')
        return value

    @model_validator(mode='after')
    def check_contract(self):
        if self.contract_enabled:
            if not self.contract_path or any(not p or not p.replace('_','').replace('-','').isalnum() for p in self.contract_path.split('.')):
                raise ValueError('Contract path must contain dot-separated JSON keys or array indices')
            if self.contract_operator not in {'equals','not_equals','exists','gte','lte'}:
                raise ValueError('Unknown contract operator')
            if self.contract_operator != 'exists' and not self.contract_expected:
                raise ValueError('Expected value cannot be empty')
        return self


async def run_check(monitor: dict) -> dict:
    key = monitor['id']
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        result = await probe(monitor['url'], contract_enabled=bool(monitor['contract_enabled']),
                             contract_path=monitor['contract_path'], contract_operator=monitor['contract_operator'],
                             contract_expected=monitor['contract_expected'])
        if store.get(key):
            store.save_check(key, **result)
        return {'monitor_id':key, **result}


async def poll_due() -> None:
    semaphore = asyncio.Semaphore(5)
    async def check_one(m: dict) -> None:
        async with semaphore:
            await run_check(m)
    while True:
        due = []
        now = datetime.now(timezone.utc)
        for m in store.list_monitors():
            last = m['last_checked']
            if not last or (now-datetime.fromisoformat(last)).total_seconds() >= m['interval_seconds']:
                if not _locks.setdefault(m['id'], asyncio.Lock()).locked():
                    due.append(m)
        if due:
            await asyncio.gather(*(check_one(m) for m in due))
        await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(application: FastAPI):
    task = asyncio.create_task(poll_due())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title='UptimeOps', version='1.0.0', lifespan=lifespan)


@app.get('/')
def index() -> FileResponse:
    return FileResponse(ROOT/'frontend'/'index.html')


@app.get('/app.css')
def css() -> FileResponse:
    return FileResponse(ROOT/'frontend'/'app.css', media_type='text/css')


@app.get('/app.js')
def javascript() -> FileResponse:
    return FileResponse(ROOT/'frontend'/'app.js', media_type='application/javascript')


@app.get('/api/health')
def health() -> dict:
    return {'status':'ok','service':'UptimeOps','version':'1.0.0'}


@app.get('/api/monitors')
def list_monitors() -> list[dict]:
    return store.list_monitors()


@app.post('/api/monitors', status_code=201)
def create_monitor(payload: NewMonitor) -> dict:
    # Do not allow users to configure generic private network probes.
    try:
        validate_target(str(payload.url))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return store.add(payload.name, str(payload.url),payload.interval_seconds,
                     payload.contract_enabled,payload.contract_path,
                     payload.contract_operator,payload.contract_expected)


@app.put('/api/monitors/{key}')
def update_monitor(key: int, payload: NewMonitor) -> dict:
    try:
        validate_target(str(payload.url))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    updated = store.update(key, payload.name, str(payload.url), payload.interval_seconds,
                           payload.contract_enabled, payload.contract_path,
                           payload.contract_operator, payload.contract_expected)
    if updated is None:
        raise HTTPException(404, 'Monitor not found')
    return updated


@app.delete('/api/monitors/{key}')
def delete_monitor(key: int) -> dict:
    if not store.delete(key):
        raise HTTPException(404, 'Monitor not found')
    _locks.pop(key, None)
    return {'deleted':True}


@app.post('/api/monitors/{key}/check')
async def check_monitor(key: int) -> dict:
    monitor = store.get(key)
    if monitor is None:
        raise HTTPException(404, 'Monitor not found')
    return await run_check(monitor)


@app.get('/api/monitors/{key}/checks')
def history(key: int, limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    if store.get(key) is None:
        raise HTTPException(404, 'Monitor not found')
    return store.checks(key,limit)


@app.get('/api/monitors/{key}/stats')
def monitor_stats(key: int) -> dict:
    if store.get(key) is None:
        raise HTTPException(404, 'Monitor not found')
    return store.uptime(key)


@app.get('/api/monitors/{key}/export.csv')
def export_csv(key: int):
    if store.get(key) is None:
        raise HTTPException(404, 'Monitor not found')
    content = io.StringIO()
    writer = csv.writer(content)
    writer.writerow(['checked_at','status','latency_ms','http_code','failure_type','error'])
    for item in reversed(store.checks(key,500)):
        writer.writerow([item[k] for k in ['checked_at','status','latency_ms','http_code','failure_type','error']])
    return StreamingResponse(iter([content.getvalue()]),media_type='text/csv',headers={'Content-Disposition': f'attachment; filename="uptimeops-monitor-{key}.csv"'})


@app.get('/api/incidents')
def incidents() -> list[dict]:
    return store.incidents()


@app.get('/api/summary')
def summary() -> dict:
    monitors = store.list_monitors()
    times = [m['last_latency_ms'] for m in monitors if m['last_latency_ms'] is not None]
    return {'monitors':len(monitors),'up':sum(m['last_status']=='up' for m in monitors),
            'down':sum(m['last_status']=='down' for m in monitors),
            'pending':sum(m['last_status']=='pending' for m in monitors),
            'contract_failures':sum(m['last_failure_type']=='contract' and m['last_status']=='down' for m in monitors),
            'avg_latency_ms':round(sum(times)/len(times)) if times else None,
            'total_checks':store.total_checks(),
            'open_incidents':store.count_open_incidents()}
