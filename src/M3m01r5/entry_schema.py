#!/usr/bin/env python3
"""
M3m01r5/entry_schema.py - Journal Entry Schema

Defines the schema for journal entries:
  Mandatory: ENTRY_START (datetime), ENTRY_TYPES (list), ENTRY (str)
  Optional:  any descriptor registered in config.d/descriptors/

Provides validate() and build_empty() helpers.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


MANDATORY_FIELDS = ("ENTRY_START", "ENTRY_TYPES", "ENTRY")


class EntryValidationError(Exception):
    """Raised when an entry fails schema validation."""


class EntrySchema:
    """
    Validates and normalises journal entry dicts.

    Parameters
    ----------
    descriptors : dict
        Merged descriptor schema from MemoirConfig.descriptors.
        Keys are field names; values are schema dicts with at least
        {"type": ..., "required": bool}.
    """

    def __init__(self, descriptors: Dict[str, Any]) -> None:
        self._descriptors = descriptors

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, entry: Dict[str, Any]) -> None:
        """
        Validate *entry* against the schema.

        Raises EntryValidationError on the first failure.
        """
        for field in MANDATORY_FIELDS:
            if field not in entry:
                raise EntryValidationError(
                    f"Missing mandatory field: {field!r}"
                )

        # ENTRY_START must be parseable as datetime or already be a datetime
        if not isinstance(entry["ENTRY_START"], datetime):
            try:
                datetime.fromisoformat(str(entry["ENTRY_START"]))
            except ValueError as exc:
                raise EntryValidationError(
                    "ENTRY_START must be a valid ISO datetime; "
                    f"got {entry['ENTRY_START']!r}"
                ) from exc

        # ENTRY_TYPES must be a list
        if not isinstance(entry["ENTRY_TYPES"], list):
            raise EntryValidationError(
                "ENTRY_TYPES must be a list; "
                f"got {type(entry['ENTRY_TYPES']).__name__}"
            )

        # ENTRY must be a non-empty string
        if not isinstance(entry["ENTRY"], str) or not entry["ENTRY"].strip():
            raise EntryValidationError(
                "ENTRY must be a non-empty string."
            )

    def build_empty(
        self,
        entry_start: Optional[datetime] = None,
        entry_types: Optional[List[str]] = None,
        entry_text: str = "",
    ) -> Dict[str, Any]:
        """Return a minimal valid entry dict with default values."""
        return {
            "ENTRY_ID": str(uuid.uuid4()),
            "ENTRY_START": (entry_start or datetime.now()).isoformat(),
            "ENTRY_TYPES": entry_types or [],
            "ENTRY": entry_text,
        }

    @property
    def optional_fields(self) -> List[str]:
        """Return list of optional descriptor field names."""
        return [
            k for k, v in self._descriptors.items()
            if not v.get("required", False)
        ]

    @property
    def sortable_fields(self) -> List[str]:
        """Return field names that may be used for sorting."""
        core = ["ENTRY_START"]
        extra = [
            k for k, v in self._descriptors.items()
            if v.get("sortable", False)
        ]
        return core + [f for f in extra if f not in core]

    @property
    def searchable_fields(self) -> List[str]:
        """Return field names that may be used for searching."""
        core = ["ENTRY_TYPES", "ENTRY"]
        extra = [
            k for k, v in self._descriptors.items()
            if v.get("searchable", False)
        ]
        return core + [f for f in extra if f not in core]
