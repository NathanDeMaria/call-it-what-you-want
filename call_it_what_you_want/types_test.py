import pytest

from .types import ESPN, NoNamesError, Team, TeamName

ARMY = Team(
    espn_id="349",
    names=(
        TeamName("Army Black Knights", 2012, ESPN),
        TeamName("Army Knights", 2025, ESPN),
        TeamName("Army", 2025, "footballlocks"),
    ),
)


def test_current_name_is_the_latest_year() -> None:
    assert ARMY.current_name() == "Army Knights"


def test_current_name_is_per_source() -> None:
    assert ARMY.current_name("footballlocks") == "Army"


def test_current_name_needs_the_source_on_record() -> None:
    with pytest.raises(NoNamesError, match="espn, footballlocks"):
        ARMY.current_name("sports-reference")


def test_name_in_the_year_of_an_observation() -> None:
    assert ARMY.name_in(2012) == "Army Black Knights"


def test_name_in_a_year_with_no_observation_holds_the_last_one() -> None:
    # Nothing recorded between 2012 and 2025, so the team is assumed to
    # have kept the name it was last seen with.
    assert ARMY.name_in(2015) == "Army Black Knights"
    assert ARMY.name_in(2024) == "Army Black Knights"


def test_name_in_a_year_after_every_observation() -> None:
    assert ARMY.name_in(2030) == "Army Knights"


def test_name_in_a_year_before_every_observation() -> None:
    # No way to know what came before the first sighting, so the earliest
    # name on record is the best guess.
    assert ARMY.name_in(1950) == "Army Black Knights"


def test_repeated_observations_of_one_name() -> None:
    # The same name seen every season is the normal case, and shouldn't
    # change what "current" means.
    team = Team(
        espn_id="1",
        names=tuple(
            TeamName("Ohio State Buckeyes", year) for year in range(2000, 2026)
        ),
    )

    assert team.current_name() == "Ohio State Buckeyes"
    assert team.name_in(2007) == "Ohio State Buckeyes"


def test_names_from_keeps_recorded_order() -> None:
    assert ARMY.names_from(ESPN) == (
        TeamName("Army Black Knights", 2012, ESPN),
        TeamName("Army Knights", 2025, ESPN),
    )


def test_a_tie_falls_to_the_first_recorded() -> None:
    team = Team(
        espn_id="1",
        names=(TeamName("First", 2025), TeamName("Second", 2025)),
    )

    assert team.current_name() == "First"
