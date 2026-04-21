from __future__ import annotations

import reflex as rx

from .common import _service


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
        replay = _service().replay_summary()
        if replay.get("loaded"):
            return (
                f"Replay mode active: {replay.get('source_name')} | "
                f"{replay.get('status_text')} | {replay.get('progress_text')}"
            )
        if self.stale_snapshot:
            return "Disconnected from gateway. Showing last cached snapshot while auto-reconnect runs in the background."
        if self.connection_status.startswith("Connected to") and not self.has_snapshot:
            return "Gateway connected. Waiting for HAN frames..."
        if self.connection_status == "No gateway found":
            return "No gateway found. Plug in the ESP gateway or open Advanced to choose a port."
        if self.has_snapshot:
            return "Live HAN data active. Front page shows unified house flow; Analysis gives deeper phase, voltage and event insight."
        return self.auto_connect_message

    @rx.var(cache=False)
    def mains_network_note(self) -> str:
        if self.mains_network_type == "IT":
            return "IT mode treats many 230 V loads as phase-to-phase. Events and signatures are labeled as L1-L2, L1-L3, L2-L3, or 3-phase when two conductors move together."
        return "TN mode treats most 230 V loads as phase-to-neutral. Events and signatures are labeled as L1, L2, L3, or 3-phase from current deltas."

    @rx.var(cache=False)
    def heatmap_assignment_text(self) -> str:
        if self.mains_network_type == "IT":
            return "Counts signed power changes at or above the selected watt level and assigns them to L1-L2, L1-L3, L2-L3, or 3-phase using phase-current deltas."
        return "Counts signed power changes at or above the selected watt level and assigns them to L1, L2, L3, or 3-phase using phase-current deltas."

    @rx.var(cache=False)
    def heatmap_recent_description(self) -> str:
        if self.mains_network_type == "IT":
            return "Rows are the most recent days. Each cell shows average net load for the hour, then L1-L2/L1-L3/L2-L3 switch counts and 3P switch count for the selected threshold."
        return "Rows are the most recent days. Each cell shows average net load for the hour, then L1/L2/L3 switch counts and 3P switch count for the selected threshold."

    @rx.var(cache=False)
    def signature_assignment_text(self) -> str:
        if self.mains_network_type == "IT":
            return "Recurring signatures now include duty-cycle hints. IT mode labels 230 V loads as L1-L2, L1-L3, or L2-L3 when two conductors move together."
        return "Recurring signatures now include duty-cycle hints. TN mode labels most 230 V loads as L1, L2, or L3 unless all three conductors move together."
