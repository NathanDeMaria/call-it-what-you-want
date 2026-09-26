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
    A lookup table over one ESPN id namespace.

    A namespace is an organization, not a sport: all of college sports
    shares one set of ids, while each pro league has its own that collides
    with it. So one registry holds football and both basketballs together,
    and the NFL lives in a separate one.

    Because names pool across leagues, a lookup finds the school no matter
    which sport's name you have -- `by_name("UNLV Lady Rebels")` and
    `by_name("UNLV Rebels")` are the same team. Ask for a name back with
    the league you want it in.

    Registries are immutable -- `with_teams` returns a new one -- so a
    caller's corrections can't leak into the bundled data.
    """

    def __init__(self, teams: Iterable[Team]) -> None:
        by_id: dict[str, Team] = {}
        for team in teams:
            for espn_id in team.espn_ids:
                if espn_id in by_id:
                    raise ValueError(
                        f"Two teams share ESPN id {espn_id}. Ids are unique "
                        "within a namespace, so these are probably from "
                        "different organizations (college and a pro league "
                        "collide) and belong in separate registries."
                    )
                by_id[espn_id] = team
        self._by_id = by_id
        self._teams = tuple(dict.fromkeys(by_id.values()))
        self._by_name: dict[str, set[str]] = {}
        for team in self._teams:
            for team_name in team.names:
                key = normalize(team_name.name)
                self._by_name.setdefault(key, set()).add(team.espn_id)

    def by_espn_id(self, espn_id: str) -> Team:
        """
        The team with this ESPN id, canonical or duplicate.
        """
        try:
            return self._by_id[espn_id]
        except KeyError:
            raise UnknownTeamError(f"No team with ESPN id {espn_id!r}") from None

    def by_name(
        self, name: str, *, source: str | None = None, league: str | None = None
    ) -> Team:
        """
        The team known by `name`, under any source, league, or year.

        `source` and `league` narrow what counts as a match: only names
        that source was seen using, and only names seen in that league (a
        name recorded without one still matches, since it holds in every
        league). Left out, they match everything, as before.

        Scoping is what makes a venue's short codes usable. Kalshi's `HC`
        is Holy Cross in women's basketball and Huntingdon in men's, and a
        code like `MIA` should be read the way the source that wrote it
        meant it, not weighed against every other source's spellings.

        Raises UnknownTeamError if nothing matches and AmbiguousTeamError
        if more than one team does -- `find` is the same lookup without
        the second.
        """
        found = self.find(name, source=source, league=league)
        scope = _describe_scope(source, league)
        if not found:
            raise UnknownTeamError(f"No team named {name!r}{scope}")
        if len(found) > 1:
            raise AmbiguousTeamError(
                f"{name!r} matches {len(found)} teams{scope} (ESPN ids "
                f"{', '.join(t.espn_id for t in found)}). Look it up by id "
                "instead."
            )
        return found[0]

    def find(
        self, name: str, *, source: str | None = None, league: str | None = None
    ) -> tuple[Team, ...]:
        """
        Every team known by `name`, scoped the way `by_name` is, in ESPN id
        order. Empty when nothing matches.

        For a caller that has something else to decide with. Even scoped to
        one league a venue's code can be two schools -- Kalshi writes both
        Washington State and Wayne State as `WSU` in college football -- and
        the game it's attached to is what says which: only one of them is
        playing that opponent on that date.
        """
        key = normalize(name)
        ids = self._by_name.get(key, set())
        if source is not None or league is not None:
            ids = {
                espn_id
                for espn_id in ids
                if any(
                    _observed_as(observed, key, source, league)
                    for observed in self._by_id[espn_id].names
                )
            }
        return tuple(self._by_id[espn_id] for espn_id in sorted(ids, key=_id_order))

    def current_name(
        self, name: str, source: str = ESPN, *, league: str | None = None
    ) -> str:
        """
        Translate any name a team has gone by into the one to use now.
        """
        return self.by_name(name).current_name(source, league=league)

    def name_in(
        self, name: str, year: int, source: str = ESPN, *, league: str | None = None
    ) -> str:
        """
        Translate any name a team has gone by into what it was called in
        `year`.
        """
        return self.by_name(name).name_in(year, source, league=league)

    def espn_id(
        self, name: str, *, source: str | None = None, league: str | None = None
    ) -> str:
        """
        The canonical ESPN team id for any name a team has gone by, scoped
        to a source and league the way `by_name` is.
        """
        return self.by_name(name, source=source, league=league).espn_id

    def with_teams(self, teams: Iterable[Team]) -> "Teams":
        """
        A copy of this registry with `teams` added.

        A team sharing any id with one already here has its names and ids
        merged in rather than replacing it, so a caller can add a spelling
        the bundled data is missing without restating the rest of the team.
        Exact duplicate observations are dropped and the original order is
        kept, so existing answers don't move.

        Raises ValueError if an incoming team's ids span two teams already
        here. That's a claim that those two are one team, which changes
        which id is canonical -- say it in the data with `same_as` instead.
        """
        merged = list(self._teams)
        index = {i: position for position, t in enumerate(merged) for i in t.espn_ids}
        for team in teams:
            hits = {index[i] for i in team.espn_ids if i in index}
            if len(hits) > 1:
                raise ValueError(
                    f"Team {team.espn_id} shares ids with {len(hits)} teams "
                    "already in this registry. Merging them is a data "
                    "decision -- use a `same_as` column to make it."
                )
            if not hits:
                index.update({i: len(merged) for i in team.espn_ids})
                merged.append(team)
                continue
            position = hits.pop()
            existing = merged[position]
            new_ids = tuple(i for i in team.espn_ids if i not in existing.espn_ids)
            merged[position] = existing._replace(
                names=_dedupe(existing.names + team.names),
                other_espn_ids=existing.other_espn_ids + new_ids,
            )
            index.update({i: position for i in new_ids})
        return Teams(merged)

    def __iter__(self) -> Iterator[Team]:
        return iter(self._teams)

    def __len__(self) -> int:
        return len(self._teams)

    def __contains__(self, name: str) -> bool:
        return normalize(name) in self._by_name


def _id_order(espn_id: str) -> tuple[int, str]:
    # ESPN ids are numeric strings; sorted as numbers where they are, so an
    # error message and `find` read 2, 10, 107 rather than 10, 107, 2.
    return (int(espn_id), "") if espn_id.isdigit() else (0, espn_id)


def _observed_as(
    observed: TeamName, key: str, source: str | None, league: str | None
) -> bool:
    return (
        normalize(observed.name) == key
        and (source is None or observed.source == source)
        and (league is None or observed.league in (league, None))
    )


def _describe_scope(source: str | None, league: str | None) -> str:
    parts = [f"from {source!r}"] if source is not None else []
    if league is not None:
        parts.append(f"in {league!r}")
    return f" ({' '.join(parts)})" if parts else ""


def _dedupe(names: Iterable[TeamName]) -> tuple[TeamName, ...]:
    # dict preserves insertion order, so this keeps the first of each
    # repeated observation where it was.
    return tuple(dict.fromkeys(names))
