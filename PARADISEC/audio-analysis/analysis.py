"""Signal-analysis helpers shared by the Streamlit app.

Every function here is pure (no Streamlit calls) so it can be cached or tested
independently. Audio is analysed at 22.05 kHz mono with a 512-sample hop.
"""
from __future__ import annotations

import io
from pathlib import Path

import librosa
import numpy as np
import pandas as pd
import soundfile as sf

REPO = Path(__file__).parent / "soundscape"
AUDIO_DIR = REPO / "audio"
EXTRA_DIR = Path(__file__).parent / "extra_audio"     # baked-in examples beyond the soundscape set
FEATURE_CACHE = Path(__file__).parent / "features" / "clip_features.csv"
SR = 22_050
HOP = 512

NOTE_NAMES = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"]

# A lean, hand-picked set: mostly music, a little speech for contrast.
DEFAULT_ITEM = "DG1-LOM027307"   # the gamelan: a strong pulse and clear tones make every view legible
CURATED = [
    "RJL1-013",        # Enga tindi, solo sung narrative (PNG)
    "CRIM-0012",       # Voulant honneur, Renaissance chanson rendered from the score (CRIM project)
    "DG1-LOM027307",   # Gamelan klenang (Lombok)
    "WF2-1979001",     # Yimas mambu bamboo flutes (PNG)
    "CF1-005",         # Tarawangsa bowed lute with plucked jentreng (West Java)
    "HDF1-FY14",       # Fumon, sustained tones (Japan)
    "WS1-006",         # Makira Boys String Band (Vanuatu)
    "BM1-Iatmul5",     # Iatmul instrumental (Sepik, PNG)
    "IB1-002",         # United Church Choir, Salamo (PNG)
    "AM5-001",         # Shanghai Ancient Music Ensemble (Tang reconstructions)
    "GAC1-07",         # Italian folk ensemble
    "TC1-003",         # Paama instrumental (Vanuatu)
    "AC1-010",         # Lavukaleve women's dances (Solomon Islands)
    "CS2-27",          # Conversation in Abma (Vanuatu), speech
    "LG1-160520",      # Earthquake interview (Nepal), speech
    "TD1-P164",        # War recollections in Tok Pisin (Manus), speech
]


# --------------------------------------------------------------------------- #
# Metadata
# --------------------------------------------------------------------------- #
def load_meta() -> pd.DataFrame:
    """Merge the music/speech spreadsheet with the story-map CSV, indexed by item."""
    flags = pd.read_excel(AUDIO_DIR / "PDSC exerpts.xlsx")
    flags["kind"] = np.where(flags["Music"].notna(), "music", "speech")
    flags = flags.rename(columns={"File": "file", "Item": "item"})[["file", "item", "kind"]]

    chapters = pd.read_csv(REPO / "csv" / "Chapters.csv")
    chapters["file"] = chapters["Media Link"].str.replace("audio/", "", regex=False)
    chapters = chapters.rename(columns={
        "Chapter": "title", "Description": "description", "Date": "date",
        "Latitude": "lat", "Longitude": "lon", "Source": "url",
    })[["file", "title", "description", "date", "lat", "lon", "url"]]

    meta = flags.merge(chapters, on="file", how="left")
    meta["collection"] = meta["item"].str.split("-").str[0]
    meta["title"] = (meta["title"].fillna(meta["item"])
                     .str.replace(r"\s*\([^()]*\)\s*$", "", regex=True).str.strip())
    meta["year"] = pd.to_datetime(meta["date"], errors="coerce").dt.year
    meta["lon"] = np.where(meta["lon"] > 180, meta["lon"] - 360, meta["lon"])
    meta["url"] = meta["url"].fillna(
        "https://catalog.paradisec.org.au/collections/" + meta["collection"]
        + "/items/" + meta["item"].str.split("-", n=1).str[1])
    meta["credit"] = np.nan
    meta["licence"] = np.nan
    meta = pd.concat([meta, load_extra_meta()], ignore_index=True)
    return meta.set_index("item").sort_index()


def load_extra_meta() -> pd.DataFrame:
    """Examples baked into extra_audio/, described by extra_audio/extra_metadata.csv.

    Columns: file, item, kind, title, description, year, collection, url, credit, licence.
    To add an example, drop the audio file in extra_audio/ and add a row; add the item to
    CURATED if it should appear in the default list.
    """
    csv = EXTRA_DIR / "extra_metadata.csv"
    if not csv.exists():
        return pd.DataFrame()
    ex = pd.read_csv(csv)
    ex["file"] = "extra_audio/" + ex["file"].astype(str)          # resolved by load_audio
    ex["year"] = pd.to_numeric(ex.get("year"), errors="coerce")
    for col in ("date", "lat", "lon"):
        ex[col] = np.nan
    return ex[["file", "item", "kind", "title", "description", "date", "lat", "lon", "url",
               "collection", "year", "credit", "licence"]]


def clip_label(row: pd.Series, item: str) -> str:
    """Short label for the picker: title, year and kind. The item id is shown separately."""
    title = row.title if len(row.title) <= 42 else row.title[:40].rstrip() + "…"
    year = "" if pd.isna(row.year) else f" ({int(row.year)})"
    return f"{title}{year} · {row.kind}"


# --------------------------------------------------------------------------- #
# Audio
# --------------------------------------------------------------------------- #
def resolve_audio(file: str) -> Path:
    """Soundscape files live under AUDIO_DIR; baked-in examples are relative to this folder."""
    for candidate in (AUDIO_DIR / file, Path(__file__).parent / file, Path(file)):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(file)


def load_audio(key: str) -> tuple[np.ndarray, int]:
    """Load a clip. `key` is a file name, or 'file|start|end' (seconds) for a section of it."""
    file, *section = key.split("|")
    y, sr = librosa.load(resolve_audio(file), sr=SR, mono=True)
    if section:
        start, end = float(section[0]), float(section[1])
        y = y[int(start * sr): int(end * sr)]
    return y, sr


def wav_bytes(y: np.ndarray, sr: int = SR) -> bytes:
    """16-bit WAV in memory, peak-normalised so quiet clips are audible."""
    peak = np.max(np.abs(y)) or 1.0
    buf = io.BytesIO()
    sf.write(buf, (0.95 * y / peak).astype(np.float32), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def frame_times(n_frames: int, sr: int = SR) -> np.ndarray:
    return librosa.frames_to_time(np.arange(n_frames), sr=sr, hop_length=HOP)


# --------------------------------------------------------------------------- #
# Time domain
# --------------------------------------------------------------------------- #
def envelope(y: np.ndarray, sr: int = SR) -> dict:
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    return {"times": frame_times(len(rms), sr), "rms_db": librosa.amplitude_to_db(rms, ref=np.max)}


def downsampled_wave(y: np.ndarray, sr: int = SR, max_points: int = 6000) -> tuple[np.ndarray, np.ndarray]:
    """Min/max envelope of the waveform for plotting without a million points."""
    step = max(1, len(y) // max_points)
    n = (len(y) // step) * step
    blocks = y[:n].reshape(-1, step)
    t = np.arange(blocks.shape[0]) * step / sr
    return t, blocks


# --------------------------------------------------------------------------- #
# Spectrograms
# --------------------------------------------------------------------------- #
def stft_db(y: np.ndarray, sr: int = SR, n_fft: int = 2048) -> dict:
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=HOP))
    return {"db": librosa.amplitude_to_db(S, ref=np.max),
            "freqs": librosa.fft_frequencies(sr=sr, n_fft=n_fft),
            "times": frame_times(S.shape[1], sr)}


def mel_db(y: np.ndarray, sr: int = SR, n_fft: int = 2048, n_mels: int = 128) -> dict:
    M = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=n_fft, hop_length=HOP, n_mels=n_mels, fmax=sr / 2)
    return {"db": librosa.power_to_db(M, ref=np.max),
            "freqs": librosa.mel_frequencies(n_mels=n_mels, fmax=sr / 2),
            "times": frame_times(M.shape[1], sr)}


def cqt_db(y: np.ndarray, sr: int = SR, fmin_note: str = "C2", n_octaves: int = 5) -> dict:
    """Constant-Q spectrogram with one bin per semitone; returns MIDI numbers for the y axis."""
    fmin = librosa.note_to_hz(fmin_note)
    C = np.abs(librosa.cqt(y, sr=sr, hop_length=HOP, fmin=fmin, n_bins=12 * n_octaves, bins_per_octave=12))
    midi = librosa.hz_to_midi(fmin) + np.arange(12 * n_octaves)
    return {"db": librosa.amplitude_to_db(C, ref=np.max), "midi": midi, "times": frame_times(C.shape[1], sr)}


# --------------------------------------------------------------------------- #
# Pitch
# --------------------------------------------------------------------------- #
def pitch_track(y: np.ndarray, sr: int = SR, fmin: float = 100.0, fmax: float = 1200.0) -> dict:
    f0, _voiced, vprob = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr, hop_length=HOP)
    # In silence pYIN pins f0 to its floor; treat those frames as unvoiced.
    f0 = np.where(f0 > fmin * 1.02, f0, np.nan)
    midi = librosa.hz_to_midi(f0)
    return {"times": frame_times(len(f0), sr), "f0": f0, "midi": midi, "vprob": vprob}


def note_label(midi: float) -> str:
    """Nearest note name plus signed cents deviation, e.g. 'G♯3 +23¢'."""
    if np.isnan(midi):
        return ""
    nearest = int(np.round(midi))
    cents = int(np.round((midi - nearest) * 100))
    name = librosa.midi_to_note(nearest, unicode=True)
    return f"{name} {cents:+d}¢"


def pitch_histograms(midi: np.ndarray, weights: np.ndarray, bin_cents: int = 10) -> dict:
    ok = ~np.isnan(midi)
    m, w = midi[ok], weights[ok]
    if len(m) == 0:
        return {"empty": True}
    lo, hi = np.floor(m.min()) - 1, np.ceil(m.max()) + 1
    edges_full = np.arange(lo, hi + 1e-6, bin_cents / 100)
    h_full, _ = np.histogram(m, bins=edges_full, weights=w)
    edges_pc = np.arange(0, 1200 + 1e-6, bin_cents)
    h_pc, _ = np.histogram(np.mod(m, 12) * 100, bins=edges_pc, weights=w)
    return {"empty": False,
            "full_centres": edges_full[:-1] + bin_cents / 200, "full": h_full,
            "pc_centres": edges_pc[:-1] + bin_cents / 2, "pc": h_pc}


def segment_notes(midi: np.ndarray, times: np.ndarray, tol: float = 0.5, min_dur: float = 0.08) -> pd.DataFrame:
    notes, buf, start = [], [], None

    def flush(end):
        if buf and (end - start) >= min_dur:
            notes.append((start, end, float(np.median(buf))))

    for t, m in zip(times, midi):
        if np.isnan(m):
            flush(t); buf, start = [], None
        elif buf and abs(m - np.median(buf)) > tol:
            flush(t); buf, start = [m], t
        else:
            if not buf:
                start = t
            buf.append(m)
    flush(times[-1])
    return pd.DataFrame(notes, columns=["start", "end", "midi"])


# --------------------------------------------------------------------------- #
# Chroma
# --------------------------------------------------------------------------- #
def clean_chroma(y: np.ndarray, sr: int = SR) -> dict:
    """Energy-weighted chroma of the harmonic layer with each frame's background removed."""
    y_h = librosa.effects.harmonic(y)
    chroma = librosa.feature.chroma_cqt(y=y_h, sr=sr, hop_length=HOP, bins_per_octave=36, norm=None)
    chroma = np.clip(chroma - np.median(chroma, axis=0, keepdims=True), 0, None)
    p = chroma.mean(axis=1)
    p = p / p.sum() if p.sum() > 0 else np.full(12, 1 / 12)
    entropy = float(-(p * np.log2(p + 1e-12)).sum())
    shown = chroma / (chroma.max(axis=0, keepdims=True) + 1e-9)
    return {"chroma": shown, "profile": p, "entropy": entropy, "times": frame_times(chroma.shape[1], sr)}


# --------------------------------------------------------------------------- #
# Rhythm
# --------------------------------------------------------------------------- #
def rhythm(y: np.ndarray, sr: int = SR, tempo_min: float = 40, tempo_max: float = 300) -> dict:
    oenv = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP, aggregate=np.median)
    times = frame_times(len(oenv), sr)
    onsets = librosa.onset.onset_detect(onset_envelope=oenv, sr=sr, hop_length=HOP, units="time")

    tg = librosa.feature.tempogram(onset_envelope=oenv, sr=sr, hop_length=HOP)
    bpm_axis = librosa.tempo_frequencies(tg.shape[0], sr=sr, hop_length=HOP)
    curve = tg.mean(axis=1)
    band = (bpm_axis >= tempo_min) & (bpm_axis <= tempo_max)
    tempo = float(bpm_axis[band][np.argmax(curve[band])]) if band.any() else 120.0

    _, beat_frames = librosa.beat.beat_track(onset_envelope=oenv, sr=sr, hop_length=HOP, bpm=tempo)
    beats = librosa.frames_to_time(beat_frames, sr=sr, hop_length=HOP)

    # Fold the onset envelope onto the beat grid: one row per beat, columns are beat phase.
    n_sub = 24
    rows = []
    for b0, b1 in zip(beats[:-1], beats[1:]):
        phase = (times - b0) / (b1 - b0)
        m = (phase >= 0) & (phase < 1)
        row, cnt = np.zeros(n_sub), np.zeros(n_sub)
        idx = (phase[m] * n_sub).astype(int)
        np.add.at(row, idx, oenv[m]); np.add.at(cnt, idx, 1)
        rows.append(row / np.maximum(cnt, 1))
    fold = np.array(rows) if rows else np.zeros((1, n_sub))

    return {"oenv": oenv, "times": times, "onsets": onsets, "beats": beats, "tempo": tempo,
            "bpm_axis": bpm_axis, "curve": curve, "band": band, "fold": fold,
            "ioi_ms": np.diff(onsets) * 1000 if len(onsets) > 1 else np.array([])}


def click_mix(y: np.ndarray, beats: np.ndarray, sr: int = SR, gain: float = 0.6) -> np.ndarray:
    clicks = librosa.clicks(times=beats, sr=sr, length=len(y), click_freq=1500)
    return y + gain * clicks * (np.max(np.abs(y)) or 1.0)


def tempogram(y: np.ndarray, sr: int = SR, win_length: int = 384, kind: str = "autocorrelation",
              bpm_min: float = 30, bpm_max: float = 400) -> dict:
    """Tempogram (periodicity of the onset envelope at every tempo, over time).

    'autocorrelation' compares the onset envelope with delayed copies of itself inside a
    sliding window; 'fourier' takes a short-time Fourier transform of the envelope. Both
    return rows = tempo (BPM), columns = time, restricted to [bpm_min, bpm_max].
    """
    oenv = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP, aggregate=np.median)
    times = frame_times(len(oenv), sr)
    if kind == "fourier":
        tg = np.abs(librosa.feature.fourier_tempogram(onset_envelope=oenv, sr=sr, hop_length=HOP, win_length=win_length))
        bpm = librosa.fourier_tempo_frequencies(sr=sr, hop_length=HOP, win_length=win_length)
    else:
        tg = librosa.feature.tempogram(onset_envelope=oenv, sr=sr, hop_length=HOP, win_length=win_length)
        bpm = librosa.tempo_frequencies(tg.shape[0], sr=sr, hop_length=HOP)
    tg = tg[:, :len(times)]                      # the Fourier variant can return one extra frame
    keep = np.isfinite(bpm) & (bpm >= bpm_min) & (bpm <= bpm_max)
    tg, bpm = tg[keep], bpm[keep]
    order = np.argsort(bpm)                      # ascending BPM for plotting
    tg, bpm = tg[order], bpm[order]
    curve = tg.mean(axis=1)
    return {"tg": tg, "bpm": bpm, "times": times, "curve": curve, "tempo": float(bpm[np.argmax(curve)]), "oenv": oenv}


def self_similarity(y: np.ndarray, sr: int = SR, feature: str = "chroma", n_steps: int = 8,
                    agg: int = 4, width: int = 4, k: int | None = None) -> dict:
    """Recurrence (self-similarity) matrix of a recording.

    Frames are described by chroma (pitch content), MFCC (timbre) or both, pooled `agg`
    frames at a time, then `n_steps` consecutive descriptors are stacked so that short
    motifs rather than single frames are compared. Cosine affinity, symmetric, with a
    band of `width` cells around the diagonal excluded. Also returns the time-lag form.
    """
    feats = []
    if feature in ("chroma", "chroma+mfcc"):
        chroma = librosa.feature.chroma_cqt(y=librosa.effects.harmonic(y), sr=sr, hop_length=HOP)
        feats.append(librosa.util.normalize(chroma, axis=0))
    if feature in ("mfcc", "chroma+mfcc"):
        mfcc = librosa.feature.mfcc(y=y, sr=sr, hop_length=HOP, n_mfcc=20)[1:]     # drop the loudness coefficient
        feats.append((mfcc - mfcc.mean(axis=1, keepdims=True)) / (mfcc.std(axis=1, keepdims=True) + 1e-9))
    F = np.vstack(feats)
    n_frames = F.shape[1]
    F = librosa.util.sync(F, np.arange(0, n_frames, agg))
    F = librosa.feature.stack_memory(F, n_steps=n_steps, delay=1)
    R = librosa.segment.recurrence_matrix(F, width=width, mode="affinity", sym=True, metric="cosine", k=k)
    n = R.shape[0]
    L = librosa.segment.recurrence_to_lag(R, pad=False)
    L = np.roll(L, n // 2, axis=0)                # lags run from -T/2 to +T/2
    cell = HOP * agg / sr
    times = np.arange(n) * cell
    lags = (np.arange(n) - n // 2) * cell
    return {"R": R, "L": L, "times": times, "lags": lags, "cell": cell}


# --------------------------------------------------------------------------- #
# Layers
# --------------------------------------------------------------------------- #
def separate(y: np.ndarray, margin: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    return librosa.effects.hpss(y, margin=(1.0, margin))


# --------------------------------------------------------------------------- #
# Collection features
# --------------------------------------------------------------------------- #
def load_features() -> pd.DataFrame | None:
    if FEATURE_CACHE.exists():
        return pd.read_csv(FEATURE_CACHE, index_col="item")
    return None


def clip_features(y: np.ndarray, sr: int = SR, seconds: float = 20.0) -> dict:
    """The collection-wide summary features, as computed by the notebook, on the first `seconds`.

    Used for baked-in examples that are not in features/clip_features.csv.
    """
    y = y[: int(seconds * sr)]
    tg = tempogram(y, sr, bpm_min=40, bpm_max=300)
    _, tonal_entropy = _profile_entropy(clean_chroma(y, sr)["profile"])
    y_h, _ = librosa.effects.hpss(y)
    rms = librosa.feature.rms(y=y)[0]
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13).mean(axis=1)
    out = {
        "pulse_strength": float(tg["curve"].max()), "tempo": tg["tempo"], "tonal_entropy": tonal_entropy,
        "harmonic_share": float((y_h ** 2).sum() / ((y ** 2).sum() + 1e-9)),
        "centroid": float(librosa.feature.spectral_centroid(y=y, sr=sr).mean()),
        "flatness": float(librosa.feature.spectral_flatness(y=y).mean()),
        "rms_cv": float(rms.std() / (rms.mean() + 1e-9)),
    }
    out.update({f"mfcc{k}": float(v) for k, v in enumerate(mfcc)})
    return out


def _profile_entropy(p: np.ndarray) -> tuple[np.ndarray, float]:
    p = p / p.sum() if p.sum() > 0 else np.full(12, 1 / 12)
    return p, float(-(p * np.log2(p + 1e-12)).sum())
