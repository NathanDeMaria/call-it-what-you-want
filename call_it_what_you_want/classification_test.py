import pytest

from .classification import (
    Classifications,
    ConflictingClassificationWarning,
    NewClassificationWarning,
    TeamClassification,
    classifications_from_csv,
    default_classifications,
    local_classifications_csv,
    record_classification,
)

_CSV = """espn_id,year,league,division,conference
2633,2019,ncaafb,NCAA Division III,
2633,2021,ncaafb,FCS,Pioneer
30,2023,ncaafb,FBS,Pac-12
"""


def _table() -> Classifications:
    return classifications_from_csv(_CSV.splitlines())


def _division(
    table: Classifications, espn_id: str, year: int, league: str = "ncaafb"
) -> str | None:
    found = table.classification_in(espn_id, year, league)
    return None if found is None else found.division


def test_a_teams_classification_is_read_back() -> None:
    assert _table().classification_in("30", 2023, "ncaafb") == TeamClassification(
        espn_id="30", year=2023, league="ncaafb", division="FBS", conference="Pac-12"
    )


def test_a_blank_conference_is_none() -> None:
    """A tier ESPN doesn't file under a conference still gets a division."""
    found = _table().classification_in("2633", 2019, "ncaafb")

    assert found is not None
    assert found.conference is None


def test_a_team_keeps_its_division_until_it_is_seen_somewhere_else() -> None:
    """Observations are sparse, so 2020 answers with what 2019 saw."""
    table = _table()

    assert _division(table, "2633", 2020) == "NCAA Division III"
    assert _division(table, "2633", 2021) == "FCS"
    assert _division(table, "2633", 2025) == "FCS"


def test_a_year_before_every_observation_gets_the_earliest() -> None:
    """Where a team started is the best guess at what came before it."""
    assert _division(_table(), "2633", 2005) == "NCAA Division III"


def test_an_unclassified_team_is_none_rather_than_an_error() -> None:
    assert _table().classification_in("999999", 2023, "ncaafb") is None


def test_division_is_per_league() -> None:
    """The same school is FBS in football and D-I in basketball."""
    table = classifications_from_csv(
        [
            "espn_id,year,league,division,conference",
            "30,2023,ncaafb,FBS,Pac-12",
            "30,2023,ncaambb,D-I,Pac-12",
        ]
    )

    assert _division(table, "30", 2023, "ncaafb") == "FBS"
    assert _division(table, "30", 2023, "ncaambb") == "D-I"


def test_two_places_in_one_season_warns_and_keeps_the_first() -> None:
    with pytest.warns(ConflictingClassificationWarning):
        table = classifications_from_csv(
            [
                "espn_id,year,league,division,conference",
                "30,2023,ncaafb,FBS,Pac-12",
                "30,2023,ncaafb,FCS,Pioneer",
            ]
        )

    assert _division(table, "30", 2023) == "FBS"


def test_a_year_that_is_not_a_number_says_which_row() -> None:
    with pytest.raises(ValueError, match="Row 2"):
        classifications_from_csv(
            ["espn_id,year,league,division,conference", "30,twenty,ncaafb,FBS,Pac-12"]
        )


def test_an_unexpected_column_is_rejected() -> None:
    with pytest.raises(ValueError, match="unexpected"):
        classifications_from_csv(
            ["espn_id,year,league,division,mascot", "30,2023,x,y,z"]
        )


def test_recording_stages_a_new_observation() -> None:
    with pytest.warns(NewClassificationWarning):
        assert record_classification("30", 2023, "ncaafb", "FBS", conference="Pac-12")

    assert _division(default_classifications(), "30", 2023) == "FBS"
    assert "30,2023,ncaafb,FBS,Pac-12" in local_classifications_csv()


def test_recording_the_same_observation_twice_is_a_no_op() -> None:
    with pytest.warns(NewClassificationWarning):
        record_classification("30", 2023, "ncaafb", "FBS", conference="Pac-12")

    assert not record_classification("30", 2023, "ncaafb", "FBS", conference="Pac-12")


def test_a_second_conference_for_one_season_warns_instead_of_being_recorded() -> None:
    """ESPN lists the odd team under two conferences.

    Staging both would put a conflict in the committed data that warns on
    every load afterwards, so it's said here and dropped.
    """
    with pytest.warns(NewClassificationWarning):
        record_classification(
            "2804", 2023, "ncaafb", "NCAA Division II", conference="CIAA"
        )

    with pytest.warns(ConflictingClassificationWarning, match="already on record"):
        recorded = record_classification(
            "2804", 2023, "ncaafb", "NCAA Division II", conference="Gulf South"
        )

    assert not recorded
    found = default_classifications().recorded_for("2804", 2023, "ncaafb")
    assert found is not None and found.conference == "CIAA"


def test_a_namespace_with_no_bundled_classifications_is_empty_not_an_error() -> None:
    """Every caller of `classification_in` already handles None.

    A namespace nobody has surveyed yet should read as unclassified, not
    as broken.
    """
    assert len(default_classifications("nfl")) == 0
