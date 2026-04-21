# AMS HAN Gateway for ESP32-WROOM-32D (ESP-IDF)

ESP32-WROOM-32D dev-board firmware scaffold for:

- HAN / M-Bus reading on **UART2**
- PC link over **USB/UART0**
- Wi-Fi setup from the PC over serial
- MQTT publishing over Wi-Fi
- NVS-backed config storage
- future-ready provisioning hooks for SoftAP / BLE

## Target hardware

This project assumes an **ESP32-WROOM-32D dev board with USB-C**, where:

- USB-C powers the board and provides the PC serial connection
- `UART0` is used for the PC command/response channel
- `UART2` is used for the HAN adapter
- `GPIO16` is HAN RX
- `GPIO17` is HAN TX

## Current status

This scaffold now includes:

- **Serial command handling** over USB/UART0
- **Wi-Fi connect / reconnect** with NVS-backed config
- **MQTT connect and publish** over Wi-Fi
- **UART2 frame capture** from the HAN side
- **HDLC-style frame reconstruction** using `0x7E` delimiters and `0x7D` unescaping
- **Kaifa `KFM_001` parser** matching the PC app field order
- **Forwarding raw frames to the PC** as `FRAME,<seq>,<len>,<hex>`
- **Derived ESP-side metrics** such as net power, total current, average voltage, phase imbalance, estimated power factor, and a short rolling window
- **Fallback debug parsers** for ASCII test payloads and preformatted `FRAME,<seq>,<len>,<hex>`

It is currently optimized for the Kaifa `KFM_001` payload you already decode on the PC side. Aidon / other meter profiles can be added later in `main/han_reader.c` as additional parsers.

## Build

Tested as an ESP-IDF-style project layout.

```bash
idf.py set-target esp32
idf.py build
idf.py -p COM5 flash monitor
```

## Pin layout

- PC / USB bridge: default UART0
- HAN RX: `GPIO16`
- HAN TX: `GPIO17`

## Serial command protocol (PC -> ESP)

One command per line.

```text
GET_INFO
GET_STATUS
SET_WIFI,<ssid>,<password>
CLEAR_WIFI
SET_MQTT,<host>,<port>,<user>,<password>,<topic_prefix>
MQTT_ENABLE
MQTT_DISABLE
START_PROVISIONING
STOP_PROVISIONING
REBOOT
FACTORY_RESET
```

## Serial response protocol (ESP -> PC)

```text
RSP:OK
RSP:ERROR,<reason>
RSP:INFO,<fw_ver>,<device_id>,<mac>
RSP:WIFI,<state>,<ip>
RSP:MQTT,<state>
STATUS,WIFI,<state>,<ip>
STATUS,MQTT,<state>
STATUS,HAN,<state>
FRAME,<seq>,<len>,<hex>
SNAP,<csv fields...>
```

## MQTT topics

Default prefix: `amshan/<device_id>`

Published topics:

- `amshan/<device_id>/status`
- `amshan/<device_id>/live/power`
- `amshan/<device_id>/live/phases`
- `amshan/<device_id>/live/metrics`
- `amshan/<device_id>/live/raw`

## Suggested next steps

1. Add Home Assistant MQTT discovery.
2. Add unified provisioning with SoftAP/BLE in `provisioning_stub.c`.
3. Extend `han_reader.c` with Aidon / other meter profiles.
4. Add retained `status` and `device info` MQTT messages.
5. Optionally expose Home Assistant-friendly binary sensors for stale data and high phase imbalance.

## Good ESP-side derived values

These are safe and cheap to calculate on the ESP:

- `net_power_w = import_w - export_w`
- `total_current_a = l1_a + l2_a + l3_a`
- `avg_voltage_v = (l1_v + l2_v + l3_v) / 3`
- `phase_imbalance_a = max(I) - min(I)`
- `frame_age_ms`
- `frames_rx`
- `frames_bad`
- `wifi_rssi`

Heavy analysis like price-aware load shifting, monthly peak logic, and reports should stay on the PC.


## Home Assistant MQTT discovery

This scaffold now publishes retained MQTT discovery payloads under `homeassistant/` for a grouped device in Home Assistant. Discovery is sent when the ESP MQTT client connects, and again when Home Assistant publishes its MQTT birth message on `homeassistant/status`.

Useful serial commands:

- `SET_MQTT,broker,1883,user,pass,amshan`
- `MQTT_ENABLE`
- `REPUBLISH_DISCOVERY`

Primary retained state topics:

- `<topic_prefix>/<device_id>/availability`
- `<topic_prefix>/<device_id>/status`
- `<topic_prefix>/<device_id>/live/power`
- `<topic_prefix>/<device_id>/live/phases`
- `<topic_prefix>/<device_id>/live/metrics`
