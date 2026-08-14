from typing import NamedTuple

# Name sources. These are just labels -- callers can use their own.
ESPN = "espn"


class TeamName(NamedTuple):
    """
    One observation of a team's name: `source` called this team `name`
    during the `year` season.

    An observation records what was actually seen, not when a name started
    or stopped being used. The same name can appear many times, once per
    season it was seen, and there's no requirement that every season be
    covered -- a team with two observations twelve years apart is fine.
    """

    name: str
    year: int
    source: str = ESPN


class NoNamesError(ValueError):
    """
    Raised when a team has no names on record from the source asked for.
    """


class Team(NamedTuple):
    """
    A team, keyed by its ESPN team id.

    The id is the identity because it's the part that survives a rename;
    the names are the part that changes. ESPN ids are only unique within a
    sport -- the id in `/college-football/team/_/id/349/` says nothing
    about id 349 in the NBA -- so a `Teams` registry covers one league and
    ids are unique within it.

    `names` is unordered; use the accessors rather than indexing it.
    """

    espn_id: str
    names: tuple[TeamName, ...]

    def names_from(self, source: str = ESPN) -> tuple[TeamName, ...]:
        """
        Every name observed from `source`, in the order they were recorded.

        Raises NoNamesError if this team was never seen under that source.
        """
        names = tuple(n for n in self.names if n.source == source)
        if not names:
            seen = sorted({n.source for n in self.names})
            raise NoNamesError(
                f"Team {self.espn_id} has no names from {source!r}. "
                f"On record: {', '.join(seen) or 'nothing'}."
            )
        return names

    def current_name(self, source: str = ESPN) -> str:
        """
        The name to use now: the one `source` was last seen using.

        If two different names share the latest year, the one recorded
        first wins, so the answer doesn't depend on dict ordering.
        """
        return _latest(self.names_from(source)).name

    def name_in(self, year: int, source: str = ESPN) -> str:
        """
        What `source` called this team in `year`.

        Observations are sparse, so this is the last name seen at or before
        `year`: a team is assumed to keep the name it was last seen with
        until it's seen with a different one. For a year that predates
        every observation, this is the earliest name on record, since a
        team's first known name is the best guess at what came before it.
        """
        names = self.names_from(source)
        earlier = tuple(n for n in names if n.year <= year)
        if earlier:
            return _latest(earlier).name
        return min(names, key=lambda n: n.year).name


def _latest(names: tuple[TeamName, ...]) -> TeamName:
    # max() returns the first of equal maxima, so ties fall to whichever
    # observation was recorded first rather than to iteration order.
    return max(names, key=lambda n: n.year)
