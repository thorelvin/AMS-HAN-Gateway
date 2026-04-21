from __future__ import annotations

from .service import GatewayService, default_db_path

_gateway_service: GatewayService | None = None


def get_gateway_service() -> GatewayService:
    global _gateway_service
    if _gateway_service is None:
        _gateway_service = GatewayService(default_db_path())
    return _gateway_service


def set_gateway_service(service: GatewayService) -> None:
    global _gateway_service
    _gateway_service = service
