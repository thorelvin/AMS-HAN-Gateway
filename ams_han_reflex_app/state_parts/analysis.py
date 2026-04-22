from __future__ import annotations

from ..domain.analysis import HeatmapRow, TopHourRow
from ..domain.signatures import SignatureRowData
from .common import _service


class DashboardAnalysisState:
    top_hour_rows: list[TopHourRow] = []
    signature_rows: list[SignatureRowData] = []
    daily_graph_rows: list[dict[str, float | str]] = []
    heatmap_recent_rows: list[HeatmapRow] = []
    heatmap_weekday_rows: list[HeatmapRow] = []
    daily_date_text: str = "No daily data"
    daily_peak_text: str = "No daily peak yet"
    daily_hours_text: str = "0 populated hours"
    heatmap_days_text: str = "0 days in heatmap"
    heatmap_peak_text: str = "No hourly load peak yet"
    heatmap_change_text: str = "No load-change spikes yet"
    heatmap_weekday_text: str = "No weekday pattern yet"

    signed_avg_text: str = "0.00 kW near balanced"
    current_hour_text: str = "0.00 kW near balanced this hour"
    projected_hour_text: str = "0.00 kWh near-balanced projection"
    hour_energy_text: str = "0.00 kWh near balanced this hour"
    hour_energy_detail_text: str = "Import 0.00 | Export 0.00 kWh"
    day_energy_text: str = "0.00 kWh near balanced today"
    day_energy_detail_text: str = "Import 0.00 | Export 0.00 kWh"
    week_energy_text: str = "0.00 kWh near balanced this week"
    week_energy_detail_text: str = "Import 0.00 | Export 0.00 kWh"
    import_peak_text: str = "0.0 W peak import"
    export_peak_text: str = "0.0 W peak export"
    import_samples_text: str = "0 import samples"
    export_samples_text: str = "0 export samples"

    phase_latest_text: str = "No phase data"
    phase_avg_text: str = "No averages yet"
    phase_dominant_text: str = "-"
    phase_imbalance_text: str = "0.000 A recent max imbalance"
    voltage_latest_text: str = "No voltage frame yet"
    voltage_avg_text: str = "No voltage averages yet"
    voltage_min_text: str = "No voltage minimums yet"
    voltage_spread_text: str = "0.0 V worst phase spread"
    heatmap_switch_threshold: str = "300"
    mains_network_type: str = "TN"

    def set_heatmap_switch_threshold(self, value: str):
        cleaned = "".join(ch for ch in str(value) if ch.isdigit())
        threshold = int(cleaned) if cleaned else 300
        self.heatmap_switch_threshold = str(_service().set_heatmap_switch_threshold(threshold))
        self.refresh_analysis()

    def set_mains_network_type(self, value: str):
        normalized = "IT" if str(value).strip().upper() == "IT" else "TN"
        self.mains_network_type = normalized
        _service().set_mains_network_type(normalized)
        self.refresh_analysis()
        self.refresh_diagnostics()

    def refresh_live_metrics(self):
        limit = int(self.history_limit or "200") if (self.history_limit or "200").isdigit() else 200
        self.refresh_history_summary()
        summary = _service().analysis_summary(max(limit, 1) * 5)
        self.signed_avg_text = summary.signed_avg_text
        self.current_hour_text = summary.current_hour_text
        self.projected_hour_text = summary.projected_hour_text
        self.hour_energy_text = summary.hour_energy_text
        self.hour_energy_detail_text = summary.hour_energy_detail_text
        self.day_energy_text = summary.day_energy_text
        self.day_energy_detail_text = summary.day_energy_detail_text
        self.week_energy_text = summary.week_energy_text
        self.week_energy_detail_text = summary.week_energy_detail_text
        self.import_peak_text = summary.import_peak_text
        self.export_peak_text = summary.export_peak_text
        self.import_samples_text = summary.import_samples_text
        self.export_samples_text = summary.export_samples_text
        capacity = _service().capacity_estimate(12000)
        self.capacity_step_text = capacity.step_label
        self.capacity_price_text = capacity.step_price_text
        self.capacity_basis_kw_text = capacity.basis_kw_text
        self.capacity_basis_text = capacity.basis_text
        self.capacity_warning_text = capacity.warning_text
        self.capacity_steps = capacity.steps

    def refresh_analysis(self):
        limit = int(self.history_limit or "200") if (self.history_limit or "200").isdigit() else 200
        self.refresh_live_metrics()
        phase = _service().phase_analysis(max(limit, 1))
        self.phase_latest_text = phase.phase_latest_text
        self.phase_avg_text = phase.phase_avg_text
        self.phase_dominant_text = phase.phase_dominant_text
        self.phase_imbalance_text = phase.phase_imbalance_text
        self.voltage_latest_text = phase.voltage_latest_text
        self.voltage_avg_text = phase.voltage_avg_text
        self.voltage_min_text = phase.voltage_min_text
        self.voltage_spread_text = phase.voltage_spread_text
        self.top_hour_rows = _service().top_hour_rows(max(limit, 1) * 10, top_n=8)

        daily = _service().daily_graph_data(max(limit, 1) * 20)
        self.daily_graph_rows = daily.rows
        self.daily_date_text = daily.date_text
        self.daily_hours_text = daily.hours_text
        self.daily_peak_text = daily.peak_text

        threshold = int(self.heatmap_switch_threshold or "300") if (self.heatmap_switch_threshold or "300").isdigit() else 300
        heatmaps = _service().load_heatmaps(max(limit, 1) * 20, switch_threshold_w=threshold)
        self.heatmap_recent_rows = heatmaps.recent_rows
        self.heatmap_weekday_rows = heatmaps.weekday_rows
        self.heatmap_days_text = heatmaps.day_count_text
        self.heatmap_peak_text = heatmaps.peak_hour_text
        self.heatmap_change_text = heatmaps.change_peak_text
        self.heatmap_weekday_text = heatmaps.weekday_focus_text
        self.signature_rows = _service().signature_rows(12, coverage_limit=max(limit, 1) * 20)
