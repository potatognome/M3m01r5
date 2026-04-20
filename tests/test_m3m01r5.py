#!/usr/bin/env python3
"""
tests/test_m3m01r5.py - M3m01r5 Test Suite

Validates:
  - _deep_merge utility
  - MemoirConfig: YAML loading, config.d merge, descriptor loading
  - EntrySchema.validate(): passes for valid, raises for missing/wrong types
  - EntrySchema.build_empty(): returns correct structure
  - EntrySchema.sortable_fields and searchable_fields
  - JournalStore: create, load, list, update, delete
  - entry_summary_line and entry_detail_lines formatters

tUilKit is mocked so tests run in any environment.
"""

import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Path setup — allow imports from src/
# ---------------------------------------------------------------------------

_TESTS_DIR = Path(__file__).resolve().parent
_SRC_DIR = _TESTS_DIR.parent / "src"
_CONFIG_DIR = _TESTS_DIR.parent / "config"

if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# ---------------------------------------------------------------------------
# tUilKit mock — installed before any M3m01r5 imports
# ---------------------------------------------------------------------------


def _make_tuilkit_mock() -> types.ModuleType:
    """Build a minimal tUilKit stub."""
    mock_logger = MagicMock()
    mock_logger.colour_log = MagicMock()
    mock_logger.log_exception = MagicMock()
    mock_logger.apply_border = MagicMock()

    tuilkit = types.ModuleType("tUilKit")
    tuilkit.get_logger = MagicMock(return_value=mock_logger)
    tuilkit.get_config_loader = MagicMock(return_value=MagicMock())
    tuilkit.get_file_system = MagicMock(return_value=MagicMock())
    return tuilkit


_tuilkit_mock = _make_tuilkit_mock()
sys.modules["tUilKit"] = _tuilkit_mock

# ---------------------------------------------------------------------------
# Now import M3m01r5 modules
# ---------------------------------------------------------------------------

from M3m01r5.config_manager import (  # noqa: E402
    MemoirConfig,
    _deep_merge,
    _load_yaml_dir,
    _load_yaml_file,
)
from M3m01r5.entry_schema import (  # noqa: E402
    EntrySchema,
    EntryValidationError,
    MANDATORY_FIELDS,
)
from M3m01r5.journal_store import JournalStore  # noqa: E402
from M3m01r5.cli.formatters import (  # noqa: E402
    entry_detail_lines,
    entry_summary_line,
)


# ===========================================================================
# 1. Utility: _deep_merge
# ===========================================================================

class TestDeepMerge(unittest.TestCase):

    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 99, "c": 3}
        result = _deep_merge(base, override)
        self.assertEqual(result, {"a": 1, "b": 99, "c": 3})

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}}
        override = {"x": {"b": 99, "c": 3}}
        result = _deep_merge(base, override)
        self.assertEqual(result["x"], {"a": 1, "b": 99, "c": 3})

    def test_base_not_mutated(self):
        base = {"a": {"nested": 1}}
        override = {"a": {"nested": 99}}
        _deep_merge(base, override)
        self.assertEqual(base["a"]["nested"], 1)

    def test_override_wins_on_scalar(self):
        result = _deep_merge({"k": "old"}, {"k": "new"})
        self.assertEqual(result["k"], "new")

    def test_empty_override(self):
        base = {"a": 1}
        self.assertEqual(_deep_merge(base, {}), {"a": 1})

    def test_empty_base(self):
        override = {"a": 1}
        self.assertEqual(_deep_merge({}, override), {"a": 1})

    def test_deeply_nested_merge(self):
        base = {"a": {"b": {"c": 1, "d": 2}}}
        override = {"a": {"b": {"c": 99}}}
        result = _deep_merge(base, override)
        self.assertEqual(result["a"]["b"]["c"], 99)
        self.assertEqual(result["a"]["b"]["d"], 2)


# ===========================================================================
# 2. MemoirConfig — loading from real files
# ===========================================================================

class TestMemoirConfig(unittest.TestCase):

    def setUp(self):
        self.config = MemoirConfig(config_dir=_CONFIG_DIR)

    def test_loads_project_name(self):
        project = self.config.get("project", {})
        self.assertEqual(project.get("name"), "M3m01r5")

    def test_loads_journal_section(self):
        journal = self.config.journal
        self.assertIsInstance(journal, dict)
        self.assertIn("data_dir", journal)

    def test_loads_logging_section(self):
        log = self.config.logging
        self.assertIsInstance(log, dict)
        self.assertIn("log_files", log)

    def test_loads_colours_section(self):
        colours = self.config.colours
        self.assertIsInstance(colours, dict)

    def test_config_d_merged_display(self):
        """config.d/20_display.yaml must be deep-merged into base."""
        raw = self.config.raw
        self.assertIn("display", raw)
        self.assertTrue(raw["display"].get("rainbow_borders"))

    def test_config_d_merged_logging(self):
        """config.d/10_logging.yaml must be deep-merged into base."""
        raw = self.config.raw
        self.assertIn("logging", raw)
        self.assertIn("rotate", raw["logging"])

    def test_raw_is_copy(self):
        r1 = self.config.raw
        r1["__mutated"] = True
        r2 = self.config.raw
        self.assertNotIn("__mutated", r2)

    def test_missing_config_dir_returns_empty(self):
        cfg = MemoirConfig(config_dir=Path("/nonexistent/path"))
        self.assertEqual(cfg.raw, {})

    def test_descriptors_loaded(self):
        """Descriptor files from config.d/descriptors/ should be merged."""
        desc = self.config.descriptors
        self.assertIsInstance(desc, dict)
        # Check fields from all four descriptor files
        self.assertIn("ABOUT_START", desc)
        self.assertIn("ABOUT_FEELINGS", desc)
        self.assertIn("IMAGES", desc)
        self.assertIn("AUTHOR", desc)

    def test_descriptors_returns_copy(self):
        d1 = self.config.descriptors
        d1["__mutated"] = True
        d2 = self.config.descriptors
        self.assertNotIn("__mutated", d2)

    def test_sortable_fields_from_descriptors(self):
        sortable = self.config.sortable_fields
        # ABOUT_START and AUTHOR are sortable in descriptor files
        self.assertIn("ABOUT_START", sortable)
        self.assertIn("AUTHOR", sortable)

    def test_searchable_fields_from_descriptors(self):
        searchable = self.config.searchable_fields
        # ABOUT_FEELINGS, AUTHOR, TAGS, LOCATION are searchable
        self.assertIn("ABOUT_FEELINGS", searchable)
        self.assertIn("AUTHOR", searchable)
        self.assertIn("TAGS", searchable)
        self.assertIn("LOCATION", searchable)

    def test_non_sortable_not_in_sortable_fields(self):
        sortable = self.config.sortable_fields
        self.assertNotIn("IMAGES", sortable)
        self.assertNotIn("ABOUT_FEELINGS", sortable)

    def test_non_searchable_not_in_searchable_fields(self):
        searchable = self.config.searchable_fields
        self.assertNotIn("IMAGES", searchable)
        self.assertNotIn("ABOUT_START", searchable)


# ===========================================================================
# 3. EntrySchema — validate()
# ===========================================================================

class TestEntrySchemaValidate(unittest.TestCase):

    def _make_schema(self):
        config = MemoirConfig(config_dir=_CONFIG_DIR)
        return EntrySchema(descriptors=config.descriptors)

    def _valid_entry(self):
        return {
            "ENTRY_ID": "test-id",
            "ENTRY_START": "2025-01-15T10:30:00",
            "ENTRY_TYPES": ["personal"],
            "ENTRY": "Today was a good day.",
        }

    def test_valid_entry_passes(self):
        schema = self._make_schema()
        schema.validate(self._valid_entry())  # should not raise

    def test_valid_entry_with_datetime_object(self):
        schema = self._make_schema()
        entry = self._valid_entry()
        entry["ENTRY_START"] = datetime(2025, 1, 15, 10, 30)
        schema.validate(entry)  # should not raise

    def test_missing_entry_start_raises(self):
        schema = self._make_schema()
        entry = self._valid_entry()
        del entry["ENTRY_START"]
        with self.assertRaises(EntryValidationError) as ctx:
            schema.validate(entry)
        self.assertIn("ENTRY_START", str(ctx.exception))

    def test_missing_entry_types_raises(self):
        schema = self._make_schema()
        entry = self._valid_entry()
        del entry["ENTRY_TYPES"]
        with self.assertRaises(EntryValidationError) as ctx:
            schema.validate(entry)
        self.assertIn("ENTRY_TYPES", str(ctx.exception))

    def test_missing_entry_raises(self):
        schema = self._make_schema()
        entry = self._valid_entry()
        del entry["ENTRY"]
        with self.assertRaises(EntryValidationError) as ctx:
            schema.validate(entry)
        self.assertIn("ENTRY", str(ctx.exception))

    def test_invalid_entry_start_string_raises(self):
        schema = self._make_schema()
        entry = self._valid_entry()
        entry["ENTRY_START"] = "not-a-datetime"
        with self.assertRaises(EntryValidationError):
            schema.validate(entry)

    def test_entry_types_not_list_raises(self):
        schema = self._make_schema()
        entry = self._valid_entry()
        entry["ENTRY_TYPES"] = "personal"
        with self.assertRaises(EntryValidationError) as ctx:
            schema.validate(entry)
        self.assertIn("list", str(ctx.exception))

    def test_entry_empty_string_raises(self):
        schema = self._make_schema()
        entry = self._valid_entry()
        entry["ENTRY"] = "   "
        with self.assertRaises(EntryValidationError):
            schema.validate(entry)

    def test_entry_not_string_raises(self):
        schema = self._make_schema()
        entry = self._valid_entry()
        entry["ENTRY"] = 12345
        with self.assertRaises(EntryValidationError):
            schema.validate(entry)

    def test_empty_entry_types_list_valid(self):
        schema = self._make_schema()
        entry = self._valid_entry()
        entry["ENTRY_TYPES"] = []
        schema.validate(entry)  # empty list is allowed


# ===========================================================================
# 4. EntrySchema — build_empty()
# ===========================================================================

class TestEntrySchemaBuilEmpty(unittest.TestCase):

    def _make_schema(self):
        config = MemoirConfig(config_dir=_CONFIG_DIR)
        return EntrySchema(descriptors=config.descriptors)

    def test_build_empty_has_mandatory_fields(self):
        schema = self._make_schema()
        entry = schema.build_empty()
        for field in MANDATORY_FIELDS:
            self.assertIn(field, entry)

    def test_build_empty_has_entry_id(self):
        schema = self._make_schema()
        entry = schema.build_empty()
        self.assertIn("ENTRY_ID", entry)
        self.assertIsInstance(entry["ENTRY_ID"], str)
        self.assertGreater(len(entry["ENTRY_ID"]), 0)

    def test_build_empty_entry_types_defaults_to_list(self):
        schema = self._make_schema()
        entry = schema.build_empty()
        self.assertIsInstance(entry["ENTRY_TYPES"], list)

    def test_build_empty_custom_types(self):
        schema = self._make_schema()
        entry = schema.build_empty(entry_types=["work", "travel"])
        self.assertEqual(entry["ENTRY_TYPES"], ["work", "travel"])

    def test_build_empty_custom_start(self):
        schema = self._make_schema()
        dt = datetime(2024, 6, 1, 9, 0)
        entry = schema.build_empty(entry_start=dt)
        self.assertIn("2024-06-01", entry["ENTRY_START"])

    def test_build_empty_custom_text(self):
        schema = self._make_schema()
        entry = schema.build_empty(entry_text="Hello world")
        self.assertEqual(entry["ENTRY"], "Hello world")

    def test_build_empty_unique_ids(self):
        schema = self._make_schema()
        e1 = schema.build_empty()
        e2 = schema.build_empty()
        self.assertNotEqual(e1["ENTRY_ID"], e2["ENTRY_ID"])


# ===========================================================================
# 5. EntrySchema — sortable_fields and searchable_fields
# ===========================================================================

class TestEntrySchemaFields(unittest.TestCase):

    def setUp(self):
        config = MemoirConfig(config_dir=_CONFIG_DIR)
        self.schema = EntrySchema(descriptors=config.descriptors)

    def test_sortable_fields_includes_entry_start(self):
        self.assertIn("ENTRY_START", self.schema.sortable_fields)

    def test_sortable_fields_includes_descriptor_sortable(self):
        # ABOUT_START and AUTHOR are sortable per descriptor files
        self.assertIn("ABOUT_START", self.schema.sortable_fields)
        self.assertIn("AUTHOR", self.schema.sortable_fields)

    def test_searchable_fields_includes_core(self):
        self.assertIn("ENTRY_TYPES", self.schema.searchable_fields)
        self.assertIn("ENTRY", self.schema.searchable_fields)

    def test_searchable_fields_includes_descriptor_searchable(self):
        # ABOUT_FEELINGS, AUTHOR, TAGS, LOCATION are searchable
        self.assertIn("ABOUT_FEELINGS", self.schema.searchable_fields)
        self.assertIn("AUTHOR", self.schema.searchable_fields)
        self.assertIn("TAGS", self.schema.searchable_fields)
        self.assertIn("LOCATION", self.schema.searchable_fields)

    def test_optional_fields_does_not_include_mandatory(self):
        for field in MANDATORY_FIELDS:
            self.assertNotIn(field, self.schema.optional_fields)

    def test_optional_fields_includes_descriptor_fields(self):
        self.assertIn("ABOUT_START", self.schema.optional_fields)
        self.assertIn("IMAGES", self.schema.optional_fields)
        self.assertIn("AUTHOR", self.schema.optional_fields)

    def test_no_duplicates_in_sortable(self):
        sortable = self.schema.sortable_fields
        self.assertEqual(len(sortable), len(set(sortable)))

    def test_no_duplicates_in_searchable(self):
        searchable = self.schema.searchable_fields
        self.assertEqual(len(searchable), len(set(searchable)))


# ===========================================================================
# 6. JournalStore — CRUD operations
# ===========================================================================

class TestJournalStore(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._data_dir = Path(self._tmpdir.name)
        config = MemoirConfig(config_dir=_CONFIG_DIR)
        self._schema = EntrySchema(descriptors=config.descriptors)
        self.store = JournalStore(
            data_dir=self._data_dir,
            schema=self._schema,
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_entry(self, text="Test entry body.", types=None):
        return self._schema.build_empty(
            entry_start=datetime(2025, 3, 10, 8, 0),
            entry_types=types or ["test"],
            entry_text=text,
        )

    # create_entry ----------------------------------------------------------

    def test_create_returns_entry_id(self):
        entry = self._make_entry()
        entry_id = self.store.create_entry(entry)
        self.assertIsInstance(entry_id, str)
        self.assertGreater(len(entry_id), 0)

    def test_create_writes_yaml_file(self):
        entry = self._make_entry()
        entry_id = self.store.create_entry(entry)
        expected_file = self._data_dir / f"{entry_id}.yaml"
        self.assertTrue(expected_file.is_file())

    def test_create_validates_before_writing(self):
        bad_entry = {"ENTRY_START": "2025-01-01T00:00:00"}
        # Missing ENTRY_TYPES and ENTRY
        with self.assertRaises(EntryValidationError):
            self.store.create_entry(bad_entry)

    def test_create_entry_count_increases(self):
        self.assertEqual(self.store.entry_count(), 0)
        self.store.create_entry(self._make_entry())
        self.assertEqual(self.store.entry_count(), 1)
        self.store.create_entry(self._make_entry())
        self.assertEqual(self.store.entry_count(), 2)

    # load_entry ------------------------------------------------------------

    def test_load_returns_entry_dict(self):
        entry = self._make_entry()
        entry_id = self.store.create_entry(entry)
        loaded = self.store.load_entry(entry_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["ENTRY_ID"], entry_id)

    def test_load_preserves_entry_text(self):
        entry = self._make_entry(text="Preserved text here.")
        entry_id = self.store.create_entry(entry)
        loaded = self.store.load_entry(entry_id)
        self.assertEqual(loaded["ENTRY"], "Preserved text here.")

    def test_load_nonexistent_returns_none(self):
        result = self.store.load_entry("nonexistent-id")
        self.assertIsNone(result)

    # list_entries ----------------------------------------------------------

    def test_list_returns_all_entries(self):
        for i in range(3):
            self.store.create_entry(self._make_entry(text=f"Entry {i}"))
        entries = self.store.list_entries()
        self.assertEqual(len(entries), 3)

    def test_list_empty_store_returns_empty_list(self):
        self.assertEqual(self.store.list_entries(), [])

    def test_list_with_filter_fn(self):
        self.store.create_entry(
            self._make_entry(text="Match this.", types=["alpha"])
        )
        self.store.create_entry(
            self._make_entry(text="No match.", types=["beta"])
        )
        results = self.store.list_entries(
            filter_fn=lambda e: "alpha" in e.get("ENTRY_TYPES", [])
        )
        self.assertEqual(len(results), 1)
        self.assertIn("alpha", results[0]["ENTRY_TYPES"])

    def test_list_sort_by_entry_start(self):
        schema = self._schema
        e1 = schema.build_empty(
            entry_start=datetime(2024, 1, 1),
            entry_types=["a"],
            entry_text="First",
        )
        e2 = schema.build_empty(
            entry_start=datetime(2025, 6, 15),
            entry_types=["b"],
            entry_text="Second",
        )
        self.store.create_entry(e1)
        self.store.create_entry(e2)
        entries = self.store.list_entries(
            sort_by="ENTRY_START", reverse=False
        )
        # Earlier date should come first
        self.assertIn("2024", entries[0]["ENTRY_START"])

    def test_list_sort_reversed(self):
        schema = self._schema
        e1 = schema.build_empty(
            entry_start=datetime(2023, 1, 1),
            entry_types=["old"],
            entry_text="Oldest",
        )
        e2 = schema.build_empty(
            entry_start=datetime(2025, 12, 31),
            entry_types=["new"],
            entry_text="Newest",
        )
        self.store.create_entry(e1)
        self.store.create_entry(e2)
        entries = self.store.list_entries(
            sort_by="ENTRY_START", reverse=True
        )
        self.assertIn("2025", entries[0]["ENTRY_START"])

    # update_entry ----------------------------------------------------------

    def test_update_modifies_entry(self):
        entry = self._make_entry()
        entry_id = self.store.create_entry(entry)
        result = self.store.update_entry(
            entry_id, {"ENTRY": "Updated text."}
        )
        self.assertTrue(result)
        loaded = self.store.load_entry(entry_id)
        self.assertEqual(loaded["ENTRY"], "Updated text.")

    def test_update_nonexistent_returns_false(self):
        result = self.store.update_entry("no-such-id", {"ENTRY": "x"})
        self.assertFalse(result)

    def test_update_revalidates(self):
        entry = self._make_entry()
        entry_id = self.store.create_entry(entry)
        with self.assertRaises(EntryValidationError):
            self.store.update_entry(
                entry_id, {"ENTRY": "   "}  # invalid empty entry
            )

    # delete_entry ----------------------------------------------------------

    def test_delete_removes_file(self):
        entry = self._make_entry()
        entry_id = self.store.create_entry(entry)
        result = self.store.delete_entry(entry_id)
        self.assertTrue(result)
        self.assertIsNone(self.store.load_entry(entry_id))

    def test_delete_nonexistent_returns_false(self):
        result = self.store.delete_entry("ghost-id")
        self.assertFalse(result)

    def test_delete_reduces_count(self):
        entry = self._make_entry()
        entry_id = self.store.create_entry(entry)
        self.assertEqual(self.store.entry_count(), 1)
        self.store.delete_entry(entry_id)
        self.assertEqual(self.store.entry_count(), 0)

    # entry_count -----------------------------------------------------------

    def test_entry_count_zero_initially(self):
        self.assertEqual(self.store.entry_count(), 0)

    def test_entry_count_correct_after_operations(self):
        ids = []
        for i in range(4):
            e = self._make_entry(text=f"Entry {i}")
            ids.append(self.store.create_entry(e))
        self.assertEqual(self.store.entry_count(), 4)
        self.store.delete_entry(ids[0])
        self.assertEqual(self.store.entry_count(), 3)


# ===========================================================================
# 7. Formatters
# ===========================================================================

class TestFormatters(unittest.TestCase):

    def _sample_entry(self):
        return {
            "ENTRY_ID": "abcdef12-0000-0000-0000-000000000000",
            "ENTRY_START": "2025-04-10T14:30:00",
            "ENTRY_TYPES": ["personal", "travel"],
            "ENTRY": "Visited the old lighthouse.\nThe view was stunning.",
        }

    # entry_summary_line ----------------------------------------------------

    def test_summary_line_contains_id_prefix(self):
        entry = self._sample_entry()
        line = entry_summary_line(1, entry)
        self.assertIn("abcdef12", line)

    def test_summary_line_contains_date(self):
        entry = self._sample_entry()
        line = entry_summary_line(1, entry)
        self.assertIn("2025-04-10", line)

    def test_summary_line_contains_types(self):
        entry = self._sample_entry()
        line = entry_summary_line(1, entry)
        self.assertIn("personal", line)
        self.assertIn("travel", line)

    def test_summary_line_contains_snippet(self):
        entry = self._sample_entry()
        line = entry_summary_line(1, entry)
        self.assertIn("Visited", line)

    def test_summary_line_no_newlines_in_snippet(self):
        entry = self._sample_entry()
        line = entry_summary_line(1, entry)
        self.assertNotIn("\n", line)

    def test_summary_line_empty_types_shows_none(self):
        entry = self._sample_entry()
        entry["ENTRY_TYPES"] = []
        line = entry_summary_line(1, entry)
        self.assertIn("(none)", line)

    def test_summary_line_missing_entry_id(self):
        entry = self._sample_entry()
        del entry["ENTRY_ID"]
        line = entry_summary_line(1, entry)
        self.assertIn("?", line)

    # entry_detail_lines ----------------------------------------------------

    def test_detail_lines_returns_list(self):
        entry = self._sample_entry()
        lines = entry_detail_lines(entry)
        self.assertIsInstance(lines, list)
        self.assertGreater(len(lines), 0)

    def test_detail_lines_contains_entry_id(self):
        entry = self._sample_entry()
        lines = entry_detail_lines(entry)
        combined = "\n".join(lines)
        self.assertIn("abcdef12-0000-0000-0000-000000000000", combined)

    def test_detail_lines_contains_date(self):
        entry = self._sample_entry()
        lines = entry_detail_lines(entry)
        combined = "\n".join(lines)
        self.assertIn("2025-04-10", combined)

    def test_detail_lines_contains_entry_body(self):
        entry = self._sample_entry()
        lines = entry_detail_lines(entry)
        combined = "\n".join(lines)
        self.assertIn("Visited the old lighthouse.", combined)

    def test_detail_lines_shows_optional_fields(self):
        entry = self._sample_entry()
        entry["LOCATION"] = "Cape Reinga"
        entry["AUTHOR"] = "Daniel"
        lines = entry_detail_lines(entry)
        combined = "\n".join(lines)
        self.assertIn("LOCATION", combined)
        self.assertIn("Cape Reinga", combined)
        self.assertIn("AUTHOR", combined)

    def test_detail_lines_no_optional_section_when_absent(self):
        entry = self._sample_entry()
        lines = entry_detail_lines(entry)
        combined = "\n".join(lines)
        self.assertNotIn("Optional fields", combined)

    def test_detail_lines_datetime_object_formatted(self):
        entry = self._sample_entry()
        entry["ENTRY_START"] = datetime(2025, 4, 10, 14, 30)
        lines = entry_detail_lines(entry)
        combined = "\n".join(lines)
        self.assertIn("2025-04-10", combined)


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
