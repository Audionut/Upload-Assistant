# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
"""Type conversion utilities shared across modules."""

from typing import Any


def to_int(value: Any, fallback: int = 0) -> int:
    """
    Safely convert a value to an integer.

    Args:
        value: The value to convert
        fallback: The value to return if conversion fails (default: 0)

    Returns:
        The converted integer value or the fallback value
    """
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except (ValueError, OverflowError):
            return fallback
    return fallback
