#!/usr/bin/env python3
"""
M3m01r5/cli/formatters.py - Display helpers for journal entries.

Formats entry dicts for terminal display: summary rows and detail views.
"""
from datetime import datetime
from typing import Any, Dict, List


def _fmt_dt(value: Any) -> str:
    """Return a readable datetime string from various input types."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass
    return str(value) if value is not None else "—"


def entry_summary_line(idx: int, entry: Dict[str, Any]) -> str:
    """Return a one-line summary string for a list view."""
    entry_id = entry.get("ENTRY_ID", "?")[:8]
    start = _fmt_dt(entry.get("ENTRY_START"))
    types = ", ".join(entry.get("ENTRY_TYPES") or []) or "(none)"
    snippet = str(entry.get("ENTRY", ""))[:60].replace("\n", " ")
    return f"[{entry_id}] {start}  [{types}]  {snippet}…"


def entry_detail_lines(entry: Dict[str, Any]) -> List[str]:
    """Return a multi-line list of strings for a full entry detail view."""
    lines: List[str] = []
    lines.append(f"ENTRY_ID    : {entry.get('ENTRY_ID', '?')}")
    lines.append(f"ENTRY_START : {_fmt_dt(entry.get('ENTRY_START'))}")
    lines.append(
        f"ENTRY_TYPES : {', '.join(entry.get('ENTRY_TYPES') or [])}"
    )
    lines.append("")
    lines.append("ENTRY:")
    for line in str(entry.get("ENTRY", "")).splitlines():
        lines.append(f"  {line}")

    # Optional descriptors
    skip = {"ENTRY_ID", "ENTRY_START", "ENTRY_TYPES", "ENTRY"}
    extras = {k: v for k, v in entry.items() if k not in skip}
    if extras:
        lines.append("")
        lines.append("── Optional fields ──────────────────────────")
        for k, v in extras.items():
            lines.append(f"  {k}: {v}")

    return lines
