"""Shared helpers used by the smaller state slices to reach the app-wide gateway service."""

from __future__ import annotations

from ..app_context import get_app_context


def _service():
    return get_app_context().gateway_service
