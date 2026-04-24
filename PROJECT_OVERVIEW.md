# AMS HAN Gateway Project Overview

## Project summary

AMS HAN Gateway is a local monitoring and analysis project built around an ESP32-based gateway and a Reflex dashboard. The repository is meant to support practical HAN/AMS development work: receiving meter data, exposing gateway state, replaying captured traffic, and interpreting electrical behavior through diagnostics, historical context, and Norwegian cost calculations.

The dashboard is intentionally broader than a simple live view. It acts as the operator-facing layer for serial discovery, snapshot storage, replay tooling, event analysis, phase and voltage insight, and cost-oriented interpretation of household import and export behavior.

## Main goals

- provide a stable local dashboard for live gateway data
- support offline replay for debugging and repeatable demonstrations
- expose gateway control functions in a usable browser interface
- turn raw HAN measurements into practical analysis and diagnostics
- make cost and capacity implications easier to understand

## System architecture

### 1. Gateway interface

The repository now includes the ESP-IDF firmware project as extracted source in `firmware/esp_idf_ams_han_gateway_wroom32d/`, and that source should be treated as the reference gateway implementation.

From that firmware, the expected gateway behavior is:

- `UART0` used as the PC command and response channel over USB
- `UART2` used for HAN input on `GPIO16` and `GPIO17`
- HDLC-style frame reconstruction with `0x7E` frame boundaries and `0x7D` unescaping
- Kaifa `KFM_001` parsing on the ESP side
- raw `FRAME` forwarding plus derived `SNAP` emission
- NVS-backed Wi-Fi and MQTT configuration
- MQTT publishing and Home Assistant discovery republish support

This gives the Reflex app a concrete protocol target rather than a generic external gateway assumption.

### 2. Application service

`ams_han_reflex_app/service.py` now acts as a thinner orchestration layer. The runtime is split more explicitly across:

- `services/connection_service.py` for port discovery, probing, and connection resolution
- `services/replay_service.py` for replay loading and playback state
- `services/history_service.py` for persisted and replay-backed snapshot history
- `services/analysis_service.py` for diagnostics, heatmaps, signature shaping, and history views
- `services/cost_service.py` for price-area context, hourly cost rows, and capacity estimation

This keeps `GatewayService` focused on runtime coordination instead of feature-specific implementation details.

### 3. Domain logic

The domain layer is responsible for turning raw measurements into operator-facing context:

- `domain/frame_parser.py` enriches long-frame details
- `domain/analysis.py` builds summaries, history rows, top hours, heatmaps, and daily views
- `domain/event_engine.py` detects power, phase, voltage, and data-quality events with mains-aware attribution
- `domain/pricing.py` applies Norwegian price-area context, grid rates, and capacity estimates
- `domain/signatures.py` groups recurring event patterns into signature rows with duty-cycle metrics

### 4. Reflex UI

`ams_han_reflex_app/ams_han_reflex_app.py` together with `state.py` and the split `state_parts/` modules provide the local web interface. The current interface includes:

- a live overview with snapshot and device status
- analysis panels for phase and voltage behavior
- diagnostics and filtered event tracking
- daily graph and hourly bucket views
- heatmap views with threshold-based switch counting
- cost and capacity views
- history and database tools
- advanced controls for serial, replay, Wi-Fi, MQTT, and electrical-model workflows

Architectural dependency rules for the repository are documented in `docs/ARCHITECTURE_BOUNDARIES.md`.

## Core capabilities

### Live monitoring

- auto-connect to compatible serial gateway
- current import, export, and signed-grid summaries
- device identity, firmware, Wi-Fi, MQTT, and last-frame visibility

### Diagnostics

- missing-voltage detection below valid threshold
- voltage-channel recovery events
- phase-spread and sag detection
- power-step events
- baseline-driven load-session start and end events
- event filtering by status and category

### Analysis and cost context

- top hourly import buckets
- phase dominance and imbalance summaries
- `TN` and `IT` mains-model selection so phase and conductor attribution matches the installation
- daily hourly bucket generation
- recent-day and weekday heatmaps with switch-activity intensity cues
- signature duty-cycle summaries including runtime, starts per day, common start hour, and weekday-versus-weekend frequency
- hourly and daily cost breakdown
- `NO1` to `NO5` spot-price context
- configurable day and night grid rates
- explicit UI warnings when live spot pricing falls back to an estimate
- background spot-price refresh so the dashboard does not block on external price fetches in the hot UI path
- capacity estimate based on top import hours on different days

### Replay and development support

- demo replay loading
- local replay path loading
- browser upload of replay files
- bundled scenario logs in `fixtures/`
- lightweight automated replay test coverage
- alignment with the bundled ESP-IDF firmware protocol and command set

## Bundled replay scenarios

The fixture pack currently covers several practical troubleshooting cases:

- `demo_session.log`
- `replay_phase_loss_l2.log`
- `replay_load_switching.log`
- `replay_voltage_sag.log`
- `replay_solar_export_cycle.log`

These are intended to validate replay loading, event-engine behavior, and the dashboard views that depend on stored snapshot history.

## Repository focus

This repository is strongest in the following areas right now:

- local operator-facing monitoring
- replay-driven debugging
- practical event interpretation
- hourly cost and capacity context
- compact but usable gateway management tools

It is not yet positioned as a packaged end-user product. The current emphasis is on development usability, technical insight, and iterative improvement of the monitoring experience.

## Developer workflow

The repository now has a clearer local and hosted development path:

- `requirements.txt` keeps the runtime dependencies minimal for dashboard use
- `requirements-dev.txt` adds contributor tooling for linting, formatting checks, and test execution
- `python scripts/run_dashboard.py` remains the one-command local launch path
- `python scripts/run_checks.py` runs the standard local quality gate
- GitHub Actions now provides visible `Python checks` and `Firmware build` workflow status in the repository

## Current status

Recent work has improved the repository with:

- stable Reflex compile behavior
- corrected reactive rendering in hourly cost rows
- functioning light and dark mode switching
- stable live serial refresh without requiring manual page reloads
- bundled replay fixtures for multiple event scenarios
- mains-aware `TN` and `IT` interpretation across events, signatures, and heatmaps
- signature duty-cycle analytics for recurring loads
- heatmap switch-threshold filtering and clearer switching-intensity visualization
- explicit cost-source warnings instead of silent spot-price fallback
- extracted firmware source tree for normal diffs, search, and review
- split Reflex state composition across feature-focused `state_parts/` modules instead of one large implementation file
- replay-driven service workflow coverage in the automated tests
- explicit escaped command encoding on the Python side together with firmware-side unescaping and validation
- one-command local launch path via `python scripts/run_dashboard.py`
- one-command local quality checks via `python scripts/run_checks.py`
- GitHub Actions workflow coverage for Python checks and ESP-IDF firmware builds
- refreshed documentation aligned with both the bundled ESP-IDF gateway source and the standard used in the related PC-side repository

## Near-term improvement areas

- more automated coverage for parsing, pricing, and diagnostics
- further decomposition of the Reflex state layer into smaller feature-focused modules
- expanded replay scenarios for additional failure and appliance patterns
- deeper export and solar analytics
- richer firmware flashing and deployment guidance for non-developer setups
- packaging and deployment improvements beyond the current local launch helper
