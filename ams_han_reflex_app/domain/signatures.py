from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
import re
from statistics import mean, median
from typing import Any, Iterable

from .mains import is_phase_pair_label, normalize_mains_network_type


TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
SESSION_END_RE = re.compile(r'^Session started (?P<start>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \((?P<signature>.+)\)$')


def likely_device_hint(
    delta_w: float,
    phase: str,
    sustained: bool = False,
    mains_network_type: str = 'TN',
) -> str:
    network_type = normalize_mains_network_type(mains_network_type)
    mag = abs(delta_w)
    if phase == '3-phase' and mag >= 6000:
        return 'Likely EV charger / large 3-phase load'
    if phase == '3-phase' and mag >= 2500:
        return 'Likely balanced 3-phase load'
    if network_type == 'IT' and is_phase_pair_label(phase):
        if mag >= 4500:
            return 'Likely large phase-to-phase load'
        if mag >= 2500:
            return 'Likely heater / water heater / kitchen pair load'
        if mag >= 1000:
            return 'Likely phase-to-phase appliance step'
        return 'Minor phase-to-phase load change'
    if mag >= 4500:
        return 'Likely oven, boiler or large heater'
    if mag >= 2500:
        return 'Likely heater / water heater / kitchen load'
    if mag >= 1000:
        return 'Likely single-phase appliance step'
    return 'Minor load change'


def _parse_delta_w(event: dict[str, Any]) -> float | None:
    raw = event.get('dW', event.get('delta_signed'))
    if raw in (None, '', '-'):
        return None
    try:
        return float(str(raw).replace('W', '').strip())
    except ValueError:
        return None


def _format_signature_watt(deltas: list[float]) -> str:
    if not deltas:
        return '-'
    return f'{median(deltas):.0f} W'


def _parse_event_dt(raw: Any) -> datetime | None:
    if raw in (None, '', '-'):
        return None
    try:
        return datetime.strptime(str(raw), TIME_FORMAT)
    except ValueError:
        return None


def _parse_observed_date(raw: Any) -> date | None:
    if isinstance(raw, date):
        return raw
    if raw in (None, '', '-'):
        return None
    text = str(raw).strip()
    if len(text) >= 10:
        text = text[:10]
    try:
        return datetime.strptime(text, '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_session_end_note(note: Any) -> tuple[datetime, str] | None:
    match = SESSION_END_RE.match(str(note or ''))
    if not match:
        return None
    try:
        start_dt = datetime.strptime(match.group('start'), TIME_FORMAT)
    except ValueError:
        return None
    return start_dt, match.group('signature')


def _normalized_signature(event: dict[str, Any]) -> tuple[str, str]:
    phase = str(event.get('phase', '-') or '-')
    note = str(event.get('note', '-') or '-')
    event_type = str(event.get('type', event.get('event_type', '')) or '')
    if event_type == 'load_session_end':
        parsed = _parse_session_end_note(note)
        if parsed is not None:
            _start_dt, parsed_signature = parsed
            return phase, parsed_signature
    return phase, note


def _format_runtime(seconds: float | None) -> str:
    if seconds is None or seconds <= 0:
        return '-'
    minutes = max(1, int(round(seconds / 60.0)))
    if minutes < 60:
        return f'{minutes}m'
    hours, rem_minutes = divmod(minutes, 60)
    if hours < 24:
        return f'{hours}h {rem_minutes}m' if rem_minutes else f'{hours}h'
    days, rem_hours = divmod(hours, 24)
    return f'{days}d {rem_hours}h' if rem_hours else f'{days}d'


def _format_rate(count: int, observed_days: int) -> str:
    if count <= 0 or observed_days <= 0:
        return '-'
    return f'{count / observed_days:.1f}/d'


def _most_common_start_hour(start_times: list[datetime]) -> str:
    if not start_times:
        return '-'
    hour_counts: dict[int, int] = defaultdict(int)
    for dt in start_times:
        hour_counts[dt.hour] += 1
    most_common_hour = max(hour_counts.items(), key=lambda item: (item[1], -item[0]))[0]
    return f'{most_common_hour:02d}:00'


def _weekday_weekend_text(start_times: list[datetime], observed_dates: set[date]) -> str:
    if not start_times:
        return '-'
    weekday_days = sum(1 for day in observed_dates if day.weekday() < 5)
    weekend_days = sum(1 for day in observed_dates if day.weekday() >= 5)
    weekday_starts = sum(1 for dt in start_times if dt.weekday() < 5)
    weekend_starts = len(start_times) - weekday_starts
    weekday_rate = _format_rate(weekday_starts, weekday_days)
    weekend_rate = _format_rate(weekend_starts, weekend_days)
    return f'WD {weekday_rate} | WE {weekend_rate}'


def _observed_date_set(events: list[dict[str, str]], observed_dates: Iterable[Any] | None) -> set[date]:
    dates = {_parse_observed_date(value) for value in (observed_dates or [])}
    cleaned = {day for day in dates if day is not None}
    if cleaned:
        return cleaned
    fallback: set[date] = set()
    for event in events:
        dt = _parse_event_dt(event.get('time'))
        if dt is not None:
            fallback.add(dt.date())
    return fallback


def build_signature_rows(
    events: list[dict[str, str]],
    limit: int = 10,
    observed_dates: Iterable[Any] | None = None,
) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    session_starts: dict[str, list[dict[str, str]]] = defaultdict(list)
    power_steps: dict[str, list[dict[str, str]]] = defaultdict(list)
    generic_hits: dict[str, list[dict[str, str]]] = defaultdict(list)
    runtime_seconds: dict[str, list[float]] = defaultdict(list)
    for e in events:
        if e.get('category') != 'power':
            continue
        phase, note = _normalized_signature(e)
        key = f"{phase}|{note}"
        grouped[key].append(e)
        event_type = str(e.get('type', e.get('event_type', '')) or '')
        if event_type == 'load_session_start':
            session_starts[key].append(e)
        elif event_type == 'power_step':
            power_steps[key].append(e)
        elif event_type == 'load_session_end':
            end_dt = _parse_event_dt(e.get('time'))
            parsed = _parse_session_end_note(e.get('note'))
            if end_dt is not None and parsed is not None:
                start_dt, _signature = parsed
                if end_dt >= start_dt:
                    runtime_seconds[key].append((end_dt - start_dt).total_seconds())
        else:
            generic_hits[key].append(e)

    coverage_dates = _observed_date_set(events, observed_dates)
    rows = []
    for key, items in grouped.items():
        phase, note = key.split('|', 1)
        primary_items = session_starts[key] or power_steps[key] or generic_hits[key]
        if not primary_items:
            continue
        deltas = [abs(delta) for delta in (_parse_delta_w(item) for item in primary_items) if delta is not None]
        typical_w_value = median(deltas) if deltas else 0.0
        start_times = [dt for dt in (_parse_event_dt(item.get('time')) for item in primary_items) if dt is not None]
        average_runtime_seconds = mean(runtime_seconds[key]) if runtime_seconds[key] else None
        last_seen_item = max(items, key=lambda item: _parse_event_dt(item.get('time')) or datetime.min)
        effective_coverage_dates = coverage_dates or {dt.date() for dt in start_times}
        rows.append({
            'signature': note,
            'phase': phase,
            'typical_w': _format_signature_watt(deltas),
            'typical_w_value': f'{typical_w_value:.3f}',
            'events': str(len(primary_items)),
            'avg_runtime': _format_runtime(average_runtime_seconds),
            'avg_runtime_value': f'{average_runtime_seconds or 0.0:.3f}',
            'starts_per_day': _format_rate(len(primary_items), len(effective_coverage_dates)),
            'starts_per_day_value': f'{(len(primary_items) / len(effective_coverage_dates)) if effective_coverage_dates else 0.0:.6f}',
            'common_start_hour': _most_common_start_hour(start_times),
            'weekday_weekend': _weekday_weekend_text(start_times, effective_coverage_dates),
            'last_seen': last_seen_item.get('time', '-'),
            'confidence': last_seen_item.get('conf', last_seen_item.get('confidence', '0.50')),
        })
    rows.sort(
        key=lambda r: (
            int(r['events']),
            float(r['starts_per_day_value']),
            float(r['typical_w_value']),
        ),
        reverse=True,
    )
    return rows[:limit]
