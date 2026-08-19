from collections.abc import Iterator
from pathlib import Path

import pytest

from call_it_what_you_want.classification import default_classifications
from call_it_what_you_want.data import default_teams
from call_it_what_you_want.local import ENV_VAR


@pytest.fixture(autouse=True)
def local_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """
    Point local records at a throwaway directory for every test.

    Without this, `default_teams` would pick up whatever the machine
    running the suite happens to have recorded, and tests that record
    would write to the developer's real data directory.
    """
    directory = tmp_path / "records"
    monkeypatch.setenv(ENV_VAR, str(directory))
    default_teams.cache_clear()
    default_classifications.cache_clear()
    yield directory
    default_teams.cache_clear()
    default_classifications.cache_clear()
