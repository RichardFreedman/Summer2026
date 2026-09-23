"""Hearing the archive: interactive signal analysis of PARADISEC excerpts.

Run with:  uv run streamlit run streamlit_app.py
"""
from __future__ import annotations

import base64
import inspect

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import analysis as an
import gallery

# --------------------------------------------------------------------------- #
# Page and colour system
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="Hearing the archive", page_icon="🎧", layout="wide")

# A wider sidebar so excerpt titles are not truncated in the picker.
st.markdown("""
<style>
  section[data-testid="stSidebar"] { width: 400px !important; min-width: 400px !important; }
  section[data-testid="stSidebar"] > div { width: 400px !important; }
  section[data-testid="stSidebar"] [data-baseweb="select"] > div { white-space: normal; }
</style>
""", unsafe_allow_html=True)

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
KIND_COLOUR = {"music": BLUE, "speech": ORANGE}
CURSOR = AQUA
SPEC_SCALE = "Magma"
RAMP_SCALE = "Blues"

LAYOUT = dict(
    template="plotly_white", font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", size=13, color=INK2),
    margin=dict(l=60, r=20, t=78, b=44), hovermode="closest",
    xaxis=dict(gridcolor=GRID, zeroline=False), yaxis=dict(gridcolor=GRID, zeroline=False),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, font=dict(size=12),
                entrywidth=150, entrywidthmode="pixels"),
)


def base_fig(title: str, height: int = 380) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(**LAYOUT, height=height,
                      title=dict(text=title, x=0, y=0.985, yanchor="top", font=dict(size=15, color=INK)))
    return fig


def note_ticks(midi: np.ndarray) -> tuple[list, list]:
    vals = [int(m) for m in range(int(np.ceil(midi.min())), int(midi.max()) + 1) if m % 12 in (0, 4, 7)]
    return vals, [an.librosa.midi_to_note(v, unicode=True) for v in vals]


# --------------------------------------------------------------------------- #
# Synchronised player: a Plotly figure with a cursor that follows the audio
# --------------------------------------------------------------------------- #
def synced_plot(fig: go.Figure, audio: bytes, key: str, height: int = 420, crosshair: bool = False) -> None:
    """Render a Plotly figure and an audio element together. The cursor follows
    playback; clicking on the plot seeks the audio to that time. With
    ``crosshair`` a horizontal line follows too, for plots whose y axis is also time."""
    fig_json = fig.to_json()
    b64 = base64.b64encode(audio).decode()
    horizontal = ("""{{ type: "line", x0: 0, x1: 1, y0: 0, y1: 0, xref: "paper", yref: "y",
                        line: {{ color: "{c}", width: 2.5 }}, layer: "above" }},""".format(c=CURSOR)) if crosshair else ""
    html = f"""
<!doctype html><html><head><meta charset="utf-8">
<script src="https://cdn.plot.ly/plotly-3.1.0.min.js" charset="utf-8"></script>
<style>
  body {{ margin:0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
  audio {{ width:100%; margin-top:4px; }}
  .hint {{ color:{MUTED}; font-size:12px; margin:2px 0 0 4px; }}
</style></head><body>
<div id="plot_{key}"></div>
<audio id="audio_{key}" controls preload="auto" src="data:audio/wav;base64,{b64}"></audio>
<div class="hint">Press play to see the cursor move with the sound. Click anywhere on the plot to jump there.</div>
<script>
  const fig = {fig_json};
  fig.layout.shapes = (fig.layout.shapes || []).concat([{horizontal}{{
    type: "line", x0: 0, x1: 0, y0: 0, y1: 1, yref: "paper", xref: "x",
    line: {{ color: "{CURSOR}", width: 2.5 }}, layer: "above"
  }}]);
  const cursorIndex = fig.layout.shapes.length - 1;
  const crossIndex = {"cursorIndex - 1" if crosshair else "-1"};
  const plotDiv = document.getElementById("plot_{key}");
  const audio = document.getElementById("audio_{key}");
  Plotly.newPlot(plotDiv, fig.data, fig.layout, {{responsive: true, displayModeBar: false}});
  let raf = null;
  function paint() {{
    const t = audio.currentTime;
    const update = {{["shapes[" + cursorIndex + "].x0"]: t, ["shapes[" + cursorIndex + "].x1"]: t}};
    if (crossIndex >= 0) {{ update["shapes[" + crossIndex + "].y0"] = t; update["shapes[" + crossIndex + "].y1"] = t; }}
    Plotly.relayout(plotDiv, update);
    if (!audio.paused && !audio.ended) raf = requestAnimationFrame(paint);
  }}
  audio.addEventListener("play", () => {{ cancelAnimationFrame(raf); paint(); }});
  audio.addEventListener("seeked", paint);
  audio.addEventListener("pause", paint);
  plotDiv.on("plotly_click", (ev) => {{
    if (ev.points && ev.points.length) {{ audio.currentTime = ev.points[0].x; paint(); }}
  }});
</script></body></html>"""
    components.html(html, height=height + 90)


# --------------------------------------------------------------------------- #
# "How this is computed": a dialog with a minimal recipe and the real source
# --------------------------------------------------------------------------- #
@st.dialog("How this is computed", width="large")
def code_dialog(title: str, recipe: str, funcs: list) -> None:
    st.markdown(f"#### {title}")
    st.markdown("**A minimal recipe**, from the MP3 to the numbers behind the plot. "
                "Each step is one librosa call; paste it into a notebook to try it yourself.")
    st.code(recipe.strip(), language="python")
    if funcs:
        st.markdown(f"**What the app actually runs** (from `analysis.py`):")
        for f in funcs:
            st.code(inspect.getsource(f), language="python")


def code_button(key: str, title: str, recipe: str, funcs: list) -> None:
    if st.button("How this is computed", key=f"code_{key}", icon=":material/code:", type="tertiary"):
        code_dialog(title, recipe, funcs)


RECIPES = {
    "wave": """
import librosa
y, sr = librosa.load("soundscape/audio/RJL1-013-B.mp3", sr=22050, mono=True)   # samples in [-1, 1]
rms = librosa.feature.rms(y=y, hop_length=512)[0]        # loudness of each 23 ms frame
rms_db = librosa.amplitude_to_db(rms, ref=rms.max())    # decibels below the loudest frame
times = librosa.frames_to_time(range(len(rms)), sr=sr, hop_length=512)
""",
    "spec": """
import numpy as np, librosa
y, sr = librosa.load("soundscape/audio/RJL1-013-B.mp3", sr=22050)

# Short-time Fourier transform: frames of n_fft samples, one spectrum per frame
S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
S_db = librosa.amplitude_to_db(S, ref=np.max)            # rows = frequency bins, columns = frames

# Mel spectrogram: the same energy pooled into perceptually spaced bands
M_db = librosa.power_to_db(librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128), ref=np.max)

# Constant-Q transform: one bin per semitone, so the y axis can carry note names
C = np.abs(librosa.cqt(y, sr=sr, fmin=librosa.note_to_hz("C2"), n_bins=60, bins_per_octave=12))
C_db = librosa.amplitude_to_db(C, ref=np.max)
""",
    "pitch": """
import numpy as np, librosa
y, sr = librosa.load("soundscape/audio/RJL1-013-B.mp3", sr=22050)

# pYIN: fundamental frequency per frame plus a voicing probability
f0, voiced, prob = librosa.pyin(y, fmin=librosa.note_to_hz("C3"), fmax=librosa.note_to_hz("C6"), sr=sr)
midi = librosa.hz_to_midi(f0)                            # 69 = A4; one unit = one semitone
librosa.midi_to_note(np.nanmedian(midi))                 # e.g. 'G♯3'

# Which pitches are used? Fold to one octave in cents and histogram, weighted by confidence
cents_in_octave = np.mod(midi[~np.isnan(midi)], 12) * 100
hist, edges = np.histogram(cents_in_octave, bins=np.arange(0, 1201, 10), weights=prob[~np.isnan(midi)])

# Chroma: energy per pitch class over time (here on the sustained layer only)
chroma = librosa.feature.chroma_cqt(y=librosa.effects.harmonic(y), sr=sr, norm=None)
""",
    "rhythm": """
import numpy as np, librosa
y, sr = librosa.load("soundscape/audio/DG1-LOM027307-B.mp3", sr=22050)

onset_env = librosa.onset.onset_strength(y=y, sr=sr)                  # how much new energy per frame
onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units="time")

tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr) # periodicity at every tempo, over time
bpm = librosa.tempo_frequencies(tempogram.shape[0], sr=sr)
tempo = bpm[np.argmax(tempogram.mean(axis=1))]                        # tallest peak of the average

_, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, bpm=tempo)
beat_times = librosa.frames_to_time(beats, sr=sr)
clicks = librosa.clicks(times=beat_times, sr=sr, length=len(y))        # mix y + clicks to hear the result
""",
    "tempogram": """
import numpy as np, librosa
y, sr = librosa.load("soundscape/audio/DG1-LOM027307-B.mp3", sr=22050)
onset_env = librosa.onset.onset_strength(y=y, sr=sr)

# Autocorrelation tempogram: inside a sliding window (win_length frames), compare the onset
# envelope with delayed copies of itself. Rows = lag, relabelled as tempo; columns = time.
tg = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr, win_length=384)
bpm = librosa.tempo_frequencies(tg.shape[0], sr=sr)          # BPM for each row (first row is infinite)

# Fourier tempogram: the same idea via a short-time Fourier transform of the envelope
ftg = np.abs(librosa.feature.fourier_tempogram(onset_envelope=onset_env, sr=sr, win_length=384))
fbpm = librosa.fourier_tempo_frequencies(sr=sr, win_length=384)

global_curve = tg.mean(axis=1)                                # average over time -> tempo curve
""",
    "structure": """
import numpy as np, librosa
y, sr = librosa.load("soundscape/audio/RJL1-013-B.mp3", sr=22050)

# 1. Describe each frame: chroma for pitch content (or MFCC for timbre)
chroma = librosa.feature.chroma_cqt(y=librosa.effects.harmonic(y), sr=sr)
chroma = librosa.util.sync(chroma, np.arange(0, chroma.shape[1], 4))   # pool 4 frames (~93 ms) per cell

# 2. Stack a few consecutive cells so short motifs, not single notes, are compared
feat = librosa.feature.stack_memory(chroma, n_steps=8)                  # ~0.75 s of context

# 3. Compare every cell with every other: cosine affinity, symmetric, diagonal band masked
R = librosa.segment.recurrence_matrix(feat, width=4, mode="affinity", sym=True, metric="cosine")

# 4. The same matrix as (time, lag): repeats at a fixed delay become horizontal lines
L = librosa.segment.recurrence_to_lag(R, pad=False)
""",
    "layers": """
import librosa
y, sr = librosa.load("soundscape/audio/CF1-005-IB.mp3", sr=22050)

# Median filtering of the spectrogram along time keeps sustained tones (harmonic),
# along frequency keeps attacks (percussive). margin > 1 makes the split stricter.
y_harmonic, y_percussive = librosa.effects.hpss(y, margin=(1.0, 2.0))
share = (y_harmonic**2).sum() / (y**2).sum()             # fraction of energy that is sustained
""",
    "all": """
# For every excerpt the notebook computes a handful of one-number summaries
# (see section 7 of paradisec_signal_analysis.ipynb) and caches them to CSV:
#   pulse_strength   tallest peak of the average tempogram between 40 and 300 BPM
#   tempo            the BPM at that peak
#   tonal_entropy    entropy of the cleaned pitch-class profile (3.58 bits = flat)
#   harmonic_share   energy in the harmonic HPSS layer / total energy
#   centroid         mean spectral centroid (brightness, Hz)
#   rms_cv           std / mean of the loudness envelope (burstiness)
import pandas as pd
features = pd.read_csv("features/clip_features.csv", index_col="item")
""",
}


# --------------------------------------------------------------------------- #
# Cached analysis
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def meta_table() -> pd.DataFrame:
    return an.load_meta()


@st.cache_data(show_spinner=False)
def audio_for(file: str):
    return an.load_audio(file)


@st.cache_data(show_spinner=False)
def wav_for(file: str) -> bytes:
    y, sr = audio_for(file)
    return an.wav_bytes(y, sr)


@st.cache_data(show_spinner=False)
def envelope_for(file: str):
    y, sr = audio_for(file)
    return an.envelope(y, sr), an.downsampled_wave(y, sr)


@st.cache_data(show_spinner=False)
def spectrogram_for(file: str, kind: str, n_fft: int):
    y, sr = audio_for(file)
    if kind == "Linear frequency (STFT)":
        return an.stft_db(y, sr, n_fft=n_fft)
    if kind == "Mel scale":
        return an.mel_db(y, sr, n_fft=n_fft)
    return an.cqt_db(y, sr)


@st.cache_data(show_spinner="Tracking pitch…")
def pitch_for(file: str, fmin: float, fmax: float):
    y, sr = audio_for(file)
    return an.pitch_track(y, sr, fmin=fmin, fmax=fmax)


@st.cache_data(show_spinner="Computing chroma…")
def chroma_for(file: str):
    y, sr = audio_for(file)
    return an.clean_chroma(y, sr)


@st.cache_data(show_spinner="Finding beats…")
def rhythm_for(file: str, tempo_min: float, tempo_max: float):
    y, sr = audio_for(file)
    return an.rhythm(y, sr, tempo_min=tempo_min, tempo_max=tempo_max)


@st.cache_data(show_spinner="Computing tempogram…")
def tempogram_for(file: str, win_length: int, kind: str):
    y, sr = audio_for(file)
    return an.tempogram(y, sr, win_length=win_length, kind=kind)


@st.cache_data(show_spinner="Comparing every moment with every other…")
def structure_for(file: str, feature: str, n_steps: int, k: int | None):
    y, sr = audio_for(file)
    return an.self_similarity(y, sr, feature=feature, n_steps=n_steps, k=k)


@st.cache_data(show_spinner="Separating layers…")
def layers_for(file: str, margin: float):
    y, sr = audio_for(file)
    return an.separate(y, margin)


@st.cache_data(show_spinner=False)
def features_table():
    feats = an.load_features()
    if feats is None:
        return None
    # Baked-in examples are not in the notebook's CSV: compute their features on the fly (cached).
    extras = [i for i in meta_table().index if i not in feats.index and str(meta_table().loc[i].file).startswith("extra_audio/")]
    for i in extras:
        y, sr = audio_for(meta_table().loc[i].file)
        feats.loc[i] = pd.Series(an.clip_features(y, sr))
    return feats


@st.cache_data(show_spinner="Rendering librosa's own plots…")
def gallery_for(file: str):
    y, sr = audio_for(file)
    return gallery.render_gallery(y, sr)


# --------------------------------------------------------------------------- #
# Sidebar: choose a clip
# --------------------------------------------------------------------------- #
meta = meta_table()

with st.sidebar:
    st.title("Hearing the archive")
    st.caption("Signal analysis of 20-second excerpts from the PARADISEC archive, via the "
               "[soundscape](https://github.com/dan321/soundscape) story map, plus a few added examples.")
    show_all = st.toggle("Show all excerpts", value=False,
                         help="Off: a hand-picked set of 13 music and 3 speech excerpts. On: all 190 PARADISEC excerpts plus the added examples.")
    pool = list(meta.index) if show_all else [i for i in an.CURATED if i in meta.index]

    kind_choice = st.segmented_control("Kind", ["All", "Music", "Speech"], default="All",
                                       selection_mode="single", key="kind_filter")
    kind_filter = {"Music": "music", "Speech": "speech"}.get(kind_choice)   # None means both
    items = [i for i in pool if kind_filter is None or meta.loc[i].kind == kind_filter]
    n_music = int((meta.loc[pool].kind == "music").sum()); n_speech = len(pool) - n_music
    st.caption(f"{len(items)} of {len(pool)} excerpts shown · {n_music} music, {n_speech} speech")

    # Keep the current excerpt when the filters change if it is still in the list.
    labels = [an.clip_label(meta.loc[i], i) for i in items]
    seen = pd.Series(labels).duplicated(keep=False).tolist()
    labels = [f"{lab} · {i}" if dup else lab for lab, i, dup in zip(labels, items, seen)]   # disambiguate twins
    options = dict(zip(labels, items))
    previous = st.session_state.get("current_item")
    default_item = previous if previous in items else (an.DEFAULT_ITEM if an.DEFAULT_ITEM in items else items[0])
    choice = st.selectbox("Excerpt", labels, index=items.index(default_item))
    item = options[choice]
    st.session_state["current_item"] = item
    row = meta.loc[item]

    st.markdown(f"### {row.title}")
    bits = [row.kind, str(int(row.year)) if not pd.isna(row.year) else None, f"item {item}"]
    st.caption(" · ".join(b for b in bits if b))
    is_extra = isinstance(row.get("credit"), str)
    if isinstance(row.description, str):
        with st.expander("Description" if is_extra else "Catalogue description"):
            st.write(row.description)
    if is_extra:
        st.caption(f"Source: {row.credit}" + (f" · {row.licence}" if isinstance(row.get("licence"), str) else ""))
    st.markdown(f"[Open the {'source page' if is_extra else 'catalogue entry'}]({row.url})")

    # Long clips are analysed a section at a time so the plots stay legible and quick.
    full_duration = len(audio_for(row.file)[0]) / an.SR
    MAX_SECTION = 60.0
    if full_duration > 45:
        st.divider()
        start, end = st.slider("Section to analyse (seconds)", 0.0, float(np.floor(full_duration)),
                               (0.0, min(45.0, float(np.floor(full_duration)))), step=1.0,
                               help=f"This clip runs {full_duration:.0f} s. Choose up to {MAX_SECTION:.0f} s to analyse at a time.")
        if end - start > MAX_SECTION:
            end = start + MAX_SECTION
            st.caption(f"Section shortened to {MAX_SECTION:.0f} s, ending at {end:.0f} s.")
        if end - start < 5:
            end = min(start + 5, float(np.floor(full_duration)))
        clip_key = f"{row.file}|{start}|{end}"
    else:
        clip_key = row.file

wav = wav_for(clip_key)
y, sr = audio_for(clip_key)
duration = len(y) / sr

# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
tab_wave, tab_spec, tab_pitch, tab_rhythm, tab_tempo, tab_struct, tab_layers, tab_all, tab_about = st.tabs(
    ["Waveform", "Spectrogram", "Pitch", "Rhythm", "Tempogram", "Structure", "Layers", "The collection", "About librosa"])

# ---- Waveform --------------------------------------------------------------
with tab_wave:
    st.markdown(
        "The **waveform** is air pressure over time. At this zoom it shows loudness and phrasing, "
        "not pitch. The orange line is the smoothed loudness (RMS energy) in decibels below the loudest moment.")
    code_button("wave", "Waveform and loudness", RECIPES["wave"], [an.load_audio, an.envelope, an.downsampled_wave])
    env, (t_blocks, blocks) = envelope_for(clip_key)
    fig = base_fig(f"Waveform and loudness: {row.title}", height=360)
    fig.add_trace(go.Scatter(x=np.r_[t_blocks, t_blocks[::-1]], y=np.r_[blocks.max(axis=1), blocks.min(axis=1)[::-1]],
                             fill="toself", fillcolor=BLUE, line=dict(width=0), name="waveform",
                             hoverinfo="skip", opacity=0.85))
    fig.add_trace(go.Scatter(x=env["times"], y=(env["rms_db"] + 60) / 60 * blocks.max() * 1.05, mode="lines",
                             line=dict(color=ORANGE, width=2), name="loudness (RMS)",
                             customdata=env["rms_db"], hovertemplate="%{x:.2f} s · %{customdata:.1f} dB<extra></extra>"))
    fig.update_xaxes(title="time (s)", range=[0, duration])
    fig.update_yaxes(title="amplitude", showticklabels=False)
    synced_plot(fig, wav, key="wave", height=360)

# ---- Spectrogram -----------------------------------------------------------
with tab_spec:
    st.markdown(
        "A **spectrogram** cuts the sound into short frames and shows how much energy sits at each frequency "
        "in each frame. Bright horizontal bands are sustained tones and their harmonics; bright vertical lines are attacks. "
        "Hover to read the frequency and level at any point.")
    code_button("spec", "Spectrograms", RECIPES["spec"], [an.stft_db, an.mel_db, an.cqt_db])
    c1, c2, c3 = st.columns([1.4, 1, 1])
    kind = c1.radio("Frequency axis", ["Log frequency, note names (constant-Q)", "Mel scale", "Linear frequency (STFT)"],
                    horizontal=True, index=0)
    n_fft = c2.select_slider("Frame length", options=[512, 1024, 2048, 4096], value=2048,
                             help="Short frames follow fast changes; long frames separate close pitches.",
                             disabled=kind.startswith("Log"))
    floor = c3.slider("Dynamic range (dB)", min_value=40, max_value=90, value=70, step=5)

    spec = spectrogram_for(clip_key, kind, n_fft)
    fig = base_fig("Spectrogram", height=460)
    if kind.startswith("Log"):
        tickvals, ticktext = note_ticks(spec["midi"])
        fig.add_trace(go.Heatmap(z=spec["db"], x=spec["times"], y=spec["midi"], colorscale=SPEC_SCALE, zmin=-floor, zmax=0,
                                 colorbar=dict(title="dB", thickness=12), hoverongaps=False,
                                 customdata=np.tile([an.librosa.midi_to_note(int(m), unicode=True) for m in spec["midi"]], (len(spec["times"]), 1)).T,
                                 hovertemplate="%{x:.2f} s · %{customdata} · %{z:.0f} dB<extra></extra>"))
        fig.update_yaxes(title="pitch", tickvals=tickvals, ticktext=ticktext)
    else:
        z, f = spec["db"], spec["freqs"]
        if kind == "Linear frequency (STFT)":
            keep = f <= 8000           # nothing survives above this in 64 kbps MP3 anyway
            z, f = z[keep], f[keep]
            step = max(1, len(f) // 300)   # thin the frequency axis for the browser
            z, f = z[::step], f[::step]
        fig.add_trace(go.Heatmap(z=z, x=spec["times"], y=f, colorscale=SPEC_SCALE, zmin=-floor, zmax=0,
                                 colorbar=dict(title="dB", thickness=12),
                                 hovertemplate="%{x:.2f} s · %{y:.0f} Hz · %{z:.0f} dB<extra></extra>"))
        fig.update_yaxes(title="frequency (Hz)", type="log" if kind == "Mel scale" else "linear",
                         range=[np.log10(60), np.log10(f.max())] if kind == "Mel scale" else None)
    fig.update_xaxes(title="time (s)", range=[0, duration])
    synced_plot(fig, wav, key="spec", height=460)

# ---- Pitch -----------------------------------------------------------------
with tab_pitch:
    st.markdown(
        "**Pitch tracking** (pYIN) estimates the fundamental frequency in every frame and how confident it is that a pitched "
        "sound is present. The green line is drawn over a note-labelled spectrogram; hover to read the note and how many "
        "cents it sits above or below equal temperament. It assumes one voice at a time, so expect octave jumps on "
        "polyphonic clips.")
    code_button("pitch", "Pitch, pitch histograms and chroma", RECIPES["pitch"],
                [an.pitch_track, an.note_label, an.pitch_histograms, an.clean_chroma])
    c1, c2 = st.columns(2)
    fmin_note = c1.select_slider("Lowest pitch to consider", options=["C2", "G2", "C3", "G3", "C4"], value="C3",
                                 help="Raise this if the tracker latches onto hum or a low accompaniment.")
    fmax_note = c2.select_slider("Highest pitch to consider", options=["C5", "G5", "C6", "G6", "C7"], value="C6")
    fmin, fmax = an.librosa.note_to_hz(fmin_note), an.librosa.note_to_hz(fmax_note)

    pt = pitch_for(clip_key, fmin, fmax)
    spec = spectrogram_for(clip_key, "cqt", 2048)
    tickvals, ticktext = note_ticks(spec["midi"])
    labels = [an.note_label(m) for m in pt["midi"]]

    fig = base_fig("Melody: pitch track over a constant-Q spectrogram", height=480)
    fig.add_trace(go.Heatmap(z=spec["db"], x=spec["times"], y=spec["midi"], colorscale=SPEC_SCALE, zmin=-70, zmax=0,
                             showscale=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=pt["times"], y=pt["midi"], mode="lines", line=dict(color=AQUA, width=3),
                             name="estimated pitch", connectgaps=False, customdata=np.c_[labels, pt["vprob"]],
                             hovertemplate="%{x:.2f} s · %{customdata[0]} · confidence %{customdata[1]:.2f}<extra></extra>"))
    fig.update_yaxes(title="pitch", tickvals=tickvals, ticktext=ticktext,
                     range=[an.librosa.hz_to_midi(fmin) - 3, an.librosa.hz_to_midi(fmax) + 3])
    fig.update_xaxes(title="time (s)", range=[0, duration])
    synced_plot(fig, wav, key="pitch", height=480)

    st.markdown(
        "#### Which pitches does the performer use?\n"
        "Every voiced frame is dropped into a histogram, weighted by the tracker's confidence. The left panel shows the "
        "range; the right folds everything into one octave so the **pitch set** stands out. Grey lines mark equal-tempered "
        "semitones: peaks between the lines are intervals the piano does not have.")
    hist = an.pitch_histograms(pt["midi"], pt["vprob"])
    if hist["empty"]:
        st.info("No pitched frames were found in this range. Try widening the pitch limits.")
    else:
        h1, h2 = st.columns([1.3, 1])
        fig = base_fig("Time spent at each pitch", height=320)
        fig.add_trace(go.Scatter(x=hist["full_centres"], y=hist["full"], fill="tozeroy", mode="lines",
                                 line=dict(color=BLUE, width=1), fillcolor=BLUE, opacity=0.85,
                                 customdata=[an.note_label(m) for m in hist["full_centres"]],
                                 hovertemplate="%{customdata}<extra></extra>"))
        tv, tt = note_ticks(hist["full_centres"])
        for m in range(int(hist["full_centres"].min()), int(hist["full_centres"].max()) + 2):
            fig.add_vline(x=m, line=dict(color=GRID, width=1))
        fig.update_xaxes(title="pitch", tickvals=tv, ticktext=tt); fig.update_yaxes(showticklabels=False, title="weight")
        h1.plotly_chart(fig, width="stretch")

        fig = base_fig("Folded into one octave", height=320)
        fig.add_trace(go.Scatter(x=hist["pc_centres"], y=hist["pc"], fill="tozeroy", mode="lines",
                                 line=dict(color=BLUE, width=1), fillcolor=BLUE, opacity=0.85,
                                 customdata=[f"{an.NOTE_NAMES[int(c // 100) % 12]} {int(c % 100):+d}¢" if c % 100 < 50 else f"{an.NOTE_NAMES[int(c // 100 + 1) % 12]} {int(c % 100) - 100:+d}¢" for c in hist["pc_centres"]],
                                 hovertemplate="%{customdata}<extra></extra>"))
        for c in range(0, 1200, 100):
            fig.add_vline(x=c, line=dict(color=GRID, width=1))
        fig.update_xaxes(title="pitch class", tickvals=list(range(0, 1200, 100)), ticktext=an.NOTE_NAMES, range=[0, 1200])
        fig.update_yaxes(showticklabels=False, title="weight")
        h2.plotly_chart(fig, width="stretch")

    st.markdown(
        "#### Pitch classes over time (chroma)\n"
        "For music with several voices, a **chromagram** shows how much energy falls into each of the twelve pitch classes at "
        "each moment, ignoring octave. A single voice draws one line; chords light several rows at once; speech scatters "
        "everywhere. The profile on the right is the time average, and its entropy is a one-number measure of how tonal the "
        "clip is (3.58 bits would be perfectly flat).")
    ch = chroma_for(clip_key)
    c1, c2 = st.columns([3, 1])
    fig = base_fig("Chromagram (harmonic layer, background removed)", height=340)
    fig.add_trace(go.Heatmap(z=ch["chroma"], x=ch["times"], y=an.NOTE_NAMES, colorscale=RAMP_SCALE, showscale=False,
                             hovertemplate="%{x:.2f} s · %{y}<extra></extra>"))
    fig.update_xaxes(title="time (s)", range=[0, duration]); fig.update_yaxes(title="pitch class")
    with c1:
        synced_plot(fig, wav, key="chroma", height=340)
    fig = base_fig(f"Profile · {ch['entropy']:.2f} bits", height=340)
    fig.add_trace(go.Bar(x=an.NOTE_NAMES, y=ch["profile"], marker_color=KIND_COLOUR[row.kind],
                         hovertemplate="%{x}: %{y:.1%}<extra></extra>"))
    fig.update_yaxes(showticklabels=False)
    c2.plotly_chart(fig, width="stretch")

# ---- Rhythm ----------------------------------------------------------------
with tab_rhythm:
    st.markdown(
        "Rhythm analysis starts from **onsets**: moments where something new begins. The grey curve measures how much "
        "energy has just appeared in each frame; orange ticks are detected onsets and green ticks the tracked **beats**. "
        "Listen with the click track to judge whether the tracker found the pulse you feel.")
    code_button("rhythm", "Onsets, beats and tempo", RECIPES["rhythm"], [an.rhythm, an.click_mix])
    c1, c2 = st.columns([2, 1])
    tempo_min, tempo_max = c1.slider("Tempo range to search (BPM)", 30, 400, (60, 240), step=5,
                                     help="Tempo curves peak at the pulse and at its halves and doubles. Narrow the range to pick the level you hear as the beat.")
    show_clicks = c2.toggle("Add clicks on the beats to the audio", value=True)

    rh = rhythm_for(clip_key, tempo_min, tempo_max)
    audio_rh = an.wav_bytes(an.click_mix(y, rh["beats"], sr), sr) if show_clicks else wav

    def tick_trace(times, y0, y1, colour, name):
        xs = np.repeat(times, 3); ys = np.tile([y0, y1, None], len(times))
        return go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=colour, width=1.6), name=name,
                          hovertemplate="%{x:.2f} s<extra>" + name + "</extra>")

    top = float(rh["oenv"].max()) or 1.0
    fig = base_fig(f"Onsets and beats · estimated tempo {rh['tempo']:.0f} BPM", height=340)
    fig.add_trace(go.Scatter(x=rh["times"], y=rh["oenv"], mode="lines", line=dict(color=INK2, width=1.2), name="onset strength",
                             hovertemplate="%{x:.2f} s · %{y:.1f}<extra></extra>"))
    fig.add_trace(tick_trace(rh["onsets"], 0, top * 0.9, ORANGE, f"onsets ({len(rh['onsets'])})"))
    fig.add_trace(tick_trace(rh["beats"], top * 0.9, top * 1.1, AQUA, f"beats ({len(rh['beats'])})"))
    fig.update_xaxes(title="time (s)", range=[0, duration]); fig.update_yaxes(showticklabels=False, title="onset strength")
    synced_plot(fig, audio_rh, key="rhythm", height=340)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Tempo curve.** How strongly the onsets repeat at each tempo. Peaks appear at the pulse and at "
                    "its multiples; which one is *the* beat is a musical judgement.")
        sel = (rh["bpm_axis"] >= 30) & (rh["bpm_axis"] <= 400)
        fig = base_fig("Global tempo curve", height=300)
        fig.add_trace(go.Scatter(x=rh["bpm_axis"][sel], y=rh["curve"][sel], mode="lines", line=dict(color=BLUE, width=2),
                                 hovertemplate="%{x:.0f} BPM<extra></extra>", name="periodicity"))
        # Shapes on a log axis take log10 coordinates in Plotly.
        fig.add_vrect(x0=np.log10(tempo_min), x1=np.log10(tempo_max), fillcolor=BLUE, opacity=0.06, line_width=0)
        fig.add_vline(x=np.log10(rh["tempo"]), line=dict(color=ORANGE, width=1.5),
                      annotation_text=f"{rh['tempo']:.0f} BPM", annotation_position="top right")
        fig.update_xaxes(type="log", title="tempo (BPM)", tickvals=[40, 60, 90, 120, 180, 240, 360], range=[np.log10(30), np.log10(400)])
        fig.update_yaxes(showticklabels=False)
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.markdown("**Inter-onset intervals.** The time from each onset to the next. Clusters at simple ratios "
                    "(1 : 2 : 3) mean the music is metrically organised; a smear means it is not.")
        beat_ms = 60000 / rh["tempo"]
        fig = base_fig("Gaps between onsets", height=300)
        if len(rh["ioi_ms"]):
            fig.add_trace(go.Histogram(x=rh["ioi_ms"], xbins=dict(start=0, end=3 * beat_ms, size=25), marker_color=BLUE,
                                       hovertemplate="%{x} ms: %{y}<extra></extra>", name="intervals"))
        for k, lab in [(0.5, "½"), (1, "1 beat"), (2, "2 beats")]:
            fig.add_vline(x=k * beat_ms, line=dict(color=GRID, width=1.5), annotation_text=lab,
                          annotation_position="top right", annotation_font_color=MUTED)
        fig.update_xaxes(title="interval (ms)", range=[0, 3 * beat_ms]); fig.update_yaxes(title="count")
        fig.update_layout(showlegend=False, bargap=0.08)
        st.plotly_chart(fig, width="stretch")
    with c3:
        st.markdown("**Folded onto the beat.** Each row is one beat, left to right is position within the beat. "
                    "Repeating vertical stripes are a recurring rhythmic figure; rows that change show the pattern changing.")
        fold = rh["fold"]
        fig = base_fig("Onset strength per beat", height=300)
        fig.add_trace(go.Heatmap(z=fold, x=(np.arange(fold.shape[1]) + 0.5) / fold.shape[1], y=np.arange(1, len(fold) + 1),
                                 colorscale=RAMP_SCALE, showscale=False,
                                 hovertemplate="beat %{y} · %{x:.2f} of the way to the next<extra></extra>"))
        fig.update_xaxes(title="position within beat", tickvals=[0, 0.25, 0.5, 0.75, 1], ticktext=["beat", "¼", "½", "¾", "next"])
        fig.update_yaxes(title="beat number")
        st.plotly_chart(fig, width="stretch")

# ---- Tempogram -------------------------------------------------------------
with tab_tempo:
    st.markdown(
        "A **tempogram** is to rhythm what a spectrogram is to pitch. At each moment it shows how strongly the onsets "
        "repeat at every possible tempo: the **autocorrelation** version compares the onset envelope with delayed copies "
        "of itself inside a sliding window, the **Fourier** version takes a short-time Fourier transform of the envelope. "
        "Bright horizontal bands are steady pulses. Bands at double and half the main tempo are the same pulse counted "
        "in different units, which is why a single BPM number is always a judgement.")
    code_button("tempogram", "Tempograms", RECIPES["tempogram"], [an.tempogram])
    c1, c2, c3 = st.columns([1.2, 1.2, 1])
    tg_kind = c1.radio("Method", ["Autocorrelation", "Fourier"], horizontal=True)
    tg_win = c2.select_slider("Window length", options=[128, 192, 256, 384, 512, 768], value=384,
                              format_func=lambda v: f"{v} frames ≈ {v * an.HOP / an.SR:.1f} s",
                              help="Longer windows give a steadier, sharper tempo estimate; shorter ones follow tempo changes.")
    tg_show_curve = c3.toggle("Show the global tempo curve", value=True)

    tgm = tempogram_for(clip_key, tg_win, tg_kind.lower())
    fig = base_fig(f"{tg_kind} tempogram · strongest pulse overall {tgm['tempo']:.0f} BPM", height=440)
    fig.add_trace(go.Heatmap(z=tgm["tg"], x=tgm["times"], y=tgm["bpm"], colorscale=RAMP_SCALE, showscale=False,
                             hovertemplate="%{x:.2f} s · %{y:.0f} BPM · strength %{z:.2f}<extra></extra>"))
    fig.add_shape(type="line", x0=0, x1=duration, y0=np.log10(tgm["tempo"]), y1=np.log10(tgm["tempo"]),
                  line=dict(color=ORANGE, width=1.4, dash="dot"))
    fig.update_yaxes(type="log", title="tempo (BPM)", tickvals=[30, 40, 60, 90, 120, 180, 240, 360],
                     range=[np.log10(30), np.log10(400)])
    fig.update_xaxes(title="time (s)", range=[0, duration])
    synced_plot(fig, wav, key="tempogram", height=440)

    if tg_show_curve:
        c1, c2 = st.columns([1, 1.4])
        with c1:
            fig = base_fig("Global tempo curve (mean over time)", height=320)
            fig.add_trace(go.Scatter(x=tgm["bpm"], y=tgm["curve"], mode="lines", line=dict(color=BLUE, width=2),
                                     hovertemplate="%{x:.0f} BPM · %{y:.2f}<extra></extra>", name="periodicity"))
            fig.add_vline(x=np.log10(tgm["tempo"]), line=dict(color=ORANGE, width=1.4),
                          annotation_text=f"{tgm['tempo']:.0f} BPM", annotation_position="top right")
            fig.update_xaxes(type="log", title="tempo (BPM)", tickvals=[30, 40, 60, 90, 120, 180, 240, 360],
                             range=[np.log10(30), np.log10(400)])
            fig.update_yaxes(showticklabels=False); fig.update_layout(showlegend=False)
            st.plotly_chart(fig, width="stretch")
        with c2:
            st.markdown(
                "**Reading the two plots together.** The tempogram on top tells you *when* a pulse is present and "
                "whether it drifts; the curve on the left averages it into one profile. Peaks in the curve at ratios "
                "of 2 : 1 are the same pulse heard at different levels (beats versus half-beats or bars), and peaks at "
                "3 : 1 hint at triple grouping. A flat, noisy curve means no steady pulse at all, which is what "
                "speech and free-rhythm music look like. Switch to the Fourier method for a smoother picture that "
                "does not show sub-harmonics; use the autocorrelation method when you want to see all the levels.")

# ---- Structure -------------------------------------------------------------
with tab_struct:
    st.markdown(
        "Music repeats. A **self-similarity matrix** compares every moment of the recording with every other moment: "
        "a dark cell means the two moments sound alike. The main diagonal (each moment matched with itself) is masked "
        "out, so anything visible is a genuine recurrence. **Stripes parallel to the diagonal** are passages that come "
        "back later at the same speed; **blocks** are stretches that are internally homogeneous. As the clip plays, the "
        "crosshair marks the current moment on both axes: look along its row to see when that moment recurs.")
    code_button("structure", "Self-similarity and lag matrices", RECIPES["structure"], [an.self_similarity])
    c1, c2, c3 = st.columns([1.3, 1.2, 1])
    feat_choice = c1.radio("Compare moments by", ["Pitch content (chroma)", "Timbre (MFCC)", "Both"], horizontal=True)
    feat_key = {"Pitch content (chroma)": "chroma", "Timbre (MFCC)": "mfcc", "Both": "chroma+mfcc"}[feat_choice]
    n_steps = c2.slider("Context per comparison", 1, 16, 8,
                        format="%d cells", help="How many consecutive ~93 ms cells are stacked before comparing. "
                                                 "More context matches whole motifs; less context matches single notes.")
    sparsity = c3.select_slider("Show only the closest matches", options=["all", "20%", "10%", "5%"], value="all",
                                help="Keep only each moment's k nearest neighbours, which cleans up noisy matrices.")

    ss_probe = structure_for(clip_key, feat_key, n_steps, None)
    n_cells = ss_probe["R"].shape[0]
    k = None if sparsity == "all" else max(2, int(n_cells * float(sparsity.strip("%")) / 100))
    ss = ss_probe if k is None else structure_for(clip_key, feat_key, n_steps, k)
    ctx_s = n_steps * ss["cell"]
    st.caption(f"{n_cells} × {n_cells} cells of {ss['cell']*1000:.0f} ms · each comparison covers about {ctx_s:.2f} s of context")

    c1, c2 = st.columns(2)
    with c1:
        fig = base_fig("Self-similarity: which moments sound alike", height=520)
        fig.add_trace(go.Heatmap(z=ss["R"], x=ss["times"], y=ss["times"], colorscale=RAMP_SCALE, showscale=False, zmin=0,
                                 hovertemplate="%{x:.2f} s ↔ %{y:.2f} s · similarity %{z:.2f}<extra></extra>"))
        fig.update_xaxes(title="time (s)", range=[0, duration], constrain="domain")
        fig.update_yaxes(title="time (s)", range=[0, duration], scaleanchor="x", scaleratio=1)
        synced_plot(fig, wav, key="structure", height=520, crosshair=True)
    with c2:
        fig = base_fig("Time-lag view: repeats at a fixed delay become horizontal lines", height=520)
        fig.add_trace(go.Heatmap(z=ss["L"], x=ss["times"], y=ss["lags"], colorscale=RAMP_SCALE, showscale=False, zmin=0,
                                 hovertemplate="at %{x:.2f} s, similar to %{y:+.2f} s away · %{z:.2f}<extra></extra>"))
        fig.add_hline(y=0, line=dict(color=GRID, width=1))
        fig.update_xaxes(title="time (s)", range=[0, duration]); fig.update_yaxes(title="lag (s)")
        synced_plot(fig, wav, key="lag", height=520)

    st.markdown(
        "**How to read the lag view.** The horizontal axis is still time; the vertical axis is *how far away* a "
        "matching moment is. A phrase that returns 4 seconds later draws a horizontal segment at lag +4 s for as long "
        "as the two phrases run in parallel, and its mirror at lag −4 s. Horizontal lines are therefore the length "
        "of a repeating cycle, and their vertical spacing is the period of the form.")

# ---- Layers ----------------------------------------------------------------
with tab_layers:
    st.markdown(
        "**Harmonic/percussive separation** splits the spectrogram into the parts that are smooth along time (held tones, "
        "which draw horizontal lines) and the parts smooth along frequency (attacks, which draw vertical lines). "
        "Listen to each layer on its own: melody and accompaniment, or voice and drums, come apart.")
    code_button("layers", "Harmonic/percussive separation", RECIPES["layers"], [an.separate, an.cqt_db])
    margin = st.slider("Separation strength", 1.0, 5.0, 2.0, 0.5,
                       help="Higher values push more ambiguous energy out of the percussive layer.")
    y_h, y_p = layers_for(clip_key, margin)
    share = float((y_h ** 2).sum() / ((y ** 2).sum() + 1e-9))
    st.caption(f"{share:.0%} of the energy in this excerpt is in the harmonic (sustained) layer, "
               f"{1 - share:.0%} in the percussive layer.")

    sub_tabs = st.tabs(["Full mix", "Harmonic layer (sustained)", "Percussive layer (attacks)"])
    for sub, (sig, title, key) in zip(sub_tabs, [(y, "Full mix", "mix"), (y_h, "Harmonic layer: held tones and their harmonics", "harm"),
                                                 (y_p, "Percussive layer: attacks and noise", "perc")]):
        spec = an.cqt_db(sig, sr, fmin_note="C2", n_octaves=6)
        tickvals, ticktext = note_ticks(spec["midi"])
        fig = base_fig(title, height=460)
        fig.add_trace(go.Heatmap(z=spec["db"], x=spec["times"], y=spec["midi"], colorscale=SPEC_SCALE, zmin=-70, zmax=0,
                                 colorbar=dict(title="dB", thickness=12),
                                 customdata=np.tile([an.librosa.midi_to_note(int(m), unicode=True) for m in spec["midi"]], (len(spec["times"]), 1)).T,
                                 hovertemplate="%{x:.2f} s · %{customdata} · %{z:.0f} dB<extra></extra>"))
        fig.update_yaxes(title="pitch", tickvals=tickvals, ticktext=ticktext)
        fig.update_xaxes(title="time (s)", range=[0, duration])
        with sub:
            synced_plot(fig, an.wav_bytes(sig, sr), key=key, height=460)

# ---- The collection --------------------------------------------------------
with tab_all:
    st.markdown(
        "The same measurements run over **all 190 excerpts** (and the added examples). Each point is one clip; the selected excerpt is ringed. "
        "Pulse strength is the height of the tallest tempo-curve peak (how regular the rhythm is); harmonic share is the "
        "fraction of energy in sustained tones; tonal entropy is the flatness of the pitch-class profile. Hover to identify "
        "any point, then choose it in the sidebar with *Show all excerpts* switched on.")
    code_button("all", "Collection-wide features", RECIPES["all"], [an.load_features])
    feats = features_table()
    if feats is None:
        st.info("Run the notebook once to build `features/clip_features.csv`, then reload this page.")
    else:
        table = meta.join(feats, how="inner")
        c1, c2 = st.columns(2)
        xcol = c1.selectbox("Horizontal axis", ["pulse_strength", "harmonic_share", "tonal_entropy", "tempo", "centroid", "rms_cv"], index=0,
                            format_func=lambda c: {"pulse_strength": "pulse strength", "harmonic_share": "harmonic share",
                                                   "tonal_entropy": "tonal entropy (bits)", "tempo": "tempo (BPM)",
                                                   "centroid": "spectral centroid (Hz, brightness)", "rms_cv": "loudness variation"}[c])
        ycol = c2.selectbox("Vertical axis", ["harmonic_share", "pulse_strength", "tonal_entropy", "tempo", "centroid", "rms_cv"], index=0,
                            format_func=lambda c: {"pulse_strength": "pulse strength", "harmonic_share": "harmonic share",
                                                   "tonal_entropy": "tonal entropy (bits)", "tempo": "tempo (BPM)",
                                                   "centroid": "spectral centroid (Hz, brightness)", "rms_cv": "loudness variation"}[c])
        fig = base_fig("Every excerpt in the collection", height=520)
        for kind in ["speech", "music"]:
            g = table[table.kind == kind]
            fig.add_trace(go.Scatter(x=g[xcol], y=g[ycol], mode="markers", name=f"{kind} ({len(g)})",
                                     marker=dict(color=KIND_COLOUR[kind], size=9, line=dict(color="white", width=1)),
                                     customdata=np.c_[g.title.str[:50], g.index, g.year.fillna(0).astype(int).astype(str).replace("0", "")],
                                     hovertemplate="%{customdata[0]}<br>%{customdata[1]} %{customdata[2]}<extra></extra>"))
        if item in table.index:
            r = table.loc[item]
            fig.add_trace(go.Scatter(x=[r[xcol]], y=[r[ycol]], mode="markers", name="selected excerpt",
                                     marker=dict(color="rgba(0,0,0,0)", size=20, line=dict(color=AQUA, width=3)),
                                     hoverinfo="skip"))
        fig.update_xaxes(title=xcol.replace("_", " ")); fig.update_yaxes(title=ycol.replace("_", " "))
        st.plotly_chart(fig, width="stretch")

        st.markdown("#### Where the excerpts were recorded")
        geo = table.dropna(subset=["lat", "lon"])
        fig = base_fig("Recording locations", height=420)
        for kind in ["speech", "music"]:
            g = geo[geo.kind == kind]
            fig.add_trace(go.Scattergeo(lon=g.lon, lat=g.lat, mode="markers", name=kind,
                                        marker=dict(color=KIND_COLOUR[kind], size=8, line=dict(color="white", width=1)),
                                        customdata=np.c_[g.title.str[:50], g.index],
                                        hovertemplate="%{customdata[0]}<br>%{customdata[1]}<extra></extra>"))
        if item in geo.index:
            r = geo.loc[item]
            fig.add_trace(go.Scattergeo(lon=[r.lon], lat=[r.lat], mode="markers", name="selected excerpt",
                                        marker=dict(color="rgba(0,0,0,0)", size=18, line=dict(color=AQUA, width=3)), hoverinfo="skip"))
        # Centre on the Pacific so points east of 180° (Cook Islands, Tahiti) stay on the map.
        fig.update_geos(projection=dict(type="natural earth", rotation=dict(lon=140)), showcountries=True,
                        countrycolor=GRID, landcolor="#f4f3ef", showocean=True, oceancolor="#ffffff",
                        lataxis_range=[-45, 55], lonaxis_range=[-140, 85])
        fig.update_layout(margin=dict(l=0, r=0, t=44, b=0))
        st.plotly_chart(fig, width="stretch")

# ---- About librosa ---------------------------------------------------------
with tab_about:
    st.markdown(f"""
**[librosa](https://librosa.org)** is an open-source Python library for music and audio analysis, started by
Brian McFee and collaborators in 2015 and still the most widely used toolkit for turning a recording into
numbers a researcher can reason about. It sits on NumPy and SciPy, reads audio through *soundfile*, and draws
with matplotlib. Everything in this app is computed with it (version {an.librosa.__version__} is installed here).

librosa does not try to be an end-to-end application. It is a box of well-documented building blocks: load a
file, cut it into frames, transform each frame, and hand back arrays whose rows and columns you already
understand. That design is why the recipes behind the *How this is computed* buttons are so short.
""")

    st.markdown("#### How the library is organised")
    st.table(pd.DataFrame(gallery.MODULES, columns=["module", "what it provides"]).set_index("module"))

    st.markdown("""
#### The visualisations librosa produces natively

librosa's plotting lives in one small module, `librosa.display`, with two functions that do almost all the work:

- **`waveshow`** draws a waveform with a proper time axis.
- **`specshow`** draws any time-frequency matrix as an image and labels the axes musically. The same call
  handles a spectrogram, a chromagram, a tempogram or a similarity matrix; you only change `y_axis` to
  `'log'`, `'mel'`, `'cqt_note'`, `'chroma'`, `'tempo'` or `'lag'`.

Everything else (a pitch track, beat markers, a histogram) is ordinary matplotlib laid on top, using
librosa's `times_like` and `frames_to_time` helpers to line the axes up. Below, each of these plot types is
rendered by librosa itself for the excerpt currently selected in the sidebar, with the code that made it.
The interactive tabs in this app reproduce the same pictures in Plotly so that they can carry hover
labels and a playback cursor.
""")

    for i, entry in enumerate(gallery_for(clip_key)):
        left, right = st.columns([1.35, 1])
        with left:
            st.image(entry["png"], width="stretch")
        with right:
            st.markdown(f"**{entry['title']}**  \n{entry['blurb']}")
            st.code(entry["code"], language="python")
        if i < 9:
            st.divider()

    st.markdown("""
#### Further reading

- librosa documentation and gallery of examples: <https://librosa.org/doc/latest/>
- McFee, B. et al. (2015). *librosa: Audio and Music Signal Analysis in Python.* Proceedings of the 14th
  Python in Science Conference (SciPy 2015).
- Müller, M. *Fundamentals of Music Processing* and the open FMP notebooks, which use librosa throughout:
  <https://www.audiolabs-erlangen.de/resources/MIR/FMP/>
""")
