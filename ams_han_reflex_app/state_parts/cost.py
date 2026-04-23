"""Reflex state slice for cost-tab settings, warnings, and hourly cost rows."""

from __future__ import annotations

from ..backend.models import CapacityStepVisual, CostRow
from .common import _service


class DashboardCostState:
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
    capacity_basis_kw_text: str = "0.00 kW basis"
    capacity_basis_text: str = "-"
    capacity_warning_text: str = "-"
    capacity_steps: list[CapacityStepVisual] = []
    cost_rows: list[CostRow] = []

    def set_price_area(self, value: str):
        self.price_area = value

    def set_grid_day_rate(self, value: str):
        self.grid_day_rate = value

    def set_grid_night_rate(self, value: str):
        self.grid_night_rate = value

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
        capacity = _service().capacity_estimate(12000)
        self.capacity_basis_kw_text = capacity.basis_kw_text
        self.capacity_basis_text = capacity.basis_text
        self.capacity_warning_text = capacity.warning_text
        self.capacity_steps = capacity.steps
        self.cost_rows = cost.rows

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
