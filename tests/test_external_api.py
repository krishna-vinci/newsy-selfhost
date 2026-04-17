import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


worker_stub = types.ModuleType("backend.worker")


async def _stub_extract_article_content_with_readability(url: str) -> str | None:
    return None


worker_stub.extract_article_content_with_readability = (
    _stub_extract_article_content_with_readability
)
sys.modules.setdefault("backend.worker", worker_stub)

from backend import external_api  # noqa: E402


def make_auth_mock(user=None, auth_method="session_cookie"):
    async def _mock_auth(request, *args, **kwargs):
        if user is None:
            return None
        request.state.auth_method = auth_method
        return user

    return _mock_auth


def build_test_app(auth_callable):
    app = FastAPI()

    @app.middleware("http")
    async def auth_guard(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api"):
            user = await auth_callable(request)
            if not user:
                return JSONResponse({"detail": "Authentication required"}, status_code=401)
            request.state.user = user
            if (
                getattr(request.state, "auth_method", None) == "api_token"
                and not path.startswith("/api/external")
            ):
                return JSONResponse(
                    {
                        "detail": "API tokens can only access dedicated external API endpoints"
                    },
                    status_code=403,
                )

        return await call_next(request)

    @app.get("/api/settings")
    async def settings():
        return {"ok": True}

    app.include_router(external_api.router)
    return app


class ExternalApiTests(unittest.TestCase):
    def setUp(self):
        self.user = {"id": 7, "role": "user", "username": "alice"}

    def test_api_tokens_are_blocked_from_non_external_routes(self):
        client = TestClient(build_test_app(make_auth_mock(self.user, auth_method="api_token")))

        response = client.get("/api/settings")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"],
            "API tokens can only access dedicated external API endpoints",
        )

    def test_external_articles_include_has_full_content_flag(self):
        conn = AsyncMock()
        conn.fetch.return_value = [
            {
                "id": 1,
                "title": "Full",
                "link": "https://example.com/full",
                "description": "desc",
                "thumbnail": None,
                "published": "Wed",
                "published_datetime": None,
                "category": "Markets",
                "source": "Reuters",
                "starred": False,
                "is_read": False,
                "feed_id": 10,
                "feed_name": "Feed A",
                "feed_url": "https://example.com/rss",
                "content": "<div><p>Long article body</p></div>",
            },
            {
                "id": 2,
                "title": "Partial",
                "link": "https://example.com/partial",
                "description": "desc",
                "thumbnail": None,
                "published": "Wed",
                "published_datetime": None,
                "category": "Markets",
                "source": "Reuters",
                "starred": False,
                "is_read": False,
                "feed_id": 10,
                "feed_name": "Feed A",
                "feed_url": "https://example.com/rss",
                "content": "<p>No content could be extracted.</p>",
            },
        ]
        conn.fetchval.return_value = 2
        client = TestClient(build_test_app(make_auth_mock(self.user, auth_method="api_token")))

        with patch(
            "backend.external_api._require_external_api_enabled",
            new=AsyncMock(return_value=self.user),
        ), patch(
            "backend.external_api.database.get_db_connection",
            new=AsyncMock(return_value=conn),
        ), patch(
            "backend.external_api.database.release_db_connection",
            new=AsyncMock(),
        ):
            response = client.get(
                "/api/external/articles?include_content=true&limit=2"
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["items"][0]["has_full_content"])
        self.assertFalse(payload["items"][1]["has_full_content"])

    def test_on_demand_extraction_persists_and_returns_content(self):
        conn = AsyncMock()
        initial_row = {
            "id": 9,
            "title": "Needs extraction",
            "link": "https://example.com/story",
            "description": "desc",
            "thumbnail": None,
            "published": "Wed",
            "published_datetime": None,
            "category": "Markets",
            "source": "Reuters",
            "starred": False,
            "is_read": False,
            "feed_id": 10,
            "feed_name": "Feed A",
            "feed_url": "https://example.com/rss",
            "content": None,
        }
        extracted_row = dict(initial_row)
        extracted_row["content"] = "<div><p>Extracted body</p></div>"
        client = TestClient(build_test_app(make_auth_mock(self.user, auth_method="api_token")))

        with patch(
            "backend.external_api._require_external_api_enabled",
            new=AsyncMock(return_value=self.user),
        ), patch(
            "backend.external_api.database.get_db_connection",
            new=AsyncMock(return_value=conn),
        ), patch(
            "backend.external_api.database.release_db_connection",
            new=AsyncMock(),
        ), patch(
            "backend.external_api._get_article_row",
            new=AsyncMock(side_effect=[initial_row, extracted_row]),
        ), patch(
            "backend.external_api.extract_article_content_with_readability",
            new=AsyncMock(return_value="<div><p>Extracted body</p></div>"),
        ), patch(
            "backend.external_api.convert_links_to_embeds",
            side_effect=lambda value: value,
        ):
            response = client.post(
                "/api/external/articles/9/extract",
                json={"force_refresh": False},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["item"]["has_full_content"])
        self.assertTrue(payload["extraction"]["performed"])
        self.assertFalse(payload["extraction"]["cached"])
        conn.execute.assert_awaited()

    def test_on_demand_extraction_returns_422_when_extraction_fails(self):
        conn = AsyncMock()
        initial_row = {
            "id": 9,
            "title": "Needs extraction",
            "link": "https://example.com/story",
            "description": "desc",
            "thumbnail": None,
            "published": "Wed",
            "published_datetime": None,
            "category": "Markets",
            "source": "Reuters",
            "starred": False,
            "is_read": False,
            "feed_id": 10,
            "feed_name": "Feed A",
            "feed_url": "https://example.com/rss",
            "content": None,
        }
        client = TestClient(build_test_app(make_auth_mock(self.user, auth_method="api_token")))

        with patch(
            "backend.external_api._require_external_api_enabled",
            new=AsyncMock(return_value=self.user),
        ), patch(
            "backend.external_api.database.get_db_connection",
            new=AsyncMock(return_value=conn),
        ), patch(
            "backend.external_api.database.release_db_connection",
            new=AsyncMock(),
        ), patch(
            "backend.external_api._get_article_row",
            new=AsyncMock(return_value=initial_row),
        ), patch(
            "backend.external_api.extract_article_content_with_readability",
            new=AsyncMock(return_value="<p>No content could be extracted.</p>"),
        ):
            response = client.post(
                "/api/external/articles/9/extract",
                json={"force_refresh": False},
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("could not be extracted", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
