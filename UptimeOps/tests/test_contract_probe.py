import asyncio
import httpx
from uptimeops.monitor import probe, validate_target


def test_contract_probe_with_mock_transport():
    def handler(request: httpx.Request):
        if request.url.path == '/bad':
            return httpx.Response(200, json={'status':'error'})
        if request.url.path == '/too-large':
            return httpx.Response(200, content=b'x'*1_048_577)
        if request.url.path == '/invalid':
            return httpx.Response(200, content=b'not json')
        return httpx.Response(200, json={'status':'ok'})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            kwargs = {'contract_enabled':True,'contract_path':'status','contract_operator':'equals','contract_expected':'ok'}
            good=await probe('https://example.com/good',client,**kwargs)
            bad=await probe('https://example.com/bad',client,**kwargs)
            invalid=await probe('https://example.com/invalid',client,**kwargs)
            huge=await probe('https://example.com/too-large',client,**kwargs)
            assert (good['status'],good['failure_type']) == ('up',None)
            assert (bad['status'],bad['failure_type']) == ('down','contract')
            assert invalid['error']=='Response is not valid JSON'
            assert '1 MB' in huge['error']
    asyncio.run(run())


def test_target_restrictions():
    assert validate_target('http://127.0.0.1:8002/api/health') is None
    for url in ['http://127.0.0.1:9999/test', 'http://10.0.0.5/','http://169.254.169.254/latest/meta-data/','ftp://example.com', 'http://localhost:9999/']:
        try: validate_target(url)
        except ValueError: pass
        else: raise AssertionError(f'{url} should be blocked')
