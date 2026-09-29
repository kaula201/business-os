import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.config import settings
from app.core.limiter import limiter
from app.api.v1.router import api_router
from app.services.nbg_rates import nbg_scheduler_loop
from app.services.financial_automation import financial_scheduler_loop
from app.services.saas import saas_billing_scheduler_loop
from app.services.accounting_periods import AccountingPeriodClosedError

_DOC_PATHS = {"/docs", "/redoc", "/openapi.json"}


def _is_docs_path(path: str) -> bool:
    return path in _DOC_PATHS or path.startswith("/docs/") or path.startswith("/redoc/")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Idempotent module catalog. Production does not run the demo seed, and
    # the sidebar reads app_modules. Missing rows leave it empty. Tests use
    # their own fixtures and must not open DATABASE_URL during import/startup.
    if settings.APP_ENV not in {"test", "sandbox"}:
        from seed_modules import seed_modules

        await seed_modules()
    scheduler_tasks = []
    if settings.NBG_AUTO_SYNC_ENABLED:
        scheduler_tasks.append(asyncio.create_task(nbg_scheduler_loop(), name="nbg-daily-sync"))
    if settings.FINANCIAL_AUTO_ENABLED:
        scheduler_tasks.append(asyncio.create_task(financial_scheduler_loop(), name="financial-monthly-close"))
    if settings.SAAS_BILLING_AUTO_ENABLED:
        scheduler_tasks.append(asyncio.create_task(saas_billing_scheduler_loop(), name="saas-billing-daily"))
    try:
        yield
    finally:
        for task in scheduler_tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

_docs_disabled = settings.is_production()
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="ქართული Business OS — საოპერაციო პლატფორმა ქართული ბიზნესებისთვის",
    lifespan=lifespan,
    docs_url=None if _docs_disabled else "/docs",
    redoc_url=None if _docs_disabled else "/redoc",
    openapi_url=None if _docs_disabled else "/openapi.json",
)


@app.exception_handler(AccountingPeriodClosedError)
async def accounting_period_closed_handler(
    _request: Request, exc: AccountingPeriodClosedError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — explicit allowlist only. Credentials are never combined with "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def hide_api_docs_in_production(request: Request, call_next):
    """Production must not expose Swagger, ReDoc, or the OpenAPI schema."""
    if settings.is_production() and _is_docs_path(request.url.path):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return await call_next(request)

# Rate limiting
app.add_middleware(SlowAPIMiddleware)

# API routes
app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/")
async def root():
    payload = {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
    if not settings.is_production():
        payload["docs"] = "/docs"
    return payload
