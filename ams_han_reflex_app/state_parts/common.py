from __future__ import annotations

from ..app_context import get_gateway_service


def _service():
    return get_gateway_service()
