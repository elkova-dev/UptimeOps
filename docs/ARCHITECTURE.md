# UptimeOps architecture

## Execution model

- **FastAPI** serves a single-page dashboard and a local REST API on port `8002`.
- **Async scheduler:** one task runs every 10 seconds and checks due monitors (at most five concurrently). Manual checks use the same `run_check` logic and a per-monitor lock.
- **Probe:** HTTPX requests use an explicit 7-second timeout, disable redirects, and do not use environment proxies. With JSON assertions, responses are limited to 1 MB.
- **Contract engine:** parses the JSON body and traverses dot-separated keys / numeric array indexes. It never executes expressions, JavaScript, or Python from responses.
- **SQLite store:** tracks monitors, individual checks, and incidents. SQL uses bound parameters and database connections are short lived.
- **UI:** HTML/CSS/vanilla JavaScript, no external icon CDN; vector icons are defined in one SVG sprite to avoid font-based misalignment.

## Data model

- `monitors`: endpoint definition, polling interval, optional JSON assertion, most recent result.
- `checks`: append-only check history (status, latency, HTTP code, failure reason/category).
- `incidents`: one active incident per monitor; a failed check opens it, recovery closes it automatically.

## Status rules

- HTTP `200`-`399` without a contract = healthy.
- HTTP `200`-`399` with a matching JSON contract = healthy.
- HTTP `4xx`/`5xx` or other non-success status = HTTP failure.
- HTTP success with invalid JSON or a failed contract = contract failure.
- Network error, invalid/reserved target address, DNS failure or timeout = network failure.

A status code is not sufficient proof of business health; contract assertions deliberately add a content-level signal.

## Database migration

`Store` creates missing tables and adds the new contract columns to databases produced by the earlier preview. Existing monitors and checks remain intact.

## Deliberate constraints

Local service, no cloud account, no distributed workers. Changes to backend interfaces and data validation should be accompanied by pytest tests. This is a personal portfolio application, not a production multi-tenant system.
