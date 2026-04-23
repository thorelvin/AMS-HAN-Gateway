"""Thin service wrapper around the pure analysis functions used by the dashboard."""

from __future__ import annotations

from typing import Any

from ..backend.models import HistoryRecord, SnapshotEvent
from ..domain.analysis import (
    AnalysisSummaryData,
    DailyGraphData,
    DiagnosticsEventRow,
    HeatmapSummaryData,
    HistoryTableRow,
    PhaseAnalysisData,
    TopHourRow,
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
from ..domain.signatures import SignatureRowData


class AnalysisService:
    def history_rows(self, records: list[HistoryRecord]) -> list[HistoryTableRow]:
        return history_rows(records)

    def analysis_summary(
        self,
        records: list[HistoryRecord],
        *,
        energy_records: list[HistoryRecord] | None = None,
    ) -> AnalysisSummaryData:
        return analysis_summary(records, energy_records_desc=energy_records)

    def phase_analysis(
        self,
        phase_samples: list[dict[str, Any]],
        history_records: list[HistoryRecord],
        *,
        mains_network_type: str,
    ) -> PhaseAnalysisData:
        return phase_analysis(phase_samples, history_records, mains_network_type=mains_network_type)

    def top_hour_rows(self, records: list[HistoryRecord], *, top_n: int = 8) -> list[TopHourRow]:
        return top_hour_rows(records, top_n)

    def daily_graph_data(self, records: list[HistoryRecord]) -> DailyGraphData:
        return daily_graph_data(records)

    def load_heatmaps(
        self,
        records: list[HistoryRecord],
        *,
        switch_threshold_w: float,
        mains_network_type: str,
    ) -> HeatmapSummaryData:
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
        events: list[DiagnosticsEventRow] = []
        issue_events: list[dict[str, str]] = []
        for event in event_log:
            if event_filter == "open" and event.get("status") != "open":
                continue
            if event_filter == "resolved" and event.get("status") != "resolved":
                continue
            if event_filter == "severe" and event.get("severity") not in ("high", "critical"):
                continue
            if event_filter in ("power", "voltage", "phase", "connectivity", "data_quality") and event.get("category") != event_filter:
                continue
            row = DiagnosticsEventRow(
                time=str(event.get("time", "-")),
                type=str(event.get("type", event.get("event_type", "-"))),
                status=str(event.get("status", "-")),
                severity=str(event.get("severity", "-")),
                confidence=str(event.get("conf", event.get("confidence", "-"))),
                delta_signed=str(event.get("dW", event.get("delta_signed", "-"))),
                phase=str(event.get("phase", "-")),
                voltages=str(event.get("voltages", "-")),
                phase_delta=str(event.get("phase_delta", "-")),
                note=str(event.get("note", "-")),
                summary=str(event.get("summary", "-")),
                category=str(event.get("category", "-")),
            )
            events.append(row)
            issue_events.append(
                {
                    "time": row.time,
                    "type": row.type,
                    "status": row.status,
                    "severity": row.severity,
                    "confidence": row.confidence,
                    "delta_signed": row.delta_signed,
                    "phase": row.phase,
                    "voltages": row.voltages,
                    "phase_delta": row.phase_delta,
                    "note": row.note,
                    "summary": row.summary,
                    "category": row.category,
                }
            )
            if len(events) >= limit:
                break
        issues = diagnose_issues(issue_events, phase, connection_status, wifi_state)
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
            "what_changed": what_changed(latest_snapshot, issue_events),
        }

    def signature_rows(
        self,
        event_log: list[dict[str, Any]],
        *,
        limit: int,
        observed_dates: list[str],
    ) -> list[SignatureRowData]:
        return build_signature_rows(event_log, limit, observed_dates=observed_dates)
