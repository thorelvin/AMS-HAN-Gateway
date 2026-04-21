"""
Tiny PC-side helper for sending configuration commands over the ESP32 USB serial port.

Usage examples:
  python pc_setup_example.py COM5 info
  python pc_setup_example.py COM5 status
  python pc_setup_example.py COM5 set-wifi MySSID MyPassword
  python pc_setup_example.py COM5 set-mqtt 192.168.1.10 1883 user pass amshan
  python pc_setup_example.py COM5 mqtt-enable
  python pc_setup_example.py COM5 republish-discovery
"""

import sys
import time
import serial

BAUD = 115200

def send_and_read(port: str, command: str, listen_seconds: float = 2.0) -> None:
    with serial.Serial(port, BAUD, timeout=0.2) as ser:
        time.sleep(1.5)  # allow USB serial to settle
        ser.write((command + "\n").encode("utf-8"))
        ser.flush()

        deadline = time.time() + listen_seconds
        while time.time() < deadline:
            line = ser.readline().decode("utf-8", errors="replace").strip()
            if line:
                print(line)

def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python pc_setup_example.py <COMx> <command> [args...]")
        return 1

    port = sys.argv[1]
    cmd = sys.argv[2]

    if cmd == "info":
        command = "GET_INFO"
    elif cmd == "status":
        command = "GET_STATUS"
    elif cmd == "set-wifi" and len(sys.argv) >= 5:
        command = f"SET_WIFI,{sys.argv[3]},{sys.argv[4]}"
    elif cmd == "clear-wifi":
        command = "CLEAR_WIFI"
    elif cmd == "set-mqtt" and len(sys.argv) >= 8:
        command = f"SET_MQTT,{sys.argv[3]},{sys.argv[4]},{sys.argv[5]},{sys.argv[6]},{sys.argv[7]}"
    elif cmd == "mqtt-enable":
        command = "MQTT_ENABLE"
    elif cmd == "mqtt-disable":
        command = "MQTT_DISABLE"
    elif cmd == "republish-discovery":
        command = "REPUBLISH_DISCOVERY"
    elif cmd == "reboot":
        command = "REBOOT"
    elif cmd == "factory-reset":
        command = "FACTORY_RESET"
    else:
        print("Unknown or incomplete command")
        return 1

    send_and_read(port, command)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
