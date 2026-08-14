from collections.abc import Iterable, Iterator

from .types import ESPN, Team, TeamName


class UnknownTeamError(KeyError):
    """
    Raised when a name or id doesn't match any team in the registry.
    """


class AmbiguousTeamError(ValueError):
    """
    Raised when a name matches more than one team.

    Two teams sharing a name is normal in college sports, so this is a
    question for the caller rather than something to guess at.
    """


def normalize(name: str) -> str:
    """
    Fold a name into the form used for lookups.

    Case, surrounding whitespace, repeated spaces, and periods are all
    ignored, so "St. Louis Rams" and "st louis  rams" find the same team.
    Nothing beyond that is guessed at: a misspelling like "San Francsico
    49ers" only resolves if it's recorded as its own TeamName.
    """
    return " ".join(name.casefold().replace(".", "").split())


class Teams:
    """
    A lookup table over one league's teams.

    One registry covers one league, because an ESPN team id is only unique
    within a sport. Registries are immutable -- `with_teams` returns a new
    one -- so a caller's corrections can't leak into the bundled data.
    """

    def __init__(self, teams: Iterable[Team]) -> None:
        by_id: dict[str, Team] = {}
        for team in teams:
            if team.espn_id in by_id:
                raise ValueError(
                    f"Two teams share ESPN id {team.espn_id}. Ids are unique "
                    "within a league, so these are probably from different "
                    "leagues and belong in separate registries."
                )
            by_id[team.espn_id] = team
        self._by_id = by_id
        self._by_name: dict[str, set[str]] = {}
        for team in by_id.values():
            for team_name in team.names:
                key = normalize(team_name.name)
                self._by_name.setdefault(key, set()).add(team.espn_id)

    def by_espn_id(self, espn_id: str) -> Team:
        """
        The team with this ESPN id.
        """
        try:
            return self._by_id[espn_id]
        except KeyError:
            raise UnknownTeamError(f"No team with ESPN id {espn_id!r}") from None

    def by_name(self, name: str) -> Team:
        """
        The team known by `name`, under any source, in any year.

        Raises UnknownTeamError if nothing matches and AmbiguousTeamError
        if more than one team does.
        """
        ids = self._by_name.get(normalize(name))
        if not ids:
            raise UnknownTeamError(f"No team named {name!r}")
        if len(ids) > 1:
            raise AmbiguousTeamError(
                f"{name!r} matches {len(ids)} teams (ESPN ids "
                f"{', '.join(sorted(ids))}). Look it up by id instead."
            )
        return self._by_id[next(iter(ids))]

    def current_name(self, name: str, source: str = ESPN) -> str:
        """
        Translate any name a team has gone by into the one to use now.
        """
        return self.by_name(name).current_name(source)

    def name_in(self, name: str, year: int, source: str = ESPN) -> str:
        """
        Translate any name a team has gone by into what it was called in
        `year`.
        """
        return self.by_name(name).name_in(year, source)

    def espn_id(self, name: str) -> str:
        """
        The ESPN team id for any name a team has gone by.
        """
        return self.by_name(name).espn_id

    def with_teams(self, teams: Iterable[Team]) -> "Teams":
        """
        A copy of this registry with `teams` added.

        A team whose id is already here has its names merged in rather than
        replacing the existing ones, so a caller can add a spelling the
        bundled data is missing without restating the rest of the team.
        Exact duplicate observations are dropped; the original order is
        kept, so existing tie-breaks don't move.
        """
        merged = dict(self._by_id)
        for team in teams:
            existing = merged.get(team.espn_id)
            if existing is None:
                merged[team.espn_id] = team
                continue
            merged[team.espn_id] = existing._replace(
                names=_dedupe(existing.names + team.names)
            )
        return Teams(merged.values())

    def __iter__(self) -> Iterator[Team]:
        return iter(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, name: str) -> bool:
        return normalize(name) in self._by_name


def _dedupe(names: Iterable[TeamName]) -> tuple[TeamName, ...]:
    # dict preserves insertion order, so this keeps the first of each
    # repeated observation where it was.
    return tuple(dict.fromkeys(names))
