import csv
from collections.abc import Iterable
from functools import cache
from importlib.resources import files
from pathlib import Path

from .registry import Teams
from .types import Team, TeamName

_PACKAGE = "call_it_what_you_want"
_DATA_DIR = "data"

# Leagues with bundled data. An ESPN team id is only unique within a
# sport, so each league is its own file and its own registry.
NCAAFB = "ncaafb"

COLUMNS = ("espn_id", "name", "year", "source")


def teams_from_csv(lines: Iterable[str]) -> Teams:
    """
    Build a registry from CSV rows of `espn_id,name,year,source`.

    One row is one observation, so a team appears once per name per season
    it was seen under that name. Rows for the same team don't have to be
    adjacent, but their order is kept, since it's what breaks ties between
    two names recorded in the same year.
    """
    reader = csv.DictReader(lines)
    if reader.fieldnames is None or tuple(reader.fieldnames) != COLUMNS:
        raise ValueError(
            f"Expected columns {', '.join(COLUMNS)}; got "
            f"{', '.join(reader.fieldnames or ['nothing'])}."
        )

    names: dict[str, list[TeamName]] = {}
    for number, row in enumerate(reader, start=2):  # row 1 is the header
        try:
            year = int(row["year"])
        except (TypeError, ValueError):
            raise ValueError(
                f"Row {number}: year {row['year']!r} isn't a number."
            ) from None
        names.setdefault(row["espn_id"], []).append(
            TeamName(name=row["name"], year=year, source=row["source"])
        )
    return Teams(
        Team(espn_id=espn_id, names=tuple(team_names))
        for espn_id, team_names in names.items()
    )


def load(path: str | Path) -> Teams:
    """
    Build a registry from a CSV file of your own.

    Same columns as the bundled data. Use this for a league that isn't
    bundled, or pass the result to `Teams.with_teams` to layer corrections
    over the bundled data.
    """
    with Path(path).open(newline="", encoding="utf-8") as file:
        return teams_from_csv(file)


@cache
def default_teams(league: str = NCAAFB) -> Teams:
    """
    The registry bundled with the package for `league`.

    Cached, and registries are immutable, so this is cheap to call
    repeatedly and no caller can modify what another one sees.
    """
    resource = files(_PACKAGE).joinpath(_DATA_DIR, f"{league}.csv")
    if not resource.is_file():
        available = sorted(
            entry.name.removesuffix(".csv")
            for entry in files(_PACKAGE).joinpath(_DATA_DIR).iterdir()
            if entry.name.endswith(".csv")
        )
        raise ValueError(
            f"No bundled data for league {league!r}. "
            f"Available: {', '.join(available) or 'none'}. "
            "Use `load` to read a CSV of your own."
        )
    return teams_from_csv(resource.read_text(encoding="utf-8").splitlines())
