"""Cost-summary service that combines stored energy data with cached price information."""

from __future__ import annotations

from datetime import datetime

from ..backend.models import CapacityEstimateData, CostRow, CostSummaryData, SnapshotEvent
from ..domain.pricing import GRID_DAY_RATE_NOK_PER_KWH, GRID_NIGHT_RATE_NOK_PER_KWH, PriceProvider, estimate_capacity
from .history_service import HistoryService


class CostService:
    def __init__(self, history_service: HistoryService, price_provider: PriceProvider | None = None) -> None:
        self.history_service = history_service
        self.price_provider = price_provider or PriceProvider()

    def capacity_estimate(self, limit: int = 12000) -> CapacityEstimateData:
        intervals = self.history_service.integrated_intervals(limit)
        latest_day = max((interval.start.date() for interval in intervals), default=None)
        month = latest_day.strftime("%Y-%m") if latest_day else ""
        bucket_map: dict[str, dict[str, float | str]] = {}
        for interval in intervals:
            start_dt = interval.start.astimezone()
            if month and not start_dt.strftime("%Y-%m-%d").startswith(month):
                continue
            key = start_dt.strftime("%Y-%m-%d %H")
            bucket = bucket_map.setdefault(
                key,
                {
                    "day": start_dt.strftime("%Y-%m-%d"),
                    "hour": start_dt.strftime("%H"),
                    "import_kwh": 0.0,
                    "duration_h": 0.0,
                },
            )
            bucket["import_kwh"] += interval.import_kw * interval.hours
            bucket["duration_h"] += interval.hours

        hourly_for_capacity: list[dict[str, float | str]] = []
        for key in sorted(bucket_map.keys()):
            bucket = bucket_map[key]
            duration_h = max(float(bucket["duration_h"]), 1e-6)
            hourly_for_capacity.append(
                {
                    "day": bucket["day"],
                    "hour": bucket["hour"],
                    "avg_import_kw": float(bucket["import_kwh"]) / duration_h,
                }
            )
        return estimate_capacity(hourly_for_capacity)

    def build_summary(
        self,
        *,
        latest_snapshot: SnapshotEvent | None,
        area: str,
        day_rate: float = GRID_DAY_RATE_NOK_PER_KWH,
        night_rate: float = GRID_NIGHT_RATE_NOK_PER_KWH,
        limit: int = 8000,
        now: datetime | None = None,
    ) -> CostSummaryData:
        active_now = now or datetime.now().astimezone()
        price_quote = self.price_provider.quote_for_hour(area, active_now)
        spot = float(price_quote.nok_per_kwh)
        grid = self.price_provider.current_grid_rate(active_now.hour, day_rate, night_rate)
        total = spot + grid
        import_cost_now = ((latest_snapshot.import_w / 1000.0) * total) if latest_snapshot else 0.0
        export_value_now = ((latest_snapshot.export_w / 1000.0) * spot) if latest_snapshot else 0.0

        intervals = self.history_service.integrated_intervals(limit)
        daily_import = 0.0
        daily_export = 0.0
        current_hour_import = 0.0
        latest_day = max((interval.start.date() for interval in intervals), default=None)
        current_hour = active_now.strftime("%Y-%m-%d %H")
        bucket_map: dict[str, dict[str, float | str]] = {}
        fallback_bucket_keys: set[str] = set()

        for interval in intervals:
            start_dt = interval.start.astimezone()
            hour_quote = self.price_provider.quote_for_hour(area, start_dt)
            spot_h = hour_quote.nok_per_kwh
            grid_h = self.price_provider.current_grid_rate(start_dt.hour, day_rate, night_rate)
            total_h = spot_h + grid_h
            import_cost = interval.import_kw * interval.hours * total_h
            export_value = interval.export_kw * interval.hours * spot_h
            if latest_day and start_dt.date() == latest_day:
                daily_import += import_cost
                daily_export += export_value
                key = start_dt.strftime("%Y-%m-%d %H")
                if hour_quote.fallback_used:
                    fallback_bucket_keys.add(key)
                bucket = bucket_map.setdefault(
                    key,
                    {
                        "day": start_dt.strftime("%Y-%m-%d"),
                        "hour": start_dt.strftime("%H"),
                        "import_kwh": 0.0,
                        "export_kwh": 0.0,
                        "import_cost_nok": 0.0,
                        "export_value_nok": 0.0,
                        "spot_nok_kwh": spot_h,
                        "grid_nok_kwh": grid_h,
                        "total_nok_kwh": total_h,
                        "duration_h": 0.0,
                    },
                )
                bucket["import_kwh"] += interval.import_kw * interval.hours
                bucket["export_kwh"] += interval.export_kw * interval.hours
                bucket["import_cost_nok"] += import_cost
                bucket["export_value_nok"] += export_value
                bucket["duration_h"] += interval.hours
                if key == current_hour:
                    current_hour_import += import_cost

        rows: list[CostRow] = []
        for key in sorted(bucket_map.keys()):
            bucket = bucket_map[key]
            duration_h = max(float(bucket["duration_h"]), 1e-6)
            rows.append(
                CostRow(
                    hour=str(bucket["hour"]),
                    day=str(bucket["day"]),
                    spot_nok_kwh=round(float(bucket["spot_nok_kwh"]), 3),
                    grid_nok_kwh=round(float(bucket["grid_nok_kwh"]), 3),
                    total_nok_kwh=round(float(bucket["total_nok_kwh"]), 3),
                    import_kw=round(float(bucket["import_kwh"]) / duration_h, 3),
                    export_kw=round(float(bucket["export_kwh"]) / duration_h, 3),
                    import_cost_nok=round(float(bucket["import_cost_nok"]), 3),
                    export_value_nok=round(float(bucket["export_value_nok"]), 3),
                    net_cost_nok=round(float(bucket["import_cost_nok"]) - float(bucket["export_value_nok"]), 3),
                )
            )

        capacity = self.capacity_estimate(limit)
        warnings: list[str] = []
        if price_quote.warning_text:
            warnings.append(price_quote.warning_text)
        if fallback_bucket_keys:
            warnings.append(
                f"Historical hourly cost rows used fallback spot pricing in {len(fallback_bucket_keys)} bucket(s)."
            )
        warning_text = " ".join(text for text in warnings if text).strip()
        spot_label = "estimated spot" if price_quote.fallback_used else "spot"

        return CostSummaryData(
            source_text=f"{price_quote.source_name} - {area} - {price_quote.source_note}",
            spot_now_text=f"{spot:.3f} NOK/kWh {spot_label}",
            grid_now_text=f"{grid:.3f} NOK/kWh {self.price_provider.current_grid_rate_label(active_now.hour)}",
            total_now_text=f"{total:.3f} NOK/kWh total",
            warning_text=warning_text,
            import_cost_now_text=f"{import_cost_now:.2f} NOK/h current import cost",
            export_value_now_text=f"{export_value_now:.2f} NOK/h current export value",
            daily_import_cost_text=f"{daily_import:.2f} NOK daily import cost",
            daily_export_value_text=f"{daily_export:.2f} NOK daily export value",
            daily_net_cost_text=f"{daily_import - daily_export:.2f} NOK daily net cost",
            current_hour_cost_text=f"{current_hour_import:.2f} NOK current hour import est.",
            capacity_step_text=capacity.step_label,
            capacity_price_text=capacity.step_price_text,
            capacity_basis_text=capacity.basis_text,
            capacity_warning_text=capacity.warning_text,
            rows=rows,
        )
