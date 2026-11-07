from __future__ import annotations

import json
from contextvars import ContextVar, Token
from typing import Any
from uuid import uuid4


_REQUEST_ID: ContextVar[str] = ContextVar(
    "sanosync_request_id",
    default="-",
)
_API_PATH: ContextVar[str] = ContextVar(
    "sanosync_api_path",
    default="-",
)


def new_request_id(value: str | None = None) -> str:
    candidate = (value or "").strip()
    if candidate and len(candidate) <= 128:
        return candidate
    return uuid4().hex


def bind_request(
    request_id: str,
    path: str,
) -> tuple[Token[str], Token[str]]:
    return (
        _REQUEST_ID.set(request_id),
        _API_PATH.set(path),
    )


def reset_request(
    tokens: tuple[Token[str], Token[str]],
) -> None:
    _REQUEST_ID.reset(tokens[0])
    _API_PATH.reset(tokens[1])


def current_request_id() -> str:
    return _REQUEST_ID.get()


def current_api_path() -> str:
    return _API_PATH.get()


def log_event(
    event: str,
    **fields: Any,
) -> None:
    payload = {
        "event": event,
        "request_id": current_request_id(),
        **fields,
    }
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ),
        flush=True,
    )
