import pytest

from .registry import AmbiguousTeamError, Teams, UnknownTeamError, normalize
from .types import ESPN, NCAAFB, NCAAMBB, NCAAWBB, Team, TeamName

ARMY = Team(
    espn_id="349",
    names=(
        TeamName("Army Black Knights", 2012, ESPN),
        TeamName("Army Knights", 2025, ESPN),
        TeamName("Army", 2025, "footballlocks"),
    ),
)
UNLV = Team(
    espn_id="2439",
    names=(
        TeamName("UNLV Rebels", 2025, ESPN, NCAAFB),
        TeamName("UNLV Lady Rebels", 2025, ESPN, NCAAWBB),
    ),
)
LIU = Team(
    espn_id="2341",
    names=(
        TeamName("LIU Sharks", 2025, ESPN, NCAAFB),
        TeamName("LIU Sharks", 2025, ESPN, NCAAMBB),
    ),
    other_espn_ids=("112358",),
)


@pytest.fixture
def teams() -> Teams:
    return Teams([ARMY, UNLV, LIU])


def test_translates_an_old_name(teams: Teams) -> None:
    assert teams.current_name("Army Black Knights") == "Army Knights"


def test_translates_another_sources_name(teams: Teams) -> None:
    # Looked up under footballlocks' spelling, answered in ESPN's.
    assert teams.current_name("Army") == "Army Knights"


def test_espn_id_from_any_name(teams: Teams) -> None:
    assert teams.espn_id("Army Black Knights") == "349"
    assert teams.espn_id("Army") == "349"


def test_name_in_a_past_year(teams: Teams) -> None:
    assert teams.name_in("Army Knights", 2015) == "Army Black Knights"


@pytest.mark.parametrize(
    "spelling",
    ["army black knights", "  Army   Black  Knights ", "ARMY BLACK KNIGHTS"],
)
def test_lookups_ignore_case_and_spacing(teams: Teams, spelling: str) -> None:
    assert teams.by_name(spelling) == ARMY


def test_lookups_ignore_periods() -> None:
    teams = Teams([Team("1", (TeamName("St. Louis Rams", 2015),))])

    assert teams.current_name("St Louis Rams") == "St. Louis Rams"


def test_names_pool_across_leagues(teams: Teams) -> None:
    # The payoff of one namespace for all of college: a women's basketball
    # name finds the same school as the football name.
    assert teams.by_name("UNLV Lady Rebels") == teams.by_name("UNLV Rebels")


def test_translates_between_leagues(teams: Teams) -> None:
    assert teams.current_name("UNLV Rebels", league=NCAAWBB) == "UNLV Lady Rebels"
    assert teams.current_name("UNLV Lady Rebels", league=NCAAFB) == "UNLV Rebels"


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


def test_a_duplicate_id_colliding_with_another_teams_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="share ESPN id 112358"):
        Teams([LIU, Team("112358", (TeamName("Someone Else", 2025),))])


def test_lookup_by_a_duplicate_id(teams: Teams) -> None:
    # ESPN filed this school under two ids; both find the one team.
    assert teams.by_espn_id("112358") == LIU
    assert teams.by_espn_id("2341") == LIU


def test_espn_id_answers_with_the_canonical_id(teams: Teams) -> None:
    assert teams.espn_id("LIU Sharks") == "2341"


def test_a_merged_team_counts_once(teams: Teams) -> None:
    assert len(teams) == 3
    assert {t.espn_id for t in teams} == {"349", "2439", "2341"}


def test_with_teams_adds_a_new_team(teams: Teams) -> None:
    navy = Team("2426", (TeamName("Navy Midshipmen", 2025),))

    extended = teams.with_teams([navy])

    assert extended.espn_id("Navy Midshipmen") == "2426"
    assert len(extended) == 4


def test_with_teams_merges_names_into_an_existing_team(teams: Teams) -> None:
    # The point of merging: add a spelling the bundled data is missing
    # without having to restate the rest of the team.
    correction = Team("349", (TeamName("Army West Point", 2015, ESPN),))

    extended = teams.with_teams([correction])

    assert extended.espn_id("Army West Point") == "349"
    assert extended.current_name("Army West Point") == "Army Knights"
    assert extended.name_in("Army", 2016) == "Army West Point"


def test_with_teams_matches_on_a_duplicate_id(teams: Teams) -> None:
    correction = Team("112358", (TeamName("Long Island Sharks", 2020, ESPN),))

    extended = teams.with_teams([correction])

    assert extended.espn_id("Long Island Sharks") == "2341"
    assert len(extended) == 3


def test_with_teams_carries_new_duplicate_ids_over() -> None:
    teams = Teams([Team("2341", (TeamName("LIU Sharks", 2025),))])

    extended = teams.with_teams(
        [Team("2341", (TeamName("LIU Sharks", 2024),), ("112358",))]
    )

    assert extended.by_espn_id("112358").espn_id == "2341"


def test_with_teams_refuses_to_join_two_existing_teams(teams: Teams) -> None:
    # Claiming two ids already here are one team changes which is
    # canonical, so it belongs in the data rather than in a merge.
    joiner = Team("349", (TeamName("Whatever", 2025),), ("2439",))

    with pytest.raises(ValueError, match="shares ids with 2 teams"):
        teams.with_teams([joiner])


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


def test_normalize() -> None:
    assert normalize("  St.  LOUIS   Rams ") == "st louis rams"
