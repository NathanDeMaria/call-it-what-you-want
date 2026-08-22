"""
What tier a team played in: which division, and which conference within it.

The second thing worth knowing about a team, after who they are. A rating
system that replays every college football game has to start every team
somewhere, and starting a D-III program and an SEC program at the same
number says they're the same strength -- which nothing in the results will
ever correct, because the two never play. Division is the missing prior.

Classifications are per-year for the same reason names are: teams move.
St. Thomas went D-III to D-I in 2021, and conferences realign constantly.
Asking what a team was in a given season is the question that has an
answer; asking what they "are" doesn't.

`conference` is None for a team ESPN doesn't file under one, rather than
the row being left out -- "we know they're D-III and know of no conference"
is a different fact from "we've never looked".

Kept to the standard library, like the rest of the read side. Filling this
out from ESPN needs the `sync` extra; reading it back doesn't.
"""

import csv
import io
import warnings
from collections.abc import Iterable, Iterator
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import NamedTuple

from .local import append_local, local_path, read_local

_PACKAGE = "call_it_what_you_want"
_DATA_DIR = "data"
# Names the local staging file and the bundled CSV, so classifications sit
# beside names rather than in them.
KIND = "classifications"

REQUIRED_COLUMNS = ("espn_id", "year", "league", "division")
# Blank means "no conference on record", which is normal for the tiers ESPN
# doesn't file under one.
OPTIONAL_COLUMNS = ("conference",)
COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


class TeamClassification(NamedTuple):
    """
    One observation of where a team sat: during the `year` season, in
    `league`, this team played in `division`, and in `conference` within
    it.

    Keyed by ESPN id rather than name, since that's the part that survives
    a rename -- the same reason `Team` is.

    `league` is required, unlike a name's: a division only means something
    within one sport. The same school is FBS in football and D-I in
    basketball, and those aren't the same fact.
    """

    espn_id: str
    year: int
    league: str
    division: str
    conference: str | None = None


class NewClassificationWarning(UserWarning):
    """
    Raised by `record_classification` when an observation wasn't already
    on file.

    A warning rather than an error, for the same reason `NewRecordWarning`
    is: finding a team the data doesn't cover is normal and shouldn't stop
    a run, but it should be loud enough to get upstreamed.
    """


class ConflictingClassificationWarning(UserWarning):
    """
    Raised when a team is already on file somewhere else for a season.

    Means either a genuine mid-season move or a sloppy source, and neither
    is something to resolve by guessing -- the first record stands and the
    disagreement is said out loud.
    """


class Classifications:
    """
    A lookup table of what tier each team played in, by ESPN id and year.

    Immutable, like `Teams`, so one caller's additions can't leak into
    another's view of the bundled data.
    """

    def __init__(self, classifications: Iterable[TeamClassification]) -> None:
        grouped: dict[tuple[str, str], dict[int, TeamClassification]] = {}
        for observation in classifications:
            key = (observation.espn_id, observation.league)
            by_year = grouped.setdefault(key, {})
            clash = by_year.get(observation.year)
            if clash is None:
                by_year[observation.year] = observation
            elif clash != observation:
                warnings.warn(
                    f"Team {observation.espn_id} is on record in both "
                    f"{_describe(clash)} and {_describe(observation)} for "
                    f"{observation.year} in {observation.league}. "
                    "Keeping the first.",
                    ConflictingClassificationWarning,
                    stacklevel=2,
                )
        self._by_team = {
            key: sorted(by_year.values(), key=lambda c: c.year)
            for key, by_year in grouped.items()
        }

    def recorded_for(
        self, espn_id: str, year: int, league: str
    ) -> TeamClassification | None:
        """
        What's on file for exactly this season, or None if nothing is.

        Unlike `classification_in`, this doesn't fall back to a neighbouring
        year: it answers "have we surveyed this season" rather than "where
        was this team". The record path needs the former, so re-running a
        scrape doesn't stage a second row for a season already covered.
        """
        for observation in self._by_team.get((espn_id, league), ()):
            if observation.year == year:
                return observation
        return None

    def classification_in(
        self, espn_id: str, year: int, league: str
    ) -> TeamClassification | None:
        """
        Where this team played in `year`, or None if that isn't known.

        Observations are sparse, so this is the last one at or before
        `year`: a team is assumed to stay put until it's seen somewhere
        else. For a year before every observation, this is the earliest on
        record, since where a team started is the best guess at what came
        before it -- the same rule `Team.name_in` follows.

        None rather than an exception because a caller surveying a whole
        league will hit teams nobody has classified, and a tally is more
        useful there than a traceback.
        """
        observations = self._by_team.get((espn_id, league))
        if not observations:
            return None
        earlier = [c for c in observations if c.year <= year]
        return earlier[-1] if earlier else observations[0]

    def with_classifications(
        self, classifications: Iterable[TeamClassification]
    ) -> "Classifications":
        """
        A copy of this table with more observations layered on top.
        """
        return Classifications(list(self) + list(classifications))

    def __iter__(self) -> Iterator[TeamClassification]:
        for observations in self._by_team.values():
            yield from observations

    def __len__(self) -> int:
        return sum(len(o) for o in self._by_team.values())


def _describe(classification: TeamClassification) -> str:
    if classification.conference is None:
        return classification.division
    return f"{classification.division}/{classification.conference}"


def _normalize_conference(conference: str | None) -> str | None:
    """Treat equivalent conference names as the same observation."""
    if conference is None:
        return None
    normalized = conference.strip()
    return normalized.removesuffix(" Conference") or None


def classifications_from_csv(lines: Iterable[str]) -> Classifications:
    """
    Build a table from CSV rows of `espn_id,year,league,division`, plus the
    optional `conference` column.
    """
    reader = csv.DictReader(lines)
    _check_columns(tuple(reader.fieldnames or ()))

    observations = []
    for number, row in enumerate(reader, start=2):  # row 1 is the header
        try:
            year = int(row["year"])
        except (TypeError, ValueError):
            raise ValueError(
                f"Row {number}: year {row['year']!r} isn't a number."
            ) from None
        observations.append(
            TeamClassification(
                espn_id=row["espn_id"],
                year=year,
                league=row["league"],
                division=row["division"],
                conference=_normalize_conference(row.get("conference")),
            )
        )
    return Classifications(observations)


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


def load_classifications(path: str | Path) -> Classifications:
    """
    Build a table from a CSV file of your own.
    """
    with Path(path).open(newline="", encoding="utf-8") as file:
        return classifications_from_csv(file)


@cache
def default_classifications(
    namespace: str = "ncaa", *, include_local: bool = True
) -> Classifications:
    """
    The classifications for `namespace`: what shipped with the package,
    with anything recorded locally layered on top.

    Cached and immutable, like `default_teams`.
    `record_classification` clears the cache when it writes.
    """
    bundled = classifications_from_csv(_bundled_text(namespace).splitlines())
    lines = read_local(namespace, KIND) if include_local else []
    if not lines:
        return bundled
    return bundled.with_classifications(classifications_from_csv(lines))


def _bundled_text(namespace: str) -> str:
    resource = files(_PACKAGE).joinpath(_DATA_DIR, f"{namespace}_{KIND}.csv")
    if not resource.is_file():
        # Unlike names, an empty table is a working answer: it means every
        # team is unclassified, and every caller of `classification_in`
        # already handles None. Raising would make a namespace that simply
        # hasn't been surveyed yet look broken.
        return ",".join(COLUMNS)
    return resource.read_text(encoding="utf-8")


def record_classification(
    espn_id: str,
    year: int,
    league: str,
    division: str,
    *,
    conference: str | None = None,
    namespace: str = "ncaa",
) -> bool:
    """
    Note that team `espn_id` played in `division` (and `conference`) during
    the `year` season of `league`, if that isn't already on file.

    Returns whether the observation was new. New ones are appended to the
    local staging file, take effect immediately for `default_classifications`,
    and warn so they don't slip by unnoticed. Anything already on file is a
    silent no-op, so this is safe to call on every row of a scrape.

    Additive, like `record`: it never edits or removes a row, because
    correcting shipped data is a judgement call rather than something a
    scrape should make in passing.
    """
    observation = TeamClassification(
        espn_id=espn_id,
        year=year,
        league=league,
        division=division,
        conference=_normalize_conference(conference),
    )
    local = read_local(namespace, KIND)
    known = classifications_from_csv(local) if local else Classifications(())
    # Keyed on the season rather than the exact observation: ESPN lists the
    # odd team under two conferences, and recording both would put a
    # conflict in the committed data that warns on every load afterwards.
    # One row per team-season, and a disagreement is said out loud here --
    # while a human is watching a scrape -- instead of shipped.
    existing = known.recorded_for(espn_id, year, league)
    if existing is not None:
        if existing != observation:
            warnings.warn(
                f"ESPN id {espn_id} is already on record as "
                f"{_describe(existing)} for {year} ({league}); not recording "
                f"{_describe(observation)}.",
                ConflictingClassificationWarning,
                stacklevel=2,
            )
        return False

    path = local_path(namespace, KIND)
    warnings.warn(
        f"ESPN id {espn_id} played {_describe(observation)} in {year} "
        f"({league}), which isn't on record for it. Recorded in {path}.",
        NewClassificationWarning,
        stacklevel=2,
    )
    append_local(
        namespace,
        COLUMNS,
        {
            "espn_id": espn_id,
            "year": str(year),
            "league": league,
            "division": division,
            "conference": _normalize_conference(conference) or "",
        },
        KIND,
    )
    default_classifications.cache_clear()
    return True


def merged_classifications_csv(namespace: str = "ncaa") -> str:
    """
    The bundled classifications with the locally recorded rows appended --
    what the file in the package should look like once they're committed.
    """
    rows = _rows(_bundled_text(namespace).splitlines()) + _rows(
        read_local(namespace, KIND)
    )
    return _to_csv(dict.fromkeys(rows))


def local_classifications_csv(namespace: str = "ncaa") -> str:
    """
    Just the locally recorded classifications, as a CSV. Empty (not even a
    header) if nothing has been recorded.
    """
    rows = _rows(read_local(namespace, KIND))
    return _to_csv(dict.fromkeys(rows)) if rows else ""


def _rows(lines: list[str]) -> list[tuple[str, ...]]:
    if not lines:
        return []
    reader = csv.DictReader(lines)
    _check_columns(tuple(reader.fieldnames or ()))
    return [tuple((row.get(c) or "").strip() for c in COLUMNS) for row in reader]


def _to_csv(rows: Iterable[tuple[str, ...]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return out.getvalue()
