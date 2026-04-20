from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any


def likely_device_hint(delta_w: float, phase: str, sustained: bool = False) -> str:
    mag = abs(delta_w)
    if phase == '3-phase' and mag >= 6000:
        return 'Likely EV charger / large 3-phase load'
    if phase == '3-phase' and mag >= 2500:
        return 'Likely balanced 3-phase load'
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


def build_signature_rows(events: list[dict[str, str]], limit: int = 10) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for e in events:
        if e.get('category') != 'power':
            continue
        phase = e.get('phase', '-')
        note = e.get('note', '-')
        key = f"{phase}|{note}"
        grouped[key].append(e)
    rows = []
    for key, items in grouped.items():
        phase, note = key.split('|', 1)
        deltas = [abs(delta) for delta in (_parse_delta_w(item) for item in items) if delta is not None]
        typical_w_value = median(deltas) if deltas else 0.0
        rows.append({
            'signature': note,
            'phase': phase,
            'typical_w': _format_signature_watt(deltas),
            'typical_w_value': f'{typical_w_value:.3f}',
            'events': str(len(items)),
            'last_seen': items[0].get('time', '-'),
            'confidence': items[0].get('conf', items[0].get('confidence', '0.50')),
        })
    rows.sort(key=lambda r: (int(r['events']), float(r['typical_w_value'])), reverse=True)
    return rows[:limit]
