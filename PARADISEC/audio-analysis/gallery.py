"""A gallery of the plots librosa draws natively through ``librosa.display``.

Each entry renders one figure with matplotlib for a given signal and returns it
as PNG bytes together with the code that produced it, so the app can show the
picture and the recipe side by side. Everything here uses librosa's own display
helpers (``waveshow`` and ``specshow``) rather than the app's Plotly figures.
"""
from __future__ import annotations

import io
from textwrap import dedent

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import librosa  # noqa: E402
import librosa.display  # noqa: E402
import numpy as np  # noqa: E402

HOP = 512
FIGSIZE = (7.5, 3.1)

MODULES = [
    ("librosa", "Loading, resampling, STFT/CQT, pitch (pyin, yin), unit conversions such as hz_to_note"),
    ("librosa.feature", "Spectrograms and descriptors: mel, chroma, MFCC, spectral centroid, tempogram, RMS"),
    ("librosa.onset", "Onset strength envelopes and onset detection"),
    ("librosa.beat", "Beat tracking, tempo estimation, predominant local pulse"),
    ("librosa.effects", "Harmonic/percussive separation, time stretching, pitch shifting, trimming silence"),
    ("librosa.decompose", "Matrix factorisation of spectrograms and nearest-neighbour filtering"),
    ("librosa.segment", "Self-similarity, recurrence and lag matrices, structural segmentation"),
    ("librosa.display", "Matplotlib helpers: waveshow and specshow with musically labelled axes"),
    ("librosa.util", "Frame slicing, normalisation, peak picking and other utilities"),
]


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _fig():
    fig, ax = plt.subplots(figsize=FIGSIZE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    return fig, ax


def render_gallery(y: np.ndarray, sr: int) -> list[dict]:
    """Return a list of {title, blurb, code, png} for the native librosa plots."""
    out = []

    # 1. Waveform ---------------------------------------------------------------
    fig, ax = _fig()
    librosa.display.waveshow(y, sr=sr, ax=ax, color="#2a78d6")
    ax.set(title="librosa.display.waveshow")
    out.append(dict(
        title="Waveform",
        blurb="Amplitude against time. `waveshow` draws the signal envelope at low zoom and the true "
              "sample values when you zoom in.",
        code="""
            librosa.display.waveshow(y, sr=sr, ax=ax)
        """, png=_png(fig)))

    # 2. Power spectrogram, log frequency ---------------------------------------
    D = librosa.amplitude_to_db(np.abs(librosa.stft(y, hop_length=HOP)), ref=np.max)
    fig, ax = _fig()
    img = librosa.display.specshow(D, sr=sr, hop_length=HOP, x_axis="time", y_axis="log", ax=ax)
    fig.colorbar(img, ax=ax, format="%+2.0f dB")
    ax.set(title="specshow(y_axis='log')")
    out.append(dict(
        title="Spectrogram (STFT, log frequency)",
        blurb="The workhorse view. `specshow` labels the axes from the sample rate and hop length; "
              "`y_axis` can be 'linear', 'log', 'mel', 'cqt_hz', 'cqt_note', 'chroma', 'tempo' or 'lag'.",
        code="""
            D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)
            librosa.display.specshow(D, sr=sr, x_axis="time", y_axis="log", ax=ax)
        """, png=_png(fig)))

    # 3. Mel spectrogram ----------------------------------------------------------
    M = librosa.power_to_db(librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128, hop_length=HOP), ref=np.max)
    fig, ax = _fig()
    img = librosa.display.specshow(M, sr=sr, hop_length=HOP, x_axis="time", y_axis="mel", ax=ax)
    fig.colorbar(img, ax=ax, format="%+2.0f dB")
    ax.set(title="specshow(y_axis='mel')")
    out.append(dict(
        title="Mel spectrogram",
        blurb="Energy pooled into perceptually spaced bands. The standard input to machine-listening models.",
        code="""
            M = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128)
            librosa.display.specshow(librosa.power_to_db(M, ref=np.max), sr=sr, x_axis="time", y_axis="mel", ax=ax)
        """, png=_png(fig)))

    # 4. Constant-Q with note names ------------------------------------------------
    C = librosa.amplitude_to_db(np.abs(librosa.cqt(y, sr=sr, hop_length=HOP, fmin=librosa.note_to_hz("C2"), n_bins=72)), ref=np.max)
    fig, ax = _fig()
    img = librosa.display.specshow(C, sr=sr, hop_length=HOP, x_axis="time", y_axis="cqt_note",
                                   fmin=librosa.note_to_hz("C2"), ax=ax)
    fig.colorbar(img, ax=ax, format="%+2.0f dB")
    ax.set(title="specshow(y_axis='cqt_note')")
    out.append(dict(
        title="Constant-Q spectrogram with note names",
        blurb="One bin per semitone, so harmonics are evenly spaced and the y axis reads in notes. "
              "The natural background for a melody.",
        code="""
            C = np.abs(librosa.cqt(y, sr=sr, fmin=librosa.note_to_hz("C2"), n_bins=72))
            librosa.display.specshow(librosa.amplitude_to_db(C, ref=np.max), sr=sr,
                                     x_axis="time", y_axis="cqt_note", fmin=librosa.note_to_hz("C2"), ax=ax)
        """, png=_png(fig)))

    # 5. Pitch track over the spectrogram -------------------------------------------
    f0, _, _ = librosa.pyin(y, fmin=librosa.note_to_hz("C3"), fmax=librosa.note_to_hz("C6"), sr=sr, hop_length=HOP)
    f0 = np.where(f0 > librosa.note_to_hz("C3") * 1.02, f0, np.nan)
    times = librosa.times_like(f0, sr=sr, hop_length=HOP)
    fig, ax = _fig()
    librosa.display.specshow(D, sr=sr, hop_length=HOP, x_axis="time", y_axis="log", ax=ax)
    ax.plot(times, f0, color="#1baf7a", linewidth=2.5, label="pyin f0")
    ax.set(ylim=(100, 4000), title="pyin over specshow"); ax.legend(loc="upper right")
    out.append(dict(
        title="Pitch track (pYIN) over the spectrogram",
        blurb="Not a display function itself, but the canonical combination: `pyin` gives a frequency per frame "
              "and `times_like` gives the matching time axis, so the track plots straight onto `specshow`.",
        code="""
            f0, voiced, prob = librosa.pyin(y, fmin=librosa.note_to_hz("C3"), fmax=librosa.note_to_hz("C6"), sr=sr)
            times = librosa.times_like(f0, sr=sr)
            librosa.display.specshow(D, sr=sr, x_axis="time", y_axis="log", ax=ax)
            ax.plot(times, f0, linewidth=2.5)
        """, png=_png(fig)))

    # 6. Chromagram -------------------------------------------------------------------
    chroma = librosa.feature.chroma_cqt(y=librosa.effects.harmonic(y), sr=sr, hop_length=HOP)
    fig, ax = _fig()
    img = librosa.display.specshow(chroma, sr=sr, hop_length=HOP, x_axis="time", y_axis="chroma", ax=ax, cmap="Blues")
    fig.colorbar(img, ax=ax)
    ax.set(title="specshow(y_axis='chroma')")
    out.append(dict(
        title="Chromagram",
        blurb="Energy per pitch class (C to B) over time, octave folded. Chords light several rows at once.",
        code="""
            chroma = librosa.feature.chroma_cqt(y=librosa.effects.harmonic(y), sr=sr)
            librosa.display.specshow(chroma, sr=sr, x_axis="time", y_axis="chroma", ax=ax)
        """, png=_png(fig)))

    # 7. MFCC ---------------------------------------------------------------------------
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20, hop_length=HOP)
    fig, ax = _fig()
    img = librosa.display.specshow(mfcc, sr=sr, hop_length=HOP, x_axis="time", ax=ax)
    fig.colorbar(img, ax=ax)
    ax.set(title="specshow(mfcc)", ylabel="MFCC coefficient")
    out.append(dict(
        title="MFCCs (timbre)",
        blurb="Mel-frequency cepstral coefficients summarise the spectral shape in a few numbers per frame. "
              "Hard to read by eye, but the standard fingerprint of timbre for comparing recordings.",
        code="""
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
            librosa.display.specshow(mfcc, sr=sr, x_axis="time", ax=ax)
        """, png=_png(fig)))

    # 8. Onsets and beats ---------------------------------------------------------------
    oenv = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    tempo, beats = librosa.beat.beat_track(onset_envelope=oenv, sr=sr, hop_length=HOP)
    t_o = librosa.times_like(oenv, sr=sr, hop_length=HOP)
    fig, ax = _fig()
    ax.plot(t_o, oenv, color="#52514e", linewidth=1, label="onset strength")
    ax.vlines(librosa.frames_to_time(beats, sr=sr, hop_length=HOP), 0, oenv.max(), color="#1baf7a", alpha=0.9, label="beats")
    ax.set(title=f"onset_strength + beat_track ({float(np.atleast_1d(tempo)[0]):.0f} BPM)", xlabel="time (s)")
    ax.legend(loc="upper right")
    out.append(dict(
        title="Onset strength and beats",
        blurb="Plain matplotlib on top of librosa's rhythm functions: the onset envelope as a line, tracked beats "
              "as vertical marks.",
        code="""
            oenv = librosa.onset.onset_strength(y=y, sr=sr)
            tempo, beats = librosa.beat.beat_track(onset_envelope=oenv, sr=sr)
            ax.plot(librosa.times_like(oenv, sr=sr), oenv)
            ax.vlines(librosa.frames_to_time(beats, sr=sr), 0, oenv.max())
        """, png=_png(fig)))

    # 9. Tempogram ------------------------------------------------------------------------
    tg = librosa.feature.tempogram(onset_envelope=oenv, sr=sr, hop_length=HOP)
    fig, ax = _fig()
    img = librosa.display.specshow(tg, sr=sr, hop_length=HOP, x_axis="time", y_axis="tempo", ax=ax, cmap="Blues")
    ax.set(ylim=(30, 400), title="specshow(y_axis='tempo')")
    fig.colorbar(img, ax=ax)
    out.append(dict(
        title="Tempogram",
        blurb="How strongly the onsets repeat at every tempo, moment by moment. Horizontal bands are steady pulses; "
              "bands at doubles and halves are the same pulse counted differently.",
        code="""
            tg = librosa.feature.tempogram(onset_envelope=oenv, sr=sr)
            librosa.display.specshow(tg, sr=sr, x_axis="time", y_axis="tempo", ax=ax)
        """, png=_png(fig)))

    # 10. Recurrence matrix -----------------------------------------------------------------
    chroma_sync = librosa.util.sync(chroma, np.arange(0, chroma.shape[1], 4))
    feat = librosa.feature.stack_memory(chroma_sync, n_steps=8)
    R = librosa.segment.recurrence_matrix(feat, width=4, mode="affinity", sym=True, metric="cosine")
    fig, ax = plt.subplots(figsize=(4.2, 3.8))
    librosa.display.specshow(R, sr=sr, hop_length=HOP * 4, x_axis="time", y_axis="time", ax=ax, cmap="Blues")
    ax.set(title="specshow(recurrence_matrix)")
    out.append(dict(
        title="Self-similarity (recurrence) matrix",
        blurb="Every moment compared with every other. Stripes parallel to the diagonal are repeated passages; "
              "blocks are homogeneous sections. `y_axis='lag'` shows the same data as delays.",
        code="""
            feat = librosa.feature.stack_memory(chroma, n_steps=8)
            R = librosa.segment.recurrence_matrix(feat, width=4, mode="affinity", sym=True, metric="cosine")
            librosa.display.specshow(R, sr=sr, x_axis="time", y_axis="time", ax=ax)
        """, png=_png(fig)))

    for entry in out:
        entry["code"] = dedent(entry["code"]).strip()
    return out
