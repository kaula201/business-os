import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from app.core.config import settings
from app.api.v1.router import api_router
from app.services.nbg_rates import nbg_scheduler_loop
from app.services.accounting_periods import AccountingPeriodClosedError

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler_task = None
    if settings.NBG_AUTO_SYNC_ENABLED:
        scheduler_task = asyncio.create_task(nbg_scheduler_loop(), name="nbg-daily-sync")
    try:
        yield
    finally:
        if scheduler_task:
            scheduler_task.cancel()
            with suppress(asyncio.CancelledError):
                await scheduler_task

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="ქართული Business OS — საოპერაციო პლატფორმა ქართული ბიზნესებისთვის",
    lifespan=lifespan,
)


@app.exception_handler(AccountingPeriodClosedError)
async def accounting_period_closed_handler(
    _request: Request, exc: AccountingPeriodClosedError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.add_middleware(SlowAPIMiddleware)

# API routes
app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
