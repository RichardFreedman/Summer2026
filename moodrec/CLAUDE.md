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
| [01] | Imports (`pandas`, `numpy`, `matplotlib`, `os`, `re`, `requests`, `concurrent.futures`) | Only to add imports |
| [02] | Part 1 header | — |
| [03] | Original `generate_waypoints`, `euclidean_distance`, `find_closest_song`, `build_playlist` (simple versions — overridden later) | **Never** |
| [04] | Part 1a header (song library) | — |
| [05] | CSV loading → `df` with `tempo_norm`, `loudness_norm` | OK |
| [06] | Part 1b header | — |
| [07] | `import json`, `ChatOpenAI`, `OPENAI_MODEL = "gpt-4.1-mini"`, `LASTFM_API_KEY` | OK |
| [08] | 1b.1 header (Last.fm tag fetching) | — |
| [09] | Last.fm tag fetching: `generate_all_tags`, `_fetch_tags_from_lastfm`, `_clean_artist`, `_csv_genres` | OK |
| [10] | 1b.2 header | — |
| [11] | OpenAI tag scoring: `aggregate_tag_scores`, `_score_tag_batch`, `_score_tag_single` | **Never** |
| [12] | Genre fit: `score_genre_fit`, `score_all_genre_fits` | OK |
| [13] | Runs the tag pipeline → adds `all_tags`, `tag_valence_shift`, `tag_arousal_shift`, `top_emotions`, `dominant_emotion` to `df` | OK |
| [14] | Super-Genre Mapping via GPT header | — |
| [15] | `df["supergenre"]` via a single GPT-4.1-mini call over `all_tags`, cached to `supergenre_cache.json` | OK |
| [16] | 1b.3 header + audio feature rationale table | OK |
| [17] | Extended `find_closest_song` (overrides [03]) | OK |
| [18] | Extended `build_playlist` (overrides [03]) | OK |
| [19] | 1b.4 header | — |
| [20] | Emotion scatter plot | OK |
| [21]–[36] | **Part 1c** — network visualisations, see below | OK (see gotchas below) |
| [37] | Step 1 header | — |
| [38] | **User inputs**: `current_valence`, `current_energy`, `desired_valence`, `desired_energy`, `genre_preferences` | OK |
| [39] | Step 2 header | — |
| [40] | Genre scoring + `build_playlist` call → `playlist` DataFrame | OK |
| [41] | Journey visualisation (arrows + target path) | OK |

Cell indices shift whenever cells are inserted/removed — re-check with a fresh dump before relying on a specific number; the roles above were current as of the Part 1c interactive-network work.

### Part 1c — network visualisations (cells 21–36)

Four `pyvis` interactive networks plus a `plotly` heatmap. Each network cell follows the same pattern: an interactive `pyvis` cell, a one-line "static version" markdown note, then a collapsed `matplotlib` fallback cell kept for PDF/slide export. All four networks pair genre with `top_emotions` (each song's top-3 weighted emotions — a list of `(label, weight)` **tuples**, not `dominant_emotion` and not plain strings) for consistency.

| Cells | Network | Level |
|---|---|---|
| 23–25 | Genre → emotional zone | individual tag (≥4 songs) |
| 26–28 | Genre → emotional zone | super-genre |
| 29 | 1c.2 header | — |
| 30–32 | Super-genre → emotion | super-genre |
| 33–35 | Tag → emotion | individual tag (dense) |
| 36 | Heatmap — super-genre × emotion, raw counts + row-normalised | `plotly` |

**pyvis gotchas** (already fixed in code — worth knowing before touching these cells or `app.py`'s network tabs):
- `net.show()`'s returned `IFrame(src=...)` doesn't render reliably outside classic Jupyter (VS Code's notebook webview in particular). Display via `IPython.display.HTML` with the saved file read back and embedded as `srcdoc`, not a file path.
- Node `title=` tooltips are plain text only — vis-network never renders `<br>`/`<b>` from a string title as HTML. Use `\n` for line breaks and inject `<style>div.vis-tooltip{white-space:pre-wrap;max-width:280px}</style>` into the generated HTML, or long tooltips run off-canvas as one unbroken line.
- pyvis's template never calls `network.fit()` after physics stabilizes — the camera stays on the nodes' random pre-physics starting positions while `forceAtlas2Based`/`repulsion` spreads them out, so sparse graphs render mostly empty. A one-shot `stabilizationIterationsDone` listener is unreliable (timing race, especially inside Streamlit's `components.html` iframe) — poll `network.fit()` every ~250ms for a few seconds instead.
- `net.show_buttons()` must be called *before* `net.set_options()` — `set_options()` replaces `self.options` wholesale and wipes out the `configure` key `show_buttons()` set, which throws `options.configure is undefined` and blanks the whole network. (`app.py` no longer uses `show_buttons()` at all — it has a plain physics on/off toggle instead; see below.)

## Architecture

### Tag pipeline (runs once, cached)
1. `generate_all_tags(df)` — CSV genres merged with Last.fm track/artist tags for every song (367/367) → `song_tags_cache.json`
2. `aggregate_tag_scores(track_tags, llm)` — OpenAI (`gpt-4.1-mini`) scores each unique tag for `valence_shift` [-1,1], `arousal_shift` [-1,1], `emotions` dict → `tag_scores_cache.json`
3. Scores merged into `df` as `tag_valence_shift`, `tag_arousal_shift`, `top_emotions` (top-3 `(label, weight)` tuples), `dominant_emotion`

### Super-genre mapping (runs once, cached)
- `df["all_tags"]` (CSV genres + Last.fm tags, comma-joined) is mapped to one of 10 broad super-genres (`Jazz`, `Soul/R&B`, `Hip Hop/Rap`, `Rock`, `Pop`, `Folk/Country`, `Electronic/Dance`, `Classical/Orchestral`, `World Music`, `Other`) via a single GPT-4.1-mini call over all unique tags → `supergenre_cache.json`
- Only in the notebook (cell [15]) — `recommender.py` does **not** mirror this step; see the Streamlit app section below

### Genre fit (runs per genre, cached)
- `score_all_genre_fits(df, genre, llm)` — OpenAI scores each song 0–1 for a free-text genre/mood → `genre_fit_cache.json`
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
| `song_tags_cache.json` | `{title}\|\|\|{artist}` | `generate_all_tags` (Last.fm only; CSV genres not cached) |
| `tag_scores_cache.json` | tag string | `aggregate_tag_scores` |
| `genre_fit_cache.json` | `{title}\|\|\|{artist}\|\|\|{genre}` | `score_all_genre_fits` |
| `supergenre_cache.json` | tag string | notebook cell [15]; also `app.py`'s `add_supergenre_column()` |

Delete a cache file and re-run to force a refresh. Empty Last.fm results are never cached (so failed lookups are retried automatically on next run).

## External services

- **Last.fm API** (`LASTFM_API_KEY` in notebook cell [07] and `recommender.py`) — `track.gettoptags` with `artist.gettoptags` fallback; parallelised with `ThreadPoolExecutor(max_workers=5)`
- **OpenAI** (`OPENAI_API_KEY`, `gpt-4.1-mini` via `langchain_openai.ChatOpenAI`) — tag scoring, genre fit, and super-genre mapping; tag scoring is batched 10 tags/prompt with per-tag fallback on JSON parse failure

## Streamlit app

`app.py` is the UI layer; `recommender.py` is the logic layer.

| File | Role | Touch? |
|------|------|--------|
| `recommender.py` | Core functions mirrored from notebook cells [09] (Last.fm tags), [11] (tag scoring), [12] (genre fit), [17]/[18] (extended `find_closest_song`/`build_playlist`), plus `load_dataframe()`/`enrich_dataframe()` pipeline helpers. **Does not mirror cell [15]'s super-genre mapping** — `enrich_dataframe()` produces `tag_valence_shift`, `tag_arousal_shift`, `top_emotions`, `dominant_emotion` but not `all_tags`/`supergenre` | Mirror notebook changes here |
| `app.py` | Streamlit UI — sidebar inputs, `@st.cache_resource` startup, 5 tabs: **Playlist**, **Song library**, **Genre network**, **Emotion network**, **Genre × Emotion**. The three network tabs port the Part 1c `pyvis`/`plotly` visualisations, each with a Super-genre/Individual-tags toggle and a simple physics on/off toggle. Since `recommender.py` doesn't provide `all_tags`/`supergenre`, `app.py`'s `add_supergenre_column()` reconstructs both locally from `song_tags_cache.json` + `supergenre_cache.json` (falls back to a live GPT call only for genuinely new, uncached tags) | UI changes only |

Run with: `streamlit run app.py`

`@st.cache_resource` in `app.py` calls `load_dataframe()` + `enrich_dataframe()` once per server session; `add_supergenre_column()` and the network-building helpers are `@st.cache_data`. Genre fit (`score_all_genre_fits`) runs on demand per generate click but hits `genre_fit_cache.json` on repeat runs. The three network tabs render without needing "Generate playlist" — they're library-level views independent of the sidebar inputs.

**When updating algorithm in notebook:** mirror the same change into the corresponding function in `recommender.py`.

## Key constraints

- **Never modify** cells [03], [11]
- **Never modify** `generate_waypoints` (in notebook or `recommender.py`)
- `top_emotions` is a list of `(emotion, weight)` **tuples**, not a list of emotion strings — `for emotion, _weight in row["top_emotions"]:` is correct; unpacking with a single loop variable silently binds the whole tuple instead of raising, corrupting anything downstream that uses it as a dict key or node label
- Notebook cells have no `id` fields after editing via JSON — use cell index for targeting
- `Artist Name(s)` uses semicolons; `_clean_artist()` splits on `;` and strips feat. suffixes before Last.fm lookups
- `df` is rebuilt every kernel restart — must run `[01]→[05]→[07]→[09]→[11]→[12]→[13]` in order before any downstream cell works; add `[15]` to that chain if working with Part 1c (needs `supergenre`)
- `LASTFM_API_KEY` lives in two places: notebook cell [07] and `recommender.py` — keep them in sync
