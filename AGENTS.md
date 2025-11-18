# Repository Guidelines

## Project Structure & Module Organization
- Energy simulator lives at `main.py`; MQTT examples under `data_transmission_example.py`.
- Home Assistant integration is in `custom_components/JackeryHome/` with `__init__.py`, `sensor.py`, `config_flow.py`, translations, and docs.
- Branding assets sit in `brands/`; release helpers and docs (e.g., `prepare_release.sh`, `README.md`, `energy_flow_card_config.yaml`) are at the repo root.
- Tests currently consist of targeted scripts such as `test_mqtt.py`; add new suites beside related modules.

## Build, Test, and Development Commands
- `uv sync` — install the Python toolchain defined in `pyproject.toml` (uses uv for fast, reproducible envs).
- `uv run main.py` — run the MQTT simulator against the broker configured inside the script.
- `python test_mqtt.py` — quick publishing/subscription sanity check for MQTT topics.
- `./prepare_release.sh` — bump integration metadata and prep a tagged release; review the script before running.

## Coding Style & Naming Conventions
- Python source follows 4-space indentation, snake_case identifiers, and descriptive constants (e.g., `MQTT_BROKER`).
- Keep Home Assistant entity IDs lowercase with underscores (`sensor.solar_power`).
- Maintain docstrings or top-of-file comments for modules that expose user-facing behavior; prefer concise inline comments for non-obvious logic.
- JSON/YAML assets should stay UTF-8, two-space indented, with trailing commas avoided.

## Testing Guidelines
- Favor lightweight integration tests that exercise MQTT flows end-to-end (publish via simulator, assert consumption by HA sensors).
- Mirror Home Assistant’s naming pattern: `test_<feature>.py` with `async` helpers where applicable.
- Run tests locally before opening a PR; when adding new sensors, include topic fixtures and expected payload assertions.

## Commit & Pull Request Guidelines
- Commits typically use an imperative summary (e.g., "Add inverter sensor mapping") followed by focused changes.
- Reference relevant issues in the body (`Fixes #42`) and keep commits scoped so they are reviewable.
- Pull requests should describe motivation, outline testing performed (`uv run main.py`, HA log screenshots), and mention any config migrations.
- Include UI screenshots/GIFs when altering Lovelace card guidance or other user-facing docs.
