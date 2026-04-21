# AMS HAN Gateway

A practical AMS/HAN smart-meter monitoring project built around an ESP32 gateway and a local Reflex dashboard.

This repository focuses on the gateway-side monitoring experience: live meter visibility, replay-driven troubleshooting, diagnostics, phase and voltage analysis, and Norwegian power-cost context in one local web application. The goal is to keep the embedded gateway workflow lightweight while letting the dashboard handle parsing, storage, visualization, event detection, and operator-facing analysis.

It is intended as a practical engineering project for understanding household import and export behavior, identifying costly load peaks, tracking power-quality hints, and testing HAN workflows without depending on live hardware for every iteration.

## Key features

- ESP-IDF firmware scaffold for ESP32-WROOM-32D with UART2 HAN capture, NVS-backed config, MQTT publishing, and Home Assistant discovery republish
- Auto-detects the gateway over serial and remembers the last working COM port
- Live overview of import, export, signed grid flow, current hour, and projected hour
- Device and link status for gateway identity, firmware, Wi-Fi, MQTT, and last frame activity
- Diagnostics for missing voltage channels, voltage sag, phase spread, power steps, and load sessions
- Phase and voltage analysis with imbalance, dominant-phase, and worst-spread summaries
- Load Signatures that group recurring power changes into likely household-device patterns with representative watt size
- Heatmap analysis with time-weighted hourly buckets, weekday pattern view, and thresholded phase-switch counts
- Local snapshot history with daily buckets, top-hour tracking, heatmaps, and event-signature summaries
- Cost analysis with Norwegian price areas `NO1` to `NO5`, configurable grid rates, and capacity estimation
- Replay and demo workflow for offline development, debugging, and scenario validation
- Upload support for replay logs directly from the dashboard
- Gateway control actions for `GET_INFO`, `GET_STATUS`, Wi-Fi setup, MQTT setup, and discovery republish

## Verified hardware setup

The hardware setup used in this repository has been verified in practice with the ESP32 gateway, HAN adapter, and the local Reflex dashboard workflow shown below.

### Hardware reference

ESP32 gateway, terminal shield, USB link, and HAN adapter wiring used in the current setup:

![ESP32 HAN gateway hardware setup](docs/images/hardware-setup.jpg)

Example setup:

- Smart meter with HAN port enabled
- HAN / M-Bus interface adapter
- ESP32-WROOM-32D dev board with USB connection
- USB connection from ESP32 to PC
- Windows PC running the Reflex dashboard

## Wiring diagram summary

The hardware is connected as follows:

- **Smart meter HAN port**
  Use the HAN / RJ45 output from the meter.
  In this setup, the HAN / M-Bus pair is taken from **pin 1** and **pin 2**.
  Polarity does **not** matter for the HAN pair itself.

- **HAN / M-Bus to TTL adapter**
  Connect the two HAN wires from the smart meter to the adapter input.
  The adapter acts as the electrical interface between the meter HAN signal and the ESP32 UART side.

- **Adapter to ESP32**
  The firmware uses **UART2** on the ESP32 for HAN communication.
  **ESP32 GPIO16** is configured as **HAN RX**.
  **ESP32 GPIO17** is configured as **HAN TX**.
  Use a shared **GND** between the adapter and the ESP32.
  The exact adapter power pin depends on the adapter board variant, so verify the board markings and voltage requirement before connecting VCC.

- **ESP32 to PC**
  Connect the ESP32 to the PC over USB.
  The USB link provides the PC-side serial channel on **UART0**, which the dashboard uses for `GET_INFO`, `GET_STATUS`, `FRAME`, and `SNAP` traffic.

This matches the current firmware configuration in the repository, where the HAN UART is set to `2400` baud on `UART2`.

## Dashboard screenshots

The screenshots below show the current interface and the main operator views available in the dashboard.

### Overview tab

Live import/export overview, latest snapshot, quick actions, and gateway status:

![Overview tab](docs/images/dashboard-overview.png)

### Analysis tab

Phase and voltage analysis together with load signatures and top-hour buckets:

![Analysis tab](docs/images/dashboard-analysis.png)

### Load Signatures explained

The `Load Signatures` table is where the dashboard starts turning repeated power changes into practical operator hints instead of just raw meter values.

![Load Signatures table](docs/images/dashboard-load-signatures.png)

Each row represents a recurring pattern seen in the event engine:

- **Signature** is the dashboard's best current description of the load behavior, such as a likely heater step, a single-phase appliance step, or a smaller background change.
- **Phase** shows whether the pattern is mostly tied to `L1`, `L2`, `L3`, or is not yet phase-specific.
- **Typical W** gives the representative watt size of that signature, making it much easier to identify whether the change looks like a panel heater, water heater, kitchen appliance, EV-related load step, or a small background consumer.
- **Events** shows how many times that pattern has been observed.
- **Avg Runtime** shows the average session length for signatures that produce clear start and end events.
- **Starts/Day** shows how often that signature begins across the observed history window.
- **Common Start** highlights the hour where that signature most often begins.
- **Weekday / Weekend** compares the per-day start frequency on weekdays versus weekends, which helps expose habits such as morning heating, weekend cooking, or evening EV charging.
- **Last Seen** helps confirm whether the device is currently active or was only present earlier in the session.
- **Confidence** shows how stable the classification is based on the samples collected so far.

Short step-like signatures may still show `-` for runtime if the data contains sharp power changes without a full load-session start/end pair.

Why this matters:

- It helps translate repeated import jumps into likely real household devices instead of forcing the user to interpret every power step manually.
- It makes troubleshooting faster when you are trying to find what caused a peak, phase imbalance, or a suspicious load session.
- It gives a practical bridge between raw HAN telemetry and energy optimization, because identifying a recurring `2500 W` to `2700 W` heater-like load is much more actionable than only seeing that import increased.
- It adds routine analysis, so recurring loads can be understood not just by size but also by timing, duty cycle, and weekday-versus-weekend behavior.
- It becomes more useful over time as the dashboard sees more repeated patterns in live traffic or replay logs.

### Diagnostics tab

Suspected issues, health panel, and filtered event tracker for power, voltage, phase, and data-quality events:

![Diagnostics tab](docs/images/dashboard-diagnostics.png)

### Daily tab

Daily load graph and hourly buckets for the latest meter day:

![Daily tab](docs/images/dashboard-daily.png)

### Heatmap tab

The Heatmap tab turns stored history into a faster pattern-recognition view.

![Heatmap tab](docs/images/dashboard-heatmap.png)

It contains two related views:

- **Recent Hourly Heatmap**
  One row per recent day, one column per hour. This is meant for spotting where the house was steadily importing, steadily exporting, or repeatedly switching loads during specific hours.
- **Weekly Pattern Heatmap**
  The same hourly data collapsed into weekday rows. This makes repeated routines such as morning heating, daytime solar export, cooking peaks, EV charging windows, or night loads much easier to see.

How to read each heatmap cell:

- The large number such as `-2.1 kW` or `+3.3 kW` is the **average net load for that hour**.
  Negative means import-dominant.
  Positive means export-dominant.
- `L x/y/z` is the count of **load switches assigned to `L1/L2/L3`** in that hour.
- `3P n` is the count of **balanced 3-phase switch events** in that hour.
- The **blue/green background** shows whether the hour was import-heavy or export-heavy overall.
- The **corner accent** is hidden for quiet hours, then steps from **yellow** to **orange** to **red** as switching activity increases.

The `Load switch threshold` dropdown controls which signed power changes are counted as switches. The default is `300 W`, but the user can raise or lower the threshold from `100 W` to `1500 W` depending on whether the goal is to catch small appliance changes or only larger load steps.

The screenshot above shows the heatmap cards, the threshold selector, and both the recent-day and weekday-pattern views together in the current dashboard.

Why this matters:

- It makes recurring hourly routines much easier to see than a raw history table.
- It connects visible grid behavior to likely real switching activity on specific phases.
- It helps separate steady background load from hours with active device cycling or rapid appliance changes.
- It gives a practical bridge between phase analysis, Load Signatures, and cost/capacity planning.

### Cost tab

Price area, grid settings, hourly cost rows, and capacity estimate:

![Cost tab](docs/images/dashboard-cost.png)

### History tab

Stored snapshot history with averages, peaks, and local database context:

![History tab](docs/images/dashboard-history.png)

### Log tab

Serial and application log view showing `RSP`, `FRAME`, and `SNAP` traffic from the gateway:

![Log tab](docs/images/dashboard-log.png)

### Advanced tools

Serial connection controls plus replay and demo workflow:

![Advanced tools](docs/images/dashboard-advanced-tools.png)

## Professional relevance

This project is directly relevant to practical metering, integration, and troubleshooting-oriented development work. It demonstrates hands-on work with:

- HAN/AMS communication
- serial communication and gateway validation
- ESP32-based embedded integration
- MQTT and smart-home oriented telemetry publishing
- phase and voltage analysis
- event detection and troubleshooting-oriented visualization
- replay-driven testing for monitoring workflows

## System overview

The project is split into two practical parts:

### ESP32 gateway

The repository includes an ESP-IDF firmware project inside `esp32_wroom32d_ams_han_gateway.zip`. Based on that source, the gateway is responsible for:

- using `UART0` as the PC command and response channel over USB
- using `UART2` for the HAN adapter on `GPIO16` and `GPIO17`
- reconstructing HDLC-style frames with `0x7E` delimiters and `0x7D` unescaping
- parsing Kaifa `KFM_001` payloads and forwarding raw `FRAME` plus derived `SNAP` data
- calculating ESP-side metrics such as net power, total current, average voltage, phase imbalance, power factor estimate, and rolling values
- storing Wi-Fi and MQTT configuration in NVS
- publishing live MQTT topics and Home Assistant discovery payloads
- accepting runtime commands such as `GET_INFO`, `GET_STATUS`, `SET_WIFI`, `SET_MQTT`, `MQTT_ENABLE`, `MQTT_DISABLE`, and `REPUBLISH_DISCOVERY`

The current firmware version defined in the source is `0.2.0-wroom32d`.

### Reflex dashboard

The local Python application is responsible for:

- automatic serial-port discovery and reconnect behavior
- parsing gateway output and enriching long-frame data
- storing snapshot history locally
- presenting live and historical views in the browser
- calculating hourly and daily energy-cost context
- detecting power, voltage, phase, and data-quality events
- building Load Signatures and hourly/weekly heatmap summaries from stored history
- supporting replay-based development and troubleshooting

## Repository structure

```text
.
|-- ams_han_reflex_app/
|   |-- ams_han_reflex_app.py
|   |-- service.py
|   |-- state.py
|   |-- backend/
|   |-- domain/
|   `-- support/
|-- docs/
|   `-- images/
|-- fixtures/
|-- tests/
|-- esp32_wroom32d_ams_han_gateway.zip
|-- PROJECT_OVERVIEW.md
|-- README.md
|-- requirements.txt
`-- rxconfig.py
```

- `ams_han_reflex_app/` contains the Reflex UI, application service, parsing, diagnostics, pricing, and replay support.
- `docs/images/` contains README screenshots and hardware reference images.
- `esp32_wroom32d_ams_han_gateway.zip` contains the bundled ESP-IDF firmware project for the ESP32 gateway.
- `fixtures/` contains bundled replay logs for testing gateway and dashboard behavior without live data.
- `tests/` contains lightweight regression coverage for replay loading, protocol parsing, heatmap analysis, service behavior, and signature grouping.
- `PROJECT_OVERVIEW.md` provides a concise engineering summary of the repository.

## ESP32 firmware reference

The bundled zip contains an ESP-IDF project with a practical module split:

```text
esp32_wroom32d_ams_han_gateway.zip
`-- esp_idf_ams_han_gateway_wroom32d/
    |-- README.md
    |-- CMakeLists.txt
    |-- sdkconfig.defaults
    |-- main/
    |   |-- app_main.c
    |   |-- app_config.h
    |   |-- han_reader.c
    |   |-- serial_link.c
    |   |-- wifi_manager.c
    |   |-- app_mqtt.c
    |   |-- config_store.c
    |   |-- telemetry.c
    |   `-- provisioning_stub.c
    `-- tools/
        `-- pc_setup_example.py
```

The most important firmware files are:

- `main/app_main.c`: command routing, runtime config, snapshot forwarding, and periodic status publishing
- `main/han_reader.c`: UART2 HAN reading, HDLC-style frame reconstruction, Kaifa `KFM_001` parsing, and fallback ASCII test input handling
- `main/serial_link.c`: PC-facing line protocol over USB/UART0
- `main/wifi_manager.c`: Wi-Fi connect and reconnect behavior
- `main/app_mqtt.c`: MQTT publishing and Home Assistant discovery handling
- `main/config_store.c`: NVS-backed persistence for Wi-Fi and MQTT settings
- `main/telemetry.c`: cheap ESP-side derived metrics and rolling values

### Target hardware and pin layout

The embedded project is set up for an `ESP32-WROOM-32D` development board with USB.

- PC link: `UART0` over USB
- HAN adapter: `UART2`
- HAN RX: `GPIO16`
- HAN TX: `GPIO17`
- HAN UART baudrate: `2400`

### Building the firmware

After extracting `esp32_wroom32d_ams_han_gateway.zip`, the bundled ESP-IDF README uses the following workflow:

```bash
idf.py set-target esp32
idf.py build
idf.py -p COM5 flash monitor
```

### Firmware serial protocol

The ESP firmware accepts one command per line over the PC serial link.

Supported commands in the current source include:

- `GET_INFO`
- `GET_STATUS`
- `SET_WIFI,<ssid>,<password>`
- `CLEAR_WIFI`
- `SET_MQTT,<host>,<port>,<user>,<password>,<topic_prefix>`
- `MQTT_ENABLE`
- `MQTT_DISABLE`
- `REPUBLISH_DISCOVERY`
- `START_PROVISIONING`
- `STOP_PROVISIONING`
- `REBOOT`
- `FACTORY_RESET`

Current response and data lines include:

- `RSP:OK`
- `RSP:ERROR,<reason>`
- `RSP:INFO,<fw_ver>,<device_id>,<mac>`
- `RSP:WIFI,<state>,<ip>`
- `RSP:MQTT,<state>`
- `STATUS,WIFI,<state>,<ip>`
- `STATUS,MQTT,<state>`
- `STATUS,HAN,<state>`
- `FRAME,<seq>,<len>,<hex>`
- `SNAP,<csv fields...>`

### MQTT and Home Assistant notes

The firmware README documents a default topic prefix of `amshan/<device_id>` and publishes live state topics for status, power, phases, metrics, and raw data. It also supports retained Home Assistant MQTT discovery and can republish discovery payloads when requested with `REPUBLISH_DISCOVERY`.

## Software requirements

- Python 3.10 or newer
- `reflex>=0.8.14,<0.9`
- `pyserial>=3.5,<4`

Python 3.10 still works with the current app, but Reflex warns that support is deprecated. Python 3.11 or newer is recommended for future-proof local development.

Install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Quick start

### 1. Start the dashboard

From the repository root, run:

```bash
reflex run
```

The app will compile the Reflex frontend and start the local dashboard.

### 2. Let the app find the gateway

When the dashboard loads, it will:

- refresh available COM ports
- probe for a compatible gateway
- remember the last working port and baudrate
- request device information and status once connected

If you are working without live hardware, open the advanced tools and use a replay file instead.

### 3. Use the dashboard

The default experience is built around a few main areas:

- `Live`: current import/export view, snapshot details, and gateway status
- `Analysis`: phase focus, imbalance, voltage behavior, top hourly buckets, and signature summaries
- `Diagnostics`: issue summary, health panel, and filtered event tracker
- `Daily`: daily hourly buckets and a graph-oriented overview of the latest meter day
- `Heatmap`: recent-day and weekday-pattern heatmaps with thresholded `L1/L2/L3` and `3P` switch counts
- `Cost`: spot-price context, grid-rate settings, hourly cost rows, and capacity estimate
- `History`: stored snapshot table, averages, peaks, and local database summary

### 4. Optional firmware workflow

If you want to work on the embedded side as well as the dashboard:

- extract `esp32_wroom32d_ams_han_gateway.zip`
- open the ESP-IDF project inside `esp_idf_ams_han_gateway_wroom32d/`
- build and flash the ESP32 firmware
- connect the ESP32 over USB so the Reflex app can probe it as the gateway source

## Replay workflow

Replay mode is useful for offline development, repeatable debugging, and demonstrating specific electrical scenarios.

Open `Show Advanced` and then use the `Replay & Demo` panel to:

- load a replay file from a full local path
- load the bundled demo replay
- upload a `.log` or `.txt` replay file through the browser
- start, pause, resume, or stop playback

Replay mode feeds the same analysis, diagnostics, daily, cost, and history views as live gateway traffic, which makes it practical for regression checking and event-engine tuning.

## Bundled replay scenarios

The repository includes ready-made replay logs in [fixtures/README.md](C:\Users\thore\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ams\AMS-HAN-Gateway\fixtures\README.md):

- `demo_session.log`: baseline demo session
- `replay_phase_loss_l2.log`: L2 voltage disappears briefly and then recovers
- `replay_load_switching.log`: single-phase and three-phase load changes
- `replay_voltage_sag.log`: import surge with visible phase sag and spread
- `replay_solar_export_cycle.log`: import shifts into export and then returns

These files are designed to exercise the current event engine and cost/history pipeline using realistic `FRAME` plus `SNAP` sequences.

## Diagnostics and analysis focus

This project is especially oriented toward practical interpretation of meter data, not just raw display.

Current analysis and diagnostics include:

- missing-voltage quality detection when a phase drops below valid range
- suppression of misleading spread alerts when a voltage channel is invalid
- voltage-sag and phase-spread detection
- baseline-driven load-session start and end events
- power-step detection against recent samples
- recurring load-signature grouping with phase tagging, event counts, representative watt size, and confidence
- time-weighted hourly heatmaps for recent-day and weekday-pattern analysis
- thresholded phase-switch counts for `L1`, `L2`, `L3`, and `3-phase` activity inside each heatmap hour
- likely device hints for large single-phase and three-phase changes
- cost rows built from elapsed time between snapshots rather than raw sample counts
- capacity estimate based on top hourly import averages on different days

## Testing

Current automated coverage is still lightweight, but it now covers the main analysis and transport building blocks:

```bash
python -m unittest tests.test_analysis tests.test_service tests.test_protocol tests.test_signatures tests.test_replay_player
```

This currently checks:

- replay lines can be loaded into a usable playback session
- protocol parsing accepts expected gateway line formats
- serial auto-connect does not reconnect an already-open link
- signature grouping produces representative watt values
- heatmap analysis produces stable hourly and weekday outputs

## Related repositories

- [AMS_HAN_Sniffer](https://github.com/thorelvin/AMS_HAN_Sniffer)  
  Arduino-oriented HAN/AMS work related to the broader project family.

- [AMS_HAN_Sniffer_PC](https://github.com/thorelvin/AMS_HAN_Sniffer_PC)  
  PC-focused monitoring and analysis project with a similar practical documentation standard.

## Important note

This is a personal engineering and learning project.

It is not a certified measuring instrument and should not be used as the sole basis for:

- electrical safety decisions
- official metering purposes
- billing disputes
- formal fault diagnosis

Suspected electrical faults or installation concerns should always be reviewed by a qualified electrician.

## Current status

The repository currently provides:

- a working Reflex dashboard for live and replayed gateway data
- bundled scenario logs for diagnostics and replay development
- integrated pricing, capacity, diagnostics, history, and heatmap views
- thresholded phase-switch heatmaps and Load Signatures for pattern-oriented analysis
- theme switching, advanced tools, and improved hourly-cost rendering
- lighter refresh behavior so heavier tabs do not churn in the background unnecessarily

The project is active and structured for continued iteration around replay coverage, gateway integration, and deeper analysis features.

## Future improvements

Possible next steps include:

- broader replay fixture coverage for more edge cases
- expanded gateway protocol and status visibility
- richer export and solar-specific analysis
- click-through from heatmap cells into matching History or Diagnostics windows
- additional historical summaries and trend views
- stronger automated tests around parsing, diagnostics, and pricing
- easier packaging for non-development use

## Author

**Thor Elvin Valo**
