"""Reflex state slice for warning filters, event lists, and diagnostic refreshes."""

from __future__ import annotations

from ..domain.analysis import DiagnosticsEventRow
from .common import _service


class DashboardDiagnosticsState:
    event_filter: str = "all"
    event_rows: list[DiagnosticsEventRow] = []
    diagnostics_issues: list[str] = []
    health_rows: list[dict[str, str]] = []

    def set_event_filter(self, value: str):
        self.event_filter = value
        self.refresh_diagnostics()

    def refresh_diagnostics(self):
        diagnostics = _service().diagnostics_summary(80, self.event_filter)
        self.diagnostics_issues = diagnostics["issues"]
        self.health_rows = diagnostics["health"]
        self.event_rows = _service().event_tracker_rows(120, self.event_filter)
