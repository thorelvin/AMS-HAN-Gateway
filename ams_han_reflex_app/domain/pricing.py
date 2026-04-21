from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.request import Request, urlopen
import json
import threading

PRICE_AREAS = ['NO1', 'NO2', 'NO3', 'NO4', 'NO5']
GRID_DAY_RATE_NOK_PER_KWH = 0.4254
GRID_NIGHT_RATE_NOK_PER_KWH = 0.2642
FALLBACK_SPOT_PRICE_NOK_PER_KWH = 1.0
PRICE_REQUEST_HEADERS = {
    'User-Agent': 'AMS-HAN-Gateway/1.0 (+https://github.com/thorelvin/AMS-HAN-Gateway)',
    'Accept': 'application/json',
}
CAPACITY_STEPS = [
    (2.0, '0-2 kW', 150),
    (5.0, '2-5 kW', 270),
    (10.0, '5-10 kW', 430),
    (15.0, '10-15 kW', 610),
    (20.0, '15-20 kW', 800),
    (25.0, '20-25 kW', 980),
    (50.0, '25-50 kW', 1500),
]


@dataclass(slots=True)
class PriceDayResult:
    entries: list[dict[str, Any]]
    warning_text: str = ''


@dataclass(slots=True)
class PriceQuote:
    nok_per_kwh: float
    source_name: str
    source_note: str
    fallback_used: bool = False
    warning_text: str = ''


class PriceProvider:
    def __init__(self, fallback_price_nok_per_kwh: float = FALLBACK_SPOT_PRICE_NOK_PER_KWH) -> None:
        self._cache: dict[tuple[str, str], PriceDayResult] = {}
        self._cache_lock = threading.Lock()
        self._inflight: set[tuple[str, str]] = set()
        self.fallback_price_nok_per_kwh = float(fallback_price_nok_per_kwh)

    def _day_key(self, dt: datetime) -> str:
        return dt.strftime('%Y-%m-%d')

    def _fetch_day(self, area: str, dt: datetime) -> PriceDayResult:
        key = (area, self._day_key(dt))
        with self._cache_lock:
            if key in self._cache:
                return self._cache[key]
        url = f"https://www.hvakosterstrommen.no/api/v1/prices/{dt.year}/{dt.month:02d}-{dt.day:02d}_{area}.json"
        data: list[dict[str, Any]] = []
        warning_text = ''
        try:
            request = Request(url, headers=PRICE_REQUEST_HEADERS)
            with urlopen(request, timeout=6) as response:
                payload = json.loads(response.read().decode('utf-8'))
                if isinstance(payload, list):
                    data = payload
                else:
                    warning_text = f'Unexpected spot-price payload for {area} {self._day_key(dt)}.'
        except Exception as exc:
            warning_text = (
                f"Spot prices for {area} {self._day_key(dt)} could not be fetched from "
                f"hvakosterstrommen.no ({exc.__class__.__name__})."
            )
        if not data and not warning_text:
            warning_text = f'No spot prices were returned for {area} {self._day_key(dt)}.'
        result = PriceDayResult(entries=data, warning_text=warning_text)
        with self._cache_lock:
            self._cache[key] = result
            self._inflight.discard(key)
        return result

    def _start_background_fetch(self, area: str, dt: datetime) -> None:
        key = (area, self._day_key(dt))
        with self._cache_lock:
            if key in self._cache or key in self._inflight:
                return
            self._inflight.add(key)
        thread = threading.Thread(
            target=self._fetch_day,
            args=(area, dt),
            name=f"price-fetch-{area}-{key[1]}",
            daemon=True,
        )
        thread.start()

    def quote_for_hour(self, area: str, dt: datetime) -> PriceQuote:
        key = (area, self._day_key(dt))
        with self._cache_lock:
            day = self._cache.get(key)
        if day is None:
            self._start_background_fetch(area, dt)
            warning = (
                f"Spot prices for {area} {self._day_key(dt)} are still loading in the background. "
                f"Using explicit fallback estimate {self.fallback_price_nok_per_kwh:.3f} NOK/kWh for now."
            )
            return PriceQuote(
                nok_per_kwh=self.fallback_price_nok_per_kwh,
                source_name="Background price refresh",
                source_note=f"{area} live spot price loading",
                fallback_used=True,
                warning_text=warning,
            )
        target_hour = dt.hour
        source_note = f'{area} spot prices ex VAT from hvakosterstrommen.no'
        for row in day.entries:
            start = str(row.get('time_start') or '')
            if not start:
                continue
            try:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            except Exception:
                continue
            if start_dt.astimezone().hour != target_hour:
                continue
            try:
                return PriceQuote(
                    nok_per_kwh=float(row['NOK_per_kWh']),
                    source_name='hvakosterstrommen.no API',
                    source_note=source_note,
                )
            except (KeyError, TypeError, ValueError):
                break
        reason = day.warning_text or f'Spot price for {area} hour {dt:%Y-%m-%d %H}:00 was unavailable.'
        warning = (
            f'{reason} Using explicit fallback estimate '
            f'{self.fallback_price_nok_per_kwh:.3f} NOK/kWh for cost calculations.'
        )
        return PriceQuote(
            nok_per_kwh=self.fallback_price_nok_per_kwh,
            source_name='Fallback spot estimate',
            source_note=f'{area} live spot price unavailable',
            fallback_used=True,
            warning_text=warning,
        )

    def price_for_hour(self, area: str, dt: datetime) -> float:
        return self.quote_for_hour(area, dt).nok_per_kwh

    def get_price_data(self, area: str, now: datetime | None = None) -> dict[str, Any]:
        current = self.quote_for_hour(area, now or datetime.now().astimezone())
        return {
            'source_name': current.source_name,
            'source_note': current.source_note,
            'current_price': current.nok_per_kwh,
            'fallback_used': current.fallback_used,
            'warning_text': current.warning_text,
        }

    @staticmethod
    def current_grid_rate(hour: int, day_rate: float, night_rate: float) -> float:
        return night_rate if (hour >= 22 or hour < 6) else day_rate

    @staticmethod
    def current_grid_rate_label(hour: int) -> str:
        return 'Night (22-06)' if (hour >= 22 or hour < 6) else 'Day (06-22)'


def estimate_capacity(hourly_rows: list[dict[str, Any]]) -> dict[str, str]:
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
        basis_kw = sum(value for _, value in top3) / len(top3)
    else:
        basis_kw = 0.0
    chosen = CAPACITY_STEPS[-1]
    for step in CAPACITY_STEPS:
        if basis_kw <= step[0]:
            chosen = step
            break
    days = ', '.join(day for day, _ in top3) if top3 else '-'
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
