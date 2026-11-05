import asyncio
import httpx
from uptimeops.monitor import probe


def test_success_and_error_with_mock_http() -> None:
    async def run():
        transport = httpx.MockTransport(lambda req: httpx.Response(200 if req.url.path == '/ok' else 503))
        async with httpx.AsyncClient(transport=transport) as client:
            good = await probe('https://example.com/ok', client)
            bad = await probe('https://example.com/unavailable', client)
        assert good['status'] == 'up'
        assert bad['status'] == 'down'
        assert bad['http_code'] == 503
    asyncio.run(run())
