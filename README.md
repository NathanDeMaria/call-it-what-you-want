# call-it-what-you-want

A python package for translating between names and ID schemes for sports
teams/athletes/etc.

## Usage

```python
from call_it_what_you_want import current_name, espn_id, name_in

current_name("Army Black Knights")  # "Army Knights"
espn_id("Army Black Knights")  # "349"
name_in("Army Knights", 2015)  # "Army Black Knights"
```

A team is keyed by its ESPN team id, because that's the part that survives a
rename. Names are the part that changes, so each one is recorded as an
observation: *during this season, this source called this team this name, in
this league.*

```python
Team(
    espn_id="2439",
    names=(
        TeamName("UNLV Rebels", 2025, "espn", "ncaafb"),
        TeamName("UNLV Rebels", 2025, "espn", "ncaambb"),
        TeamName("UNLV Lady Rebels", 2025, "espn", "ncaawbb"),
    ),
)
```

Recording sightings rather than date ranges means the data can be sparse --
you never have to know what a team was called in a season nobody looked at.
`current_name` is the name from the latest season on record, and `name_in`
holds the last name seen until a different one shows up.

## Namespaces and leagues

An ESPN id is unique within an **organization**, not within a sport. One
school keeps its id across every college sport -- Duke is 150 in football,
men's basketball, and women's basketball -- while each pro league numbers
from scratch and collides with the NCAA (id 2 is both the Buffalo Bills and
the Auburn Tigers).

So a registry covers one namespace, and all of college shares a single one:

```python
from call_it_what_you_want import default_teams, load

teams = default_teams("ncaa")  # football and both basketballs together
teams.by_name("Army")  # -> Team
teams.by_espn_id("349")  # -> Team

# Registries are immutable; corrections layer on top.
teams = teams.with_teams(load("my_corrections.csv"))
```

**League is a name context, not a namespace.** The same school in the same
season has different names depending on which sport you asked about: `UNLV
Rebels` / `UNLV Lady Rebels`, `The Citadel Bulldogs` (basketball) /
`Citadel Bulldogs` (football). Because names pool into one team, you can
translate across that boundary:

```python
current_name("UNLV Rebels", league="ncaawbb")  # "UNLV Lady Rebels"
current_name("UNLV Lady Rebels", league="ncaafb")  # "UNLV Rebels"
```

Asking without a league for a team whose name depends on one raises
`AmbiguousNameError`, listing the candidates -- guessing would be a silent
wrong answer. A name recorded with no league isn't league-specific and
matches every league, so most teams need no league at all.

A name that matches no team raises `UnknownTeamError`; one that matches
several raises `AmbiguousTeamError` rather than guessing, since sharing a
nickname is normal in college sports.

## Duplicate ESPN records

ESPN occasionally files one school under two ids. Point the duplicate at the
id that should own it with `same_as`, and their names pool into one team
while both ids keep resolving:

```python
teams.by_espn_id("112358") == teams.by_espn_id("2341")  # True
teams.by_espn_id("112358").espn_ids  # ("2341", "112358")
```

### Bundled data

`call_it_what_you_want/data/<namespace>.csv`. Required columns
`espn_id,name,year,source`; optional `league` and `same_as`, which may be
blank or left out entirely, so a file written without them still loads.
Column order doesn't matter. One row per observation.

**This is a seed, not a dataset** -- a handful of teams covering each shape
the schema supports. Populating it properly means a pull from ESPN.

## Development

Dependencies are managed with [uv](https://docs.astral.sh/uv/).

```shell
uv sync
```

Lint, format, type check, and test:

```shell
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
```

Tests live next to the code they cover, named `*_test.py`.
