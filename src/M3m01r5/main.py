#!/usr/bin/env python3
"""
M3m01r5/main.py - M3m01r5 Memoir Journal Entry Point

Bootstraps configuration, journal store, and launches the interactive CLI.
"""
import argparse
import sys
from pathlib import Path

# Resolve project root (src/M3m01r5/main.py → project root)
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parents[2]
_CONFIG_DIR = _PROJECT_ROOT / "config"
_DEFAULT_DATA_DIR = _PROJECT_ROOT / "data" / "entries"
_DEFAULT_LOG_DIR = _PROJECT_ROOT / "logFiles"

try:
    from tUilKit import get_config_loader, get_file_system, get_logger
    _TUILKIT_AVAILABLE = True
except ImportError:
    _TUILKIT_AVAILABLE = False
    get_logger = get_config_loader = get_file_system = None  # type: ignore

from M3m01r5.config_manager import MemoirConfig
from M3m01r5.entry_schema import EntrySchema
from M3m01r5.journal_store import JournalStore
from M3m01r5.cli import menu as menu_module


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="m3m01r5",
        description=(
            "M3m01r5 — personal journalling and memoir archiving."
        ),
    )
    parser.add_argument(
        "--config-dir",
        default=str(_CONFIG_DIR),
        metavar="DIR",
        help="Path to the config/ directory (default: auto-detected).",
    )
    parser.add_argument(
        "--data-dir",
        default=str(_DEFAULT_DATA_DIR),
        metavar="DIR",
        help="Path to the journal entries directory.",
    )
    return parser


def main(argv=None) -> int:
    """Application entry point. Returns an exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    config_dir = Path(args.config_dir)
    data_dir = Path(args.data_dir)

    # Load merged config
    config = MemoirConfig(config_dir=config_dir)

    # Resolve data dir from config if not overridden on CLI
    journal_cfg = config.get("journal", {})
    if args.data_dir == str(_DEFAULT_DATA_DIR):
        cfg_data = journal_cfg.get("data_dir")
        if cfg_data:
            data_dir = config_dir.parent / cfg_data

    # Set up log files in menu module
    log_cfg = config.logging
    log_files_cfg = log_cfg.get("log_files", {})
    for key, rel_path in log_files_cfg.items():
        abs_path = config_dir.parent / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        menu_module.LOG_FILES[key] = str(abs_path)

    # Build schema and store
    schema = EntrySchema(descriptors=config.descriptors)
    store = JournalStore(data_dir=data_dir, schema=schema)

    # Launch menu
    menu_module.run_menu(store=store, schema=schema, config=config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
