import pytest

from .types import (
    ESPN,
    NCAAFB,
    NCAAMBB,
    NCAAWBB,
    AmbiguousNameError,
    NoNamesError,
    Team,
    TeamName,
)

ARMY = Team(
    espn_id="349",
    names=(
        TeamName("Army Black Knights", 2012, ESPN),
        TeamName("Army Knights", 2025, ESPN),
        TeamName("Army", 2025, "footballlocks"),
    ),
)

# The same school, called something different depending on the sport and
# the gender of the team. One id, one school, three names in one season.
UNLV = Team(
    espn_id="2439",
    names=(
        TeamName("UNLV Rebels", 2025, ESPN, NCAAFB),
        TeamName("UNLV Rebels", 2025, ESPN, NCAAMBB),
        TeamName("UNLV Lady Rebels", 2025, ESPN, NCAAWBB),
    ),
)


def test_current_name_is_the_latest_year() -> None:
    assert ARMY.current_name() == "Army Knights"


def test_current_name_is_per_source() -> None:
    assert ARMY.current_name("footballlocks") == "Army"


def test_current_name_needs_the_source_on_record() -> None:
    with pytest.raises(NoNamesError, match="espn"):
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


def test_current_name_per_league() -> None:
    assert UNLV.current_name(league=NCAAFB) == "UNLV Rebels"
    assert UNLV.current_name(league=NCAAMBB) == "UNLV Rebels"
    assert UNLV.current_name(league=NCAAWBB) == "UNLV Lady Rebels"


def test_a_name_that_varies_by_league_raises_without_one() -> None:
    # The whole point: two names tie for the latest season, so picking one
    # would be a silent wrong answer.
    with pytest.raises(AmbiguousNameError, match="went by 2 names in 2025"):
        UNLV.current_name()


def test_the_ambiguity_message_names_the_leagues() -> None:
    with pytest.raises(AmbiguousNameError, match="ncaawbb"):
        UNLV.current_name()


def test_a_league_free_name_holds_in_every_league() -> None:
    # Army's names were recorded without a league, so asking about one
    # still finds them rather than coming back empty.
    assert ARMY.current_name(league=NCAAFB) == "Army Knights"
    assert ARMY.current_name(league=NCAAWBB) == "Army Knights"


def test_a_league_specific_name_is_hidden_from_other_leagues() -> None:
    assert TeamName("UNLV Lady Rebels", 2025, ESPN, NCAAWBB) not in UNLV.names_from(
        ESPN, league=NCAAFB
    )


def test_a_league_with_nothing_on_record() -> None:
    with pytest.raises(NoNamesError, match="ncaambb"):
        UNLV.names_from("footballlocks", league=NCAAMBB)


def test_name_in_respects_league() -> None:
    team = Team(
        espn_id="1",
        names=(
            TeamName("Old Name", 2010, ESPN, NCAAWBB),
            TeamName("New Lady Name", 2025, ESPN, NCAAWBB),
            TeamName("Mens Name", 2025, ESPN, NCAAFB),
        ),
    )

    assert team.name_in(2015, league=NCAAWBB) == "Old Name"


def test_names_that_agree_across_leagues_need_no_league() -> None:
    # Duke is 150 in football and both basketballs and called the same
    # thing in all of them, so there's nothing to disambiguate.
    duke = Team(
        espn_id="150",
        names=tuple(
            TeamName("Duke Blue Devils", 2025, ESPN, league)
            for league in (NCAAFB, NCAAMBB, NCAAWBB)
        ),
    )

    assert duke.current_name() == "Duke Blue Devils"


def test_espn_ids_lists_the_canonical_id_first() -> None:
    team = Team("2341", (TeamName("LIU Sharks", 2025),), ("112358",))

    assert team.espn_ids == ("2341", "112358")


def test_a_team_with_no_duplicate_ids() -> None:
    assert ARMY.espn_ids == ("349",)
