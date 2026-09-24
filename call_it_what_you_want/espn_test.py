import asyncio

import pytest

from .data import default_teams
from .espn import TeamSighting, TeamTier, _sightings, _walk, record_names
from .types import NFL

_BASE = "https://example.test/seasons/2023/types/2"


class _FakeSession:
    """Answers the group and listing URLs `_walk` asks for, from a dict."""

    def __init__(self, payloads: dict[str, dict]) -> None:
        self._payloads = payloads
        self.requested: list[str] = []

    def get(self, url: str, params=None):
        self.requested.append(url)
        return _FakeResponse(self._payloads[url.removeprefix(_BASE)])


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_) -> None:
        return None

    async def json(self) -> dict:
        return self._payload


def _refs(path: str, ids: list[str]) -> dict:
    return {
        "items": [{"$ref": f"https://example.test/x/{path}/{i}?lang=en"} for i in ids]
    }


def test_a_division_of_conferences_reports_both_levels() -> None:
    session = _FakeSession(
        {
            "/groups/80": {"name": "FBS", "isConference": False, "children": {}},
            "/groups/80/children": _refs("groups", ["9"]),
            "/groups/9": {"name": "Pac-12 Conference", "isConference": True},
            "/groups/9/teams": _refs("teams", ["30", "12"]),
        }
    )

    tiers = asyncio.run(_walk(session, _BASE, "80", None))

    assert tiers == [
        TeamTier("30", "FBS", "Pac-12 Conference"),
        TeamTier("12", "FBS", "Pac-12 Conference"),
    ]


def test_the_nearest_division_wins_over_the_lumped_parent() -> None:
    """Group 35 holds D-II and D-III; a team belongs to the one it plays in."""
    session = _FakeSession(
        {
            "/groups/35": {"name": "D2/D3", "isConference": False, "children": {}},
            "/groups/35/children": _refs("groups", ["57", "58"]),
            "/groups/57": {
                "name": "NCAA Division II",
                "isConference": False,
                "children": {},
            },
            "/groups/57/children": _refs("groups", ["104"]),
            "/groups/104": {"name": "Great Lakes Valley", "isConference": True},
            "/groups/104/teams": _refs("teams", ["2000"]),
            "/groups/58": {
                "name": "NCAA Division III",
                "isConference": False,
                "children": {},
            },
            "/groups/58/children": _refs("groups", ["105"]),
            "/groups/105": {"name": "Ohio Athletic", "isConference": True},
            "/groups/105/teams": _refs("teams", ["3000"]),
        }
    )

    tiers = asyncio.run(_walk(session, _BASE, "35", None))

    assert sorted(tiers) == [
        TeamTier("2000", "NCAA Division II", "Great Lakes Valley"),
        TeamTier("3000", "NCAA Division III", "Ohio Athletic"),
    ]


def test_a_division_with_no_conferences_records_the_division_alone() -> None:
    """No conference on record is the honest answer, not a gap to fill."""
    session = _FakeSession(
        {
            "/groups/35": {"name": "D2/D3", "isConference": False},
            "/groups/35/teams": _refs("teams", ["2000"]),
        }
    )

    assert asyncio.run(_walk(session, _BASE, "35", None)) == [
        TeamTier("2000", "D2/D3", None)
    ]


def test_no_team_is_fetched_individually() -> None:
    """The ids come out of the listing's URLs, which is what keeps this cheap."""
    session = _FakeSession(
        {
            "/groups/9": {"name": "Pac-12 Conference", "isConference": True},
            "/groups/9/teams": _refs("teams", ["30", "12"]),
        }
    )

    asyncio.run(_walk(session, _BASE, "9", "FBS"))

    assert session.requested == [f"{_BASE}/groups/9", f"{_BASE}/groups/9/teams"]


def test_a_conference_walked_as_a_root_is_an_error() -> None:
    """Means ESPN moved a root -- filing its teams under itself would be wrong."""
    session = _FakeSession({"/groups/9": {"name": "Pac-12", "isConference": True}})

    with pytest.raises(ValueError, match="no division"):
        asyncio.run(_walk(session, _BASE, "9", None))


def test_a_pro_season_is_each_team_under_that_seasons_name() -> None:
    """The listing only has ids; each team's own record has the name."""
    session = _FakeSession(
        {
            "/seasons/2019/teams": _refs("teams", ["13", "24"]),
            "/seasons/2019/teams/13": {"id": "13", "displayName": "Oakland Raiders"},
            "/seasons/2019/teams/24": {
                "id": "24",
                "displayName": "Los Angeles Chargers",
            },
        }
    )

    found = asyncio.run(_sightings(session, f"{_BASE}/seasons/2019/teams"))

    assert found == [
        TeamSighting("13", "Oakland Raiders"),
        TeamSighting("24", "Los Angeles Chargers"),
    ]


def test_recorded_names_go_to_the_leagues_own_namespace() -> None:
    staged = record_names(
        {
            2020: [TeamSighting("13", "Las Vegas Raiders")],
            2019: [TeamSighting("13", "Oakland Raiders")],
        },
        NFL,
    )

    raiders = default_teams(NFL).by_espn_id("13")
    assert staged == 0  # both already bundled
    assert raiders.current_name() == "Las Vegas Raiders"
    assert default_teams(NFL).name_in("Las Vegas Raiders", 2019) == "Oakland Raiders"


def test_a_new_season_is_staged_quietly() -> None:
    staged = record_names({2031: [TeamSighting("13", "Las Vegas Raiders")]}, NFL)

    assert staged == 1
    assert default_teams(NFL).by_espn_id("13").current_name() == "Las Vegas Raiders"
