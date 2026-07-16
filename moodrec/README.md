# MoodRec — Emotion-Regulated Music Recommender

A music recommendation system that generates iso-principle playlists using content-based filtering on Spotify audio features, built as an expansion of Lowe-Brown et al. (2024).

The iso principle from music therapy: start with music that matches where the listener is emotionally, then shift step-by-step toward where they want to be.

---

## Interfaces

MoodRec has two interfaces that share the same underlying algorithm:

- **Jupyter notebook** (`recommender.ipynb`) — primary interface; run cells interactively
- **Streamlit app** (`app.py`) — web UI with five tabs: playlist generation, the song library scatter plot, and three interactive genre/emotion network visualisations (see [Network visualisations](#network-visualisations) below)

---

## Setup

### 1. Install Python
Requires Python 3.9+. Check with:
```
python --version
```

### 2. Install dependencies
```
pip install -r requirements.txt
```

### 3. Set your OpenAI API key
OpenAI (`gpt-4.1-mini` by default) is used for tag scoring, genre fit, and super-genre mapping. Get a key at https://platform.openai.com/api-keys, then add it to `.env` as `OPENAI_API_KEY` (see [API keys](#api-keys)).

### 4. Run MoodRec

**Option A — Streamlit app** (recommended)
```
streamlit run app.py
```
The app loads and enriches the song library on first launch (uses cached results on subsequent runs).

**Option B — Jupyter notebook** (for interactive exploration)
```
jupyter notebook recommender.ipynb
```
Run all cells in order from top to bottom.

---

## How it works

1. **Song library** — `MoodRec_Songs.csv` (367 songs with Spotify audio features)
2. **Tag enrichment** — Genre/mood tags sourced from the CSV and Last.fm API, merged per song, then scored by OpenAI for emotional valence, arousal, and discrete emotions (each song's top 3, weighted)
3. **Super-genre mapping** — The sprawling tag vocabulary (hundreds of unique tags) is clustered into 10 broad super-genres (Rock, Pop, Hip Hop/Rap, Jazz, ...) by a single GPT call, so genre-level patterns are visible without hundreds of one-off tags
4. **Genre fit** — OpenAI scores each song against your genre preference (0–1), cached to `genre_fit_cache.json`
5. **Playlist generation** — Linear waypoints from current → desired emotion; each song picked by multi-dimensional distance (valence/energy + tags + genre fit + audio features)

---

## Network visualisations

The **Genre network**, **Emotion network**, and **Genre × Emotion** tabs (also in the notebook's Part 1c) are exploratory views of the same tag/emotion data the recommender's distance function actually uses — they explain *why* genre and mood tags influence song selection, not just *that* they do.

- **Genre network** — how genre tags map onto the four emotional quadrants (Stressed/Anxious, Excited/Happy, Sad/Depressed, Calm/Relaxed), at both the super-genre and individual-tag level. `find_closest_song` penalises songs with low genre fit (weight 0.4) when you give a genre preference — this network shows what that preference is actually steering toward. A genre spread evenly across all four quadrants (e.g. "classic rock") carries little emotional signal on its own; one concentrated in a single quadrant is a much stronger mood cue.
- **Emotion network** — how those same genres connect to specific discrete emotions (joy, nostalgia, rebellion, ...) rather than just the four broad quadrants. This exposes a semantic gap: the same super-genre routinely carries very different emotional textures depending on the specific song — e.g. Rock spans everything from *energy* and *excitement* to *rebellion* and *nostalgia*. A genre label alone can't tell you which of those a given song is; that's why the recommender's fine-grained tag-based valence/arousal scoring (weight 0.3) adds value beyond genre matching alone.
- **Genre × Emotion heatmap** — the same super-genre/emotion relationship as a precise grid readout instead of a graph, with a row-normalised view alongside the raw counts so lower-volume super-genres (Jazz, Folk/Country) are visually comparable to high-volume ones (Rock) despite having far fewer songs.

Each network is interactive (`pyvis`/`plotly`): hover a node or cell for exact counts, drag nodes around, and toggle physics on/off to freeze the layout in place.

---

## User inputs

| Variable | Description |
|---|---|
| `current_valence` | How pleasant you feel now (0–1) |
| `current_energy` | How energized you feel now (0–1) |
| `desired_valence` | How pleasant you want to feel (0–1) |
| `desired_energy` | How energized you want to feel (0–1) |
| `genre_preferences` | List of genres e.g. `["indie folk"]`, `["jazz", "soul"]`, or `[]` |

In the notebook these are set in **Step 1**. In the app they are sidebar sliders.

---

## Project structure

- `recommender.ipynb` — primary interface
- `app.py` — Streamlit UI
- `recommender.py` — shared logic, imported by `app.py`
- `MoodRec_Songs.csv` — song library
- `requirements.txt`
- `.env.example` — copy to `.env`
- `*_cache.json` — cached API results (tags, genre fit, super-genre)

---

## API keys

Copy `.env.example` to `.env` and fill in your key — it is gitignored and never committed.

```
cp .env.example .env
# then edit .env and paste your Last.fm and OpenAI API keys
```

- **Last.fm** — Free API key at https://www.last.fm/api. Add it to `.env` as `LASTFM_API_KEY`.
- **OpenAI** — API key at https://platform.openai.com/api-keys. Add it to `.env` as `OPENAI_API_KEY`. Usage is billed per request (tag scoring and genre fit calls, cached to disk after first run).

---

## Research notes

Based on the iso principle and feedback methodology from Lowe-Brown et al. (2024).
