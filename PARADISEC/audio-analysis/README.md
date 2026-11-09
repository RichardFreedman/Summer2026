# Exploring sound with librosa

An interactive Streamlit app for listening to music and speech through the eyes of
signal analysis, built with [librosa](https://librosa.org). It is aimed at an
audience with musical knowledge but little technical background: every plot has
an audio player whose cursor moves across the figure as the clip plays, and a
"How this is computed" button that shows the few lines of code behind it.

The app works on two kinds of material:

- **Field recordings**: 190 twenty-second excerpts from the
  [PARADISEC](https://catalog.paradisec.org.au) archive of Pacific and regional
  languages and music, which is where the app began.
- **Added examples**: any other recordings you choose (for example score renderings
  from the [CRIM project](https://crimproject.org) or commercial performances
  for teaching), kept in `extra_audio/`.

Deployed at <https://sound.crimproject.org> behind a password; see
[`deploy/DEPLOY.md`](deploy/DEPLOY.md). It grew out of a PARADISEC workshop
version, deployed at
<https://dhworkshops.researchsoftware.unimelb.edu.au/paradisec-audio-analysis/>.

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
| The collection | Every clip on any two features, and a map of recording locations for the PARADISEC set |
| About librosa | The library, its modules, and a gallery of the plots `librosa.display` draws natively |

The sidebar's **Clips** control chooses which recordings to offer:

- **Hand-picked**: a curated list (`CURATED` in `analysis.py`). This is the default.
- **Added examples**: only the recordings in `extra_audio/`. The collection tab is
  limited to them too, and the PARADISEC map is hidden.
- **Everything**: all 190 PARADISEC excerpts plus the added examples.

The choice is kept in the page address, so a link such as
`https://sound.crimproject.org/?clips=added` opens straight onto the added
examples (after the password). A music/speech filter narrows any of these. Clips longer than
45 seconds are analysed a section at a time (up to 60 s), chosen with a slider in
the sidebar.

## Password

The app opens on a password page, and nothing else runs or is sent to the browser
until the password is entered. The password is read from the `APP_PASSWORD`
environment variable, or from `app_password` in `.streamlit/secrets.toml`
(gitignored). If neither is set, the app stays locked.

```toml
# .streamlit/secrets.toml
app_password = "choose-a-password"
```

**What counts as the password.** Only the text between the quotes. With the file
above, people type `choose-a-password`.

- Everything between the quotes counts, including spaces. `"blue whale"` and
  `"bluewhale"` are different passwords, and a space before the closing quote becomes
  part of the password.
- It is case-sensitive.
- Inside double quotes, write `\"` for a quote mark and `\\` for a backslash. Or use
  single quotes, where everything is taken exactly as typed:
  `app_password = 'my"pass\word'`. Simplest is to avoid those two characters.
- Keep it on one line, with nothing after the closing quote except an optional `# comment`.

**Changing the password on the server** (droplet console, so the password is never
sent anywhere else):

```bash
cd /root/exploring_sound/app
printf 'app_password = "NEW-PASSWORD"\n' > .streamlit/secrets.toml
systemctl restart exploring-sound
```

If the password contains `"` or `\`, edit the file instead with
`nano .streamlit/secrets.toml`: change the text between the quotes, press **Ctrl+O**
then **Enter** to save and **Ctrl+X** to exit, then run `systemctl restart exploring-sound`.

- The restart signs everyone out; they need the new password on their next visit.
- To check: `systemctl is-active exploring-sound` should print `active`. Then open
  https://sound.crimproject.org in a private window and try the new password.
- Updates from the Mac never overwrite it: the rsync in
  [`deploy/DEPLOY.md`](deploy/DEPLOY.md) skips `secrets.toml`.
- The Mac's own `.streamlit/secrets.toml` is separate, so changing one does not change the other.

## Added examples

Recordings beyond the PARADISEC set live in `extra_audio/`, one row each in a
metadata CSV:

| column | meaning |
|---|---|
| `file` | audio file name in `extra_audio/` (MP3, WAV, FLAC, ...) |
| `item` | short identifier, e.g. `CRIM-0012`; add it to `CURATED` in `analysis.py` to show it by default |
| `kind` | `music` or `speech` |
| `title`, `description`, `year` | shown in the sidebar (year may be blank) |
| `collection`, `url` | grouping label and the link offered as "Open the source page" |
| `credit`, `licence` | shown under the title |

Many of these recordings are under copyright, so **audio and the real metadata
stay out of git**:

- Audio files (`*.mp3`, `*.wav`, `*.flac`, ...) are gitignored. They reach the server
  only by rsync (see [`deploy/DEPLOY.md`](deploy/DEPLOY.md)).
- `extra_audio/extra_metadata.csv` is the real, local list. It is gitignored, so edit it freely.
- `extra_audio/extra_metadata.sample.csv` is committed. It lists only the openly licensed
  example, *Voulant honneur* (CRIM Model 0012), a Pierre Sandrin chanson rendered from
  the score (CC BY-NC 4.0), whose audio is also committed. The app reads it when the
  real list is absent, so a fresh clone runs.

Add rows to the sample file only for audio that is itself committed and freely
licensed, since the app fails on a row whose audio file is missing.

Features for the collection scatter are computed on the fly for added examples
(on their first 20 seconds, matching the notebook), so nothing else needs rebuilding.

## PARADISEC data

The excerpts and metadata come from
[`dan321/soundscape`](https://github.com/dan321/soundscape), a story map of
sample files from the archive. They are not committed here; `fetch_data.sh`
downloads them into `soundscape/` (about 60 MB). `features/clip_features.csv` holds
per-clip summary features computed once by the companion Jupyter notebook
(`paradisec_signal_analysis.ipynb` in the paradisec-analysis project).

Each excerpt links back to its catalogue entry, where the depositor's access
conditions apply.

## Running locally

```bash
./fetch_data.sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
printf 'app_password = "local"\n' > .streamlit/secrets.toml
streamlit run streamlit_app.py
```

The app is developed and deployed on Python 3.13. The pinned packages won't install on
older versions such as Python 3.10.

Or with Docker (not used for the production deployment):

```bash
docker build -t exploring-sound .
docker run --rm -p 8501:8501 -e APP_PASSWORD=local exploring-sound
# then open http://localhost:8501/exploring-sound/
```

## Files

- `streamlit_app.py`: the UI, password page, caching, Plotly figures and the synced audio player.
- `analysis.py`: pure librosa helpers (no Streamlit), including the curated clip list.
- `gallery.py`: the native `librosa.display` gallery for the About tab.
- `features/clip_features.csv`: collection-wide features for the PARADISEC scatter.
- `extra_audio/`: added examples and their metadata (see above).
- `deploy/`: the systemd service, Traefik route and step-by-step deployment guide.
