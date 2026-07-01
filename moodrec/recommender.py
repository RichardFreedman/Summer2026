"""Core MoodRec logic — extracted from recommender.ipynb for use in the Streamlit app."""

import os
import re
import json
import time
import threading
import concurrent.futures

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OLLAMA_MODEL     = "llama3.2"
LASTFM_API_KEY   = os.environ.get("LASTFM_API_KEY", "")

SONG_TAGS_CACHE  = "song_tags_cache.json"
CACHE_FILE       = "tag_scores_cache.json"
GENRE_FIT_CACHE  = "genre_fit_cache.json"
LASTFM_WORKERS   = 5
SCORE_BATCH      = 10

# ---------------------------------------------------------------------------
# Part 1 — Core algorithm
# ---------------------------------------------------------------------------

def generate_waypoints(current_valence, current_energy,
                       desired_valence, desired_energy, n_steps=5):
    valence_steps = np.linspace(current_valence, desired_valence, n_steps)
    energy_steps  = np.linspace(current_energy,  desired_energy,  n_steps)
    return list(zip(valence_steps, energy_steps))


def find_closest_song(df, target_valence, target_energy, exclude_indices=None,
                      use_tag_features=True,    tag_weight=0.3,
                      genre_request=None,        genre_weight=0.4,
                      use_audio_features=True,   audio_feature_weight=0.2,
                      prev_valence=None,          prev_energy=None,
                      journey_dv=0,              journey_de=0,
                      backtrack_tolerance=0.05):
    if exclude_indices is None:
        exclude_indices = []
    candidates = df[~df.index.isin(exclude_indices)].copy()

    if prev_valence is not None and prev_energy is not None:
        filtered = candidates.copy()
        if journey_dv > 0:
            filtered = filtered[filtered["valence"] >= prev_valence - backtrack_tolerance]
        elif journey_dv < 0:
            filtered = filtered[filtered["valence"] <= prev_valence + backtrack_tolerance]
        if journey_de > 0:
            filtered = filtered[filtered["energy"] >= prev_energy - backtrack_tolerance]
        elif journey_de < 0:
            filtered = filtered[filtered["energy"] <= prev_energy + backtrack_tolerance]
        if len(filtered) >= 1:
            candidates = filtered

    dist = (
        (candidates["valence"] - target_valence) ** 2
        + (candidates["energy"]  - target_energy)  ** 2
    )

    if use_tag_features and "tag_valence_shift" in df.columns:
        tv_norm = (candidates["tag_valence_shift"] + 1) / 2
        ta_norm = (candidates["tag_arousal_shift"] + 1) / 2
        dist += tag_weight * (
            (tv_norm - target_valence) ** 2
            + (ta_norm - target_energy)  ** 2
        )

    if genre_request and "genre_fit" in df.columns:
        dist += genre_weight * (1 - candidates["genre_fit"]) ** 2

    if use_audio_features and all(
        c in df.columns for c in ["acousticness", "danceability", "tempo_norm", "loudness_norm"]
    ):
        acousticness_target = 1 - target_energy
        danceability_target = target_valence
        tempo_target        = target_energy
        loudness_target     = target_energy
        dist += audio_feature_weight * (
            (candidates["acousticness"]   - acousticness_target) ** 2
            + (candidates["danceability"] - danceability_target) ** 2
            + (candidates["tempo_norm"]   - tempo_target)        ** 2
            + (candidates["loudness_norm"]- loudness_target)     ** 2
        )

    candidates["distance"] = np.sqrt(dist)
    return candidates.nsmallest(1, "distance").iloc[0]


def build_playlist(df, current_valence, current_energy,
                   desired_valence, desired_energy, n_steps=5,
                   genre_request=None,       genre_weight=0.4,
                   use_audio_features=True,  audio_feature_weight=0.2,
                   use_tag_features=True,    tag_weight=0.3,
                   backtrack_tolerance=0.05):
    waypoints  = generate_waypoints(
        current_valence, current_energy,
        desired_valence, desired_energy, n_steps=n_steps
    )
    journey_dv = int(np.sign(desired_valence - current_valence))
    journey_de = int(np.sign(desired_energy  - current_energy))

    selected, used_indices = [], []
    prev_v, prev_e = current_valence, current_energy

    for i, (target_v, target_e) in enumerate(waypoints):
        song = find_closest_song(
            df, target_v, target_e,
            exclude_indices=used_indices,
            use_tag_features=use_tag_features,
            tag_weight=tag_weight,
            genre_request=genre_request,
            genre_weight=genre_weight,
            use_audio_features=use_audio_features,
            audio_feature_weight=audio_feature_weight,
            prev_valence=prev_v,
            prev_energy=prev_e,
            journey_dv=journey_dv,
            journey_de=journey_de,
            backtrack_tolerance=backtrack_tolerance,
        )
        used_indices.append(song.name)
        prev_v = song["valence"]
        prev_e = song["energy"]
        selected.append({
            "step":           i + 1,
            "title":          song.get("title",  "Unknown"),
            "artist":         song.get("artist", "Unknown"),
            "valence":        round(song["valence"], 3),
            "energy":         round(song["energy"],  3),
            "genre_fit":      round(song.get("genre_fit", 1.0), 3),
            "target_valence": round(target_v, 3),
            "target_energy":  round(target_e, 3),
            "distance":       round(song["distance"], 4),
        })
    return pd.DataFrame(selected)


# ---------------------------------------------------------------------------
# Part 1b.1 — Tag sourcing helpers
# ---------------------------------------------------------------------------

def _load_song_tags_cache() -> dict:
    if os.path.exists(SONG_TAGS_CACHE):
        with open(SONG_TAGS_CACHE) as f:
            return json.load(f)
    return {}


def _save_song_tags_cache(cache: dict) -> None:
    with open(SONG_TAGS_CACHE, "w") as f:
        json.dump(cache, f, indent=2)


def _parse_json(text: str):
    if "```" in text:
        parts = text.split("```")
        text = parts[1] if len(parts) >= 2 else parts[0]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _clean_artist(artist: str) -> str:
    primary = artist.split(";")[0].strip()
    return re.sub(r'\s+(ft\.?|feat\.?|featuring)\s+.*', '', primary, flags=re.IGNORECASE).strip()


def _lastfm_get(method: str, params: dict) -> list:
    resp = requests.get(
        "https://ws.audioscrobbler.com/2.0/",
        params={"method": method, "api_key": LASTFM_API_KEY,
                "format": "json", "autocorrect": 1, **params},
        timeout=10,
    )
    resp.raise_for_status()
    raw = resp.json().get("toptags", {}).get("tag", [])
    return [t["name"].lower() for t in raw[:6]]


def _fetch_tags_from_lastfm(title: str, artist: str) -> list:
    if not LASTFM_API_KEY:
        raise ValueError("LASTFM_API_KEY is empty — paste your key into recommender.py.")
    clean = _clean_artist(artist)
    for query_artist in dict.fromkeys([clean, artist]):
        try:
            tags = _lastfm_get("track.gettoptags", {"track": title, "artist": query_artist})
            if tags:
                return tags
            tags = _lastfm_get("artist.gettoptags", {"artist": query_artist})
            if tags:
                return tags
        except Exception:
            pass
    return []


def _csv_genres(row) -> list:
    val = row.get("genres", None)
    if not val or (isinstance(val, float)):
        return []
    return [g.strip().lower() for g in str(val).split(",") if g.strip()]


def generate_all_tags(df, progress_callback=None) -> dict:
    """Hybrid tag sourcing: CSV Genres → Last.fm track tags → Last.fm artist tags."""
    cache    = _load_song_tags_cache()
    result   = {}
    to_fetch = []

    for _, row in df.iterrows():
        csv_tags = _csv_genres(row)
        if csv_tags:
            result[row["title"]] = csv_tags
        elif f"{row['title']}|||{row['artist']}" in cache:
            result[row["title"]] = cache[f"{row['title']}|||{row['artist']}"]
        else:
            to_fetch.append((row["title"], row["artist"]))

    if to_fetch:
        counter = {"done": 0}
        lock    = threading.Lock()

        def fetch_one(args):
            title, artist = args
            time.sleep(0.2)
            return title, artist, _fetch_tags_from_lastfm(title, artist)

        with concurrent.futures.ThreadPoolExecutor(max_workers=LASTFM_WORKERS) as ex:
            futures = {ex.submit(fetch_one, pair): pair for pair in to_fetch}
            for future in concurrent.futures.as_completed(futures):
                title, artist, tags = future.result()
                with lock:
                    counter["done"] += 1
                    if progress_callback:
                        progress_callback(counter["done"], len(to_fetch), title)
                if tags:
                    cache[f"{title}|||{artist}"] = tags
                    result[title] = tags
        _save_song_tags_cache(cache)

    return result


# ---------------------------------------------------------------------------
# Part 1b.2 — LLM tag scoring
# ---------------------------------------------------------------------------

def _load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict) -> None:
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def _score_tag_single(tag: str, llm: ChatOllama, cache: dict) -> None:
    prompt = (
        f'Score the music genre/mood tag "{tag}" on three dimensions.\n'
        "Return ONLY valid JSON with exactly this structure (no extra text):\n"
        "{\n"
        '  "valence_shift": <float -1 to 1, negative=unpleasant, positive=pleasant>,\n'
        '  "arousal_shift": <float -1 to 1, negative=calm, positive=energised>,\n'
        '  "emotions": {"<label>": <weight 0-1>, ...}\n'
        "}\n"
        "Include 3-5 discrete emotion labels in the emotions dict."
    )
    try:
        result = _parse_json(llm.invoke(prompt).content)
        cache[tag] = result
        _save_cache(cache)
    except Exception:
        pass


def _score_tag_batch(tags: list, llm: ChatOllama, cache: dict) -> None:
    prompt = (
        "Score each of the following music genre/mood tags on three dimensions.\n"
        "Return ONLY a valid JSON object mapping each tag to its scores (no extra text):\n"
        "{\n"
        '  "<tag>": {"valence_shift": <-1 to 1>, "arousal_shift": <-1 to 1>, '
        '"emotions": {"<label>": <0-1>, ...}},\n'
        "  ...\n"
        "}\n"
        "Tags to score: " + json.dumps(tags) + "\n"
        "Include 3-5 emotion labels per tag."
    )
    try:
        results = _parse_json(llm.invoke(prompt).content)
        for tag in tags:
            if tag in results:
                cache[tag] = results[tag]
                _save_cache(cache)
    except Exception:
        for tag in tags:
            _score_tag_single(tag, llm, cache)


def aggregate_tag_scores(track_tags: dict, llm: ChatOllama,
                         progress_callback=None) -> dict:
    cache       = _load_cache()
    unique_tags = sorted({t for tags in track_tags.values() for t in tags})
    to_score    = [t for t in unique_tags if t not in cache]
    n_batches   = -(-len(to_score) // SCORE_BATCH) if to_score else 0

    for i in range(0, len(to_score), SCORE_BATCH):
        batch = to_score[i : i + SCORE_BATCH]
        b_num = i // SCORE_BATCH + 1
        _score_tag_batch(batch, llm, cache)
        if progress_callback:
            progress_callback(b_num, n_batches, batch)

    track_agg = {}
    for title, tags in track_tags.items():
        scores = [cache[t] for t in tags if t in cache]
        if not scores:
            continue
        avg_val = float(np.mean([s["valence_shift"] for s in scores]))
        avg_aro = float(np.mean([s["arousal_shift"] for s in scores]))
        combined: dict = {}
        for s in scores:
            for emo, w in s.get("emotions", {}).items():
                combined[emo] = combined.get(emo, 0.0) + w
        for emo in combined:
            combined[emo] /= len(scores)
        top3     = sorted(combined.items(), key=lambda x: -x[1])[:3]
        dominant = top3[0][0] if top3 else "neutral"
        track_agg[title] = {
            "tag_valence_shift": avg_val,
            "tag_arousal_shift": avg_aro,
            "top_emotions":      top3,
            "dominant_emotion":  dominant,
        }
    return track_agg


# ---------------------------------------------------------------------------
# Part 1b — Genre fit scoring
# ---------------------------------------------------------------------------

def _load_genre_cache() -> dict:
    if os.path.exists(GENRE_FIT_CACHE):
        with open(GENRE_FIT_CACHE) as f:
            return json.load(f)
    return {}


def _save_genre_cache(cache: dict) -> None:
    with open(GENRE_FIT_CACHE, "w") as f:
        json.dump(cache, f, indent=2)


def score_genre_fit(title: str, artist: str, genre_request: str,
                    llm, cache: dict) -> float:
    key = f"{title}|||{artist}|||{genre_request}"
    if key in cache:
        return cache[key]

    prompt = (
        f'How well does "{title}" by {artist} fit the genre/mood "{genre_request}"?\n'
        "Return ONLY a single float between 0.0 (no fit) and 1.0 (perfect fit). No other text."
    )
    response = llm.invoke(prompt)
    try:
        score = float(response.content.strip())
        score = max(0.0, min(1.0, score))
    except ValueError:
        score = 0.5

    cache[key] = score
    _save_genre_cache(cache)
    return score


def score_all_genre_fits(df, genre_request: str, llm,
                         progress_callback=None):
    if not genre_request:
        df["genre_fit"] = 1.0
        return df

    cache  = _load_genre_cache()
    total  = len(df)
    scores = []
    for i, (_, row) in enumerate(df.iterrows()):
        score = score_genre_fit(row["title"], row["artist"], genre_request, llm, cache)
        scores.append(score)
        if progress_callback:
            progress_callback(i + 1, total, row["title"])

    df["genre_fit"] = scores
    return df


# ---------------------------------------------------------------------------
# Pipeline helpers used by app.py
# ---------------------------------------------------------------------------

def load_dataframe() -> pd.DataFrame:
    df = pd.read_csv("MoodRec_Songs.csv")
    df = df.rename(columns={"Track Name": "title", "Artist Name(s)": "artist"})
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    keep = ["title", "artist", "valence", "energy",
            "danceability", "acousticness", "loudness", "tempo",
            "instrumentalness", "genres"]
    df = df[keep].copy()
    df["tempo_norm"]    = (df["tempo"]    - df["tempo"].min())    / (df["tempo"].max()    - df["tempo"].min())
    df["loudness_norm"] = (df["loudness"] - df["loudness"].min()) / (df["loudness"].max() - df["loudness"].min())
    return df.reset_index(drop=True)


def enrich_dataframe(df: pd.DataFrame, llm: ChatOllama) -> pd.DataFrame:
    track_tags = generate_all_tags(df)
    track_agg  = aggregate_tag_scores(track_tags, llm)

    df["tag_valence_shift"] = df["title"].map(
        lambda t: track_agg.get(t, {}).get("tag_valence_shift", 0.0)
    )
    df["tag_arousal_shift"] = df["title"].map(
        lambda t: track_agg.get(t, {}).get("tag_arousal_shift", 0.0)
    )
    df["top_emotions"] = df["title"].map(
        lambda t: track_agg.get(t, {}).get("top_emotions", [])
    )
    df["dominant_emotion"] = df["title"].map(
        lambda t: track_agg.get(t, {}).get("dominant_emotion", "neutral")
    )
    return df
