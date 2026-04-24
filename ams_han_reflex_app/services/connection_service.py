"""Serial-port discovery and connection helpers for finding the ESP32 gateway reliably."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import re
import time

from ..backend.models import PortOption
from ..backend.protocol import is_gateway_protocol_line
from ..backend.serial_worker import SerialConfig, SerialManager

PROBE_TIMEOUT_S = 2.6
PROBE_RETRY_INTERVAL_S = 0.45


@dataclass(slots=True)
class ConnectionResult:
    option: PortOption
    baudrate: int


class ConnectionService:
    def __init__(self, serial_manager: SerialManager) -> None:
        self.serial = serial_manager
        self._last_port_options: list[PortOption] = []

    def refresh_ports(self) -> list[PortOption]:
        self._last_port_options = [
            PortOption(port=port, description=description) for port, description in SerialManager.list_ports()
        ]
        return list(self._last_port_options)

    def list_port_labels(self) -> list[str]:
        return [option.label for option in self.refresh_ports()]

    def preferred_port_label(self, preferred: str = "") -> str:
        option = self.resolve_port_option(preferred, refresh=False)
        return option.label if option is not None else str(preferred or "").strip()

    def ordered_candidates(self, preferred: str = "") -> list[PortOption]:
        preferred_port = self.extract_port_name(preferred)
        options = self.refresh_ports()
        return sorted(options, key=lambda option: 0 if option.port == preferred_port else 1)

    def resolve_port_option(self, selection: str, *, refresh: bool = True) -> PortOption | None:
        text = str(selection or "").strip()
        if refresh or not self._last_port_options:
            self.refresh_ports()
        if not text:
            return None
        for option in self._last_port_options:
            if option.matches_display(text):
                return option
        extracted = self.extract_port_name(text)
        for option in self._last_port_options:
            if option.port == extracted:
                return option
        if extracted:
            return PortOption(port=extracted)
        return None

    def connect(self, selection: str, baudrate: int) -> ConnectionResult:
        option = self.resolve_port_option(selection)
        if option is None:
            raise ValueError(f"Unknown serial port selection: {selection!r}")
        self.serial.connect(SerialConfig(port=option.port, baudrate=baudrate))
        return ConnectionResult(option=option, baudrate=baudrate)

    def disconnect(self) -> None:
        self.serial.disconnect()

    def send(self, command: str) -> None:
        self.serial.send(command)

    def probe_port(self, port: str, baudrate: int) -> bool:
        try:
            import serial as pyserial

            with pyserial.Serial(port, baudrate, timeout=0.25, write_timeout=0.25) as ser:
                SerialManager._stabilize_port(ser)
                end = time.monotonic() + PROBE_TIMEOUT_S
                next_probe = 0.0
                while time.monotonic() < end:
                    now = time.monotonic()
                    if now >= next_probe:
                        for cmd in (b"GET_INFO\n", b"GET_STATUS\n"):
                            ser.write(cmd)
                        ser.flush()
                        next_probe = now + PROBE_RETRY_INTERVAL_S
                    line = ser.readline().decode("utf-8", errors="replace").strip()
                    if line and is_gateway_protocol_line(line):
                        return True
            return False
        except Exception:
            return False

    @staticmethod
    def extract_port_name(raw: str) -> str:
        text = str(raw or "").strip()
        if not text:
            return ""
        punctuated = re.match(r"^(?P<port>\S+)\s+[^\w\s]+\s+.+$", text)
        if punctuated:
            return str(punctuated.group("port"))
        for separator in (" - ", " — "):
            if separator in text:
                return text.split(separator, 1)[0].strip()
        return text

    @property
    def last_port_options(self) -> Iterable[PortOption]:
        return tuple(self._last_port_options)
