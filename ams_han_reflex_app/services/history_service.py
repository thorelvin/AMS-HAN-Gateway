"""History storage service for persisted readings and replay-backed in-memory records."""

from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path
from statistics import mean

from ..backend.models import HistoryRecord, HistorySummary, IntegratedInterval, SnapshotEvent
from ..backend.storage import SnapshotStore
from ..domain.analysis import parse_meter_dt


class HistoryService:
    def __init__(self, db_path: Path, snapshot_store: SnapshotStore | None = None) -> None:
        self.db_path = Path(db_path)
        self.store = snapshot_store or SnapshotStore(self.db_path)
        self.replay_records: deque[HistoryRecord] = deque(maxlen=12000)
        self._replay_row_id = 0

    def set_db_path(self, path: str | Path) -> None:
        self.db_path = Path(path)
        self.store = SnapshotStore(self.db_path)

    def clear_history(self) -> None:
        self.store.clear_history()
        self.clear_replay()

    def clear_replay(self) -> None:
        self.replay_records.clear()
        self._replay_row_id = 0

    def has_replay_records(self) -> bool:
        return bool(self.replay_records)

    def record_snapshot(self, snap: SnapshotEvent, *, replay_mode: bool) -> None:
        if replay_mode:
            self._replay_row_id += 1
            self.replay_records.appendleft(
                HistoryRecord(
                    row_id=self._replay_row_id,
                    received_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    snapshot=snap,
                )
            )
            return
        self.store.save_snapshot(snap)

    def records_desc(self, limit: int = 500) -> list[HistoryRecord]:
        if self.replay_records:
            return list(self.replay_records)[:limit]
        return self.store.get_recent(limit)

    def all_records_desc(self, limit: int = 0) -> list[HistoryRecord]:
        if self.replay_records:
            rows = list(self.replay_records)
            return rows[:limit] if limit > 0 else rows
        # Most dashboard analytics only need the newest N rows. Fetching the full
        # table and slicing in Python makes the UI gradually slower as history grows.
        return self.store.get_recent(limit) if limit > 0 else self.store.get_all()

    def records_since_meter_time(self, since: datetime, limit: int = 0) -> list[HistoryRecord]:
        if self.replay_records:
            rows = [
                record
                for record in self.replay_records
                if (dt := parse_meter_dt(record.snapshot.timestamp)) is not None and dt >= since
            ]
            return rows[:limit] if limit > 0 else rows
        return self.store.get_since_meter_time(since.strftime("%Y-%m-%d %H:%M:%S"), limit)

    def summary(self, limit: int = 500) -> HistorySummary:
        if not self.replay_records:
            return self.store.get_summary(limit)
        recs = self.records_desc(limit)
        if not recs:
            return HistorySummary()
        return HistorySummary(
            count=len(recs),
            avg_import_w=mean(record.snapshot.import_w for record in recs),
            avg_net_w=mean(record.snapshot.net_power_w for record in recs),
            max_import_w=max(record.snapshot.import_w for record in recs),
            min_net_w=min(record.snapshot.net_power_w for record in recs),
            max_net_w=max(record.snapshot.net_power_w for record in recs),
            latest_received_at=recs[0].received_at,
        )

    def integrated_intervals(self, limit: int = 8000) -> list[IntegratedInterval]:
        recs = list(reversed(self.all_records_desc(limit)))
        rows: list[IntegratedInterval] = []
        prev_dt = None
        prev_snap = None
        for record in recs:
            dt = parse_meter_dt(record.snapshot.timestamp)
            if dt is None:
                continue
            if prev_dt is not None and prev_snap is not None:
                delta_h = max(0.0, (dt - prev_dt).total_seconds() / 3600.0)
                if 0 < delta_h < 0.5:
                    rows.append(
                        IntegratedInterval(
                            start=prev_dt,
                            end=dt,
                            hours=delta_h,
                            import_kw=prev_snap.import_w / 1000.0,
                            export_kw=prev_snap.export_w / 1000.0,
                        )
                    )
            prev_dt = dt
            prev_snap = record.snapshot
        return rows
