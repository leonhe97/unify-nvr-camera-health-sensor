# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant custom integration (`custom_components/unify_nvr_camera_sensor/`) that detects when UniFi Protect silently stops recording an ONVIF camera. UniFi Protect can fail to record external cameras without any visible error — the timeline just goes grey. This integration polls the Protect API for a recording snapshot from N minutes ago; if none exists, recording has stalled, and that gets surfaced as Home Assistant entities.

There is no build, lint, or test tooling in this repo (no requirements file, no test suite). It's a small, self-contained HA integration distributed via HACS.

## Architecture

Data flows in one direction: `api.py` → `coordinator.py` → `sensor.py` / `binary_sensor.py`, wired together in `__init__.py`.

- **`api.py`** (`UnifyProtectClient`) — thin wrapper around `uiprotect.ProtectApiClient`. `check_recording_at(camera_id, lookback_seconds)` calls the undocumented `cameras/{id}/recording-snapshot` endpoint directly via `api_request_raw` (not part of the public `uiprotect` API surface) and returns whether a snapshot exists. Note the local-time vs UTC conversion in `check_recording_at` — the NVR's recording-snapshot endpoint expects local time, not UTC, so the lookback timestamp adds `time.localtime().tm_gmtoff` before subtracting the lookback window.
- **`coordinator.py`** (`UnifyNvrCoordinator`, a `DataUpdateCoordinator`) — on every poll, refreshes the Protect session and checks all configured cameras concurrently (`asyncio.gather`). Critically, it owns `_last_confirmed: dict[str, datetime]`, an in-memory map of camera_id → last time a recording was confirmed. This persists across polls (not just within one), so "gap minutes" is computed from the last time recording was *actually seen*, not from the last poll. A failed check for one camera doesn't affect others or reset their last-confirmed time.
- **`sensor.py` / `binary_sensor.py`** — read `coordinator.data[camera_id]` (a dict with `last_confirmed_recording`, `gap_minutes`, `last_check_had_recording`, `last_check_time`). The `RecordingProblemSensor` binary sensor is `on` (problem) when `gap_minutes > threshold`. Each camera is its own HA device (`DeviceInfo` keyed by camera_id); each sensor is a sub-entity of that device via `_attr_has_entity_name`.
- **`config_flow.py`** — two-step user flow: (1) connect with host/username/password and discover cameras via `client.get_cameras()`, (2) select which cameras to monitor plus gap threshold and poll interval. `OptionsFlow` reuses the same camera-selection step for reconfiguration and triggers `async_reload` on save. Camera display names are snapshotted into config entry data (`CONF_CAMERA_NAMES`) at selection time rather than re-fetched live.
- **`const.py`** — all config keys and defaults in one place; check here first when tracing a config value through the flow → entry data → coordinator → entity chain.

The username/password must be a **local NVR user**, not a Ubiquiti cloud account — this is a common source of `invalid_auth` during setup.

## agent-metadata/

`agent-metadata/` is a separate, portable knowledge base of software-engineering practices (principles/rules/heuristics/checklists) consumed by the custom subagents in `.claude/agents/` (`mdk-developer`, `mdk-reviewer`, `mdk-tester`). It is unrelated to the Home Assistant integration's own logic — don't conflate changes to `agent-metadata/` with changes to the integration.

- Packs (`agent-metadata/packs/*.md`) are entrypoints that compose practice files via `@./path` references; `baseline.md` is inherited by all other packs.
- Validate pack references after editing anything under `agent-metadata/`:
  ```bash
  python3 agent-metadata/tools/lint.py
  ```
  Exits non-zero on unresolved `@./path` references.
- New practices go in `agent-metadata/practices/{domain}/{category}/*.md` and are picked up automatically by any pack referencing that directory — no registration step needed.
