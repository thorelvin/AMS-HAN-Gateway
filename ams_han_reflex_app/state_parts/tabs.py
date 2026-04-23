"""Reflex state slice for cross-tab refresh behavior and current-tab selection."""

from __future__ import annotations


class DashboardTabState:
    current_tab: str = "live"

    def set_current_tab(self, value: str):
        self.current_tab = value
        self.refresh_tab_data()

    def refresh_tab_data(self):
        if self.current_tab == "history":
            self.refresh_history()
        elif self.current_tab == "diagnostics":
            self.refresh_diagnostics()
        elif self.current_tab == "cost":
            self.refresh_cost()
        elif self.current_tab in ("analysis", "daily", "heatmap"):
            self.refresh_analysis()
