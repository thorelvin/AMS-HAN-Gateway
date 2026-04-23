"""Dashboard state composition that combines the smaller Reflex state slices into one UI-facing state object."""

from __future__ import annotations

import reflex as rx

from .backend.models import CapacityStepVisual, CostRow
from .domain.analysis import DiagnosticsEventRow, HeatmapRow, HistoryTableRow, TopHourRow
from .domain.signatures import SignatureRowData
from .state_parts import (
    DashboardAnalysisState,
    DashboardCostState,
    DashboardConnectionState,
    DashboardDiagnosticsState,
    DashboardDerivedState,
    DashboardHistoryState,
    DashboardReplayState,
    DashboardTabState,
)


def _state_members(*parts: type) -> dict[str, object]:
    # Reflex wants one concrete State class. We keep the code maintainable by
    # defining smaller slices and merging their fields/methods here.
    annotations: dict[str, object] = {}
    namespace: dict[str, object] = {}
    for part in parts:
        annotations.update(getattr(part, "__annotations__", {}))
        for name, value in part.__dict__.items():
            if name.startswith("__") or name == "__annotations__":
                continue
            namespace[name] = value
    namespace["__annotations__"] = annotations
    return namespace


class DashboardState(rx.State):
    """Single Reflex state object assembled from the focused dashboard state slices."""

    locals().update(
        _state_members(
            DashboardConnectionState,
            DashboardReplayState,
            DashboardHistoryState,
            DashboardDiagnosticsState,
            DashboardCostState,
            DashboardAnalysisState,
            DashboardTabState,
            DashboardDerivedState,
        )
    )
