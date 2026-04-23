"""Reflex state slice for saved-reading tables and history-tab summaries."""

from __future__ import annotations

from ..domain.analysis import HistoryTableRow
from .common import _service


class DashboardHistoryState:
    history_limit: str = "200"
    db_path: str = ""
    history_rows: list[HistoryTableRow] = []
    db_count: int = 0
    avg_import_text: str = "0.0 W average import"
    avg_net_text: str = "0.0 W average net flow"
    peak_text: str = "0.0 W highest import | 0.0/0.0 W net range"
    latest_history_text: str = "-"

    def set_history_limit(self, value: str):
        self.history_limit = value

    def set_db_path(self, value: str):
        self.db_path = value

    def refresh_history_summary(self):
        limit = int(self.history_limit or "200") if (self.history_limit or "200").isdigit() else 200
        summary = _service().get_summary(max(limit, 1))
        self.db_count = summary.count
        self.avg_import_text = f"{summary.avg_import_w:.1f} W average import"
        self.avg_net_text = f"{summary.avg_net_w:.1f} W average net flow"
        self.peak_text = (
            f"{summary.max_import_w:.1f} W highest import | "
            f"{summary.min_net_w:.1f}/{summary.max_net_w:.1f} W net range"
        )
        self.latest_history_text = summary.latest_received_at

    def refresh_history(self):
        limit = int(self.history_limit or "200") if (self.history_limit or "200").isdigit() else 200
        self.history_rows = _service().get_history_rows(limit)
        self.refresh_history_summary()

    def clear_history(self):
        _service().clear_history()
        self.refresh_history()
        self.refresh_analysis()
        self.refresh_cost()
        self.refresh_diagnostics()
        self.sync_from_service()

    def apply_db_path(self):
        _service().set_db_path(self.db_path)
        self.refresh_history()
        self.refresh_analysis()
        self.refresh_cost()
        self.sync_from_service()
