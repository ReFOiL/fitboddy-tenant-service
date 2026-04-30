from contextlib import asynccontextmanager

from fastapi import FastAPI

from application.config import Settings
from application.runtime import TenantApplicationRuntime
from presentation.http.error_translator import ErrorTranslator
from presentation.http.handlers.tenant_handler import TenantHttpHandler
from presentation.http.request_factory import TenantRequestFactory
from presentation.http.response_factory import TenantResponseFactory
from presentation.http.routes.system_routes import SystemRoutes
from presentation.http.routes.tenant_routes import TenantRoutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    runtime = TenantApplicationRuntime(settings=settings)
    app.state.tenant_handler = TenantHttpHandler(
        runtime=runtime,
        request_factory=TenantRequestFactory(),
        response_factory=TenantResponseFactory(),
        error_translator=ErrorTranslator(),
    )
    try:
        yield
    finally:
        runtime.shutdown()


app = FastAPI(title="tenant-service", version="0.1.0", lifespan=lifespan)
app.include_router(SystemRoutes().router)
app.include_router(TenantRoutes().router)
