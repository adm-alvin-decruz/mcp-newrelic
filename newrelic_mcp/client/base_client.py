"""
Base New Relic API client.

Provides common HTTP client functionality and NRQL query capabilities.
"""

import logging
from typing import Any

import httpx

from ..config import NewRelicConfig
from ..types import ApiError, PaginatedResult
from ..utils.graphql_helpers import extract_nested_data

logger = logging.getLogger(__name__)


class BaseNewRelicClient:
    """Base client for interacting with New Relic APIs"""

    def __init__(self, config: NewRelicConfig):
        self.config = config
        self.base_url = (
            "https://api.newrelic.com" if config.effective_region == "US" else "https://api.eu.newrelic.com"
        )
        self.headers: dict[str, str] = {"Api-Key": config.api_key or "", "Content-Type": "application/json"}
        self._http_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=config.effective_timeout,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._http_client.aclose()

    async def _execute_http_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute HTTP request with common error handling"""
        response = await self._http_client.post("/graphql", json=payload)
        response.raise_for_status()
        result: dict[str, Any] = response.json()

        if "errors" in result:
            logger.error("GraphQL errors: %s", result['errors'])
            raise ValueError(f"GraphQL query failed: {result['errors']}")

        return result

    def _extract_mutation_result(
        self, result: dict[str, Any], mutation_key: str, *, error_message: str = "Mutation failed"
    ) -> dict[str, Any] | ApiError:
        """Extract mutation result, returning ApiError if empty or if errors are present."""
        mutation_result: dict[str, Any] = result.get("data", {}).get(mutation_key, {})
        errors = mutation_result.get("errors")
        if errors:
            return ApiError(f"{error_message}: {errors}")
        if not mutation_result:
            return ApiError(error_message)
        return mutation_result

    async def query_nrql(self, account_id: str, query: str) -> dict[str, Any]:
        """Execute a NRQL query using GraphQL variables to prevent injection"""
        graphql_query = {
            "query": """
            query($accountId: Int!, $nrqlQuery: Nrql!) {
                actor {
                    account(id: $accountId) {
                        nrql(query: $nrqlQuery) {
                            results
                        }
                    }
                }
            }
            """,
            "variables": {
                "accountId": int(account_id),
                "nrqlQuery": query,
            },
        }

        logger.debug("Executing NRQL query: %s", query)
        result = await self._execute_http_request(graphql_query)
        logger.debug("Query result: %s", result)
        return result

    async def execute_graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query with optional variables"""
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        return await self._execute_http_request(payload)

    async def paginate_graphql(
        self,
        query: str,
        variables: dict[str, Any],
        data_path: list[str],
        items_key: str,
        *,
        max_pages: int = 10,
        limit: int | None = None,
    ) -> PaginatedResult:
        """Execute a paginated GraphQL query using cursor-based pagination.

        Follows nextCursor through up to max_pages pages, collecting items from
        the given data_path and items_key.
        """
        all_items: list[dict[str, Any]] = []
        cursor: str | None = None
        total_count: int | None = None

        for _ in range(max_pages):
            result = await self.execute_graphql(query, {**variables, "cursor": cursor})
            page_data = extract_nested_data(result, data_path)
            all_items.extend(page_data.get(items_key, []))
            total_count = page_data.get("totalCount", total_count)
            cursor = page_data.get("nextCursor")
            if not cursor or (limit is not None and len(all_items) >= limit):
                break

        if limit is not None:
            all_items = all_items[:limit]

        return PaginatedResult(items=all_items, total_count=total_count)
