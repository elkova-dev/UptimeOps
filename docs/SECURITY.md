# Security model and known limitations

**UptimeOps is intended for a single trusted user on localhost.** It is not safe to deploy publicly without additional engineering.

## Current precautions

- Server startup defaults to `127.0.0.1`.
- HTTP and HTTPS URL validation; embedded username/password are rejected.
- Outgoing probes use explicit timeouts, don't follow redirects, and bypass proxy environment configuration.
- Private, loopback, link-local, multicast and reserved IPs are blocked for general monitors. Only the exact self-check endpoint `http://127.0.0.1:8002/api/health` is allowed for local demonstration.
- JSON contract responses are limited to 1 MiB. No remote code is executed.
- SQL statements are parameterized; API input uses Pydantic validation; UI escapes content interpolated into HTML.
- `.gitignore` prevents SQLite databases and local `.env` files from being committed.

## Important gaps

- The hostname-to-IP validation is separate from HTTPX's DNS resolution; **DNS rebinding remains possible**. This is **not** a full SSRF mitigation. A production service must pin/validate the actual connected IP and enforce egress firewall rules.
- No user authentication or CSRF defenses. An untrusted webpage visited on the same machine may attempt requests to localhost; use in a trusted environment only.
- The scheduler is not durable across process downtime. Monitoring is unavailable if your computer or process is offline.
- No notification delivery retries, multi-tenancy, backups, data retention, secret manager or encryption at rest.
- URL/exception details may include infrastructure information. Do not publish databases or screenshots with private URLs.

## What would be required before public deployment

Authentication and authorization, CSRF protections, hardened outbound HTTP transport with IP pinning, network firewall, rate limiting, a production worker/scheduler, database concurrency strategy, monitoring, audit log, and real deployment testing.
