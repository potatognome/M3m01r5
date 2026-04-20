#!/usr/bin/env python3
"""
M3m01r5/cli/menu.py - Interactive CLI menus for M3m01r5.

Main menu options:
  1. 📝 New Entry
  2. 📋 List Entries
  3. 🔍 Search Entries
  4. 👁️  View / Edit Entry
  5. 🗑️  Delete Entry
  6. ⚙️  Show Config
  7. 🚪 Exit

Follows tUilKit CLI menu patterns from
  .github/copilot-instructions.d/cli_menu_patterns.md
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from tUilKit import get_logger
except ImportError:
    get_logger = None  # type: ignore[assignment]

from M3m01r5.cli.formatters import entry_detail_lines, entry_summary_line
from M3m01r5.entry_schema import EntrySchema, EntryValidationError
from M3m01r5.journal_store import JournalStore

LOG_FILES: Dict[str, str] = {}

_logger = None


def _get_logger():
    global _logger
    if _logger is None and get_logger:
        _logger = get_logger()
    return _logger


# ---------------------------------------------------------------------------
# Helper: safe colour_log / print fallback
# ---------------------------------------------------------------------------

def _clog(colour: str, *parts, **kwargs) -> None:
    """Emit a colour_log if tUilKit is available, otherwise plain print."""
    lg = _get_logger()
    if lg:
        lg.colour_log(
            colour, *parts,
            log_files=list(LOG_FILES.values()),
            **kwargs,
        )
    else:
        print(" ".join(str(p) for p in parts))


def _border(text: str, colour: str = "!info") -> None:
    """Print a bordered section header."""
    lg = _get_logger()
    if lg:
        lg.apply_border(
            text=text,
            pattern={
                "TOP": "=", "BOTTOM": "=",
                "LEFT": " ", "RIGHT": " ",
            },
            total_length=70,
            border_rainbow=True,
            log_files=list(LOG_FILES.values()),
        )
    else:
        width = 70
        print("=" * width)
        print(f"  {text}")
        print("=" * width)


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def _prompt(message: str, allow_empty: bool = False) -> Optional[str]:
    """Prompt user for input; return None if blank and not allowed."""
    try:
        val = input(f"\n{message}: ").strip()
    except (KeyboardInterrupt, EOFError):
        return None
    return val if val or allow_empty else None


def _confirm(message: str, default: bool = False) -> bool:
    """Prompt yes/no confirmation; returns bool."""
    default_str = "Y/n" if default else "y/N"
    try:
        choice = input(f"\n{message} ({default_str}): ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return False
    if not choice:
        return default
    return choice in ("y", "yes")


# ---------------------------------------------------------------------------
# Menu: New Entry
# ---------------------------------------------------------------------------

def menu_new_entry(store: JournalStore, schema: EntrySchema) -> None:
    """Interactive new-entry wizard."""
    print()
    _border("📝 New Journal Entry")

    # ENTRY_START
    start_raw = _prompt(
        "ENTRY_START (ISO datetime, blank = now)"
    )
    if start_raw:
        try:
            entry_start = datetime.fromisoformat(start_raw)
        except ValueError:
            _clog("!error", f"❌ Invalid datetime: {start_raw!r}. Using now.")
            entry_start = datetime.now()
    else:
        entry_start = datetime.now()

    # ENTRY_TYPES
    types_raw = _prompt(
        "ENTRY_TYPES (comma-separated, e.g. personal,work)"
    )
    entry_types = [
        t.strip() for t in (types_raw or "").split(",") if t.strip()
    ]

    # ENTRY body
    _clog(
        "!info",
        "ENTRY body — enter text, blank line then '.' to finish:",
    )
    lines = []
    while True:
        try:
            line = input()
        except (KeyboardInterrupt, EOFError):
            break
        if line.strip() == ".":
            break
        lines.append(line)
    entry_text = "\n".join(lines)

    # Build entry dict
    entry: Dict[str, Any] = schema.build_empty(
        entry_start=entry_start,
        entry_types=entry_types,
        entry_text=entry_text,
    )

    # Optional descriptors
    optional_fields = schema.optional_fields
    if optional_fields:
        _clog(
            "!info",
            f"Optional descriptors: {', '.join(optional_fields)}",
        )
        if _confirm("Add optional fields?", default=False):
            for field in optional_fields:
                val = _prompt(f"  {field} (blank = skip)", allow_empty=True)
                if val:
                    entry[field] = val

    # Save
    try:
        entry_id = store.create_entry(entry)
        _clog("!done", f"✅ Entry saved: {entry_id}")
    except EntryValidationError as exc:
        _clog("!error", f"❌ Validation failed: {exc}")


# ---------------------------------------------------------------------------
# Menu: List Entries
# ---------------------------------------------------------------------------

def menu_list_entries(
    store: JournalStore, schema: EntrySchema
) -> None:
    """List entries with sort options."""
    print()
    _border("📋 List Entries")

    sortable = schema.sortable_fields
    _clog("!info", f"Sort by: {', '.join(sortable)}")
    sort_by = (
        _prompt("Sort field (blank = ENTRY_START)") or "ENTRY_START"
    )
    if sort_by not in sortable:
        _clog(
            "!warn",
            f"⚠️  Unknown sort field '{sort_by}'; using ENTRY_START.",
        )
        sort_by = "ENTRY_START"

    reverse = _confirm("Reverse order (newest first)?", default=True)
    entries = store.list_entries(sort_by=sort_by, reverse=reverse)

    if not entries:
        _clog("!warn", "⚠️  No entries found.")
        return

    print()
    for i, entry in enumerate(entries, 1):
        _clog(
            "!list", str(i),
            "!info", ". " + entry_summary_line(i, entry),
        )


# ---------------------------------------------------------------------------
# Menu: Search Entries
# ---------------------------------------------------------------------------

def menu_search_entries(
    store: JournalStore, schema: EntrySchema
) -> None:
    """Search entries by keyword across searchable fields."""
    print()
    _border("🔍 Search Entries")

    query = _prompt("Search keyword")
    if not query:
        _clog("!warn", "⚠️  No keyword provided.")
        return

    query_lower = query.lower()
    searchable = schema.searchable_fields

    def matches(entry: Dict[str, Any]) -> bool:
        for field in searchable:
            val = entry.get(field)
            if val is None:
                continue
            if isinstance(val, list):
                if any(
                    query_lower in str(item).lower() for item in val
                ):
                    return True
            elif isinstance(val, dict):
                if any(
                    query_lower in str(k).lower()
                    or query_lower in str(v).lower()
                    for k, v in val.items()
                ):
                    return True
            else:
                if query_lower in str(val).lower():
                    return True
        return False

    results = store.list_entries(filter_fn=matches)
    if not results:
        _clog("!warn", f"⚠️  No entries matching '{query}'.")
        return

    _clog("!info", f"Found {len(results)} matching entries:")
    for i, entry in enumerate(results, 1):
        _clog(
            "!list", str(i),
            "!info", ". " + entry_summary_line(i, entry),
        )


# ---------------------------------------------------------------------------
# Menu: View / Edit Entry
# ---------------------------------------------------------------------------

def menu_view_edit_entry(
    store: JournalStore, schema: EntrySchema
) -> None:
    """View or edit a single entry."""
    print()
    _border("👁️  View / Edit Entry")

    entries = store.list_entries(sort_by="ENTRY_START", reverse=True)
    if not entries:
        _clog("!warn", "⚠️  No entries found.")
        return

    for i, entry in enumerate(entries, 1):
        _clog(
            "!list", str(i),
            "!info", ". " + entry_summary_line(i, entry),
        )

    idx_raw = _prompt(f"Select entry (1-{len(entries)})")
    try:
        idx = int(idx_raw or "0") - 1
        if not (0 <= idx < len(entries)):
            raise ValueError
    except (ValueError, TypeError):
        _clog("!error", "❌ Invalid selection.")
        return

    entry = entries[idx]
    print()
    _border("📖 Entry Detail")
    for line in entry_detail_lines(entry):
        print(f"  {line}")

    if _confirm("Edit this entry?", default=False):
        _clog(
            "!info",
            "Enter new ENTRY body (blank line then '.' to finish,"
            " blank = keep existing):",
        )
        lines = []
        while True:
            try:
                line = input()
            except (KeyboardInterrupt, EOFError):
                break
            if line.strip() == ".":
                break
            lines.append(line)
        if lines:
            new_text = "\n".join(lines)
            entry_id = entry.get("ENTRY_ID", "")
            if store.update_entry(entry_id, {"ENTRY": new_text}):
                _clog("!done", "✅ Entry updated.")
            else:
                _clog("!error", "❌ Failed to update entry.")


# ---------------------------------------------------------------------------
# Menu: Delete Entry
# ---------------------------------------------------------------------------

def menu_delete_entry(store: JournalStore) -> None:
    """Delete an entry with confirmation."""
    print()
    _border("🗑️  Delete Entry")

    entries = store.list_entries(sort_by="ENTRY_START", reverse=True)
    if not entries:
        _clog("!warn", "⚠️  No entries found.")
        return

    for i, entry in enumerate(entries, 1):
        _clog(
            "!list", str(i),
            "!info", ". " + entry_summary_line(i, entry),
        )

    idx_raw = _prompt(f"Select entry to delete (1-{len(entries)})")
    try:
        idx = int(idx_raw or "0") - 1
        if not (0 <= idx < len(entries)):
            raise ValueError
    except (ValueError, TypeError):
        _clog("!error", "❌ Invalid selection.")
        return

    entry = entries[idx]
    entry_id = entry.get("ENTRY_ID", "")
    if _confirm(f"Really delete entry {entry_id[:8]}?", default=False):
        if store.delete_entry(entry_id):
            _clog("!done", f"✅ Entry {entry_id[:8]} deleted.")
        else:
            _clog("!error", "❌ Delete failed.")
    else:
        _clog("!info", "Delete cancelled.")


# ---------------------------------------------------------------------------
# Main interactive menu loop
# ---------------------------------------------------------------------------

def run_menu(
    store: JournalStore,
    schema: EntrySchema,
    config: Any,
) -> None:
    """Run the main interactive CLI menu loop."""
    while True:
        print()
        _border("📓 M3m01r5 — Memoir Journal")
        print()

        count = store.entry_count()
        _clog("!info", f"  📦 Total entries: {count}")
        print()
        _clog("!list", "1", "!info", ". 📝 New Entry")
        _clog("!list", "2", "!info", ". 📋 List Entries")
        _clog("!list", "3", "!info", ". 🔍 Search Entries")
        _clog("!list", "4", "!info", ". 👁️  View / Edit Entry")
        _clog("!list", "5", "!info", ". 🗑️  Delete Entry")
        _clog("!list", "6", "!info", ". ⚙️  Show Config")
        _clog("!list", "7", "!info", ". 🚪 Exit")

        choice = ""
        try:
            choice = input("\nSelect option (1-7): ").strip()
        except (KeyboardInterrupt, EOFError):
            choice = "7"

        if choice == "1":
            menu_new_entry(store, schema)
        elif choice == "2":
            menu_list_entries(store, schema)
        elif choice == "3":
            menu_search_entries(store, schema)
        elif choice == "4":
            menu_view_edit_entry(store, schema)
        elif choice == "5":
            menu_delete_entry(store)
        elif choice == "6":
            print()
            _border("⚙️  Configuration")
            try:
                import yaml
                print(
                    yaml.dump(
                        config.raw,
                        default_flow_style=False,
                        sort_keys=True,
                    )
                )
            except Exception:
                import json
                print(
                    json.dumps(
                        getattr(config, "raw", {}),
                        indent=2,
                        default=str,
                    )
                )
        elif choice == "7":
            print()
            _clog("!done", "👋 Goodbye from M3m01r5!")
            break
        else:
            _clog("!error", "❌ Invalid choice. Please select 1-7.")
