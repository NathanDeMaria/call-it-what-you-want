from .classification import (
    Classifications,
    ConflictingClassificationWarning,
    NewClassificationWarning,
    TeamClassification,
    classifications_from_csv,
    default_classifications,
    load_classifications,
    local_classifications_csv,
    merged_classifications_csv,
    record_classification,
)
from .data import (
    COLUMNS,
    NCAA,
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    NewNameWarning,
    NewRecordWarning,
    NewTeamWarning,
    default_teams,
    load,
    local_csv,
    merged_csv,
    record,
    teams_from_csv,
)
from .local import clear_local, local_dir, local_path
from .namer import TeamNamer, namespace_for, registry_league
from .registry import AmbiguousTeamError, Teams, UnknownTeamError, normalize
from .types import (
    ESPN,
    NCAAFB,
    NCAAMBB,
    NCAAWBB,
    AmbiguousNameError,
    NoNamesError,
    Team,
    TeamName,
)
from .version import __version__


def team(name: str, *, namespace: str = NCAA) -> Team:
    """
    The team known by `name`, from the bundled data for `namespace`.
    """
    return default_teams(namespace).by_name(name)


def current_name(
    name: str,
    *,
    namespace: str = NCAA,
    league: str | None = None,
    source: str = ESPN,
) -> str:
    """
    Translate any name a team has gone by into the one to use now.

    >>> current_name("Appalachian State Mountaineers")
    'App State Mountaineers'

    Pass a `league` for a team whose name depends on the sport, which is
    also what resolves an AmbiguousNameError.
    """
    return default_teams(namespace).current_name(name, source, league=league)


def name_in(
    name: str,
    year: int,
    *,
    namespace: str = NCAA,
    league: str | None = None,
    source: str = ESPN,
) -> str:
    """
    Translate any name a team has gone by into what it was called in `year`.
    """
    return default_teams(namespace).name_in(name, year, source, league=league)


def espn_id(name: str, *, namespace: str = NCAA) -> str:
    """
    The canonical ESPN team id for any name a team has gone by.
    """
    return default_teams(namespace).espn_id(name)
