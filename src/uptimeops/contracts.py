"""Content assertions for JSON API responses (without executing user code)."""
from __future__ import annotations

from typing import Any


def inspect_contract(data: Any, path: str, operator: str, expected: str) -> str | None:
    """Return a descriptive mismatch, or None when the contract passes.

    The path is a dot-separated sequence of JSON object keys or array indices.
    No Python expressions or arbitrary JSONPath expressions are evaluated.
    """
    current = data
    for part in path.split('.'):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdecimal() and int(part) < len(current):
            current = current[int(part)]
        else:
            return f"Missing JSON field: {path}"
    if operator == 'exists':
        return None
    if operator == 'equals':
        # Values are intentionally configured as human-readable strings.
        actual = 'null' if current is None else (str(current).lower() if isinstance(current, bool) else str(current))
        return None if actual == expected else f"Expected {path} = {expected!r}, got {actual!r}"
    if operator == 'not_equals':
        actual = 'null' if current is None else (str(current).lower() if isinstance(current, bool) else str(current))
        return None if actual != expected else f"Unexpected {path} = {expected!r}"
    if operator in {'gte', 'lte'}:
        if isinstance(current, bool):
            return f"{path} is not numeric"
        try:
            value = float(current)
            target = float(expected)
        except (ValueError, TypeError, OverflowError):
            return f"{path} or expected value is not numeric"
        good = value >= target if operator == 'gte' else value <= target
        sign = '>=' if operator == 'gte' else '<='
        return None if good else f"Expected {path} {sign} {expected}, got {value:g}"
    return 'Unsupported contract operator'
