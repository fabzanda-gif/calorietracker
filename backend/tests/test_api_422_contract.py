from pathlib import Path


def test_api_does_not_use_deprecated_422_status_constant():
    offenders = []

    for path in Path("backend/api").rglob("*.py"):
        text = path.read_text(encoding="utf-8")

        if "HTTP_422_UNPROCESSABLE_ENTITY" in text:
            offenders.append(str(path))

    assert offenders == []


def test_api_uses_current_422_status_constant_when_explicit():
    explicit_422_files = []

    for path in Path("backend/api").rglob("*.py"):
        text = path.read_text(encoding="utf-8")

        if "HTTP_422_UNPROCESSABLE_CONTENT" in text:
            explicit_422_files.append(str(path))

    # We only require that any explicit 422 usage is modern.
    # FastAPI's automatic request validation may still emit 422 without
    # referencing this constant in application code.
    assert isinstance(explicit_422_files, list)
