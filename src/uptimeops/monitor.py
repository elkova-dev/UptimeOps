"""Bounded asynchronous HTTP probes and optional API contract validation."""
from __future__ import annotations

import ipaddress
import socket
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from .contracts import inspect_contract

MAX_RESPONSE_BYTES = 1_048_576


def validate_target(url: str) -> None:
    """Block common private-network targets except the explicitly supported self-demo.

    This is defense in depth for a local-only tool, NOT a guarantee against DNS
    rebinding. Do not expose this app to untrusted users.
    """
    parsed = urlsplit(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise ValueError('Only HTTP and HTTPS URLs are accepted')
    if parsed.username or parsed.password:
        raise ValueError('Credentials in URLs are not allowed')
    if parsed.hostname == '127.0.0.1' and parsed.port == 8002 and parsed.path == '/api/health':
        return
    if parsed.hostname.lower() == 'localhost' or parsed.hostname.lower().endswith('.localhost'):
        raise ValueError('Private-network URLs are disabled')
    try:
        ips = [ipaddress.ip_address(parsed.hostname)]
    except ValueError:
        try:
            ips = [ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)]
        except (socket.gaierror, ValueError, OSError) as exc:
            raise ValueError('Cannot resolve endpoint hostname') from exc
    if not ips or any(not ip.is_global for ip in ips):
        raise ValueError('Private, loopback and reserved addresses are disabled')


async def probe(url: str, client: httpx.AsyncClient | None = None, *, contract_enabled: bool = False,
                contract_path: str = '', contract_operator: str = 'equals', contract_expected: str = '') -> dict[str, Any]:
    """Perform GET with no redirects, requiring 2xx and optional JSON assertion."""
    started = time.perf_counter()
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=httpx.Timeout(7.0), follow_redirects=False, trust_env=False)
    assert client is not None
    try:
        # In-memory injected test clients still use target validation through API.
        if own_client:
            validate_target(url)
        async with client.stream('GET', url, follow_redirects=False) as response:
            latency_ms = int((time.perf_counter() - started) * 1000)
            code = response.status_code
            if code < 200 or code >= 300:
                return {'status':'down', 'latency_ms':latency_ms, 'http_code':code, 'error':f'HTTP {code}', 'failure_type':'http'}
            if contract_enabled:
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        return {'status':'down', 'latency_ms':latency_ms, 'http_code':code, 'error':'JSON response exceeds 1 MB', 'failure_type':'contract'}
                try:
                    import json
                    body = json.loads(content)
                except (ValueError, UnicodeDecodeError):
                    return {'status':'down', 'latency_ms':latency_ms, 'http_code':code, 'error':'Response is not valid JSON', 'failure_type':'contract'}
                mismatch = inspect_contract(body, contract_path, contract_operator, contract_expected)
                if mismatch:
                    return {'status':'down', 'latency_ms':latency_ms, 'http_code':code, 'error':mismatch[:240], 'failure_type':'contract'}
            return {'status':'up', 'latency_ms':latency_ms, 'http_code':code, 'error':None, 'failure_type':None}
    except (httpx.HTTPError, ValueError, OSError) as exc:
        return {'status':'down', 'latency_ms':None, 'http_code':None, 'error':f'{type(exc).__name__}: {str(exc)[:180]}', 'failure_type':'network'}
    finally:
        if own_client:
            await client.aclose()
