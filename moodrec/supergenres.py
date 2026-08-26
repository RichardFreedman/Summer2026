"""Deterministic super-genre preference: no LLM calls, just set membership
against the tag -> super-genre mapping cached in supergenre_cache.json."""

import pandas as pd

SUPERGENRE_CACHE = "supergenre_cache.json"

# Order used for prompts and the UI dropdown. "Other" is the catch-all
# bucket and matches most of the library, so it is not offered as a filter.
SUPERGENRES = ["Jazz", "Soul/R&B", "Hip Hop/Rap", "Rock", "Pop", "Folk/Country",
               "Electronic/Dance", "Classical/Orchestral", "World Music", "Other"]
SELECTABLE_SUPERGENRES = [s for s in SUPERGENRES if s != "Other"]


def song_supergenres(all_tags: str, supergenre_map: dict) -> set:
    """Every super-genre any of the song's tags maps to ("Other" if none)."""
    tags = [t for t in (all_tags or "").split(",") if t]
    found = {supergenre_map[t] for t in tags if t in supergenre_map}
    return found or {"Other"}


def apply_supergenre_preference(df: pd.DataFrame, selected: list, min_songs: int):
    """Restrict df to songs in any selected super-genre.

    Returns (df, hard_filtered). If fewer than min_songs match, the full
    frame is returned with a 0/1 genre_fit column instead, so the playlist
    builder can prefer matching songs without running out of candidates.
    """
    if not selected:
        return df, False
    wanted = set(selected)
    matches = df["supergenres"].apply(lambda s: bool(s & wanted))
    if matches.sum() >= min_songs:
        return df[matches].copy(), True
    df = df.copy()
    df["genre_fit"] = matches.astype(float)
    return df, False
