# M3m01r5 — Memoir Journal

Personal journalling and memoir archiving utility with drop-in
categorical descriptors.

## Features

- **YAML-backed entries** — one file per journal entry under `data/entries/`
- **Drop-in descriptors** — extend entry schema via `config/config.d/descriptors/*.yaml`
- **Interactive CLI** — create, list, search, view, edit, and delete entries
- **Sortable & searchable** — sort by any descriptor field marked `sortable: true`
- **ROOT_MODES** — workspace-level or project-level log/config routing

## Project Structure

```
M3m01r5/
├── config/
│   ├── GLOBAL_CONFIG.json
│   ├── m3m01r5_config.yaml
│   └── config.d/
│       ├── 10_logging.yaml
│       ├── 20_display.yaml
│       └── descriptors/
│           ├── 10_about.yaml
│           ├── 20_feelings.yaml
│           ├── 30_media.yaml
│           └── 40_metadata.yaml
├── data/entries/
├── src/M3m01r5/
│   ├── config_manager.py
│   ├── entry_schema.py
│   ├── journal_store.py
│   └── cli/
│       ├── menu.py
│       └── formatters.py
└── tests/
```

## Mandatory Entry Fields

| Field         | Type         | Description                        |
|---------------|--------------|------------------------------------|
| `ENTRY_START` | datetime     | When the entry was written         |
| `ENTRY_TYPES` | list[str]    | Category tags                      |
| `ENTRY`       | str          | Journal body text (multi-line)     |

## Optional Descriptors (drop-in via config.d/descriptors/)

| Field            | Type     | Sortable | Searchable |
|------------------|----------|----------|------------|
| `ABOUT_START`    | datetime | ✓        |            |
| `ABOUT_END`      | datetime |          |            |
| `ABOUT_FEELINGS` | dict     |          | ✓          |
| `IMAGES`         | list     |          |            |
| `FILES`          | list     |          |            |
| `AUTHOR`         | str      | ✓        | ✓          |
| `TAGS`           | list     |          | ✓          |
| `LOCATION`       | str      |          | ✓          |

## Installation

```bash
# From the workspace root, with venv active:
pip install -e Applications/M3m01r5
```

## Usage

```bash
m3m01r5
# or
python src/M3m01r5/main.py
```

## Adding Descriptors

Drop a new `*.yaml` file into `config/config.d/descriptors/`:

```yaml
descriptors:
  MOOD_SCORE:
    type: int
    required: false
    description: "Overall mood score from 1-10."
    sortable: true
    searchable: false
```

The field is immediately available in the entry wizard and search.

## Running Tests

```bash
cd Applications/M3m01r5
python -m pytest tests/ -v
```

