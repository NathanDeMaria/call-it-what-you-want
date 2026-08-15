from typing import NamedTuple

# Name sources. These are just labels -- callers can use their own.
ESPN = "espn"

# Leagues, as a name context rather than an id namespace. ESPN calls the
# same school different things depending on which league you asked about,
# so a name observation records which one it came from.
NCAAFB = "ncaafb"
NCAAMBB = "ncaambb"
NCAAWBB = "ncaawbb"


class TeamName(NamedTuple):
    """
    One observation of a team's name: during the `year` season, `source`
    called this team `name` in the context of `league`.

    An observation records what was actually seen, not when a name started
    or stopped being used. The same name can appear many times, once per
    season it was seen, and there's no requirement that every season be
    covered -- a team with two observations twelve years apart is fine.

    `league` is None for a name that isn't league-specific, which matches
    any league on lookup. Set it when the name only holds in one: ESPN
    calls the same school "UNLV Rebels" in football and "UNLV Lady Rebels"
    in women's basketball, in the same season, from the same source.
    """

    name: str
    year: int
    source: str = ESPN
    league: str | None = None


class NoNamesError(ValueError):
    """
    Raised when a team has no names on record for the source and league
    asked for.
    """


class AmbiguousNameError(ValueError):
    """
    Raised when a team went by more than one name in the season being
    asked about, and nothing in the question says which one to pick.

    Usually a team whose name varies by league -- pass one to resolve it.
    Guessing here would be a silent wrong answer, which is worse than a
    caller having to say what they meant.
    """


class Team(NamedTuple):
    """
    A team, keyed by its ESPN team id.

    The id is the identity because it's the part that survives a rename;
    the names are the part that changes.

    ESPN ids are namespaced per *organization*, not per sport: one school
    keeps its id across football and both basketballs (Duke is 150 in all
    three), while each pro league numbers from scratch and collides with
    the NCAA (id 2 is both the Buffalo Bills and the Auburn Tigers). So a
    `Teams` registry covers one namespace, and every college sport shares
    a single one.

    `other_espn_ids` holds duplicate records for the same team -- ESPN
    occasionally files one school under two ids -- so their names pool
    into one team and lookups by either id land in the same place.

    `names` is unordered; use the accessors rather than indexing it.
    """

    espn_id: str
    names: tuple[TeamName, ...]
    other_espn_ids: tuple[str, ...] = ()

    @property
    def espn_ids(self) -> tuple[str, ...]:
        """
        Every ESPN id for this team, the canonical one first.
        """
        return (self.espn_id, *self.other_espn_ids)

    def names_from(
        self, source: str = ESPN, *, league: str | None = None
    ) -> tuple[TeamName, ...]:
        """
        Every name observed from `source`, in the order they were recorded.

        Passing a `league` narrows to names seen in it, plus names recorded
        without a league, since those aren't league-specific and hold
        everywhere. Passing None keeps all of them.

        Raises NoNamesError if nothing is on record for that combination.
        """
        names = tuple(
            n
            for n in self.names
            if n.source == source
            and (league is None or n.league == league or n.league is None)
        )
        if not names:
            raise NoNamesError(
                f"Team {self.espn_id} has no names from {source!r}"
                f"{'' if league is None else f' in {league!r}'}. "
                f"On record: {_describe(self.names) or 'nothing'}."
            )
        return names

    def current_name(self, source: str = ESPN, *, league: str | None = None) -> str:
        """
        The name to use now: the one `source` was last seen using.

        Raises AmbiguousNameError if the team went by more than one name in
        that season -- pass a `league` to say which one you want.
        """
        names = self.names_from(source, league=league)
        year = max(n.year for n in names)
        return self._one_name(names, year)

    def name_in(
        self, year: int, source: str = ESPN, *, league: str | None = None
    ) -> str:
        """
        What `source` called this team in `year`.

        Observations are sparse, so this is the last name seen at or before
        `year`: a team is assumed to keep the name it was last seen with
        until it's seen with a different one. For a year that predates
        every observation, this is the earliest name on record, since a
        team's first known name is the best guess at what came before it.
        """
        names = self.names_from(source, league=league)
        earlier = [n.year for n in names if n.year <= year]
        return self._one_name(
            names, max(earlier) if earlier else min(n.year for n in names)
        )

    def _one_name(self, names: tuple[TeamName, ...], year: int) -> str:
        at_year = [n for n in names if n.year == year]
        distinct = {n.name for n in at_year}
        if len(distinct) == 1:
            return at_year[0].name
        leagues: dict[str, dict[str, None]] = {}
        for observed in at_year:
            leagues.setdefault(observed.name, {})[observed.league or "no league"] = None
        described = ", ".join(
            f"{name!r} ({', '.join(seen)})" for name, seen in leagues.items()
        )
        raise AmbiguousNameError(
            f"Team {self.espn_id} went by {len(distinct)} names in {year}: "
            f"{described}. Pass a league to say which one you want."
        )


def _describe(names: tuple[TeamName, ...]) -> str:
    return ", ".join(
        f"{source} ({league or 'no league'})"
        for source, league in sorted({(n.source, n.league or "") for n in names})
    )
