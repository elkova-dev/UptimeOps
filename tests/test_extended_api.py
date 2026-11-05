from pathlib import Path
from fastapi.testclient import TestClient
import uptimeops.api as api_module
from uptimeops.storage import Store


def test_endpoint_contract_incident_and_csv(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(api_module, 'store', Store(tmp_path / 'api.sqlite3'))
    async def fake_probe(url, **kwargs):
        return {'status':'down', 'latency_ms':15, 'http_code':200,
                'error':'Expected status = ok, got error','failure_type':'contract'}
    monkeypatch.setattr(api_module, 'probe', fake_probe)
    client = TestClient(api_module.app)
    payload={'name':'Contract endpoint','url':'http://127.0.0.1:8002/api/health','interval_seconds':60,
             'contract_enabled':True,'contract_path':'status','contract_operator':'equals','contract_expected':'ok'}
    created=client.post('/api/monitors',json=payload)
    assert created.status_code==201, created.text
    key=created.json()['id']
    bad=client.post(f'/api/monitors/{key}/check')
    assert bad.status_code==200
    assert bad.json()['failure_type']=='contract'
    assert client.get('/api/summary').json()['contract_failures']==1
    assert client.get('/api/incidents').json()[0]['resolved_at'] is None
    assert client.get(f'/api/monitors/{key}/stats').json()['uptime_percent']==0.0
    exported=client.get(f'/api/monitors/{key}/export.csv')
    assert exported.status_code==200 and 'contract' in exported.text
    assert client.delete(f'/api/monitors/{key}').status_code==200
    assert client.get('/api/incidents').json()==[]


def test_contract_input_validation():
    client=TestClient(api_module.app)
    obj={'name':'Test','url':'http://127.0.0.1:8002/api/health','contract_enabled':True,
         'contract_path':'status','contract_operator':'equals'}
    assert client.post('/api/monitors',json=obj).status_code==422
    obj['contract_operator']='evil_python_code'
    assert client.post('/api/monitors',json=obj).status_code==422


def test_update_monitor_clears_old_status(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(api_module, 'store', Store(tmp_path / 'updates.sqlite3'))
    client=TestClient(api_module.app)
    body={'name':'Old API','url':'http://127.0.0.1:8002/api/health','interval_seconds':60}
    created=client.post('/api/monitors',json=body).json()
    key=created['id']
    api_module.store.save_check(key,'down',15,500,'HTTP 500','http')
    body['name']='New API'
    body.update(contract_enabled=True,contract_path='status',contract_operator='equals',contract_expected='ok')
    updated=client.put(f'/api/monitors/{key}',json=body)
    assert updated.status_code==200
    assert updated.json()['name']=='New API'
    assert updated.json()['last_status']=='pending'
    assert api_module.store.count_open_incidents()==0
    assert client.put('/api/monitors/999999',json=body).status_code==404
