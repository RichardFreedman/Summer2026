import pandas as pd

from supergenres import song_supergenres, apply_supergenre_preference


SG_MAP = {"indie rock": "Rock", "jazz": "Jazz", "chill": "Other"}


def test_song_supergenres_matches_any_tag_and_ignores_unknown():
    assert song_supergenres("chill,indie rock,unknown", SG_MAP) == {"Other", "Rock"}
    assert song_supergenres("", SG_MAP) == {"Other"}


def _df():
    return pd.DataFrame({
        "title": list("abcde"),
        "supergenres": [{"Rock"}, {"Jazz"}, {"Rock", "Jazz"}, {"Other"}, {"Pop"}],
    })


def test_no_selection_returns_df_unchanged():
    df, hard = apply_supergenre_preference(_df(), [], min_songs=2)
    assert len(df) == 5 and hard is False


def test_hard_filter_when_enough_matches():
    df, hard = apply_supergenre_preference(_df(), ["Rock"], min_songs=2)
    assert hard is True
    assert list(df["title"]) == ["a", "c"]


def test_soft_scoring_when_too_few_matches():
    df, hard = apply_supergenre_preference(_df(), ["Pop"], min_songs=2)
    assert hard is False
    assert len(df) == 5
    assert list(df["genre_fit"]) == [0.0, 0.0, 0.0, 0.0, 1.0]
