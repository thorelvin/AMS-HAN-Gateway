"""Helpers for switching between TN and IT mains interpretations throughout the analysis stack."""

from __future__ import annotations

import re

DEFAULT_MAINS_NETWORK_TYPE = 'TN'
MAINS_NETWORK_TYPES = ('TN', 'IT')
TN_SWITCH_LABELS = ('L1', 'L2', 'L3')
IT_SWITCH_LABELS = ('L1-L2', 'L1-L3', 'L2-L3')
PHASE_ORDER = {'L1': 0, 'L2': 1, 'L3': 2}

PHASE_DELTA_RE = re.compile(
    r'L1\s+(?P<l1>[+-]?\d+(?:\.\d+)?)\s*\|\s*'
    r'L2\s+(?P<l2>[+-]?\d+(?:\.\d+)?)\s*\|\s*'
    r'L3\s+(?P<l3>[+-]?\d+(?:\.\d+)?)'
)


def normalize_mains_network_type(value: str | None) -> str:
    candidate = str(value or DEFAULT_MAINS_NETWORK_TYPE).strip().upper()
    return candidate if candidate in MAINS_NETWORK_TYPES else DEFAULT_MAINS_NETWORK_TYPE


def switch_slot_labels(mains_network_type: str) -> tuple[str, str, str]:
    network_type = normalize_mains_network_type(mains_network_type)
    return IT_SWITCH_LABELS if network_type == 'IT' else TN_SWITCH_LABELS


def switch_slot_text(mains_network_type: str) -> str:
    return '/'.join(switch_slot_labels(mains_network_type))


def is_phase_pair_label(label: str) -> bool:
    return str(label or '') in IT_SWITCH_LABELS


def _pair_label(first: str, second: str) -> str:
    ordered = sorted((first, second), key=lambda phase: PHASE_ORDER.get(phase, 99))
    return f'{ordered[0]}-{ordered[1]}'


def classify_phase_delta(d1: float, d2: float, d3: float, mains_network_type: str = DEFAULT_MAINS_NETWORK_TYPE) -> str:
    network_type = normalize_mains_network_type(mains_network_type)
    mags = {'L1': abs(d1), 'L2': abs(d2), 'L3': abs(d3)}
    ordered = sorted(mags.items(), key=lambda item: item[1], reverse=True)
    top_mag = ordered[0][1]
    second_mag = ordered[1][1]
    third_mag = ordered[2][1]
    if top_mag < 0.2:
        return '-'
    if third_mag > 0.4 and third_mag / max(top_mag, 0.001) > 0.55:
        return '3-phase'
    if network_type == 'IT':
        if second_mag > 0.35 and second_mag / max(top_mag, 0.001) > 0.55 and third_mag / max(top_mag, 0.001) < 0.38:
            return _pair_label(ordered[0][0], ordered[1][0])
    return ordered[0][0]


def parse_phase_delta_text(text: str | None) -> tuple[float, float, float] | None:
    match = PHASE_DELTA_RE.search(str(text or ''))
    if not match:
        return None
    try:
        return (
            float(match.group('l1')),
            float(match.group('l2')),
            float(match.group('l3')),
        )
    except ValueError:
        return None
