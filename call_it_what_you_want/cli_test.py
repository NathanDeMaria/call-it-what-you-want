from pathlib import Path

import pytest

from .cli import Records, main
from .data import NewNameWarning, NewTeamWarning, record, teams_from_csv

# An id ESPN will never issue, so a real pull landing in the bundled data
# can't turn this test's "team nobody has seen" into one somebody has.
UNSEEN = "test-1"


@pytest.fixture
def records() -> Records:
    return Records()


def test_show_prints_the_merged_csv(
    records: Records, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.warns(NewNameWarning):
        record("349", "Army West Point", 2015)

    records.show()

    out = capsys.readouterr().out.splitlines()
    assert out[0] == "espn_id,name,year,source,league,same_as"
    assert out[-1] == "349,Army West Point,2015,espn,,"


def test_show_writes_a_file_that_loads(
    records: Records, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.warns(NewTeamWarning):
        record(UNSEEN, "Nowhere State Armadillos", 2025)
    path = tmp_path / "ncaa.csv"

    records.show(output=str(path))

    assert capsys.readouterr().out == ""
    rebuilt = teams_from_csv(path.read_text().splitlines())
    assert rebuilt.espn_id("Nowhere State Armadillos") == UNSEEN


def test_new_prints_only_the_local_rows(
    records: Records, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.warns(NewNameWarning):
        record("349", "Army West Point", 2015)

    records.new()

    assert capsys.readouterr().out.splitlines() == [
        "espn_id,name,year,source,league,same_as",
        "349,Army West Point,2015,espn,,",
    ]


def test_new_says_so_when_there_is_nothing(
    records: Records, capsys: pytest.CaptureFixture[str]
) -> None:
    records.new()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Nothing recorded locally" in captured.err


def test_where_prints_the_path(
    records: Records, local_records: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records.where()

    assert capsys.readouterr().out.strip() == str(local_records / "ncaa.csv")


def test_count_separates_bundled_from_local(
    records: Records, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.warns(NewTeamWarning):
        record(UNSEEN, "Nowhere State Armadillos", 2025)

    records.count()

    assert "1 added locally" in capsys.readouterr().out


def test_clear_needs_confirmation(records: Records) -> None:
    with pytest.warns(NewNameWarning):
        record("349", "Army West Point", 2015)

    with pytest.raises(SystemExit, match="pass --yes"):
        records.clear()


def test_clear_with_yes(records: Records, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.warns(NewNameWarning):
        record("349", "Army West Point", 2015)

    records.clear(yes=True)

    assert "Deleted" in capsys.readouterr().out
    records.new()
    assert "Nothing recorded locally" in capsys.readouterr().err


def test_clear_with_nothing_recorded(
    records: Records, capsys: pytest.CaptureFixture[str]
) -> None:
    records.clear()

    assert "Nothing recorded locally" in capsys.readouterr().out


def test_the_entry_point_dispatches(
    monkeypatch: pytest.MonkeyPatch,
    local_records: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.argv", ["ciwyw", "where"])

    main()

    assert str(local_records / "ncaa.csv") in capsys.readouterr().out
