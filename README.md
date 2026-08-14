# call-it-what-you-want

A python package for translating between names and ID schemes for sports
teams/athletes/etc.

## Development

Dependencies are managed with [uv](https://docs.astral.sh/uv/).

```shell
uv sync
```

Lint, format, type check, and test:

```shell
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
```

Tests live next to the code they cover, named `*_test.py`.
