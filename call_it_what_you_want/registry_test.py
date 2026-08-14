import pytest

from .registry import AmbiguousTeamError, Teams, UnknownTeamError, normalize
from .types import ESPN, Team, TeamName

ARMY = Team(
    espn_id="349",
    names=(
        TeamName("Army Black Knights", 2012, ESPN),
        TeamName("Army Knights", 2025, ESPN),
        TeamName("Army", 2025, "footballlocks"),
    ),
)
NAVY = Team(
    espn_id="2426",
    names=(TeamName("Navy Midshipmen", 2025, ESPN),),
)


@pytest.fixture
def teams() -> Teams:
    return Teams([ARMY, NAVY])


def test_translates_an_old_name(teams: Teams) -> None:
    assert teams.current_name("Army Black Knights") == "Army Knights"


def test_translates_another_sources_name(teams: Teams) -> None:
    # Looked up under footballlocks' spelling, answered in ESPN's.
    assert teams.current_name("Army") == "Army Knights"


def test_a_current_name_translates_to_itself(teams: Teams) -> None:
    assert teams.current_name("Army Knights") == "Army Knights"


def test_espn_id_from_any_name(teams: Teams) -> None:
    assert teams.espn_id("Army Black Knights") == "349"
    assert teams.espn_id("Army") == "349"


def test_name_in_a_past_year(teams: Teams) -> None:
    assert teams.name_in("Army Knights", 2015) == "Army Black Knights"


def test_by_espn_id(teams: Teams) -> None:
    assert teams.by_espn_id("349") == ARMY


@pytest.mark.parametrize(
    "spelling",
    ["army black knights", "  Army   Black  Knights ", "ARMY BLACK KNIGHTS"],
)
def test_lookups_ignore_case_and_spacing(teams: Teams, spelling: str) -> None:
    assert teams.by_name(spelling) == ARMY


def test_lookups_ignore_periods() -> None:
    teams = Teams([Team("1", (TeamName("St. Louis Rams", 2015),))])

    assert teams.current_name("St Louis Rams") == "St. Louis Rams"


def test_unknown_name(teams: Teams) -> None:
    with pytest.raises(UnknownTeamError, match="Yale"):
        teams.by_name("Yale Bulldogs")


def test_unknown_espn_id(teams: Teams) -> None:
    with pytest.raises(UnknownTeamError, match="404"):
        teams.by_espn_id("404")


def test_a_shared_name_is_ambiguous_rather_than_a_guess() -> None:
    # Plenty of college teams share a nickname, so picking one would be
    # wrong about as often as it was right.
    teams = Teams(
        [
            Team("1", (TeamName("Bulldogs", 2025),)),
            Team("2", (TeamName("Bulldogs", 2025),)),
        ]
    )

    with pytest.raises(AmbiguousTeamError, match="matches 2 teams"):
        teams.by_name("Bulldogs")


def test_duplicate_espn_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="share ESPN id"):
        Teams([ARMY, ARMY])


def test_with_teams_adds_a_new_team(teams: Teams) -> None:
    navy_prep = Team("9999", (TeamName("Navy Prep", 2025),))

    extended = teams.with_teams([navy_prep])

    assert extended.espn_id("Navy Prep") == "9999"
    assert len(extended) == 3


def test_with_teams_merges_names_into_an_existing_team(teams: Teams) -> None:
    # The point of merging: add a spelling the bundled data is missing
    # without having to restate the rest of the team.
    correction = Team("349", (TeamName("Army West Point", 2015, ESPN),))

    extended = teams.with_teams([correction])

    assert extended.espn_id("Army West Point") == "349"
    assert extended.current_name("Army West Point") == "Army Knights"
    assert extended.name_in("Army", 2016) == "Army West Point"


def test_with_teams_leaves_the_original_alone(teams: Teams) -> None:
    teams.with_teams([Team("349", (TeamName("Army West Point", 2015, ESPN),))])

    with pytest.raises(UnknownTeamError):
        teams.by_name("Army West Point")


def test_with_teams_drops_duplicate_observations(teams: Teams) -> None:
    extended = teams.with_teams([ARMY])

    assert extended.by_espn_id("349").names == ARMY.names


def test_contains(teams: Teams) -> None:
    assert "army black knights" in teams
    assert "Yale Bulldogs" not in teams


def test_iterates_over_teams(teams: Teams) -> None:
    assert {t.espn_id for t in teams} == {"349", "2426"}


def test_normalize() -> None:
    assert normalize("  St.  LOUIS   Rams ") == "st louis rams"
