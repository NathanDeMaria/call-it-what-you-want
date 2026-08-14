from pathlib import Path

import pytest

from . import current_name, espn_id, name_in
from .data import default_teams, load, teams_from_csv

CSV = """espn_id,name,year,source
349,Army Black Knights,2012,espn
349,Army Knights,2025,espn
349,Army,2025,footballlocks
2426,Navy Midshipmen,2025,espn
"""


def test_reads_observations_into_teams() -> None:
    teams = teams_from_csv(CSV.splitlines())

    assert len(teams) == 2
    assert teams.current_name("Army Black Knights") == "Army Knights"
    assert teams.espn_id("Army") == "349"


def test_rows_for_a_team_can_be_scattered() -> None:
    scattered = """espn_id,name,year,source
349,Army Black Knights,2012,espn
2426,Navy Midshipmen,2025,espn
349,Army Knights,2025,espn
"""

    teams = teams_from_csv(scattered.splitlines())

    assert teams.current_name("Army Black Knights") == "Army Knights"


def test_rejects_unexpected_columns() -> None:
    with pytest.raises(ValueError, match="Expected columns"):
        teams_from_csv(["team,name\n", "349,Army\n"])


def test_rejects_a_year_that_isnt_a_number() -> None:
    bad = "espn_id,name,year,source\n349,Army,twenty-five,espn\n"

    with pytest.raises(ValueError, match="Row 2"):
        teams_from_csv(bad.splitlines())


def test_load_from_a_file(tmp_path: Path) -> None:
    path = tmp_path / "teams.csv"
    path.write_text(CSV, encoding="utf-8")

    assert load(path).current_name("Army Black Knights") == "Army Knights"


def test_bundled_data_loads() -> None:
    assert len(default_teams()) > 0


def test_unknown_league_lists_what_is_bundled() -> None:
    with pytest.raises(ValueError, match="ncaafb"):
        default_teams("underwater-basket-weaving")


def test_module_level_helpers_use_the_bundled_data() -> None:
    assert current_name("Army Black Knights") == "Army Knights"
    assert espn_id("Army Black Knights") == "349"
    assert name_in("Army Knights", 2015) == "Army Black Knights"
