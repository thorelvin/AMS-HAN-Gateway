from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import serial
import serial.tools.list_ports


@dataclass(slots=True)
class SerialConfig:
    port: str
    baudrate: int = 115200
    timeout: float = 0.2


class SerialManager:
    def __init__(self, on_line: Callable[[str], None], on_state: Callable[[bool, str], None]) -> None:
        self._on_line = on_line
        self._on_state = on_state
        self._serial: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._tx_queue: queue.Queue[str] = queue.Queue()

    @staticmethod
    def list_ports() -> list[tuple[str, str]]:
        return [(p.device, p.description or "") for p in serial.tools.list_ports.comports()]

    @property
    def connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def connect(self, config: SerialConfig) -> None:
        if self.connected:
            self.disconnect()
        self._clear_tx_queue()
        self._stop.clear()
        self._serial = serial.Serial(config.port, config.baudrate, timeout=config.timeout)
        self._thread = threading.Thread(target=self._worker, name="serial-worker", daemon=True)
        self._thread.start()
        self._on_state(True, f"Connected to {config.port}")

    def disconnect(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except serial.SerialException:
                pass
        self._serial = None
        self._clear_tx_queue()
        self._on_state(False, "Disconnected")

    def send(self, command: str) -> None:
        self._tx_queue.put(command.rstrip("\r\n") + "\n")

    def _clear_tx_queue(self) -> None:
        while True:
            try:
                self._tx_queue.get_nowait()
            except queue.Empty:
                break

    def _worker(self) -> None:
        assert self._serial is not None
        ser = self._serial
        while not self._stop.is_set():
            try:
                while True:
                    cmd = self._tx_queue.get_nowait()
                    ser.write(cmd.encode("utf-8", errors="replace"))
                    ser.flush()
            except queue.Empty:
                pass

            try:
                line = ser.readline()
                if line:
                    decoded = line.decode("utf-8", errors="replace").rstrip("\r\n")
                    self._on_line(decoded)
            except serial.SerialException as exc:
                self._on_state(False, f"Serial error: {exc}")
                break
            except Exception as exc:  # noqa: BLE001
                self._on_state(False, f"Unexpected serial error: {exc}")
                break

            time.sleep(0.01)

        try:
            if ser.is_open:
                ser.close()
        except serial.SerialException:
            pass
        finally:
            self._serial = None
