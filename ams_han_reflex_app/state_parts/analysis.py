from __future__ import annotations

from ..backend.models import CostRow
from ..domain.analysis import DiagnosticsEventRow, HeatmapRow, HistoryTableRow, TopHourRow
from ..domain.signatures import SignatureRowData
from .common import _service


class DashboardAnalysisState:
    price_area: str = "NO3"
    grid_day_rate: str = "0.4254"
    grid_night_rate: str = "0.2642"
    cost_source_text: str = "-"
    spot_now_text: str = "-"
    grid_now_text: str = "-"
    total_now_text: str = "-"
    cost_warning_text: str = ""
    import_cost_now_text: str = "-"
    export_value_now_text: str = "-"
    daily_import_cost_text: str = "-"
    daily_export_value_text: str = "-"
    daily_net_cost_text: str = "-"
    current_hour_cost_text: str = "-"
    capacity_step_text: str = "-"
    capacity_price_text: str = "-"
    capacity_basis_text: str = "-"
    capacity_warning_text: str = "-"
    cost_rows: list[CostRow] = []

    history_limit: str = "200"
    db_path: str = ""
    history_rows: list[HistoryTableRow] = []
    top_hour_rows: list[TopHourRow] = []
    event_rows: list[DiagnosticsEventRow] = []
    signature_rows: list[SignatureRowData] = []
    diagnostics_issues: list[str] = []
    health_rows: list[dict[str, str]] = []
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
    current_tab: str = "live"
    db_count: int = 0
    avg_import_text: str = "0.0 W avg import"
    avg_net_text: str = "0.0 W avg net"
    peak_text: str = "0.0 W max import | 0.0/0.0 W net"
    latest_history_text: str = "-"

    signed_avg_text: str = "0.0 W signed avg"
    current_hour_text: str = "0.0 W current hour avg"
    projected_hour_text: str = "0.00 kWh projected hour"
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
    event_filter: str = "all"

    def set_price_area(self, value: str):
        self.price_area = value

    def set_grid_day_rate(self, value: str):
        self.grid_day_rate = value

    def set_grid_night_rate(self, value: str):
        self.grid_night_rate = value

    def set_history_limit(self, value: str):
        self.history_limit = value

    def set_db_path(self, value: str):
        self.db_path = value

    def set_event_filter(self, value: str):
        self.event_filter = value
        self.refresh_diagnostics()

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

    def set_current_tab(self, value: str):
        self.current_tab = value
        self.refresh_tab_data()

    def refresh_history_summary(self):
        limit = int(self.history_limit or "200") if (self.history_limit or "200").isdigit() else 200
        summary = _service().get_summary(max(limit, 1))
        self.db_count = summary.count
        self.avg_import_text = f"{summary.avg_import_w:.1f} W avg import"
        self.avg_net_text = f"{summary.avg_net_w:.1f} W avg net"
        self.peak_text = (
            f"{summary.max_import_w:.1f} W max import | "
            f"{summary.min_net_w:.1f}/{summary.max_net_w:.1f} W net"
        )
        self.latest_history_text = summary.latest_received_at

    def refresh_history(self):
        limit = int(self.history_limit or "200") if (self.history_limit or "200").isdigit() else 200
        self.history_rows = _service().get_history_rows(limit)
        self.refresh_history_summary()

    def refresh_live_metrics(self):
        limit = int(self.history_limit or "200") if (self.history_limit or "200").isdigit() else 200
        self.refresh_history_summary()
        summary = _service().analysis_summary(max(limit, 1) * 5)
        self.signed_avg_text = summary.signed_avg_text
        self.current_hour_text = summary.current_hour_text
        self.projected_hour_text = summary.projected_hour_text
        self.import_peak_text = summary.import_peak_text
        self.export_peak_text = summary.export_peak_text
        self.import_samples_text = summary.import_samples_text
        self.export_samples_text = summary.export_samples_text

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

    def refresh_diagnostics(self):
        diagnostics = _service().diagnostics_summary(80, self.event_filter)
        self.diagnostics_issues = diagnostics["issues"]
        self.health_rows = diagnostics["health"]
        self.event_rows = _service().event_tracker_rows(120, self.event_filter)

    def refresh_cost(self):
        cost = _service().cost_summary(12000)
        self.cost_source_text = cost.source_text
        self.spot_now_text = cost.spot_now_text
        self.grid_now_text = cost.grid_now_text
        self.total_now_text = cost.total_now_text
        self.cost_warning_text = cost.warning_text
        self.import_cost_now_text = cost.import_cost_now_text
        self.export_value_now_text = cost.export_value_now_text
        self.daily_import_cost_text = cost.daily_import_cost_text
        self.daily_export_value_text = cost.daily_export_value_text
        self.daily_net_cost_text = cost.daily_net_cost_text
        self.current_hour_cost_text = cost.current_hour_cost_text
        self.capacity_step_text = cost.capacity_step_text
        self.capacity_price_text = cost.capacity_price_text
        self.capacity_basis_text = cost.capacity_basis_text
        self.capacity_warning_text = cost.capacity_warning_text
        self.cost_rows = cost.rows

    def refresh_tab_data(self):
        if self.current_tab == "history":
            self.refresh_history()
        elif self.current_tab == "diagnostics":
            self.refresh_diagnostics()
        elif self.current_tab == "cost":
            self.refresh_cost()
        elif self.current_tab in ("analysis", "daily", "heatmap"):
            self.refresh_analysis()

    def apply_cost_settings(self):
        try:
            day = float(self.grid_day_rate or "0")
        except ValueError:
            day = 0.4254
            self.grid_day_rate = str(day)
        try:
            night = float(self.grid_night_rate or "0")
        except ValueError:
            night = 0.2642
            self.grid_night_rate = str(night)
        _service().save_cost_settings(price_area=self.price_area, grid_day_rate=day, grid_night_rate=night)
        self.refresh_cost()

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
