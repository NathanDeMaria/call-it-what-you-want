import warnings
from pathlib import Path

import pytest

from . import current_name, espn_id
from .data import (
    NewNameWarning,
    NewTeamWarning,
    default_teams,
    local_csv,
    merged_csv,
    record,
    teams_from_csv,
)
from .local import ENV_VAR, clear_local, local_dir, local_path, read_local
from .types import NCAAFB, NCAAWBB

# Ids ESPN will never issue. Tests that need a team the data has never
# seen used to borrow plausible-looking numbers, which stopped being
# unseen the moment a real pull landed -- so they say so out loud now.
UNSEEN = "test-1"
ALSO_UNSEEN = "test-2"

# On record in the bundled pull, either side of ESPN's 2024 rename.
APP_STATE = "2026"
APP_STATE_NOW = "App State Mountaineers"
APP_STATE_THEN = "Appalachian State Mountaineers"


def test_local_dir_follows_the_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_VAR, "/somewhere/else")

    assert local_dir() == Path("/somewhere/else")


def test_local_dir_falls_back_to_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR)
    monkeypatch.setenv("XDG_DATA_HOME", "/xdg")

    assert local_dir() == Path("/xdg/call-it-what-you-want")


def test_local_dir_falls_back_to_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/nobody")))

    assert local_dir() == Path("/home/nobody/.local/share/call-it-what-you-want")


def test_a_new_name_for_a_known_team_warns() -> None:
    with pytest.warns(NewNameWarning, match="Army West Point"):
        assert record("349", "Army West Point", 2015) is True


def test_a_new_name_is_usable_immediately() -> None:
    with pytest.warns(NewNameWarning):
        record(APP_STATE, "Appalachian State", 2015)

    # No reload, no cache to clear by hand -- the lookup that comes next
    # in the same run already knows the name.
    assert espn_id("Appalachian State") == APP_STATE
    assert current_name("Appalachian State") == APP_STATE_NOW


def test_recording_the_same_observation_twice_does_nothing(
    local_records: Path,
) -> None:
    with pytest.warns(NewNameWarning):
        record("349", "Army West Point", 2015)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert record("349", "Army West Point", 2015) is False

    # Header plus the one row: the second call didn't append.
    assert len(read_local("ncaa")) == 2
    assert local_records.exists()


def test_an_observation_already_in_the_bundled_data_does_nothing() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert record("349", "Army Black Knights", 2025, league=NCAAFB) is False

    assert read_local("ncaa") == []


def test_an_unknown_id_warns_that_the_team_is_new() -> None:
    with pytest.warns(NewTeamWarning, match="isn't in the 'ncaa' data"):
        record(UNSEEN, "Nowhere State Armadillos", 2025)

    assert espn_id("Nowhere State Armadillos") == UNSEEN


def test_a_new_id_reusing_a_known_name_points_at_same_as() -> None:
    # The duplicate-ESPN-record case: ESPN filed a school twice, so the
    # name lands on an id that isn't the one already carrying it.
    with pytest.warns(NewTeamWarning, match="same_as"):
        record(UNSEEN, APP_STATE_NOW, 2025, league=NCAAFB)


def test_records_carry_a_league() -> None:
    with pytest.warns(NewTeamWarning, match="ncaawbb"):
        record(UNSEEN, "Nowhere State Lady Armadillos", 2025, league=NCAAWBB)

    with pytest.warns(NewNameWarning, match="ncaafb"):
        record(UNSEEN, "Nowhere State Armadillos", 2025, league=NCAAFB)

    assert (
        current_name("Nowhere State Lady Armadillos", league=NCAAFB)
        == "Nowhere State Armadillos"
    )


def test_records_survive_into_a_fresh_registry() -> None:
    with pytest.warns(NewNameWarning):
        record("349", "Army West Point", 2015)
    default_teams.cache_clear()

    assert "Army West Point" in default_teams()


def test_the_bundled_data_can_be_read_without_local_records() -> None:
    with pytest.warns(NewNameWarning):
        record("349", "Army West Point", 2015)

    assert "Army West Point" not in default_teams("ncaa", include_local=False)


def test_the_local_file_gets_one_header() -> None:
    with pytest.warns(NewTeamWarning):
        record(UNSEEN, "Nowhere State Armadillos", 2025)
    with pytest.warns(NewNameWarning):
        record(UNSEEN, "Nowhere State", 2025, source="footballlocks")

    lines = read_local("ncaa")

    assert lines[0].startswith("espn_id,")
    assert len(lines) == 3


def test_local_csv_holds_only_what_was_recorded() -> None:
    with pytest.warns(NewNameWarning):
        record("349", "Army West Point", 2015)

    rows = local_csv().splitlines()

    assert rows == [
        "espn_id,name,year,source,league,same_as",
        "349,Army West Point,2015,espn,,",
    ]


def test_local_csv_is_empty_with_nothing_recorded() -> None:
    assert local_csv() == ""


def test_merged_csv_is_the_bundled_file_when_nothing_is_recorded() -> None:
    merged = merged_csv().splitlines()

    assert merged[0] == "espn_id,name,year,source,league,same_as"
    assert f"{APP_STATE},{APP_STATE_NOW},2025,espn,ncaafb," in merged
    assert f"{APP_STATE},{APP_STATE_THEN},2015,espn,ncaafb," in merged


def test_merged_csv_appends_the_local_rows() -> None:
    with pytest.warns(NewNameWarning):
        record(APP_STATE, "Appalachian State", 2015)

    merged = merged_csv().splitlines()

    assert merged[-1] == f"{APP_STATE},Appalachian State,2015,espn,,"
    assert f"{APP_STATE},{APP_STATE_NOW},2025,espn,ncaafb," in merged


def test_merged_csv_reloads_into_the_same_registry() -> None:
    # The output is meant to be committed over the bundled file, so it
    # has to parse back into what's in memory now.
    with pytest.warns(NewTeamWarning):
        record(ALSO_UNSEEN, "Nowhere State Armadillos", 2025)

    rebuilt = teams_from_csv(merged_csv().splitlines())

    assert {t.espn_id for t in rebuilt} == {t.espn_id for t in default_teams()}
    assert rebuilt.by_espn_id(ALSO_UNSEEN).espn_id == ALSO_UNSEEN


def test_clear_local_removes_the_records() -> None:
    with pytest.warns(NewNameWarning):
        record("349", "Army West Point", 2015)

    assert clear_local("ncaa") is True
    assert local_csv() == ""
    assert not local_path("ncaa").exists()


def test_clear_local_with_nothing_to_clear() -> None:
    assert clear_local("ncaa") is False
