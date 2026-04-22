from __future__ import annotations

from dataclasses import dataclass

from .service import GatewayService, default_db_path


@dataclass(slots=True)
class AppContext:
    gateway_service: GatewayService


_app_context: AppContext | None = None


def configure_default_app_context() -> AppContext:
    global _app_context
    if _app_context is None:
        _app_context = AppContext(gateway_service=GatewayService(default_db_path()))
    return _app_context


def set_app_context(context: AppContext) -> None:
    global _app_context
    _app_context = context


def set_gateway_service(service: GatewayService) -> None:
    set_app_context(AppContext(gateway_service=service))


def get_app_context() -> AppContext:
    if _app_context is None:
        raise RuntimeError(
            "App context has not been configured. Call configure_default_app_context() "
            "from the application entrypoint or inject a test context first."
        )
    return _app_context


def get_gateway_service() -> GatewayService:
    return get_app_context().gateway_service
