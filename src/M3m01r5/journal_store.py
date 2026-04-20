#!/usr/bin/env python3
"""
M3m01r5/journal_store.py - Journal Entry Store

Manages persistence of journal entries as individual YAML files.

One file per entry:  data/entries/<ENTRY_ID>.yaml

Supports:
  - create_entry()  : write a new entry file
  - load_entry()    : read one entry by ID
  - list_entries()  : return all entries, with optional sort/filter
  - update_entry()  : overwrite an entry file
  - delete_entry()  : remove an entry file
"""
import copy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    import yaml
except ImportError as exc:
    raise ImportError("PyYAML is required: pip install pyyaml") from exc

from M3m01r5.entry_schema import EntrySchema, EntryValidationError


class JournalStore:
    """
    YAML-backed journal entry store.

    Parameters
    ----------
    data_dir : Path
        Directory where entry YAML files are kept.
    schema : EntrySchema
        Schema instance used to validate entries before writing.
    """

    def __init__(self, data_dir: Path, schema: EntrySchema) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._schema = schema

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_entry(self, entry: Dict[str, Any]) -> str:
        """
        Validate and persist *entry*.  Returns the ENTRY_ID.

        Raises EntryValidationError if validation fails.
        """
        self._schema.validate(entry)
        entry_id = entry.get("ENTRY_ID") or str(
            __import__("uuid").uuid4()
        )
        entry = copy.deepcopy(entry)
        entry["ENTRY_ID"] = entry_id
        self._write(entry_id, entry)
        return entry_id

    def load_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Return the entry dict for *entry_id*, or None if not found."""
        path = self._path_for(entry_id)
        if not path.is_file():
            return None
        return self._read(path)

    def list_entries(
        self,
        sort_by: str = "ENTRY_START",
        reverse: bool = False,
        filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return all entries, optionally sorted and filtered.

        Parameters
        ----------
        sort_by : str
            Field name to sort by.  Missing fields sort last.
        reverse : bool
            Descending order if True.
        filter_fn : callable, optional
            Predicate taking an entry dict; returns True to include it.
        """
        entries = []
        for yaml_file in sorted(self._data_dir.glob("*.yaml")):
            try:
                entry = self._read(yaml_file)
                entries.append(entry)
            except Exception:
                continue

        if filter_fn:
            entries = [e for e in entries if filter_fn(e)]

        def sort_key(e: Dict[str, Any]):
            val = e.get(sort_by)
            if val is None:
                return ("", "")
            if isinstance(val, datetime):
                return (0, val.isoformat())
            return (0, str(val))

        entries.sort(key=sort_key, reverse=reverse)
        return entries

    def update_entry(
        self, entry_id: str, updates: Dict[str, Any]
    ) -> bool:
        """
        Merge *updates* into the existing entry and re-validate.

        Returns True on success, False if entry not found.
        """
        existing = self.load_entry(entry_id)
        if existing is None:
            return False
        merged = {**existing, **updates}
        self._schema.validate(merged)
        self._write(entry_id, merged)
        return True

    def delete_entry(self, entry_id: str) -> bool:
        """Remove entry file. Returns True if deleted, False if not found."""
        path = self._path_for(entry_id)
        if not path.is_file():
            return False
        path.unlink()
        return True

    def entry_count(self) -> int:
        """Return the total number of stored entries."""
        return len(list(self._data_dir.glob("*.yaml")))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _path_for(self, entry_id: str) -> Path:
        return self._data_dir / f"{entry_id}.yaml"

    def _write(self, entry_id: str, entry: Dict[str, Any]) -> None:
        with open(
            self._path_for(entry_id), "w", encoding="utf-8"
        ) as fh:
            yaml.dump(
                entry, fh, default_flow_style=False, allow_unicode=True
            )

    def _read(self, path: Path) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data if isinstance(data, dict) else {}
