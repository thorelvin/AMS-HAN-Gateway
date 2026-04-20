from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen
import json

PRICE_AREAS = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']
GRID_DAY_RATE_NOK_PER_KWH = 0.4254
GRID_NIGHT_RATE_NOK_PER_KWH = 0.2642
CAPACITY_STEPS = [
    (2.0, '0-2 kW', 150),
    (5.0, '2-5 kW', 270),
    (10.0, '5-10 kW', 430),
    (15.0, '10-15 kW', 610),
    (20.0, '15-20 kW', 800),
    (25.0, '20-25 kW', 980),
    (50.0, '25-50 kW', 1500),
]

class PriceProvider:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def _day_key(self, dt: datetime) -> str:
        return dt.strftime('%Y-%m-%d')

    def _fetch_day(self, area: str, dt: datetime) -> list[dict[str, Any]]:
        key = (area, self._day_key(dt))
        if key in self._cache:
            return self._cache[key]
        url = f"https://www.hvakosterstrommen.no/api/v1/prices/{dt.year}/{dt.month:02d}-{dt.day:02d}_{area}.json"
        data: list[dict[str, Any]] = []
        try:
            with urlopen(url, timeout=6) as r:
                payload = json.loads(r.read().decode('utf-8'))
                if isinstance(payload, list):
                    data = payload
        except Exception:
            data = []
        self._cache[key] = data
        return data

    def price_for_hour(self, area: str, dt: datetime) -> float:
        day = self._fetch_day(area, dt)
        target_hour = dt.hour
        for row in day:
            start = str(row.get('time_start') or '')
            if not start:
                continue
            try:
                # convert '2024-01-01T12:00:00+01:00'
                st = datetime.fromisoformat(start.replace('Z', '+00:00'))
                if st.astimezone().hour == target_hour:
                    return float(row.get('NOK_per_kWh') or 1.0)
            except Exception:
                continue
        return 1.0

    def get_price_data(self, area: str, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now().astimezone()
        current = self.price_for_hour(area, now)
        return {
            'source_name': 'hvakosterstrommen.no API',
            'source_note': f'{area} · Spot prices ex VAT from hvakosterstrommen.no',
            'current_price': current,
        }

    @staticmethod
    def current_grid_rate(hour: int, day_rate: float, night_rate: float) -> float:
        return night_rate if (hour >= 22 or hour < 6) else day_rate

    @staticmethod
    def current_grid_rate_label(hour: int) -> str:
        return 'Night (22-06)' if (hour >= 22 or hour < 6) else 'Day (06-22)'


def estimate_capacity(hourly_rows: list[dict[str, Any]]) -> dict[str, str]:
    # hourly_rows: [{'day':'YYYY-MM-DD','hour':'HH','avg_import_kw':x}, ...]
    best_by_day: dict[str, float] = {}
    for row in hourly_rows:
        day = str(row.get('day', ''))
        kw = float(row.get('avg_import_kw', 0.0) or 0.0)
        if not day:
            continue
        if kw > best_by_day.get(day, 0.0):
            best_by_day[day] = kw
    peaks = sorted(best_by_day.items(), key=lambda kv: kv[1], reverse=True)
    top3 = peaks[:3]
    if top3:
        basis_kw = sum(v for _, v in top3) / len(top3)
    else:
        basis_kw = 0.0
    chosen = CAPACITY_STEPS[-1]
    for step in CAPACITY_STEPS:
        if basis_kw <= step[0]:
            chosen = step
            break
    days = ', '.join(day for day,_ in top3) if top3 else '-'
    warning = ''
    next_step = None
    for step in CAPACITY_STEPS:
        if step[0] > basis_kw:
            next_step = step
            break
    if next_step is not None:
        warning = f'If this month basis rises above {next_step[0]:.1f} kW, estimated step becomes {next_step[1]}'
    return {
        'step_label': chosen[1],
        'step_price_text': f'~{chosen[2]} NOK/month',
        'basis_text': f'{basis_kw:.2f} kW basis from top 3 hourly averages on different days this month ({days})',
        'warning_text': warning or 'Estimate only. Local network tariffs can differ.',
    }
