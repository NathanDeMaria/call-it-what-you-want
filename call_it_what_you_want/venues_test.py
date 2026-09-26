import pytest

from .data import NCAA, default_teams, local_csv, record_all
from .registry import Teams
from .types import ESPN, KALSHI, NCAAFB, NCAAMBB, NFL, POLYMARKET, Team, TeamName
from .venues import (
    Placement,
    VenueTeam,
    kalshi_team,
    observations,
    place,
    polymarket_team,
)


def _target(league: str, code: str, market: str, team_name: str, name: str = ""):
    # The shape of a Kalshi structured target, trimmed to what's read.
    return {
        "name": name or market,
        "type": "football_team",
        "details": {
            "abbreviation": code,
            "league": league,
            "market": market,
            "team_name": team_name,
        },
    }


def test_kalshi_college_football_names_the_whole_team() -> None:
    target = _target("NCAAFB", "LOU", "Louisville", "Louisville Cardinals")

    assert kalshi_team(target, NCAAFB) == VenueTeam(
        KALSHI, NCAAFB, "LOU", ("Louisville Cardinals", "Louisville")
    )


def test_kalshi_basketball_is_the_location_and_the_nickname() -> None:
    target = _target("NCAAMB", "WVSU", "West Virginia State", "Yellow Jackets")

    team = kalshi_team(target, NCAAMBB)

    assert team is not None
    assert team.names[0] == "West Virginia State Yellow Jackets"
    # A bare college nickname is never filed: there are dozens of Tigers.
    assert "Yellow Jackets" not in team.names


def test_kalshi_nfl_drops_the_short_city_from_the_nickname() -> None:
    target = _target("NFL", "LAR", "Los Angeles", "LA Rams", name="Los Angeles R")

    team = kalshi_team(target, NFL)

    assert team is not None
    assert team.names == ("Los Angeles Rams", "Los Angeles R", "Los Angeles", "Rams")


def test_kalshi_skips_another_leagues_target() -> None:
    target = _target("NCAAWB", "KU", "Kansas", "Jayhawks")

    assert kalshi_team(target, NCAAMBB) is None


def test_polymarket_nfl_has_the_full_name_in_name() -> None:
    row = {"name": "Dallas Cowboys", "alias": "Cowboys", "abbreviation": "dal"}

    assert polymarket_team(row, NFL) == VenueTeam(
        POLYMARKET, NFL, "dal", ("Dallas Cowboys", "Cowboys")
    )


def test_polymarket_college_football_splits_it_the_other_way() -> None:
    row = {"name": "Rams", "alias": "Fordham", "abbreviation": "fordm"}

    assert polymarket_team(row, NCAAFB) == VenueTeam(
        POLYMARKET, NCAAFB, "fordm", ("Fordham Rams", "Fordham")
    )


def test_polymarket_basketball_is_just_the_name() -> None:
    row = {"name": "Utah Tech Trailblazers", "alias": None, "abbreviation": "dxst"}

    assert polymarket_team(row, NCAAMBB) == VenueTeam(
        POLYMARKET, NCAAMBB, "dxst", ("Utah Tech Trailblazers",)
    )


OHIO_STATE = Team("194", (TeamName("Ohio State Buckeyes", 2025, ESPN, NCAAFB),))
SAN_DIEGO_STATE = Team("21", (TeamName("San Diego State Aztecs", 2025, ESPN, NCAAFB),))
MIAMI = Team("2390", (TeamName("Miami Hurricanes", 2025, ESPN, NCAAFB),))
APP_STATE = Team(
    "2026",
    (
        TeamName("Appalachian State Mountaineers", 2024, ESPN, NCAAFB),
        TeamName("App State Mountaineers", 2025, ESPN, NCAAMBB),
    ),
)
# Two schools ESPN calls the same thing, the way a college nickname is
# shared.
TIGERS = (
    Team("1", (TeamName("Tigers", 2025, ESPN, NCAAFB),)),
    Team("2", (TeamName("Tigers", 2025, ESPN, NCAAFB),)),
)


@pytest.fixture
def college() -> Teams:
    return Teams([OHIO_STATE, SAN_DIEGO_STATE, MIAMI, APP_STATE, *TIGERS])


def test_places_by_espn_name(college: Teams) -> None:
    team = VenueTeam(KALSHI, NCAAFB, "OSU", ("Ohio State Buckeyes", "Ohio St."))

    assert place(college, team) == Placement(team, "194", "ESPN name")


def test_places_an_abbreviated_state(college: Teams) -> None:
    team = VenueTeam(KALSHI, NCAAFB, "SDSU", ("San Diego St. Aztecs",))

    assert place(college, team).espn_id == "21"


def test_places_without_a_state_tag_espn_leaves_off(college: Teams) -> None:
    team = VenueTeam(KALSHI, NCAAFB, "MIA", ("Miami (FL) Hurricanes",))

    assert place(college, team).espn_id == "2390"


def test_places_by_another_leagues_espn_name(college: Teams) -> None:
    # ESPN's basketball feed never said "Appalachian State", its football
    # feed did, and it's one school.
    team = VenueTeam(KALSHI, NCAAMBB, "APP", ("Appalachian State Mountaineers",))

    assert place(college, team) == Placement(
        team, "2026", "ESPN name in another league"
    )


def test_a_name_two_teams_share_places_nothing(college: Teams) -> None:
    team = VenueTeam(POLYMARKET, NCAAFB, "tig", ("Tigers",))

    assert place(college, team).espn_id is None


def test_an_unknown_school_places_nothing(college: Teams) -> None:
    team = VenueTeam(KALSHI, NCAAFB, "UMF", ("Maine-Farmington Beavers",))

    assert place(college, team) == Placement(team, None, "no ESPN name matches")


def test_a_row_already_on_file_wins(college: Teams) -> None:
    # How a miss gets fixed: a hand-written row for the venue's code.
    fixed = college.with_teams([Team("2390", (TeamName("UM", 2026, KALSHI, NCAAFB),))])
    team = VenueTeam(KALSHI, NCAAFB, "UM", ("Hurricanes of Coral Gables",))

    assert place(fixed, team) == Placement(team, "2390", "already on file from kalshi")


def test_a_pro_league_falls_back_to_the_nickname() -> None:
    nfl = Teams(
        [
            Team("14", (TeamName("Los Angeles Rams", 2025, ESPN, NFL),)),
            Team("24", (TeamName("Los Angeles Chargers", 2025, ESPN, NFL),)),
        ]
    )
    team = VenueTeam(KALSHI, NFL, "LAR", ("Los Angeles R", "Rams"))

    assert place(nfl, team) == Placement(team, "14", "nickname")


def test_observations_file_the_code_and_every_spelling(college: Teams) -> None:
    team = VenueTeam(KALSHI, NCAAFB, "OSU", ("Ohio State Buckeyes", "Ohio St."))

    found, skipped = observations(college, place(college, team), 2026)

    assert found == [
        ("194", TeamName("OSU", 2026, KALSHI, NCAAFB)),
        ("194", TeamName("Ohio State Buckeyes", 2026, KALSHI, NCAAFB)),
        ("194", TeamName("Ohio St.", 2026, KALSHI, NCAAFB)),
    ]
    assert skipped == []


def test_observations_leave_out_another_teams_espn_name(college: Teams) -> None:
    # Filing "Miami Hurricanes" under Ohio State would make every unscoped
    # lookup of it ambiguous.
    placement = Placement(
        VenueTeam(KALSHI, NCAAFB, "OSU", ("Miami Hurricanes",)), "194", "test"
    )

    found, skipped = observations(college, placement, 2026)

    assert [name.name for _, name in found] == ["OSU"]
    assert skipped == ["Miami Hurricanes"]


def test_observations_keep_a_name_espn_already_gives_two_teams(
    college: Teams,
) -> None:
    placement = Placement(VenueTeam(POLYMARKET, NCAAFB, "t1", ("Tigers",)), "1", "")

    found, skipped = observations(college, placement, 2026)

    assert [name.name for _, name in found] == ["t1", "Tigers"]
    assert skipped == []


def test_nothing_is_filed_for_an_unplaced_team(college: Teams) -> None:
    placement = Placement(VenueTeam(KALSHI, NCAAFB, "X", ("X",)), None, "")

    assert observations(college, placement, 2026) == ([], [])


def test_record_all_stages_only_whats_new() -> None:
    teams = default_teams(NCAA)
    team = teams.by_name("Ohio State Buckeyes")
    already = next(iter(team.names))
    new = TeamName("tOSU", 2099, "testvenue", NCAAFB)

    staged = record_all(
        [(team.espn_id, already), (team.espn_id, new), (team.espn_id, new)],
        namespace=NCAA,
    )

    assert staged == 1
    assert local_csv(NCAA).splitlines()[1:] == [
        f"{team.espn_id},tOSU,2099,testvenue,ncaafb,"
    ]
    assert default_teams(NCAA).espn_id("tOSU", source="testvenue") == team.espn_id


def test_record_all_refuses_an_id_it_doesnt_know() -> None:
    with pytest.raises(KeyError, match="No team with ESPN id"):
        record_all([("999999999", TeamName("Nobody", 2026, KALSHI))], namespace=NCAA)
