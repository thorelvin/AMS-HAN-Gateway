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

The repository now includes a bundled ESP-IDF firmware project in `esp32_wroom32d_ams_han_gateway.zip`, and that source should be treated as the reference gateway implementation.

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

`ams_han_reflex_app/service.py` is the central orchestration layer. It manages:

- serial connectivity
- settings persistence
- snapshot storage
- event logging
- replay playback
- cached summaries for the UI

### 3. Domain logic

The domain layer is responsible for turning raw measurements into operator-facing context:

- `domain/frame_parser.py` enriches long-frame details
- `domain/analysis.py` builds summaries, history rows, top hours, and daily views
- `domain/event_engine.py` detects power, phase, voltage, and data-quality events
- `domain/pricing.py` applies Norwegian price-area context, grid rates, and capacity estimates
- `domain/signatures.py` groups recurring event patterns into signature rows

### 4. Reflex UI

`ams_han_reflex_app/ams_han_reflex_app.py` and `state.py` provide the local web interface. The current interface includes:

- a live overview with snapshot and device status
- analysis panels for phase and voltage behavior
- diagnostics and filtered event tracking
- daily graph and hourly bucket views
- cost and capacity views
- history and database tools
- advanced controls for serial, replay, Wi-Fi, and MQTT workflows

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
- daily hourly bucket generation
- hourly and daily cost breakdown
- `NO1` to `NO5` spot-price context
- configurable day and night grid rates
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

## Current status

Recent work has improved the repository with:

- stable Reflex compile behavior
- corrected reactive rendering in hourly cost rows
- functioning light and dark mode switching
- bundled replay fixtures for multiple event scenarios
- refreshed documentation aligned with both the bundled ESP-IDF gateway source and the standard used in the related PC-side repository

## Near-term improvement areas

- more automated coverage for parsing, pricing, and diagnostics
- expanded replay scenarios for additional failure and appliance patterns
- deeper export and solar analytics
- broader gateway protocol documentation
- packaging and deployment improvements for easier setup
