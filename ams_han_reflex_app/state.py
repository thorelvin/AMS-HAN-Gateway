from __future__ import annotations

import reflex as rx

from .backend.models import CostRow
from .domain.analysis import DiagnosticsEventRow, HeatmapRow, HistoryTableRow, TopHourRow
from .domain.signatures import SignatureRowData
from .state_parts import (
    DashboardAnalysisState,
    DashboardConnectionState,
    DashboardDerivedState,
    DashboardReplayState,
)


def _state_members(*parts: type) -> dict[str, object]:
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
    locals().update(
        _state_members(
            DashboardConnectionState,
            DashboardAnalysisState,
            DashboardReplayState,
            DashboardDerivedState,
        )
    )
