from __future__ import annotations

from collections import defaultdict
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
        rows.append({
            'signature': note,
            'phase': phase,
            'events': str(len(items)),
            'last_seen': items[0].get('time', '-'),
            'confidence': items[0].get('confidence', '0.50'),
        })
    rows.sort(key=lambda r: int(r['events']), reverse=True)
    return rows[:limit]
