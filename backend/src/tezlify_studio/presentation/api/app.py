import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from tezlify_studio.infrastructure.configuration.settings import settings
from tezlify_studio.infrastructure.persistence.database import init_db
from tezlify_studio.presentation.api.routes import (
    channels,
    comments,
    dashboard,
    health,
    media,
    platforms,
    publish,
    scheduler,
)
from tezlify_studio.domain.exceptions.media_exceptions import (
    EntityNotFoundException,
    DuplicateMediaException,
    InvalidMediaFileException,
    MediaStorageException,
    DomainException,
)
from tezlify_studio.domain.exceptions.publish_exceptions import (
    SocialAccountNotFoundException,
    DuplicatePublishException,
    QuotaExceededException,
    AuthenticationRequiredException,
    TokenStorageException,
)
from tezlify_studio.domain.exceptions.schedule_exceptions import (
    ScheduledPublishNotFoundException,
    DuplicateScheduleException,
    InvalidScheduleTimeException,
    InvalidScheduleStateTransitionException,
    ScheduleAlreadyClaimedException,
)
from tezlify_studio.domain.exceptions.creator_exceptions import (
    AnalyticsUnavailableException,
    CreatorApiException,
    CreatorStudioException,
    InsufficientScopeException,
    PlatformNotSupportedException,
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background scheduler worker if enabled and not running inside pytest
    is_test = os.environ.get("TEZLIFY_TEST_ENV") == "1" or "pytest" in sys.modules
    if settings.scheduler_enabled and not is_test:
        from tezlify_studio.presentation.dependencies.container import publish_scheduler_service
        publish_scheduler_service.start()
    yield
    # Graceful shutdown of scheduler worker
    if settings.scheduler_enabled and not is_test:
        from tezlify_studio.presentation.dependencies.container import publish_scheduler_service
        publish_scheduler_service.stop()

def create_app() -> FastAPI:
    # Initialize SQLite database schema
    init_db()

    # Reconcile interrupted in-flight publishing jobs on startup
    from tezlify_studio.infrastructure.persistence.repositories.publish_record_repository_impl import (
        PublishRecordRepositoryImpl,
    )
    from tezlify_studio.infrastructure.persistence.repositories.scheduled_publish_repository_impl import (
        ScheduledPublishRepositoryImpl,
    )
    from tezlify_studio.infrastructure.persistence.database import SessionLocal
    from tezlify_studio.application.use_cases.reconcile_publish_records_use_case import (
        ReconcilePublishRecordsUseCase,
    )
    from tezlify_studio.application.use_cases.reconcile_scheduled_publishes_use_case import (
        ReconcileScheduledPublishesUseCase,
    )

    startup_db = SessionLocal()
    try:
        pub_repo = PublishRecordRepositoryImpl(startup_db)
        ReconcilePublishRecordsUseCase(pub_repo).execute()

        sched_repo = ScheduledPublishRepositoryImpl(startup_db)
        ReconcileScheduledPublishesUseCase(
            schedule_repo=sched_repo,
            publish_repo=pub_repo,
            grace_period_minutes=settings.scheduler_missed_grace_period_minutes,
        ).execute()
    finally:
        startup_db.close()

    app = FastAPI(
        title=settings.app_name,
        description="Local-first YouTube channel management, publishing and scheduling studio",
        version="2.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception Handlers
    @app.exception_handler(EntityNotFoundException)
    async def entity_not_found_handler(request: Request, exc: EntityNotFoundException):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc), "error_code": "ENTITY_NOT_FOUND"},
        )

    @app.exception_handler(DuplicateMediaException)
    async def duplicate_media_handler(request: Request, exc: DuplicateMediaException):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": str(exc),
                "error_code": "DUPLICATE_MEDIA",
                "existing_id": exc.existing_id,
            },
        )

    @app.exception_handler(InvalidMediaFileException)
    async def invalid_media_handler(request: Request, exc: InvalidMediaFileException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "error_code": "INVALID_MEDIA_FILE"},
        )

    @app.exception_handler(MediaStorageException)
    async def media_storage_handler(request: Request, exc: MediaStorageException):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc), "error_code": "STORAGE_ERROR"},
        )

    @app.exception_handler(SocialAccountNotFoundException)
    async def social_account_not_found_handler(request: Request, exc: SocialAccountNotFoundException):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc), "error_code": "SOCIAL_ACCOUNT_NOT_FOUND"},
        )

    @app.exception_handler(DuplicatePublishException)
    async def duplicate_publish_handler(request: Request, exc: DuplicatePublishException):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": str(exc),
                "error_code": "DUPLICATE_PUBLISH",
                "existing_publish_id": exc.existing_publish_id,
            },
        )

    @app.exception_handler(QuotaExceededException)
    async def quota_exceeded_handler(request: Request, exc: QuotaExceededException):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": str(exc), "error_code": "QUOTA_EXCEEDED"},
        )

    @app.exception_handler(AuthenticationRequiredException)
    async def auth_required_handler(request: Request, exc: AuthenticationRequiredException):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc), "error_code": "AUTHENTICATION_REQUIRED"},
        )

    @app.exception_handler(TokenStorageException)
    async def token_storage_handler(request: Request, exc: TokenStorageException):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc), "error_code": "TOKEN_STORAGE_ERROR"},
        )

    @app.exception_handler(ScheduledPublishNotFoundException)
    async def schedule_not_found_handler(request: Request, exc: ScheduledPublishNotFoundException):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc), "error_code": "SCHEDULE_NOT_FOUND"},
        )

    @app.exception_handler(DuplicateScheduleException)
    async def duplicate_schedule_handler(request: Request, exc: DuplicateScheduleException):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": str(exc),
                "error_code": "DUPLICATE_SCHEDULE",
                "existing_schedule_id": exc.existing_schedule_id,
            },
        )

    @app.exception_handler(InvalidScheduleTimeException)
    async def invalid_schedule_time_handler(request: Request, exc: InvalidScheduleTimeException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "error_code": "INVALID_SCHEDULE_TIME"},
        )

    @app.exception_handler(InvalidScheduleStateTransitionException)
    async def invalid_schedule_transition_handler(request: Request, exc: InvalidScheduleStateTransitionException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "error_code": "INVALID_STATE_TRANSITION"},
        )

    @app.exception_handler(ScheduleAlreadyClaimedException)
    async def schedule_claimed_handler(request: Request, exc: ScheduleAlreadyClaimedException):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc), "error_code": "SCHEDULE_ALREADY_CLAIMED"},
        )

    @app.exception_handler(PlatformNotSupportedException)
    async def platform_not_supported_handler(request: Request, exc: PlatformNotSupportedException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "error_code": exc.error_code, "platform_id": exc.platform_id},
        )

    @app.exception_handler(InsufficientScopeException)
    async def insufficient_scope_handler(request: Request, exc: InsufficientScopeException):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": str(exc),
                "error_code": exc.error_code,
                "required_scope": exc.required_scope,
                "action": exc.action,
            },
        )

    @app.exception_handler(AnalyticsUnavailableException)
    async def analytics_unavailable_handler(request: Request, exc: AnalyticsUnavailableException):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": str(exc), "error_code": exc.error_code, "reason": exc.reason},
        )

    @app.exception_handler(CreatorApiException)
    async def creator_api_handler(request: Request, exc: CreatorApiException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": str(exc), "error_code": exc.error_code},
        )

    @app.exception_handler(CreatorStudioException)
    async def creator_studio_handler(request: Request, exc: CreatorStudioException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "error_code": exc.error_code},
        )

    @app.exception_handler(DomainException)
    async def general_domain_handler(request: Request, exc: DomainException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "error_code": "DOMAIN_ERROR"},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "error_code": "VALIDATION_ERROR"},
        )

    # Mount API routers under /api/v1
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(media.router, prefix="/api/v1")
    app.include_router(publish.router, prefix="/api/v1")
    app.include_router(scheduler.router, prefix="/api/v1")
    app.include_router(platforms.router, prefix="/api/v1")
    app.include_router(channels.router, prefix="/api/v1")
    app.include_router(comments.router, prefix="/api/v1")
    app.include_router(dashboard.router, prefix="/api/v1")

    return app

app = create_app()
