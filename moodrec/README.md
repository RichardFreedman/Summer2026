# MoodRec — Emotion-Regulated Music Recommender

A music recommendation system that generates iso-principle playlists using content-based filtering on Spotify audio features, built as an expansion of Lowe-Brown et al. (2024).

The iso principle from music therapy: start with music that matches where the listener is emotionally, then shift step-by-step toward where they want to be.

---

## Interfaces

MoodRec has two interfaces that share the same underlying algorithm:

- **Jupyter notebook** (`recommender.ipynb`) — primary interface; run cells interactively
- **Streamlit app** (`app.py`) — web UI with sliders and live playlist generation

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

### 3. Install Ollama
Ollama runs the local LLM (`llama3.2`) used for tag scoring and genre fit.
```
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2
```

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
2. **Tag enrichment** — Genre/mood tags sourced from the CSV or Last.fm API, then scored by Ollama for emotional valence and arousal
3. **Genre fit** — Ollama scores each song against your genre preference (0–1), cached to `genre_fit_cache.json`
4. **Playlist generation** — Linear waypoints from current → desired emotion; each song picked by multi-dimensional distance (valence/energy + tags + genre fit + audio features)

---

## User inputs

| Variable | Description |
|---|---|
| `current_valence` | How pleasant you feel now (0–1) |
| `current_energy` | How energized you feel now (0–1) |
| `desired_valence` | How pleasant you want to feel (0–1) |
| `desired_energy` | How energized you want to feel (0–1) |
| `genre_preferences` | List of genres e.g. `["indie folk"]`, `["jazz", "soul"]`, or `[]` |

In the notebook these are set in **Step 1** (cell [20]). In the app they are sidebar sliders.

---

## Project structure

```
moodrec/
├── recommender.ipynb     # Main notebook (primary interface)
├── app.py                # Streamlit web app (UI layer)
├── recommender.py        # Core logic module (imported by app.py)
├── MoodRec_Songs.csv     # 367-song library with Spotify audio features
├── requirements.txt
├── song_tags_cache.json  # Last.fm tags per song (cached)
├── tag_scores_cache.json # Ollama tag scores (cached)
└── genre_fit_cache.json  # Ollama genre fit scores (cached)
```

---

## API keys

Copy `.env.example` to `.env` and fill in your key — it is gitignored and never committed.

```
cp .env.example .env
# then edit .env and paste your Last.fm API key
```

- **Last.fm** — Free API key at https://www.last.fm/api. Add it to `.env` as `LASTFM_API_KEY`.
- **Ollama** — No key needed; runs locally.

---

## Research notes

Based on the iso principle and feedback methodology from Lowe-Brown et al. (2024).
