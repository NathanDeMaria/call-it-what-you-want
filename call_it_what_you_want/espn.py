"""
Filling in classifications from ESPN.

The read side of this package is standard-library only, so this module is
the one thing that needs the network. It's behind the `sync` extra, and
nothing imports it unless you're building the knowledge base.

ESPN's core API keeps divisions and conferences in one tree of "groups":
FBS (80), FCS (81), and D-II/D-III (35) are the roots for football, each
group knows its children, and a group with `isConference: true` is a
conference and has no children of its own. So walking down from a root
until conferences gives both facts at once -- the conference a team played
in, and the division that conference sits under -- without either being
guessed at from the game data.

Two things this buys over reading it off a scoreboard:

*It's cheap.* A conference's roster listing names every team in it, and
each entry's URL has the team id in it, so no team has to be fetched
individually. One season of football is a few dozen requests, against the
few hundred a full scoreboard crawl takes.

*D-II and D-III come apart.* ESPN's scoreboard lumps them into one group
(35), but that group's children are "NCAA Division II" (57) and "NCAA
Division III" (58), so descending gets the real tier where crawling by
scoreboard can't.

Division and conference names are ESPN's own strings, kept as-is rather
than mapped onto a vocabulary of our own -- the point is to record what
the source said.
"""

import asyncio
import re
from collections.abc import Iterable, Iterator
from typing import Any, NamedTuple

from .classification import record_classification
from .data import NCAA
from .types import NCAAFB, NCAAMBB, NCAAWBB

_CORE_API = "https://sports.core.api.espn.com/v2/sports"
# Listings are paged; every one we ask for fits well inside this.
_PAGE_LIMIT = 500
_TEAM_ID = re.compile(r"/teams/(\d+)")
_GROUP_ID = re.compile(r"/groups/(\d+)")


class _LeagueGroups(NamedTuple):
    sport: str
    slug: str
    # The groups to descend from. Football splits its divisions across
    # three; basketball has only D-I, so there's one.
    roots: tuple[str, ...]


_LEAGUES = {
    NCAAFB: _LeagueGroups("football", "college-football", ("80", "81", "35")),
    NCAAMBB: _LeagueGroups("basketball", "mens-college-basketball", ("50",)),
    NCAAWBB: _LeagueGroups("basketball", "womens-college-basketball", ("50",)),
}


class TeamTier(NamedTuple):
    """Where one team sat in one season, as ESPN files it."""

    espn_id: str
    division: str
    conference: str | None


def leagues() -> tuple[str, ...]:
    """The leagues classifications can be fetched for."""
    return tuple(_LEAGUES)


async def fetch_tiers(year: int, league: str) -> list[TeamTier]:
    """
    Every team's division and conference for one season, from ESPN.

    Returns them rather than recording them, so a caller can look before
    writing anything.
    """
    try:
        groups = _LEAGUES[league]
    except KeyError:
        raise ValueError(
            f"No ESPN groups known for league {league!r}. "
            f"Available: {', '.join(sorted(_LEAGUES))}."
        ) from None

    try:
        import aiohttp
    except ImportError:
        raise RuntimeError(
            "Fetching classifications needs aiohttp: "
            "pip install 'call-it-what-you-want[sync]'"
        ) from None

    base = f"{_CORE_API}/{groups.sport}/leagues/{groups.slug}/seasons/{year}/types/2"
    async with aiohttp.ClientSession(
        raise_for_status=True, timeout=aiohttp.ClientTimeout(total=60)
    ) as session:
        found: list[list[TeamTier]] = await asyncio.gather(
            *(_walk(session, base, root, None) for root in groups.roots)
        )
    return [tier for group in found for tier in group]


async def record_tiers(year: int, league: str, *, namespace: str = NCAA) -> int:
    """
    Fetch one season's classifications and stage anything new.

    Returns how many observations were new. Re-running a year already on
    file costs the requests and writes nothing, so this is safe to repeat.
    """
    tiers = await fetch_tiers(year, league)
    return sum(
        record_classification(
            tier.espn_id,
            year,
            league,
            tier.division,
            conference=tier.conference,
            namespace=namespace,
        )
        for tier in tiers
    )


async def _walk(
    session: Any, base: str, group_id: str, division: str | None
) -> list[TeamTier]:
    """
    Collect every team under one group.

    `division` is the nearest non-conference ancestor's name, which is what
    a division *is* in this tree -- a group that holds conferences. A
    non-conference group overrides it with its own name on the way down, so
    descending 35 -> 57 -> a conference reports "NCAA Division II" rather
    than the lumped-together parent.
    """
    group = await _get_json(session, f"{base}/groups/{group_id}")
    name = group.get("name") or group_id

    if group.get("isConference"):
        # A conference with no division above it would mean ESPN moved a
        # root; recording it under its own name is wrong, so say so.
        if division is None:
            raise ValueError(
                f"Group {group_id} ({name}) is a conference but was walked "
                "as a root, so there's no division to file its teams under."
            )
        return [
            TeamTier(team_id, division, name)
            for team_id in await _listed_ids(
                session, f"{base}/groups/{group_id}/teams", _TEAM_ID
            )
        ]

    if "children" not in group:
        # A division with no conferences under it. Its teams still have a
        # division, they just have no conference -- which is the honest
        # record, not a gap to fill in.
        return [
            TeamTier(team_id, name, None)
            for team_id in await _listed_ids(
                session, f"{base}/groups/{group_id}/teams", _TEAM_ID
            )
        ]

    child_ids = await _listed_ids(
        session, f"{base}/groups/{group_id}/children", _GROUP_ID
    )
    nested: list[list[TeamTier]] = await asyncio.gather(
        *(_walk(session, base, child, name) for child in child_ids)
    )
    return [tier for group_tiers in nested for tier in group_tiers]


async def _listed_ids(session: Any, url: str, pattern: re.Pattern[str]) -> list[str]:
    """
    The ids in a listing, read out of the `$ref` URLs it hands back.

    The listing only gives references, but each one has the id in its path,
    so this avoids a request per item.
    """
    payload = await _get_json(session, url, {"limit": _PAGE_LIMIT})
    return list(_ids_in(payload.get("items", ()), pattern))


def _ids_in(items: Iterable[dict], pattern: re.Pattern[str]) -> Iterator[str]:
    for item in items:
        match = pattern.search(item.get("$ref", ""))
        if match is not None:
            yield match.group(1)


async def _get_json(
    session: Any, url: str, params: dict[str, Any] | None = None
) -> dict:
    async with session.get(url, params=params or {}) as response:
        return await response.json()
