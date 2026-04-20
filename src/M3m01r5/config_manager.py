#!/usr/bin/env python3
"""
M3m01r5/config_manager.py - M3m01r5 Configuration Manager

Loads and deep-merges the M3m01r5 configuration stack:
  1. config/m3m01r5_config.yaml           (root config)
  2. config/config.d/*.yaml               (sorted, override fragments)
  3. config/config.d/descriptors/*.yaml   (drop-in descriptor schema)

Provides a ``MemoirConfig`` object with descriptor-aware accessors.
"""

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError("PyYAML is required: pip install pyyaml") from exc


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """
    Recursively deep-merge *override* into a copy of *base*.

    Mapping values are merged recursively; all other values in
    *override* replace those in *base*.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _load_yaml_file(path: Path) -> Dict:
    """Load a single YAML file and return its contents as a dict."""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


def _load_yaml_dir(directory: Path) -> Dict:
    """
    Load all *.yaml files from *directory* in lexical order and
    deep-merge them into a single dict.
    """
    merged: Dict = {}
    if not directory.is_dir():
        return merged
    for yaml_file in sorted(directory.glob("*.yaml")):
        fragment = _load_yaml_file(yaml_file)
        merged = _deep_merge(merged, fragment)
    return merged


class MemoirConfig:
    """
    Layered configuration object for M3m01r5.

    Layers (applied in order, later layers win):
      1. config/m3m01r5_config.yaml
      2. config/config.d/*.yaml          (lexical order)
      3. config/config.d/descriptors/*.yaml  (descriptor schema)
    """

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = Path(config_dir)
        self._base: Dict = {}
        self._descriptors: Dict = {}
        self._load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Build the merged config from all layers."""
        root_file = self._config_dir / "m3m01r5_config.yaml"
        if root_file.is_file():
            self._base = _load_yaml_file(root_file)
        else:
            self._base = {}

        override_dir = self._config_dir / "config.d"
        overrides = _load_yaml_dir(override_dir)
        self._base = _deep_merge(self._base, overrides)

        # Load descriptor fragments separately; merge their
        # ``descriptors`` sections into a flat dict.
        descriptor_dir = self._config_dir / "config.d" / "descriptors"
        self._descriptors = {}
        if descriptor_dir.is_dir():
            for yaml_file in sorted(descriptor_dir.glob("*.yaml")):
                fragment = _load_yaml_file(yaml_file)
                desc_section = fragment.get("descriptors", {})
                if isinstance(desc_section, dict):
                    self._descriptors = _deep_merge(
                        self._descriptors, desc_section
                    )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return a top-level config value."""
        return self._base.get(key, default)

    @property
    def logging(self) -> Dict:
        """Return the logging config section."""
        return self._base.get("logging", {})

    @property
    def colours(self) -> Dict:
        """Return the colours config section."""
        return self._base.get("colours", {})

    @property
    def display(self) -> Dict:
        """Return the display config section."""
        return self._base.get("display", {})

    @property
    def journal(self) -> Dict:
        """Return the journal config section."""
        return self._base.get("journal", {})

    @property
    def descriptors(self) -> Dict:
        """
        Return the merged descriptor schema dict.

        Keys are field names; values are schema dicts with at least
        ``{"type": ..., "required": bool}``.
        """
        return copy.deepcopy(self._descriptors)

    @property
    def sortable_fields(self) -> List[str]:
        """Return field names from descriptors that have ``sortable: true``."""
        return [
            k for k, v in self._descriptors.items()
            if v.get("sortable", False)
        ]

    @property
    def searchable_fields(self) -> List[str]:
        """Return field names from descriptors that have ``searchable: true``."""
        return [
            k for k, v in self._descriptors.items()
            if v.get("searchable", False)
        ]

    @property
    def raw(self) -> Dict:
        """Return the full merged config dict (read-only copy)."""
        return copy.deepcopy(self._base)

    def __repr__(self) -> str:  # pragma: no cover
        return f"MemoirConfig(config_dir={self._config_dir})"
