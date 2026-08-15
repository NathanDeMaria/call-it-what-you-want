from pathlib import Path

import pytest

from . import current_name, espn_id, name_in
from .data import default_teams, load, teams_from_csv
from .types import NCAAFB, NCAAWBB, AmbiguousNameError

CSV = """espn_id,name,year,source,league,same_as
349,Army Black Knights,2012,espn,,
349,Army Knights,2025,espn,,
2439,UNLV Rebels,2025,espn,ncaafb,
2439,UNLV Lady Rebels,2025,espn,ncaawbb,
2341,LIU Sharks,2025,espn,ncaafb,
112358,LIU Sharks,2025,espn,ncaambb,2341
"""

# What the file looked like before `league` and `same_as` existed.
OLD_CSV = """espn_id,name,year,source
349,Army Black Knights,2012,espn
349,Army Knights,2025,espn
"""


def test_reads_observations_into_teams() -> None:
    teams = teams_from_csv(CSV.splitlines())

    assert len(teams) == 3
    assert teams.current_name("Army Black Knights") == "Army Knights"


def test_reads_leagues() -> None:
    teams = teams_from_csv(CSV.splitlines())

    assert teams.current_name("UNLV Rebels", league=NCAAWBB) == "UNLV Lady Rebels"


def test_a_blank_league_is_no_league() -> None:
    teams = teams_from_csv(CSV.splitlines())

    assert teams.current_name("Army Knights", league=NCAAFB) == "Army Knights"


def test_same_as_pools_two_ids_into_one_team() -> None:
    teams = teams_from_csv(CSV.splitlines())

    assert teams.by_espn_id("112358") == teams.by_espn_id("2341")
    assert teams.by_espn_id("112358").espn_ids == ("2341", "112358")


def test_a_file_written_before_the_new_columns_still_loads() -> None:
    teams = teams_from_csv(OLD_CSV.splitlines())

    assert teams.current_name("Army Black Knights") == "Army Knights"


def test_columns_can_be_in_any_order() -> None:
    reordered = "name,year,source,espn_id\nArmy,2025,espn,349\n"

    assert teams_from_csv(reordered.splitlines()).espn_id("Army") == "349"


def test_rows_for_a_team_can_be_scattered() -> None:
    scattered = """espn_id,name,year,source
349,Army Black Knights,2012,espn
2426,Navy Midshipmen,2025,espn
349,Army Knights,2025,espn
"""

    teams = teams_from_csv(scattered.splitlines())

    assert teams.current_name("Army Black Knights") == "Army Knights"


def test_rejects_a_missing_required_column() -> None:
    with pytest.raises(ValueError, match="missing source"):
        teams_from_csv(["espn_id,name,year\n", "349,Army,2025\n"])


def test_rejects_an_unexpected_column() -> None:
    with pytest.raises(ValueError, match="unexpected mascot"):
        teams_from_csv(["espn_id,name,year,source,mascot\n", "349,Army,2025,espn,x\n"])


def test_rejects_a_year_that_isnt_a_number() -> None:
    bad = "espn_id,name,year,source\n349,Army,twenty-five,espn\n"

    with pytest.raises(ValueError, match="Row 2"):
        teams_from_csv(bad.splitlines())


def test_rejects_same_as_itself() -> None:
    bad = "espn_id,name,year,source,same_as\n349,Army,2025,espn,349\n"

    with pytest.raises(ValueError, match="same_as itself"):
        teams_from_csv(bad.splitlines())


def test_rejects_conflicting_same_as() -> None:
    bad = """espn_id,name,year,source,same_as
1,A,2025,espn,2
1,A,2024,espn,3
"""

    with pytest.raises(ValueError, match="same_as both"):
        teams_from_csv(bad.splitlines())


def test_rejects_a_same_as_loop() -> None:
    bad = """espn_id,name,year,source,same_as
1,A,2025,espn,2
2,B,2025,espn,1
"""

    with pytest.raises(ValueError, match="loops between"):
        teams_from_csv(bad.splitlines())


def test_same_as_resolves_through_a_chain() -> None:
    chained = """espn_id,name,year,source,same_as
1,A,2025,espn,
2,A,2025,espn,1
3,A,2025,espn,2
"""

    teams = teams_from_csv(chained.splitlines())

    assert len(teams) == 1
    assert teams.by_espn_id("3").espn_id == "1"


def test_load_from_a_file(tmp_path: Path) -> None:
    path = tmp_path / "teams.csv"
    path.write_text(CSV, encoding="utf-8")

    assert load(path).current_name("Army Black Knights") == "Army Knights"


def test_bundled_data_loads() -> None:
    assert len(default_teams()) > 0


def test_unknown_namespace_lists_what_is_bundled() -> None:
    with pytest.raises(ValueError, match="ncaa"):
        default_teams("underwater-basket-weaving")


@pytest.mark.xfail(
    reason="The bundled pull is football-only, so no team in it carries "
    "names from two leagues yet. Flips back to passing once a basketball "
    "pull lands; registry_test.py covers the property on a fixture "
    "in the meantime.",
    strict=True,
)
def test_college_sports_share_one_namespace() -> None:
    # Duke is 150 in football and both basketballs -- one row of teams,
    # names added to it per sport, not a new team per sport.
    duke = default_teams().by_espn_id("150")

    assert duke.current_name(league=NCAAFB) == "Duke Blue Devils"
    assert duke.current_name(league=NCAAWBB) == "Duke Blue Devils"


def test_module_level_helpers_use_the_bundled_data() -> None:
    # ESPN went from "Appalachian State Mountaineers" to "App State
    # Mountaineers" in 2024, which is on record either side of the change.
    assert current_name("Appalachian State Mountaineers") == "App State Mountaineers"
    assert espn_id("Appalachian State Mountaineers") == "2026"
    assert name_in("App State Mountaineers", 2015) == "Appalachian State Mountaineers"


def test_module_level_current_name_takes_a_league() -> None:
    long_island = "Long Island University Sharks"

    assert current_name(long_island, league=NCAAFB) == long_island


def test_ambiguity_surfaces_through_the_module_level_helper() -> None:
    teams = teams_from_csv(CSV.splitlines())

    with pytest.raises(AmbiguousNameError):
        teams.current_name("UNLV Rebels")
