from __future__ import annotations

from typing import Any

from ..backend.models import HistoryRecord, SnapshotEvent
from ..domain.analysis import (
    analysis_summary,
    build_load_heatmaps,
    daily_graph_data,
    diagnose_issues,
    health_rows,
    history_rows,
    phase_analysis,
    top_hour_rows,
    what_changed,
)
from ..domain.signatures import build_signature_rows


class AnalysisService:
    def history_rows(self, records: list[HistoryRecord]) -> list[dict[str, str]]:
        return history_rows(records)

    def analysis_summary(self, records: list[HistoryRecord]) -> dict[str, str]:
        return analysis_summary(records)

    def phase_analysis(
        self,
        phase_samples: list[dict[str, Any]],
        history_records: list[HistoryRecord],
        *,
        mains_network_type: str,
    ) -> dict[str, str]:
        return phase_analysis(phase_samples, history_records, mains_network_type=mains_network_type)

    def top_hour_rows(self, records: list[HistoryRecord], *, top_n: int = 8) -> list[dict[str, str]]:
        return top_hour_rows(records, top_n)

    def daily_graph_data(self, records: list[HistoryRecord]) -> dict[str, Any]:
        return daily_graph_data(records)

    def load_heatmaps(
        self,
        records: list[HistoryRecord],
        *,
        switch_threshold_w: float,
        mains_network_type: str,
    ) -> dict[str, Any]:
        return build_load_heatmaps(
            records,
            switch_threshold_w=switch_threshold_w,
            mains_network_type=mains_network_type,
        )

    def diagnostics_summary(
        self,
        *,
        recent_phase_samples: list[dict[str, Any]],
        history_records: list[HistoryRecord],
        connection_status: str,
        wifi_state: str,
        mqtt_state: str,
        last_frame_seq: int,
        last_frame_len: int,
        latest_snapshot: SnapshotEvent | None,
        event_log: list[dict[str, Any]],
        event_filter: str,
        limit: int,
        mains_network_type: str,
    ) -> dict[str, Any]:
        phase = self.phase_analysis(
            recent_phase_samples,
            history_records,
            mains_network_type=mains_network_type,
        )
        events: list[dict[str, Any]] = []
        for event in event_log:
            if event_filter == "open" and event.get("status") != "open":
                continue
            if event_filter == "resolved" and event.get("status") != "resolved":
                continue
            if event_filter == "severe" and event.get("severity") not in ("high", "critical"):
                continue
            if event_filter in ("power", "voltage", "phase", "connectivity", "data_quality") and event.get("category") != event_filter:
                continue
            events.append(
                {
                    "time": event.get("time", "-"),
                    "type": event.get("type", event.get("event_type", "-")),
                    "status": event.get("status", "-"),
                    "severity": event.get("severity", "-"),
                    "confidence": event.get("conf", event.get("confidence", "-")),
                    "delta_signed": event.get("dW", event.get("delta_signed", "-")),
                    "phase": event.get("phase", "-"),
                    "voltages": event.get("voltages", "-"),
                    "phase_delta": event.get("phase_delta", "-"),
                    "note": event.get("note", "-"),
                    "summary": event.get("summary", "-"),
                    "category": event.get("category", "-"),
                }
            )
            if len(events) >= limit:
                break
        issues = diagnose_issues(events, phase, connection_status, wifi_state)
        health = health_rows(
            connection_status,
            wifi_state,
            mqtt_state,
            last_frame_seq,
            last_frame_len,
            latest_snapshot,
            len(event_log),
        )
        return {
            "issues": issues,
            "health": health,
            "events": events,
            "phase": phase,
            "what_changed": what_changed(latest_snapshot, events),
        }

    def signature_rows(
        self,
        event_log: list[dict[str, Any]],
        *,
        limit: int,
        observed_dates: list[str],
    ) -> list[dict[str, str]]:
        return build_signature_rows(event_log, limit, observed_dates=observed_dates)
