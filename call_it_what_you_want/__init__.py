from .data import COLUMNS, NCAAFB, default_teams, load, teams_from_csv
from .registry import AmbiguousTeamError, Teams, UnknownTeamError, normalize
from .types import ESPN, NoNamesError, Team, TeamName
from .version import __version__


def team(name: str, league: str = NCAAFB) -> Team:
    """
    The team known by `name`, from the bundled data for `league`.
    """
    return default_teams(league).by_name(name)


def current_name(name: str, league: str = NCAAFB, source: str = ESPN) -> str:
    """
    Translate any name a team has gone by into the one to use now.

    >>> current_name("Army Black Knights")
    'Army Knights'
    """
    return default_teams(league).current_name(name, source)


def name_in(name: str, year: int, league: str = NCAAFB, source: str = ESPN) -> str:
    """
    Translate any name a team has gone by into what it was called in `year`.
    """
    return default_teams(league).name_in(name, year, source)


def espn_id(name: str, league: str = NCAAFB) -> str:
    """
    The ESPN team id for any name a team has gone by.
    """
    return default_teams(league).espn_id(name)
