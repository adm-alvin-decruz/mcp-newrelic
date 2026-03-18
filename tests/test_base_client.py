"""Tests for BaseNewRelicClient."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from newrelic_mcp.client.base_client import BaseNewRelicClient
from newrelic_mcp.config.newrelic_config import NewRelicConfig
from newrelic_mcp.types import PaginatedResult


def _make_config(region="US", api_key="NRAK-test", timeout=30) -> NewRelicConfig:
    cfg = NewRelicConfig()
    cfg.api_key = api_key
    cfg.account_id = "1234567"
    cfg.region = region
    cfg.timeout = timeout
    return cfg


class TestInit:
    def test_us_region(self):
        client = BaseNewRelicClient(_make_config(region="US"))
        assert client.base_url == "https://api.newrelic.com"

    def test_eu_region(self):
        client = BaseNewRelicClient(_make_config(region="EU"))
        assert client.base_url == "https://api.eu.newrelic.com"

    def test_headers_include_api_key(self):
        client = BaseNewRelicClient(_make_config(api_key="NRAK-mykey"))
        assert client.headers["Api-Key"] == "NRAK-mykey"

    def test_persistent_http_client_created(self):
        client = BaseNewRelicClient(_make_config())
        assert isinstance(client._http_client, httpx.AsyncClient)


class TestAclose:
    async def test_closes_http_client(self):
        client = BaseNewRelicClient(_make_config())
        # Patch the internal client's aclose
        client._http_client.aclose = AsyncMock()
        await client.aclose()
        client._http_client.aclose.assert_called_once()


class TestExecuteHttpRequest:
    async def test_success(self):
        client = BaseNewRelicClient(_make_config())
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"result": "ok"}}
        mock_response.raise_for_status = MagicMock()
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client._execute_http_request({"query": "{ actor { user { name } } }"})
        assert result == {"data": {"result": "ok"}}

    async def test_graphql_errors_raise(self):
        client = BaseNewRelicClient(_make_config())
        mock_response = MagicMock()
        mock_response.json.return_value = {"errors": [{"message": "bad query"}]}
        mock_response.raise_for_status = MagicMock()
        client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(ValueError, match="GraphQL query failed"):
            await client._execute_http_request({"query": "bad"})

    async def test_http_error_propagates(self):
        client = BaseNewRelicClient(_make_config())
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_response
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(httpx.HTTPStatusError):
            await client._execute_http_request({"query": "test"})


class TestQueryNrql:
    async def test_uses_graphql_variables(self):
        client = BaseNewRelicClient(_make_config())
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"actor": {"account": {"nrql": {"results": []}}}}}
        mock_response.raise_for_status = MagicMock()
        client._http_client.post = AsyncMock(return_value=mock_response)

        await client.query_nrql("1234567", "SELECT count(*) FROM Transaction")

        call_args = client._http_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert "variables" in payload
        assert payload["variables"]["accountId"] == 1234567
        assert payload["variables"]["nrqlQuery"] == "SELECT count(*) FROM Transaction"


class TestExecuteGraphql:
    async def test_with_variables(self):
        client = BaseNewRelicClient(_make_config())
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"ok": True}}
        mock_response.raise_for_status = MagicMock()
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.execute_graphql("query($id: Int!) { ... }", {"id": 42})

        call_args = client._http_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["variables"] == {"id": 42}
        assert result == {"data": {"ok": True}}

    async def test_without_variables(self):
        client = BaseNewRelicClient(_make_config())
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"ok": True}}
        mock_response.raise_for_status = MagicMock()
        client._http_client.post = AsyncMock(return_value=mock_response)

        await client.execute_graphql("{ actor { user { name } } }")

        call_args = client._http_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert "variables" not in payload


class TestPaginateGraphql:
    async def test_single_page(self):
        client = BaseNewRelicClient(_make_config())
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {"actor": {"entitySearch": {"results": {
                "entities": [{"name": "App1"}, {"name": "App2"}],
                "nextCursor": None,
                "totalCount": 2,
            }}}}
        }
        mock_response.raise_for_status = MagicMock()
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.paginate_graphql(
            "query($cursor: String) { ... }",
            {},
            ["data", "actor", "entitySearch", "results"],
            "entities",
        )

        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 2
        assert result.total_count == 2

    async def test_multiple_pages(self):
        client = BaseNewRelicClient(_make_config())
        page1 = MagicMock()
        page1.json.return_value = {
            "data": {"actor": {"entitySearch": {"results": {
                "entities": [{"name": "App1"}],
                "nextCursor": "cursor1",
                "totalCount": 2,
            }}}}
        }
        page1.raise_for_status = MagicMock()

        page2 = MagicMock()
        page2.json.return_value = {
            "data": {"actor": {"entitySearch": {"results": {
                "entities": [{"name": "App2"}],
                "nextCursor": None,
                "totalCount": 2,
            }}}}
        }
        page2.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(side_effect=[page1, page2])

        result = await client.paginate_graphql(
            "query($cursor: String) { ... }",
            {},
            ["data", "actor", "entitySearch", "results"],
            "entities",
        )

        assert len(result.items) == 2
        assert result.items[0]["name"] == "App1"
        assert result.items[1]["name"] == "App2"

    async def test_limit_truncates(self):
        client = BaseNewRelicClient(_make_config())
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {"actor": {"entitySearch": {"results": {
                "entities": [{"name": f"App{i}"} for i in range(10)],
                "nextCursor": None,
                "totalCount": 10,
            }}}}
        }
        mock_response.raise_for_status = MagicMock()
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.paginate_graphql(
            "query($cursor: String) { ... }",
            {},
            ["data", "actor", "entitySearch", "results"],
            "entities",
            limit=3,
        )

        assert len(result.items) == 3
