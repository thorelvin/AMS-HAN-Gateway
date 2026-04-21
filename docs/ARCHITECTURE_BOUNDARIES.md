# Architecture Boundaries

This repository is easiest to maintain when each layer has a narrow job and a clear direction of dependency.

## Layer map

### Firmware

Path:
`firmware/esp_idf_ams_han_gateway_wroom32d/`

Owns:

- serial command parsing and validation
- HAN capture and `FRAME` / `SNAP` emission
- Wi-Fi and MQTT runtime config
- embedded persistence in NVS

Rules:

- firmware should not assume dashboard internals
- firmware protocol changes must keep Python parsing tests in sync
- command parsing should stay centralized instead of spreading string handling across many files

### Backend transport and storage

Path:
`ams_han_reflex_app/backend/`

Owns:

- serial worker
- protocol parsing and command encoding
- typed data models
- snapshot persistence

Rules:

- backend code should stay UI-agnostic
- protocol helpers should be the only place that knows how escaping works
- storage code should not import Reflex or UI state

### Domain logic

Path:
`ams_han_reflex_app/domain/`

Owns:

- analysis summaries
- diagnostics
- mains-aware classification
- pricing and capacity logic
- signature grouping

Rules:

- domain functions should operate on typed inputs and plain values
- domain code should not talk to serial ports, Reflex state, or settings files directly
- pricing must surface fallback state explicitly instead of silently masking missing data

### Service layer

Path:
`ams_han_reflex_app/service.py`
`ams_han_reflex_app/services/`

Owns:

- orchestration between connection, replay, history, analysis, and cost services
- runtime state coordination
- persistence-backed settings updates through explicit service methods

Rules:

- `GatewayService` acts as a coordinator, not a catch-all implementation bucket
- feature-specific work should live in `ConnectionService`, `ReplayService`, `HistoryService`, `AnalysisService`, or `CostService`
- the UI must call explicit service methods instead of mutating service internals

### UI state and Reflex pages

Path:
`ams_han_reflex_app/state.py`
`ams_han_reflex_app/ams_han_reflex_app.py`

Owns:

- view state
- tab refresh behavior
- user actions
- text formatting for cards and tables

Rules:

- UI state may read service outputs, but should not persist settings by writing into `service.settings`
- page components should stay declarative and keep non-trivial data shaping in the service or domain layers
- browser-facing descriptions should be derived from service results, not reimplement business logic

## Dependency direction

Preferred flow:

`firmware -> protocol lines -> backend -> domain/services -> state -> Reflex UI`

Avoid:

- UI importing backend storage directly
- domain code importing Reflex
- firmware protocol assumptions duplicated in multiple Python modules
- direct settings writes from UI code

## Testing contract

The highest-value regression tests should protect these seams:

- firmware-emitted `RSP`, `STATUS`, `FRAME`, and `SNAP` lines still parse cleanly in Python
- command escaping for `SET_WIFI` and `SET_MQTT` remains compatible with firmware parsing
- pricing fallback remains explicit in cost summaries
- replay fixtures continue to produce valid history, diagnostics, signatures, and heatmaps
