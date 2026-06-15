---
title: "Code Style"
description: "Code style guide and linting configuration — Ruff, Pyright, formatting conventions, and commit message standards."
---

# Code Style & Linting

OsuRender API enforces a strict but pragmatic code style to maintain readability and prevent bugs.

## Tooling

We use the following tools, all enforced in CI:

1. **Black**: Uncompromising code formatter
2. **Ruff**: Extremely fast Python linter
3. **Pyright**: Static type checker

## Formatting (Black)

Run Black before committing:

```bash
black src/ scripts/ tests/
```

We use standard Black defaults (88 character line length).

## Linting (Ruff)

Run Ruff to catch logic errors and anti-patterns:

```bash
ruff check src/

# Auto-fix fixable issues
ruff check --fix src/
```

## Type Checking (Pyright)

All new code must be fully type-hinted.

```bash
pyright src/
```

### Type Hinting Guidelines

- **Use built-in types**: `list[str]` instead of `List[str]`, `dict[str, Any]` instead of `Dict[str, Any]` (Requires Python 3.9+)
- **Use union operator**: `str | None` instead of `Optional[str]` (Requires Python 3.10+)
- **Pydantic models**: Prefer Pydantic models for structured data passing over raw dicts
- **SQLAlchemy**: Use `Mapped[T]` for ORM attributes

## Logging Conventions

We use structured JSON logging. **Do not use the standard `print()` or basic `logging.info()`.**

```python
from src.core.logging import get_logger

logger = get_logger(__name__)

# BAD
logger.info(f"Processed job {job_id} in {duration} seconds")

# GOOD
logger.info(
    "Job processed successfully",
    extra={"job_id": job_id, "duration_sec": duration}
)
```

The custom `JSONFormatter` in `src/core/logging.py` will format this as a JSON object, automatically injecting `request_id`, `job_id`, and other context variables if they are set in the current execution context.
