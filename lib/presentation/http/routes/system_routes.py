from fastapi import APIRouter, Request

from presentation.http.schemas import HealthResponse


class SystemRoutes:
    def __init__(self) -> None:
        self.router = APIRouter()
        self.router.add_api_route("/health", self.health, methods=["GET"], response_model=HealthResponse)
        self.router.add_api_route("/ready", self.ready, methods=["GET"], response_model=HealthResponse)

    @staticmethod
    def health(request: Request) -> HealthResponse:
        payload = request.app.state.tenant_handler.health()
        return HealthResponse(status=payload["status"])

    @staticmethod
    def ready(request: Request) -> HealthResponse:
        payload = request.app.state.tenant_handler.ready()
        return HealthResponse(status=payload["status"])
