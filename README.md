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
observation: *this source called this team this name during this season.*

```python
Team(
    espn_id="349",
    names=(
        TeamName("Army Black Knights", 2012, "espn"),
        TeamName("Army Knights", 2025, "espn"),
        TeamName("Army", 2025, "footballlocks"),
    ),
)
```

Recording sightings rather than date ranges means the data can be sparse --
you never have to know what a team was called in a season nobody looked at.
`current_name` is the name from the latest season on record, and `name_in`
holds the last name seen until a different one shows up.

Tagging names with a source keeps two different problems in one table: a
*rename* is the same source using a new name in a later year, while an
*alias* is another source spelling the same team differently in the same
year. Lookups match any name from any source; answers come back in the
source you ask for, ESPN by default.

An ESPN team id is only unique within a sport, so a registry covers one
league.

```python
from call_it_what_you_want import Teams, default_teams, load

teams = default_teams("ncaafb")
teams.by_name("Army")  # -> Team
teams.by_espn_id("349")  # -> Team

# Registries are immutable; corrections layer on top.
teams = teams.with_teams(load("my_corrections.csv"))
```

A name that matches no team raises `UnknownTeamError`; one that matches
several raises `AmbiguousTeamError` rather than guessing, since sharing a
nickname is normal in college sports.

### Bundled data

`call_it_what_you_want/data/<league>.csv`, with columns
`espn_id,name,year,source` -- one row per observation. **This is a seed, not
a dataset**: it currently holds one team, and the years on it are
illustrative. Populating it properly means a pull from ESPN.

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
