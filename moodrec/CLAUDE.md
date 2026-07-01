# MoodRec — Claude Code Guide

## What this project is

MoodRec has two interfaces that share the same algorithm:

1. **`recommender.ipynb`** — the primary Jupyter notebook; all algorithmic work happens here
2. **`app.py` + `recommender.py`** — a Streamlit web app that imports from `recommender.py`

Both generate iso-principle playlists — sequences of songs that guide a listener from their current emotional state to a desired one, following the music therapy principle of starting where the listener is and shifting gradually.

Emotions are modelled as points in a 2D space: **valence** (unpleasant → pleasant) × **energy** (calm → energized).

**Rule of thumb:** Algorithmic changes go in the notebook first, then are mirrored into `recommender.py`. Never edit `app.py` for logic changes.

## Song library

`MoodRec_Songs.csv` — 367 songs, 24 Spotify columns. Key facts:
- `Genres`: 238/367 populated, comma-separated (e.g. `"jazz rap,east coast hip hop"`)
- `Artist Name(s)`: semicolon-separated for multi-artist tracks
- `Tempo`: 60–208 BPM (min-max normalized → `tempo_norm`)
- `Loudness`: −28.6 to −2.8 dB (min-max normalized → `loudness_norm`)
- `Valence`, `Energy`, `Danceability`, `Acousticness`: already 0–1

## Notebook cell map

| Cell | Role | Touch? |
|------|------|--------|
| [00] | Intro markdown | — |
| [01] | Imports (`pandas`, `numpy`, `matplotlib`, `os`, `re`, `requests`, `concurrent.futures`, `datetime`) | Only to add imports |
| [02] | Part 1 header | — |
| [03] | Original `generate_waypoints`, `euclidean_distance`, `find_closest_song`, `build_playlist` (simple versions — overridden later) | **Never** |
| [04] | Part 2 header | — |
| [05] | CSV loading → `df` with `tempo_norm`, `loudness_norm` | OK |
| [06] | Part 1b header | — |
| [07] | `import json`, `ChatOllama`, `OLLAMA_MODEL`, `LASTFM_API_KEY` | OK |
| [08] | 1b.1 header | — |
| [09] | Last.fm tag fetching: `generate_all_tags`, `_fetch_tags_from_lastfm`, `_clean_artist`, `_csv_genres` | OK |
| [10] | 1b.2 header | — |
| [11] | Ollama tag scoring: `aggregate_tag_scores`, `_score_tag_batch`, `_score_tag_single` | **Never** |
| [12] | Genre fit: `score_genre_fit`, `score_all_genre_fits` | OK |
| [13] | Run tag pipeline, merge `tag_valence_shift`, `tag_arousal_shift`, `dominant_emotion` into `df` | OK |
| [14] | 1b.3 header + audio feature rationale table | OK |
| [15] | Extended `find_closest_song` (overrides [03]) | OK |
| [16] | Extended `build_playlist` (overrides [03]) | OK |
| [17] | 1b.4 header | — |
| [18] | Emotion scatter plot | OK |
| [19] | Step 1 header | — |
| [20] | **User inputs**: `current_valence`, `current_energy`, `desired_valence`, `desired_energy`, `genre_preferences` | OK |
| [21] | Step 2 header | — |
| [22] | Genre scoring + `build_playlist` call → `playlist` DataFrame | OK |
| [23] | Journey visualisation (arrows + target path) | OK |
| [24]–[31] | Feedback / survey / results analysis (removed from notebook) | **Never** |

## Architecture

### Tag pipeline (runs once, cached)
1. `generate_all_tags(df)` — CSV genres merged with Last.fm track/artist tags for every song (367/367) → `song_tags_cache.json`
2. `aggregate_tag_scores(track_tags, llm)` — Ollama scores each unique tag for `valence_shift` [-1,1], `arousal_shift` [-1,1], `emotions` dict → `tag_scores_cache.json`
3. Scores merged into `df` as `tag_valence_shift`, `tag_arousal_shift`, `dominant_emotion`

### Genre fit (runs per genre, cached)
- `score_all_genre_fits(df, genre, llm)` — Ollama scores each song 0–1 for a free-text genre/mood → `genre_fit_cache.json`
- Each song's prompt is grounded with its known tags (`_merged_tags`: CSV genres + cached Last.fm tags from `song_tags_cache.json`), not just title/artist recall
- Multiple genres: scores averaged across genres, result stored in `df["genre_fit"]`
- Note: `genre_fit_cache.json` entries computed before this grounding was added were scored without tag context — delete the cache to force a re-score with grounding for a given genre request

### Playlist generation
- `generate_waypoints` — linear interpolation from current → desired in n steps
- `find_closest_song` — multi-dimensional distance with hard directional band filter:
  - Core: `(valence − target)² + (energy − target)²`
  - Tag features (weight 0.3): `tag_valence_shift` + `tag_arousal_shift` normalised to [0,1]
  - Genre fit (weight 0.4): `(1 − genre_fit)²` penalty
  - Audio features (weight 0.2): `acousticness`, `danceability`, `tempo_norm`, `loudness_norm`
  - Directional filter: hard-exclude songs that backtrack > `backtrack_tolerance=0.05` or overshoot > `overshoot_tolerance=0.1` from the global journey direction
  - Shortlist (`shortlist_size=15`): candidates are ranked by raw core distance first, and only the N closest are eligible for tag/genre/audio re-ranking — keeps those weights from pulling in a song that's a great mood/genre match but far from the target waypoint
- `build_playlist` — loops waypoints, tracks `prev_v/prev_e`, passes global `journey_dv/journey_de` direction signs

## Cache files

| File | Keyed by | Written by |
|------|----------|-----------|
| `song_tags_cache.json` | `{title}|||{artist}` | `generate_all_tags` (Last.fm only; CSV genres not cached) |
| `tag_scores_cache.json` | tag string | `aggregate_tag_scores` |
| `genre_fit_cache.json` | `{title}|||{artist}|||{genre}` | `score_all_genre_fits` |

Delete a cache file and re-run to force a refresh. Empty Last.fm results are never cached (so failed lookups are retried automatically on next run).

## External services

- **Last.fm API** (`LASTFM_API_KEY` in cell [07] and `recommender.py`) — `track.gettoptags` with `artist.gettoptags` fallback; parallelised with `ThreadPoolExecutor(max_workers=5)`
- **Ollama** (`llama3.2` local model) — tag scoring and genre fit; batched 10 tags/prompt with per-tag fallback on JSON parse failure

## Streamlit app

`app.py` is the UI layer; `recommender.py` is the logic layer.

| File | Role | Touch? |
|------|------|--------|
| `recommender.py` | All core functions mirrored from notebook cells [09], [11], [12], [15], [16] plus `load_dataframe()` / `enrich_dataframe()` pipeline helpers | Mirror notebook changes here |
| `app.py` | Streamlit UI — sidebar inputs, `@st.cache_resource` startup, playlist display, journey chart, scatter plot tab | UI changes only |

Run with: `streamlit run app.py`

`@st.cache_resource` in `app.py` calls `load_dataframe()` + `enrich_dataframe()` once per server session. Genre fit (`score_all_genre_fits`) runs on demand per generate click but hits `genre_fit_cache.json` on repeat runs.

**When updating algorithm in notebook:** mirror the same change into the corresponding function in `recommender.py`.

## Key constraints

- **Never modify** cells [03], [11], [24]–[31]
- **Never modify** `generate_waypoints` (in notebook or `recommender.py`)
- Notebook cells have no `id` fields after editing via JSON — use cell index for targeting
- `Artist Name(s)` uses semicolons; `_clean_artist()` splits on `;` and strips feat. suffixes before Last.fm lookups
- `df` is rebuilt every kernel restart — must run [01] → [05] → [07] → [09] → [11] → [12] → [13] in order before any downstream cell works
- `LASTFM_API_KEY` lives in two places: notebook cell [07] and `recommender.py` — keep them in sync
