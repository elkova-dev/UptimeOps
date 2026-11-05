import asyncio

import httpx
import pytest

from uptimeops.monitor import probe


@pytest.mark.parametrize('status', [301, 302, 307, 308])
def test_redirect_not_reported_as_healthy(status: int) -> None:
    """A redirect must not look like a healthy response when redirects are disabled."""
    async def run() -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status, headers={'Location': 'https://elsewhere.example/'})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            result = await probe('https://example.com/redirect', client)
        assert result['status'] == 'down'
        assert result['failure_type'] == 'http'
        assert result['http_code'] == status

    asyncio.run(run())
