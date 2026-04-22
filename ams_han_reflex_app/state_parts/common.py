from __future__ import annotations

from ..app_context import get_app_context


def _service():
    return get_app_context().gateway_service
