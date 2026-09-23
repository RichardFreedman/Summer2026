# PARADISEC audio analysis

An interactive Streamlit app for listening to 20-second excerpts from the
[PARADISEC](https://catalog.paradisec.org.au) archive through the eyes of
signal analysis, built with [librosa](https://librosa.org). It is aimed at an
audience with musical knowledge but little technical background: every plot has
an audio player whose cursor moves across the figure as the clip plays, and a
"How this is computed" button that shows the few lines of code behind it.

Deployed at <https://dhworkshops.researchsoftware.unimelb.edu.au/paradisec-audio-analysis/>
(shared workshop login). Deployment lives in `deploy/paradisec-audio-analysis/`.

## Views

| Tab | What it shows |
|---|---|
| Waveform | Amplitude and loudness envelope |
| Spectrogram | Constant-Q with note names, mel or linear STFT; frame length and dynamic range controls |
| Pitch | pYIN melody track with note-and-cents hover, pitch histograms, chromagram and pitch-class profile |
| Rhythm | Onset envelope, tracked beats with an optional click track, tempo curve, inter-onset intervals, onset pattern folded onto the beat |
| Tempogram | Autocorrelation or Fourier tempogram with adjustable window, plus the global tempo curve |
| Structure | Self-similarity and time-lag matrices from chroma, MFCC or both; crosshair cursor |
| Layers | Harmonic/percussive separation with audio for each layer |
| The collection | All 190 excerpts on any two features, and a map of recording locations |
| About librosa | The library, its modules, and a gallery of the plots `librosa.display` draws natively |

The sidebar offers a curated set of 13 music and 3 speech excerpts by default,
a toggle to open up all 190 PARADISEC excerpts, and a music/speech filter.
Clips longer than 45 seconds are analysed a section at a time (up to 60 s),
chosen with a slider in the sidebar.

## Added examples

Besides the soundscape excerpts, the app can carry its own examples in
`extra_audio/`. Each is one row in `extra_audio/extra_metadata.csv`:

| column | meaning |
|---|---|
| `file` | audio file name in `extra_audio/` (MP3, WAV, FLAC, ...) |
| `item` | short identifier, e.g. `CRIM-0012`; add it to `CURATED` in `analysis.py` to show it by default |
| `kind` | `music` or `speech` |
| `title`, `description`, `year` | shown in the sidebar (year may be blank) |
| `collection`, `url` | grouping label and the link offered as "Open the source page" |
| `credit`, `licence` | shown under the title; keep files to material you may redistribute |

Features for the collection scatter are computed on the fly for added examples
(on their first 20 seconds, matching the notebook), so nothing else needs
rebuilding. Keep files small (a few MB) since they live in git; anything larger
should be fetched at build time like the soundscape set.

The first added example is *Voulant honneur* (CRIM Model 0012), a Pierre
Sandrin chanson rendered from the score, from the CRIM project (CC BY-NC 4.0).

## Data

The excerpts and metadata come from
[`dan321/soundscape`](https://github.com/dan321/soundscape), a story map of
sample files from the archive. They are not committed here; `fetch_data.sh`
downloads them into `soundscape/` (about 60 MB). The Dockerfile runs the same
script during the build, pinned to a commit. `features/clip_features.csv` holds
per-clip summary features computed once by the companion Jupyter notebook
(`paradisec_signal_analysis.ipynb` in the paradisec-analysis project, which is
where this app was developed).

Each excerpt links back to its catalogue entry, where the depositor's access
conditions apply.

## Running locally

```bash
./fetch_data.sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Or with Docker, exactly as deployed:

```bash
docker build -t paradisec-audio-analysis .
docker run --rm -p 8501:8501 paradisec-audio-analysis
# then open http://localhost:8501/paradisec-audio-analysis/
```

## Files

- `streamlit_app.py`: the UI, caching, Plotly figures and the synced audio player.
- `analysis.py`: pure librosa helpers (no Streamlit), including the curated clip list.
- `gallery.py`: the native `librosa.display` gallery for the About tab.
- `features/clip_features.csv`: collection-wide features for the scatter plot.
