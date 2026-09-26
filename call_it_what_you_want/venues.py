"""
Kalshi's and Polymarket's names for the teams they list, tied to ESPN ids.

A prediction market's game is only useful next to a game endgame stores if
something says which ESPN team each side is, and the venues don't: Kalshi
writes a team as `OSU` in `KXNCAAFGAME-26SEP26ILLOSU`, Polymarket as `sdak`
in `cbb-dxst-sdak-2025-11-03`. This module is what files those codes -- and
every other spelling the venue uses -- under the right ESPN id, as names
observed from that venue, so a reader resolves one with

    espn_id("OSU", source="kalshi", league="ncaafb")

and never guesses.

Both venues publish a roster. Kalshi's is its "structured targets", one
per team per league; Polymarket's is `/teams?league=`. Each writes a team
three ways -- a code, a location ("Ohio St.", "Fordham"), and a full name
("Louisville Cardinals", "Fordham Rams") -- and the full name is the one
thing a venue shares with ESPN, so it's what `place` matches on, and
`observations` is what gets filed once it has. Against the bundled data in
September 2026 that placed 307 of Kalshi's 316 college football teams and
all 32 NFL ones outright, and every Division I team in the three college
leagues once the misses among them had a row written by hand.

What doesn't place is reported rather than guessed at. Most of it is a
school ESPN never listed -- both rosters carry D-II, D-III and NAIA
programs that only ever play each other -- and the rest is a spelling that
wants one hand-written row (Kalshi's "UMass Minutemen" is ESPN's
"Massachusetts Minutemen"). Once any of a team's venue names is on file,
`place` finds it there first, so a hand-written row is how a miss gets
fixed and a re-run leaves it alone.

Like `espn`, this is behind the `sync` extra: it needs the network, and
nothing imports it unless you're building the knowledge base.
"""

import re
from collections.abc import Iterable, Iterator, Sequence
from typing import Any, NamedTuple

from .data import NCAA
from .registry import AmbiguousTeamError, Teams, UnknownTeamError, normalize
from .types import ESPN, KALSHI, NCAAFB, NCAAMBB, NCAAWBB, NFL, POLYMARKET, TeamName

_KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2"
_POLYMARKET_API = "https://gamma-api.polymarket.com"

# Each venue's name for the leagues this package records, and what kind
# of Kalshi target lists that league's teams. Kalshi's basketball targets
# carry both college leagues and are told apart by `details.league`.
_KALSHI_LEAGUES = {
    NCAAFB: ("football_team", "NCAAFB"),
    NCAAMBB: ("basketball_team", "NCAAMB"),
    NCAAWBB: ("basketball_team", "NCAAWB"),
    NFL: ("football_team", "NFL"),
}
_POLYMARKET_LEAGUES = {NCAAFB: "cfb", NCAAMBB: "cbb", NCAAWBB: "cwbb", NFL: "nfl"}

# The ESPN id namespace each league's teams are numbered in.
_NAMESPACES = {NCAAFB: NCAA, NCAAMBB: NCAA, NCAAWBB: NCAA, NFL: NFL}

# Polymarket answers Python's default user agent with a 403.
_USER_AGENT = "call-it-what-you-want"
_PAGE_LIMIT = 500


class VenueTeam(NamedTuple):
    """
    One team as a venue lists it.

    `code` is what the venue writes in tickers and slugs. `names` is every
    other spelling it gives, full names first, since those are what
    `place` matches ESPN's on.
    """

    source: str
    league: str
    code: str
    names: tuple[str, ...]


class Placement(NamedTuple):
    """
    Where `place` put a venue team: an ESPN id, or why there isn't one.

    `how` says which name did it, for a report a person reads.
    """

    team: VenueTeam
    espn_id: str | None
    how: str


def namespace_for(league: str) -> str:
    """The ESPN id namespace a league's teams are numbered in."""
    try:
        return _NAMESPACES[league]
    except KeyError:
        raise ValueError(
            f"No namespace known for league {league!r}. "
            f"Available: {', '.join(sorted(_NAMESPACES))}."
        ) from None


def kalshi_team(target: dict, league: str) -> VenueTeam | None:
    """
    One Kalshi structured target as a VenueTeam, or None if it's not a
    team in `league`.

    Kalshi splits a name differently by sport. College football's
    `team_name` is the whole thing ("Louisville Cardinals"), basketball's
    is the nickname ("Jayhawks"), and the NFL's is the nickname behind a
    short city ("GB Packers", "LA Rams"). `market` is the location in all
    three. So the full name is `team_name` when it already starts with the
    location, and otherwise the location plus the nickname, with any
    short capitalized city dropped from the front of it.
    """
    _, kalshi_league = _KALSHI_LEAGUES[league]
    details = target.get("details") or {}
    code = details.get("abbreviation")
    if details.get("league") != kalshi_league or not code:
        return None
    market = details.get("market") or target.get("name") or ""
    team_name = details.get("team_name") or ""
    if team_name and normalize(team_name).startswith(normalize(market)):
        nickname, full = team_name, team_name
    else:
        nickname = _CITY_PREFIX.sub("", team_name)
        full = f"{market} {nickname}".strip()
    spellings = [full, target.get("name") or "", market]
    if _namespace_is_pro(league) and nickname:
        # A bare nickname is a name in a league of 32 franchises and a
        # coin flip in one of 360 schools, most of them Tigers or Eagles.
        spellings.append(nickname)
    return VenueTeam(KALSHI, league, code, _distinct(spellings))


def polymarket_team(row: dict, league: str) -> VenueTeam | None:
    """
    One Polymarket `/teams` row as a VenueTeam.

    Polymarket fills `name` and `alias` differently by league: the NFL has
    the full name in `name` and the nickname in `alias` ("Dallas Cowboys",
    "Cowboys"); college football has them the other way round and split
    ("Rams", "Fordham"); basketball has the full name and no alias. So
    the full name is `name` when it already holds the alias, and the alias
    then the name otherwise.
    """
    code = row.get("abbreviation")
    name = (row.get("name") or "").strip()
    if not code or not name:
        return None
    alias = (row.get("alias") or "").strip()
    if alias and normalize(alias) not in normalize(name):
        full = f"{alias} {name}"
        spellings = [full, alias]
        if _namespace_is_pro(league):
            spellings.append(name)
    else:
        spellings = [name]
        if alias and _namespace_is_pro(league):
            spellings.append(alias)
    return VenueTeam(POLYMARKET, league, code, _distinct(spellings))


def place(teams: Teams, team: VenueTeam) -> Placement:
    """
    The ESPN id a venue team is, found by the names both sides use.

    In order, stopping at the first that answers:

    1. A name already filed under this venue and league -- a previous run,
       or a row written by hand to fix a miss.
    2. ESPN's names in the league, tried with each of the venue's
       spellings and a few mechanical variants of them ("San Diego St." as
       "San Diego State", "Miami (FL) Hurricanes" without the state).
       Then ESPN's names in any league, for a school ESPN spells
       differently by sport.
    3. In a pro league only, the one team whose ESPN name ends with the
       venue's nickname: Kalshi calls the Rams "Los Angeles R", which is no
       name ESPN has used, but only one franchise is the Rams.

    A step that finds two teams stops the search rather than falling
    through to a looser one, since a looser match can only be less sure.
    """
    on_file = _ids(teams, (team.code, *team.names), team.source, team.league)
    if on_file:
        return _placement(team, on_file, f"already on file from {team.source}")
    spellings = [variant for name in team.names for variant in _variants(name)]
    espn = _ids(teams, spellings, ESPN, team.league)
    if espn:
        return _placement(team, espn, "ESPN name")
    # A school keeps its ESPN id across sports, so its name in another
    # league is still the same school: ESPN's basketball feed says "App
    # State Mountaineers" where its football feed said "Appalachian State".
    # Tried second, because the per-sport duplicate records ESPN sometimes
    # issues make this find two ids, and then it has to stop.
    espn = _ids(teams, spellings, ESPN, None)
    if espn:
        return _placement(team, espn, "ESPN name in another league")
    if _namespace_is_pro(team.league):
        by_nickname = _ids_by_nickname(teams, team)
        if by_nickname:
            return _placement(team, by_nickname, "nickname")
    return Placement(team, None, "no ESPN name matches")


def observations(
    teams: Teams, placement: Placement, year: int
) -> tuple[list[tuple[str, TeamName]], list[str]]:
    """
    A placed team's code and spellings, as observations from its venue in
    its league -- for `record_all` -- and the spellings left out.

    One is left out when it's another team's ESPN name, and only that
    team's: filing it would turn a lookup that works today into an
    AmbiguousTeamError for every caller that doesn't scope by source, and
    those callers are reading ESPN's names out of endgame's seasons.
    Collisions between venue codes are fine -- nothing looks those up
    unscoped -- so only ESPN's names are protected.
    """
    team, espn_id = placement.team, placement.espn_id
    if espn_id is None:
        return [], []
    found, skipped = [], []
    for name in _distinct((team.code, *team.names)):
        if _espn_name_of_another_team(teams, name, espn_id):
            skipped.append(name)
            continue
        found.append((espn_id, TeamName(name, year, team.source, team.league)))
    return found, skipped


async def fetch_roster(source: str, league: str) -> list[VenueTeam]:
    """
    Every team a venue lists in `league`, parsed.

    Kalshi's targets are listed by kind across every league it covers --
    a basketball listing is NCAAMB, NCAAWB, the NBA, the WNBA and a few
    hundred teams from elsewhere -- so the league is picked out after.
    """
    if source not in (KALSHI, POLYMARKET):
        raise ValueError(
            f"No roster known for {source!r}. Available: {KALSHI}, {POLYMARKET}."
        )
    leagues = _KALSHI_LEAGUES if source == KALSHI else _POLYMARKET_LEAGUES
    if league not in leagues:
        raise ValueError(
            f"{source} has no roster for league {league!r}. "
            f"Available: {', '.join(sorted(leagues))}."
        )
    async with _session() as session:
        if source == KALSHI:
            kind, _ = _KALSHI_LEAGUES[league]
            rows = await _kalshi_targets(session, kind)
            parsed = (kalshi_team(row, league) for row in rows)
        else:
            rows = await _polymarket_teams(session, _POLYMARKET_LEAGUES[league])
            parsed = (polymarket_team(row, league) for row in rows)
        return [team for team in parsed if team is not None]


def _namespace_is_pro(league: str) -> bool:
    return _NAMESPACES.get(league) != NCAA


def _distinct(names: Iterable[str]) -> tuple[str, ...]:
    seen: dict[str, str] = {}
    for name in names:
        name = " ".join(name.split())
        if name and normalize(name) not in seen:
            seen[normalize(name)] = name
    return tuple(seen.values())


# The short city Kalshi puts in front of an NFL nickname: "GB", "LA", "NY".
_CITY_PREFIX = re.compile(r"^[A-Z]{2,3} (?=\S)")
# "San Diego St." as ESPN writes it. Only a trailing or word-bounded "St."
# -- "St. Francis" is a saint, not a state.
_STATE = re.compile(r"(?<=\w) St\.?(?=\s|$)")
# "Miami (FL) Hurricanes" -> "Miami Hurricanes", where ESPN leaves the
# state off. Only ever a variant, tried after the name as written, so a
# school ESPN does write with its state ("Miami (OH) RedHawks") still
# matches that way first.
_STATE_TAG = re.compile(r"\s*\([A-Z]{2}\)")


def _variants(name: str) -> Iterator[str]:
    yield name
    stated = _STATE.sub(" State", name)
    if stated != name:
        yield stated
    untagged = _STATE_TAG.sub("", stated)
    if untagged != stated:
        yield untagged


def _ids(
    teams: Teams, names: Iterable[str], source: str, league: str | None
) -> set[str]:
    found = set()
    for name in names:
        try:
            found.add(teams.espn_id(name, source=source, league=league))
        except UnknownTeamError:
            continue
        except AmbiguousTeamError:
            # Two teams answer to this spelling. Not proof of anything on
            # its own -- another spelling may pin it down -- but it can't
            # be the answer either.
            continue
    return found


def _ids_by_nickname(teams: Teams, team: VenueTeam) -> set[str]:
    nicknames = {normalize(name).rsplit(" ", 1)[-1] for name in team.names}
    found = set()
    for candidate in teams:
        try:
            current = normalize(candidate.current_name(ESPN, league=team.league))
        except ValueError:
            continue
        if current.rsplit(" ", 1)[-1] in nicknames:
            found.add(candidate.espn_id)
    return found


def _placement(team: VenueTeam, ids: set[str], how: str) -> Placement:
    if len(ids) == 1:
        return Placement(team, next(iter(ids)), how)
    return Placement(team, None, f"{how} matches ESPN ids {', '.join(sorted(ids))}")


def _espn_name_of_another_team(teams: Teams, name: str, espn_id: str) -> bool:
    try:
        other = teams.espn_id(name, source=ESPN)
    except UnknownTeamError:
        return False
    except AmbiguousTeamError:
        # Already two teams' ESPN name -- ESPN's per-sport duplicate records
        # do this -- so an unscoped lookup of it fails today and filing one
        # more can't make that worse.
        return False
    return other != teams.by_espn_id(espn_id).espn_id


def _session() -> Any:
    try:
        import aiohttp
    except ImportError:
        raise RuntimeError(
            "Fetching a venue's roster needs aiohttp: "
            "pip install 'call-it-what-you-want[sync]'"
        ) from None
    return aiohttp.ClientSession(
        raise_for_status=True,
        timeout=aiohttp.ClientTimeout(total=60),
        headers={"User-Agent": _USER_AGENT},
    )


async def _kalshi_targets(session: Any, kind: str) -> list[dict]:
    rows: list[dict] = []
    cursor = ""
    while True:
        params = {"type": kind, "limit": str(_PAGE_LIMIT)}
        if cursor:
            params["cursor"] = cursor
        async with session.get(
            f"{_KALSHI_API}/structured_targets", params=params
        ) as response:
            page = await response.json()
        targets = page.get("structured_targets") or []
        rows.extend(targets)
        cursor = page.get("cursor") or ""
        if not cursor or not targets:
            return rows


async def _polymarket_teams(session: Any, league: str) -> list[dict]:
    # Paged until a page comes back empty, not until one comes back short:
    # Polymarket caps `limit` below what's asked for on some requests and
    # says nothing, so a short page isn't the end.
    rows: list[dict] = []
    while True:
        params = {"league": league, "limit": str(_PAGE_LIMIT), "offset": str(len(rows))}
        async with session.get(f"{_POLYMARKET_API}/teams", params=params) as response:
            page: Sequence[dict] = await response.json()
        if not page:
            return rows
        rows.extend(page)
