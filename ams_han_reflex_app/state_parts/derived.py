"""Reflex state slice that converts backend sync data into display-friendly UI fields."""

from __future__ import annotations

import reflex as rx


class DashboardDerivedState:
    @rx.var(cache=False)
    def wifi_summary(self) -> str:
        return f"{self.wifi_state} | {self.wifi_ip}" if self.wifi_ip else self.wifi_state

    @rx.var(cache=False)
    def db_summary(self) -> str:
        return f"{self.db_count} snapshots"

    @rx.var(cache=False)
    def has_diagnostics_issues(self) -> bool:
        return len(self.diagnostics_issues) > 0

    @rx.var(cache=False)
    def has_snapshot(self) -> bool:
        return self.snapshot_meter != "-"

    @rx.var(cache=False)
    def has_cost_warning(self) -> bool:
        return bool(self.cost_warning_text.strip())

    @rx.var(cache=False)
    def show_cached_banner(self) -> bool:
        return self.stale_snapshot

    @rx.var(cache=False)
    def live_opacity(self) -> str:
        return "0.58" if self.stale_snapshot else "1.0"

    @rx.var(cache=False)
    def onboarding_message(self) -> str:
        if self.replay_loaded:
            return (
                f"Replay mode is active. Source: {self.replay_source_text} | "
                f"Status: {self.replay_status_text} | Progress: {self.replay_progress_text}"
            )
        if self.stale_snapshot:
            return "The gateway is disconnected. The dashboard is showing the latest saved reading while it keeps trying to reconnect."
        if self.connection_status.startswith("Connected to") and not self.has_snapshot:
            return "The gateway is connected. Waiting for a meter reading..."
        if self.connection_status == "No gateway found":
            return "No gateway was found. Connect the ESP gateway or open the extra tools to choose a port yourself."
        if self.has_snapshot:
            return "Live meter data is coming in. Live View shows what the house is doing now, and the other tabs explain patterns, warnings, costs and repeating loads."
        return self.auto_connect_message

    @rx.var(cache=False)
    def mains_network_note(self) -> str:
        if self.mains_network_type == "IT":
            return "IT mode assumes many 230 V loads are connected between two phases. The app will label switching as L1-L2, L1-L3, L2-L3 or 3-phase."
        return "TN mode assumes most 230 V loads are connected between one phase and neutral. The app will label switching as L1, L2, L3 or 3-phase."

    @rx.var(cache=False)
    def heatmap_assignment_text(self) -> str:
        if self.mains_network_type == "IT":
            return "Only load changes at or above the selected watt level are counted. Each change is then assigned to L1-L2, L1-L3, L2-L3 or 3-phase by comparing the current change on each line."
        return "Only load changes at or above the selected watt level are counted. Each change is then assigned to L1, L2, L3 or 3-phase by comparing the current change on each line."

    @rx.var(cache=False)
    def heatmap_recent_description(self) -> str:
        if self.mains_network_type == "IT":
            return "Each row is one recent day. Each cell shows the average grid direction for that hour, plus how many larger load changes were seen on L1-L2, L1-L3, L2-L3 and 3-phase."
        return "Each row is one recent day. Each cell shows the average grid direction for that hour, plus how many larger load changes were seen on L1, L2, L3 and 3-phase."

    @rx.var(cache=False)
    def signature_assignment_text(self) -> str:
        if self.mains_network_type == "IT":
            return "These are repeating load patterns the app has recognized. It also estimates runtime and start habits, and in IT mode it labels 230 V loads as L1-L2, L1-L3 or L2-L3 when two lines move together."
        return "These are repeating load patterns the app has recognized. It also estimates runtime and start habits, and in TN mode it labels most 230 V loads as L1, L2 or L3 unless all three lines move together."
