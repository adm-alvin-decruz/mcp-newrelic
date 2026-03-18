"""Response formatting utilities for consistent API responses."""

from typing import Any


def format_create_response(result: dict[str, Any], **extra_fields: str | list[str]) -> dict[str, Any]:
    """Format standardized create response.

    Args:
        result: The raw API result dict.
        **extra_fields: Mapping of output key → source field name (str) or
                        nested path (list[str], e.g. ["nrql", "query"]).
    """
    response: dict[str, Any] = {
        "success": True,
        "id": result.get("id"),
    }

    for key, field_name in extra_fields.items():
        if isinstance(field_name, list):
            value: Any = result
            for part in field_name:
                value = value.get(part, {}) if isinstance(value, dict) else {}
            response[key] = value
        else:
            response[key] = result.get(field_name)

    return response
