from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from .models import HistoryRecord, HistorySummary, SnapshotEvent


class SnapshotStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    received_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),
                    sequence INTEGER NOT NULL,
                    meter_id TEXT,
                    meter_type TEXT,
                    meter_timestamp TEXT,
                    import_w REAL,
                    export_w REAL,
                    q_import_var REAL,
                    q_export_var REAL,
                    avg_voltage_v REAL,
                    phase_imbalance_a REAL,
                    l1_a REAL,
                    l2_a REAL,
                    l3_a REAL,
                    net_power_w REAL,
                    estimated_power_factor REAL,
                    total_current_a REAL,
                    apparent_power_va REAL,
                    rolling_samples INTEGER,
                    frames_rx INTEGER,
                    frames_bad INTEGER
                )
                """
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_received_at ON snapshots(received_at DESC)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_meter_time ON snapshots(meter_timestamp DESC)")
            con.commit()

    def save_snapshot(self, snap: SnapshotEvent) -> None:
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO snapshots (
                    sequence, meter_id, meter_type, meter_timestamp,
                    import_w, export_w, q_import_var, q_export_var,
                    avg_voltage_v, phase_imbalance_a,
                    l1_a, l2_a, l3_a,
                    net_power_w, estimated_power_factor,
                    total_current_a, apparent_power_va,
                    rolling_samples, frames_rx, frames_bad
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snap.sequence,
                    snap.meter_id,
                    snap.meter_type,
                    snap.timestamp,
                    snap.import_w,
                    snap.export_w,
                    snap.q_import_var,
                    snap.q_export_var,
                    snap.avg_voltage_v,
                    snap.phase_imbalance_a,
                    snap.l1_a,
                    snap.l2_a,
                    snap.l3_a,
                    snap.net_power_w,
                    snap.estimated_power_factor,
                    snap.total_current_a,
                    snap.apparent_power_va,
                    snap.rolling_samples,
                    snap.frames_rx,
                    snap.frames_bad,
                ),
            )
            con.commit()

    def get_recent(self, limit: int = 200) -> list[HistoryRecord]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT * FROM snapshots
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_all(self) -> list[HistoryRecord]:
        with self._connect() as con:
            rows = con.execute("SELECT * FROM snapshots ORDER BY id DESC").fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_summary(self, limit: int = 500) -> HistorySummary:
        with self._connect() as con:
            row = con.execute(
                """
                SELECT
                    COUNT(*) AS count,
                    COALESCE(AVG(import_w), 0) AS avg_import_w,
                    COALESCE(AVG(net_power_w), 0) AS avg_net_w,
                    COALESCE(MAX(import_w), 0) AS max_import_w,
                    COALESCE(MIN(net_power_w), 0) AS min_net_w,
                    COALESCE(MAX(net_power_w), 0) AS max_net_w,
                    COALESCE(MAX(received_at), '-') AS latest_received_at
                FROM (
                    SELECT * FROM snapshots ORDER BY id DESC LIMIT ?
                )
                """,
                (limit,),
            ).fetchone()
        if row is None:
            return HistorySummary()
        return HistorySummary(
            count=int(row["count"] or 0),
            avg_import_w=float(row["avg_import_w"] or 0),
            avg_net_w=float(row["avg_net_w"] or 0),
            max_import_w=float(row["max_import_w"] or 0),
            min_net_w=float(row["min_net_w"] or 0),
            max_net_w=float(row["max_net_w"] or 0),
            latest_received_at=str(row["latest_received_at"] or "-"),
        )

    def export_csv(self, csv_path: Path, limit: int = 0) -> None:
        rows = self.get_recent(limit) if limit > 0 else self.get_all()
        csv_path = Path(csv_path)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "received_at", "sequence", "meter_id", "meter_type", "meter_timestamp",
                    "import_w", "export_w", "q_import_var", "q_export_var",
                    "avg_voltage_v", "phase_imbalance_a",
                    "l1_a", "l2_a", "l3_a",
                    "net_power_w", "estimated_power_factor",
                    "total_current_a", "apparent_power_va",
                    "rolling_samples", "frames_rx", "frames_bad",
                ]
            )
            for record in reversed(rows):
                s = record.snapshot
                writer.writerow(
                    [
                        record.received_at,
                        s.sequence,
                        s.meter_id,
                        s.meter_type,
                        s.timestamp,
                        s.import_w,
                        s.export_w,
                        s.q_import_var,
                        s.q_export_var,
                        s.avg_voltage_v,
                        s.phase_imbalance_a,
                        s.l1_a,
                        s.l2_a,
                        s.l3_a,
                        s.net_power_w,
                        s.estimated_power_factor,
                        s.total_current_a,
                        s.apparent_power_va,
                        s.rolling_samples,
                        s.frames_rx,
                        s.frames_bad,
                    ]
                )

    def clear_history(self) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM snapshots")
            con.commit()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> HistoryRecord:
        snap = SnapshotEvent(
            sequence=int(row["sequence"]),
            meter_id=str(row["meter_id"] or ""),
            meter_type=str(row["meter_type"] or ""),
            timestamp=str(row["meter_timestamp"] or ""),
            import_w=float(row["import_w"] or 0),
            export_w=float(row["export_w"] or 0),
            q_import_var=float(row["q_import_var"] or 0),
            q_export_var=float(row["q_export_var"] or 0),
            avg_voltage_v=float(row["avg_voltage_v"] or 0),
            phase_imbalance_a=float(row["phase_imbalance_a"] or 0),
            l1_a=float(row["l1_a"] or 0),
            l2_a=float(row["l2_a"] or 0),
            l3_a=float(row["l3_a"] or 0),
            net_power_w=float(row["net_power_w"] or 0),
            estimated_power_factor=float(row["estimated_power_factor"] or 0),
            total_current_a=float(row["total_current_a"] or 0),
            apparent_power_va=float(row["apparent_power_va"] or 0),
            rolling_samples=int(row["rolling_samples"] or 0),
            frames_rx=int(row["frames_rx"] or 0),
            frames_bad=int(row["frames_bad"] or 0),
        )
        return HistoryRecord(row_id=int(row["id"]), received_at=str(row["received_at"]), snapshot=snap)
