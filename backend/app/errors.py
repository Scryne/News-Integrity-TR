"""Domain errors raised by services and rendered as FastAPI's ``{"detail": ...}``.

Services never import FastAPI; they raise :class:`ApiError` with the status code
the contract assigns (ARCHITECTURE §6: standard ``{"detail": ...}`` shape with
appropriate 4xx/5xx codes). ``main.create_app`` registers the handler.
"""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    def __init__(self, status_code: int, detail: Any) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def not_found(what: str) -> ApiError:
    return ApiError(404, f"{what} not found")


def unprocessable(detail: Any) -> ApiError:
    return ApiError(422, detail)


def conflict(detail: Any) -> ApiError:
    return ApiError(409, detail)
