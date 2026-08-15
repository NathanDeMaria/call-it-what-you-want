import csv
from collections.abc import Iterable
from functools import cache
from importlib.resources import files
from pathlib import Path

from .registry import Teams
from .types import Team, TeamName

_PACKAGE = "call_it_what_you_want"
_DATA_DIR = "data"

# ESPN id namespaces. An id is unique within an organization, not within a
# sport: every college sport shares one namespace, and each pro league
# has its own that collides with it.
NCAA = "ncaa"

REQUIRED_COLUMNS = ("espn_id", "name", "year", "source")
# `league` scopes a name to one sport; `same_as` points a duplicate ESPN
# record at the id that should own it. Both may be left out entirely, and
# blank cells mean "not set", so a file written before they existed still
# loads.
OPTIONAL_COLUMNS = ("league", "same_as")
COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


def teams_from_csv(lines: Iterable[str]) -> Teams:
    """
    Build a registry from CSV rows of `espn_id,name,year,source`, plus the
    optional `league` and `same_as` columns.

    One row is one observation, so a team appears once per name per season
    it was seen under that name. Rows for the same team don't have to be
    adjacent, but their order is kept.

    A row with `same_as` set declares its `espn_id` a duplicate record of
    that team: the names pool into the target, and both ids resolve to it.
    """
    reader = csv.DictReader(lines)
    _check_columns(tuple(reader.fieldnames or ()))

    names: dict[str, list[TeamName]] = {}
    same_as: dict[str, str] = {}
    for number, row in enumerate(reader, start=2):  # row 1 is the header
        espn_id = row["espn_id"]
        try:
            year = int(row["year"])
        except (TypeError, ValueError):
            raise ValueError(
                f"Row {number}: year {row['year']!r} isn't a number."
            ) from None
        names.setdefault(espn_id, []).append(
            TeamName(
                name=row["name"],
                year=year,
                source=row["source"],
                league=(row.get("league") or "").strip() or None,
            )
        )
        duplicate_of = (row.get("same_as") or "").strip()
        if not duplicate_of:
            continue
        if duplicate_of == espn_id:
            raise ValueError(f"Row {number}: {espn_id} is same_as itself.")
        if espn_id in same_as and same_as[espn_id] != duplicate_of:
            raise ValueError(
                f"Row {number}: {espn_id} is same_as both "
                f"{same_as[espn_id]} and {duplicate_of}."
            )
        same_as[espn_id] = duplicate_of

    return Teams(_merge(names, same_as))


def _check_columns(fields: tuple[str, ...]) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in fields]
    unknown = [c for c in fields if c not in COLUMNS]
    if not missing and not unknown:
        return
    problems = []
    if missing:
        problems.append(f"missing {', '.join(missing)}")
    if unknown:
        problems.append(f"unexpected {', '.join(unknown)}")
    raise ValueError(
        f"Expected columns {', '.join(REQUIRED_COLUMNS)} "
        f"(optionally {', '.join(OPTIONAL_COLUMNS)}); {' and '.join(problems)}."
    )


def _merge(names: dict[str, list[TeamName]], same_as: dict[str, str]) -> list[Team]:
    pooled: dict[str, list[TeamName]] = {}
    duplicates: dict[str, list[str]] = {}
    for espn_id in names:
        canonical = _canonical(espn_id, same_as)
        pooled.setdefault(canonical, [])
        if canonical != espn_id:
            duplicates.setdefault(canonical, []).append(espn_id)
    # Second pass so a duplicate's names land after the canonical team's,
    # whichever order the rows happened to be in.
    for espn_id, team_names in names.items():
        pooled[_canonical(espn_id, same_as)].extend(team_names)
    return [
        Team(
            espn_id=canonical,
            names=tuple(team_names),
            other_espn_ids=tuple(duplicates.get(canonical, ())),
        )
        for canonical, team_names in pooled.items()
    ]


def _canonical(espn_id: str, same_as: dict[str, str]) -> str:
    seen = [espn_id]
    while espn_id in same_as:
        espn_id = same_as[espn_id]
        if espn_id in seen:
            raise ValueError(
                f"same_as loops between {', '.join(sorted(seen))}. "
                "One of them has to be the canonical id."
            )
        seen.append(espn_id)
    return espn_id


def load(path: str | Path) -> Teams:
    """
    Build a registry from a CSV file of your own.

    Same columns as the bundled data. Use this for a namespace that isn't
    bundled, or pass the result to `Teams.with_teams` to layer corrections
    over the bundled data.
    """
    with Path(path).open(newline="", encoding="utf-8") as file:
        return teams_from_csv(file)


@cache
def default_teams(namespace: str = NCAA) -> Teams:
    """
    The registry bundled with the package for `namespace`.

    Cached, and registries are immutable, so this is cheap to call
    repeatedly and no caller can modify what another one sees.
    """
    resource = files(_PACKAGE).joinpath(_DATA_DIR, f"{namespace}.csv")
    if not resource.is_file():
        available = sorted(
            entry.name.removesuffix(".csv")
            for entry in files(_PACKAGE).joinpath(_DATA_DIR).iterdir()
            if entry.name.endswith(".csv")
        )
        raise ValueError(
            f"No bundled data for namespace {namespace!r}. "
            f"Available: {', '.join(available) or 'none'}. "
            "Namespaces are organizations, not sports -- every college "
            "sport shares one. Use `load` to read a CSV of your own."
        )
    return teams_from_csv(resource.read_text(encoding="utf-8").splitlines())
