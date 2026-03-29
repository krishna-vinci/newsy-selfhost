from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from fastapi_backend.models import (
    ErrorResponse,
    FeedsearchSearchResponse,
    HealthResponse,
    ResolvedSourceResponse,
    YouTubeFeedType,
)
from fastapi_backend.services import (
    APIError,
    FEEDSEARCH_ATTRIBUTION,
    ServiceContainer,
    Settings,
    build_service_container,
    detect_source,
)


FRONTEND_DIR = Path(__file__).parent / "frontend"
FRONTEND_ASSETS_DIR = FRONTEND_DIR / "assets"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    timeout = httpx.Timeout(settings.request_timeout_seconds)
    client = httpx.AsyncClient(
        timeout=timeout, headers={"User-Agent": settings.user_agent}
    )
    app.state.services = build_service_container(settings=settings, client=client)
    try:
        yield
    finally:
        await client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="RSS Gen",
        version="1.0.0",
        description=(
            "Standalone FastAPI app for YouTube feed generation, Reddit feed "
            "resolution, website feed discovery via Feedsearch, and a lightweight frontend."
        ),
        lifespan=lifespan,
    )

    settings = Settings.from_env()
    allow_origins = settings.cors_origins or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_ASSETS_DIR),
        name="frontend-assets",
    )

    register_exception_handlers(app)
    register_routes(app)
    return app


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def handle_api_error(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error_code=exc.error_code, detail=exc.detail
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first_error = exc.errors()[0] if exc.errors() else {}
        detail = first_error.get("msg", "Invalid request.")
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error_code="validation_error",
                detail=detail,
            ).model_dump(),
        )


def get_services(request: Request) -> ServiceContainer:
    return request.app.state.services


def register_routes(app: FastAPI) -> None:
    async def render_youtube_feed_response(
        request: Request,
        services: ServiceContainer,
        channel_id: str,
        feed_type: YouTubeFeedType,
    ) -> Response:
        xml = await run_in_threadpool(
            services.youtube.build_feed_xml,
            channel_id,
            feed_type,
            str(request.url),
        )
        return Response(content=xml, media_type="application/rss+xml; charset=utf-8")

    @app.get("/", tags=["meta"])
    async def root() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/api/v1", tags=["meta"])
    async def api_root() -> dict[str, str]:
        return {
            "message": "RSS Gen API is running.",
            "docs": "/docs",
        }

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["meta"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get(
        "/api/v1/resolve",
        response_model=ResolvedSourceResponse,
        responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        tags=["resolve"],
    )
    async def resolve_source(
        request: Request,
        query: str = Query(..., min_length=1),
        reddit_limit: int = Query(10, ge=1, le=100),
        include_preview: bool = True,
        preview_limit: int = Query(6, ge=1, le=20),
        feedsearch_info: bool = True,
        feedsearch_favicon: bool = False,
        feedsearch_skip_crawl: bool = False,
        services: ServiceContainer = Depends(get_services),
    ) -> ResolvedSourceResponse:
        base_feed_url = f"{str(request.base_url).rstrip('/')}/api/v1/youtube/feed"
        source = detect_source(query)
        if source.value == "youtube":
            preview_items = []
            if include_preview:
                preview_url = await run_in_threadpool(
                    services.youtube.native_preview_url, query
                )
                preview_items = await services.preview.fetch(
                    preview_url, max_items=preview_limit
                )
            return await run_in_threadpool(
                services.youtube.build_resolved_response,
                query,
                base_feed_url,
                preview_items,
            )

        if source.value == "reddit":
            preview_items = []
            if include_preview:
                hot_feed_url = await run_in_threadpool(
                    services.reddit.hot_feed_url,
                    query,
                    reddit_limit,
                )
                preview_items = await services.preview.fetch(
                    hot_feed_url, max_items=preview_limit
                )
            return await run_in_threadpool(
                services.reddit.build_resolved_response,
                query,
                reddit_limit,
                preview_items,
            )

        preview_items = []
        search_results = await services.feedsearch.search(
            query,
            info=feedsearch_info,
            favicon=feedsearch_favicon,
            skip_crawl=feedsearch_skip_crawl,
            opml=False,
        )
        first_feed_url = search_results[0].url if search_results else None
        if include_preview and first_feed_url:
            preview_items = await services.preview.fetch(
                first_feed_url, max_items=preview_limit
            )
        return await services.feedsearch.build_resolved_response(
            query,
            preview_items,
            info=feedsearch_info,
            favicon=feedsearch_favicon,
            skip_crawl=feedsearch_skip_crawl,
            results=search_results,
        )

    @app.get(
        "/api/v1/youtube/resolve",
        response_model=ResolvedSourceResponse,
        responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        tags=["youtube"],
    )
    async def resolve_youtube(
        request: Request,
        query: str = Query(..., min_length=1),
        include_preview: bool = True,
        preview_limit: int = Query(6, ge=1, le=20),
        services: ServiceContainer = Depends(get_services),
    ) -> ResolvedSourceResponse:
        base_feed_url = f"{str(request.base_url).rstrip('/')}/api/v1/youtube/feed"
        preview_items = []
        if include_preview:
            preview_url = await run_in_threadpool(
                services.youtube.native_preview_url, query
            )
            preview_items = await services.preview.fetch(
                preview_url, max_items=preview_limit
            )
        return await run_in_threadpool(
            services.youtube.build_resolved_response,
            query,
            base_feed_url,
            preview_items,
        )

    @app.get(
        "/api/v1/youtube/feed/{feed_type}/{channel_id}.xml",
        tags=["youtube"],
        responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    async def youtube_feed(
        feed_type: YouTubeFeedType,
        channel_id: str,
        request: Request,
        services: ServiceContainer = Depends(get_services),
    ) -> Response:
        return await render_youtube_feed_response(
            request=request,
            services=services,
            channel_id=channel_id,
            feed_type=feed_type,
        )

    @app.get(
        "/feeds/videos.xml",
        tags=["youtube"],
        responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    async def legacy_youtube_feed_query(
        request: Request,
        channel_id: str = Query(""),
        legacy_type: str | None = Query(None, alias="type"),
        services: ServiceContainer = Depends(get_services),
    ) -> Response:
        normalized_channel_id = channel_id.strip()
        if not normalized_channel_id:
            raise APIError(
                detail="Missing channel_id",
                error_code="missing_channel_id",
                status_code=400,
            )

        try:
            feed_type = YouTubeFeedType((legacy_type or "all").strip().lower())
        except ValueError as exc:
            raise APIError(
                detail=f"Unknown feed type: {(legacy_type or '').strip().lower() or 'all'}",
                error_code="invalid_feed_type",
                status_code=400,
            ) from exc

        return await render_youtube_feed_response(
            request=request,
            services=services,
            channel_id=normalized_channel_id,
            feed_type=feed_type,
        )

    @app.get(
        "/feeds/{channel_id}",
        tags=["youtube"],
        responses={404: {"model": ErrorResponse}},
    )
    async def legacy_youtube_feed_all(
        channel_id: str,
        request: Request,
        services: ServiceContainer = Depends(get_services),
    ) -> Response:
        return await render_youtube_feed_response(
            request=request,
            services=services,
            channel_id=channel_id,
            feed_type=YouTubeFeedType.all,
        )

    @app.get(
        "/feed/{legacy_feed_type}/{channel_id}",
        tags=["youtube"],
        responses={404: {"model": ErrorResponse}},
    )
    async def legacy_youtube_feed_typed(
        legacy_feed_type: str,
        channel_id: str,
        request: Request,
        services: ServiceContainer = Depends(get_services),
    ) -> Response:
        try:
            feed_type = YouTubeFeedType(legacy_feed_type.strip().lower())
        except ValueError as exc:
            raise APIError(
                detail="Unknown feed type",
                error_code="invalid_feed_type",
                status_code=404,
            ) from exc

        return await render_youtube_feed_response(
            request=request,
            services=services,
            channel_id=channel_id,
            feed_type=feed_type,
        )

    @app.get(
        "/api/v1/reddit/resolve",
        response_model=ResolvedSourceResponse,
        responses={400: {"model": ErrorResponse}},
        tags=["reddit"],
    )
    async def resolve_reddit(
        query: str = Query(..., min_length=1),
        limit: int = Query(10, ge=1, le=100),
        include_preview: bool = True,
        preview_limit: int = Query(6, ge=1, le=20),
        services: ServiceContainer = Depends(get_services),
    ) -> ResolvedSourceResponse:
        preview_items = []
        if include_preview:
            hot_feed_url = await run_in_threadpool(
                services.reddit.hot_feed_url, query, limit
            )
            preview_items = await services.preview.fetch(
                hot_feed_url, max_items=preview_limit
            )
        return await run_in_threadpool(
            services.reddit.build_resolved_response,
            query,
            limit,
            preview_items,
        )

    @app.get(
        "/api/v1/feedsearch/search",
        response_model=FeedsearchSearchResponse,
        responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
        tags=["feedsearch"],
    )
    async def feedsearch_search(
        url: str = Query(..., min_length=1),
        info: bool = True,
        favicon: bool = False,
        skip_crawl: bool = False,
        opml: bool = False,
        services: ServiceContainer = Depends(get_services),
    ) -> FeedsearchSearchResponse | Response:
        results = await services.feedsearch.search(
            url,
            info=info,
            favicon=favicon,
            skip_crawl=skip_crawl,
            opml=opml,
        )
        if opml:
            return Response(
                content=str(results), media_type="application/xml; charset=utf-8"
            )
        return FeedsearchSearchResponse(
            query=url,
            results=results,
            attribution=FEEDSEARCH_ATTRIBUTION,
        )


app = create_app()
