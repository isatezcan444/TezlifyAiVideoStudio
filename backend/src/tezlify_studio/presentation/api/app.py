from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from tezlify_studio.infrastructure.configuration.settings import settings
from tezlify_studio.infrastructure.persistence.database import init_db
from tezlify_studio.presentation.api.routes import health, media, publish
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

def create_app() -> FastAPI:
    # Initialize SQLite database schema
    init_db()

    app = FastAPI(
        title=settings.app_name,
        description="Local-First Professional Video Production & Publishing Core",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url=None,
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

    @app.exception_handler(DomainException)
    async def general_domain_handler(request: Request, exc: DomainException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "error_code": "DOMAIN_ERROR"},
        )

    # Mount API routers under /api/v1
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(media.router, prefix="/api/v1")
    app.include_router(publish.router, prefix="/api/v1")

    return app

app = create_app()

