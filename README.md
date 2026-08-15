# call-it-what-you-want

A python package for translating between names and ID schemes for sports
teams/athletes/etc.

## Usage

```python
from call_it_what_you_want import current_name, espn_id, name_in

current_name("Lock Haven Bald Eagles")  # "Lock Haven University Bald Eagles"
espn_id("Lock Haven Bald Eagles")  # "209"
name_in("Lock Haven University Bald Eagles", 2015)  # "Lock Haven Bald Eagles"
```

A team is keyed by its ESPN team id, because that's the part that survives a
rename. Names are the part that changes, so each one is recorded as an
observation: *during this season, this source called this team this name, in
this league.*

```python
Team(
    espn_id="149",
    names=(
        TeamName("Montana Grizzlies", 2025, "espn", "ncaafb"),
        TeamName("Montana Grizzlies", 2025, "espn", "ncaambb"),
        TeamName("Montana Lady Griz", 2025, "espn", "ncaawbb"),
    ),
)
```

Recording sightings rather than date ranges means the data can be sparse --
you never have to know what a team was called in a season nobody looked at.
`current_name` is the name from the latest season on record, and `name_in`
holds the last name seen until a different one shows up.

## Namespaces and leagues

An ESPN id is unique within an **organization**, not within a sport. A
school generally keeps its id across every college sport -- Duke is 150 in
football, men's basketball, and women's basketball -- while each pro league
numbers from scratch and collides with the NCAA (id 2 is both the Buffalo
Bills and the Auburn Tigers).

*Generally*, because ESPN doesn't hold to it for smaller programs: 147
school names in the bundled data show up under two or more ids covering
different sports, which is ESPN having issued a separate id per sport
rather than two schools sharing a name. Those want a `same_as` row (below).

So a registry covers one namespace, and all of college shares a single one:

```python
from call_it_what_you_want import default_teams, load

teams = default_teams("ncaa")  # football and both basketballs together
teams.by_name("App State Mountaineers")  # -> Team
teams.by_espn_id("2026")  # -> Team

# Registries are immutable; corrections layer on top.
teams = teams.with_teams(load("my_corrections.csv"))
```

**League is a name context, not a namespace.** The same school in the same
season has different names depending on which sport you asked about:
`Montana Grizzlies` / `Montana Lady Griz`, `Massachusetts Minutemen` /
`Massachusetts Minutewomen`. Because names pool into one team, you can
translate across that boundary:

```python
current_name("Montana Grizzlies", league="ncaawbb")  # "Montana Lady Griz"
current_name("Montana Lady Griz", league="ncaafb")  # "Montana Grizzlies"
```

A rename can also land in one sport before another. ESPN's football feed
called 2026 `Appalachian State Mountaineers` until 2024; both basketball
feeds had said `App State Mountaineers` since 2001. So `name_in(..., 2015)`
has two right answers and needs a league to pick one.

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
# Purdue Northwest is filed under three ids, merged onto 368 in the data
teams.by_espn_id("111911") == teams.by_espn_id("368")  # True
teams.by_espn_id("111911").espn_ids  # ("368", "111995", "111911")
espn_id("Purdue Northwest Pride")  # "368" -- answers with the canonical id
```

Until a duplicate is merged its name matches two teams, so `by_name` raises
`AmbiguousTeamError` while `by_espn_id` keeps working for both. 182 names
in the bundled data are still in that state.

### Bundled data

`call_it_what_you_want/data/<namespace>.csv`. Required columns
`espn_id,name,year,source`; optional `league` and `same_as`, which may be
blank or left out entirely, so a file written without them still loads.
Column order doesn't matter. One row per observation.

`ncaa.csv` is an ESPN college pull: 1,777 teams, 42,520 observations,
seasons 2001-2025, every row `source=espn`. Split by league that's 14,965
football, 15,165 men's basketball, and 12,390 women's basketball.

## Recording what you find

The bundled data will always be behind whatever you're actually scraping,
so an application can hand back what it runs into. `record` files an
observation, and returns whether it was one the data didn't already have:

```python
from call_it_what_you_want import record

record("2426", "Navy Midshipmen", 2025)  # True, and warns
record("2426", "Navy Midshipmen", 2025)  # False, silent
```

A new observation takes effect immediately -- `espn_id("Navy
Midshipmen")` answers on the next line -- and warns so it doesn't slip
by: `NewTeamWarning` for an ESPN id the data didn't have, `NewNameWarning`
for a new name on a team it did. If the new id's name is already on
another team, the warning says so, since that's usually a duplicate ESPN
record that wants a `same_as` row rather than a team of its own.

Filter them like any other warning:

```python
import warnings
from call_it_what_you_want import NewRecordWarning

warnings.simplefilter("ignore", NewRecordWarning)  # quiet
warnings.simplefilter("error", NewRecordWarning)  # or fail the run
```

Recording is additive only. It appends rows and never edits or deletes
one, because contradicting data that shipped is a judgement call rather
than something an application should make in passing.

### Where the rows go

Not into the installed package -- that's read-only under most installs
and a reinstall would wipe it. They go to one file per namespace under
`$CIWYW_DATA_DIR`, else `$XDG_DATA_HOME/call-it-what-you-want`, else
`~/.local/share/call-it-what-you-want`, and get layered over the bundled
data on load. Set `CIWYW_DATA_DIR` per project to keep one application's
discoveries out of another's, and use `default_teams(include_local=False)`
for just what shipped.

That file is a staging area, so getting the rows into the package is the
other half of the loop. Install the CLI with the `cli` extra:

```shell
uv add 'call-it-what-you-want[cli]'
```

```shell
ciwyw where    # the file rows are written to, and how many are in it
ciwyw new      # just the rows that aren't in the package yet
ciwyw count    # how many teams, bundled vs. recorded locally
ciwyw show     # the bundled CSV with those rows appended
```

`ciwyw show --output` writes it, which is the commit:

```shell
ciwyw show --output call_it_what_you_want/data/ncaa.csv
git diff  # exactly the new rows -- everything else passes through as written
ciwyw clear --yes  # once they're committed, so they aren't carried twice
```

Every command takes a namespace as its first argument (`ciwyw new nfl`)
and defaults to `ncaa`.

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
