"""Generate 7 self-contained 1600x900 HTML slide tiles summarising the
audio-analysis functions in streamlit_app.py, with hand-built SVG diagrams
(no external chart libs, so headless-Chrome screenshots render deterministically).
"""
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "tiles"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- palette ---
CREAM = "#faf6ef"
SURFACE = "#fffdf9"
INK = "#18140f"
INK_DIM = "#5b564c"
MUTED = "#948d7e"
BORDER = "rgba(24,20,15,0.13)"
GRIDLN = "rgba(24,20,15,0.07)"

ACCENTS = {
    "wave": "#2a78d6",
    "spec": "#c1531f",
    "pitch": "#1a9a6c",
    "rhythm": "#c78312",
    "tempo": "#0f7a72",
    "struct": "#a63752",
    "layers": "#6b7b3f",
}

MAGMA = ["#000004", "#3b0f70", "#8c2981", "#de4968", "#fe9f6d", "#fcfdbf"]
BLUES = ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]


def lerp(c1, c2, t):
    c1 = c1.lstrip("#"); c2 = c2.lstrip("#")
    r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
    r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
    r = round(r1 + (r2 - r1) * t); g = round(g1 + (g2 - g1) * t); b = round(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def ramp(stops, t):
    t = max(0.0, min(1.0, t))
    n = len(stops) - 1
    seg = min(int(t * n), n - 1)
    local = t * n - seg
    return lerp(stops[seg], stops[seg + 1], local)


def smooth(x, win):
    k = np.ones(win) / win
    return np.convolve(x, k, mode="same")


# =============================================================== WAVEFORM ===
def svg_waveform():
    rng = np.random.default_rng(7)
    n = 240
    x = np.linspace(0, 900, n)
    env = (0.32 + 0.22 * np.sin(x / 130) ** 2 + 0.14 * np.sin(x / 41 + 1.3) ** 2)
    env *= (0.35 + 0.65 * (0.5 + 0.5 * np.sin(x / 480 - 0.6)))
    noise = smooth(rng.normal(0, 1, n), 5)
    env = np.clip(env + 0.06 * noise, 0.03, 1.0)
    top = 470 - env * 330
    bot = 470 + env * 330
    pts_top = " ".join(f"{px:.1f},{py:.1f}" for px, py in zip(x, top))
    pts_bot = " ".join(f"{px:.1f},{py:.1f}" for px, py in zip(x[::-1], bot[::-1]))
    rms = smooth(env, 21)
    rms_y = 150 - rms * 110
    rms_path = "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in zip(x, rms_y))
    ticks = "".join(
        f'<line x1="{gx}" y1="470" x2="{gx}" y2="478" stroke="{MUTED}" stroke-width="2"/>'
        for gx in np.linspace(0, 900, 10)
    )
    li = 130
    return f"""
<svg viewBox="0 0 900 540" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
  {"".join(f'<line x1="0" y1="{gy}" x2="900" y2="{gy}" stroke="{GRIDLN}" stroke-width="1"/>' for gy in np.linspace(60, 470, 6))}
  <polygon points="{pts_top} {pts_bot}" fill="{ACCENTS['wave']}" fill-opacity="0.85"/>
  <path d="{rms_path}" fill="none" stroke="{ACCENTS['spec']}" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>
  <line x1="600" y1="76" x2="630" y2="76" stroke="{ACCENTS['spec']}" stroke-width="4.5"/>
  <text x="638" y="82" font-family="'JetBrains Mono',monospace" font-size="17" fill="{ACCENTS['spec']}" font-weight="600">loudness (RMS)</text>
  <text x="16" y="40" font-family="'JetBrains Mono',monospace" font-size="17" fill="{INK_DIM}" font-weight="600">amplitude</text>
  {ticks}
  <text x="450" y="512" text-anchor="middle" font-family="'JetBrains Mono',monospace" font-size="17" fill="{MUTED}">time &#8594;</text>
</svg>"""


# ============================================================ SPECTROGRAM ===
def spectrogram_grid(rng_seed=3, cols=64, rows=34, extra_attacks=None):
    rng = np.random.default_rng(rng_seed)
    t = np.linspace(0, 1, cols)
    grid = np.zeros((rows, cols))
    bands = [(0.72, 0.9, 1.0), (0.55, 0.6, 0.55), (0.40, 0.35, 0.38), (0.27, 0.2, 0.24)]
    for center, wobble, strength in bands:
        for j in range(cols):
            r = center + wobble * 0.05 * np.sin(t[j] * 7 + center * 9)
            row = r * rows
            for i in range(rows):
                grid[i, j] += strength * np.exp(-((i - row) ** 2) / (2 * 1.3 ** 2))
    attacks = extra_attacks if extra_attacks is not None else sorted(rng.choice(cols, size=6, replace=False))
    for j in attacks:
        width = 1
        for dj in range(-width, width + 1):
            jj = j + dj
            if 0 <= jj < cols:
                grid[:, jj] += 0.5 * np.exp(-abs(dj)) * np.linspace(0.4, 1.0, rows)
    grid += rng.normal(0, 0.03, grid.shape)
    grid = np.clip(grid, 0, None)
    grid = grid / grid.max()
    return grid, attacks


def svg_spectrogram():
    grid, _ = spectrogram_grid()
    rows, cols = grid.shape
    cw, ch = 900 / cols, 460 / rows
    cells = []
    for i in range(rows):
        for j in range(cols):
            color = ramp(MAGMA, grid[i, j] ** 0.7)
            cells.append(f'<rect x="{j*cw:.2f}" y="{(rows-1-i)*ch+40:.2f}" width="{cw+0.6:.2f}" height="{ch+0.6:.2f}" fill="{color}"/>')
    notes = ["C3", "G3", "C4", "G4", "C5"]
    yticks = "".join(
        f'<text x="908" y="{40+ch*rows*(1-p):.1f}" font-family="\'JetBrains Mono\',monospace" font-size="15" fill="{MUTED}">{lab}</text>'
        for p, lab in zip(np.linspace(0.08, 0.92, len(notes)), notes)
    )
    return f"""
<svg viewBox="0 0 960 540" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
  {''.join(cells)}
  <rect x="0" y="40" width="900" height="460" fill="none" stroke="{BORDER}" stroke-width="1.5"/>
  {yticks}
  <text x="450" y="518" text-anchor="middle" font-family="'JetBrains Mono',monospace" font-size="17" fill="{MUTED}">time &#8594;</text>
  <text x="16" y="24" font-family="'JetBrains Mono',monospace" font-size="15" fill="{INK_DIM}" font-weight="600">bright = more energy &#8226; horizontal bands = harmonics &#8226; vertical lines = attacks</text>
</svg>"""


# ==================================================================== PITCH ===
def svg_pitch():
    grid, _ = spectrogram_grid(rng_seed=11)
    rows, cols = grid.shape
    cw, ch = 900 / cols, 460 / rows
    cells = []
    for i in range(rows):
        for j in range(cols):
            color = ramp(MAGMA, (grid[i, j] ** 0.7) * 0.55)
            cells.append(f'<rect x="{j*cw:.2f}" y="{(rows-1-i)*ch+40:.2f}" width="{cw+0.6:.2f}" height="{ch+0.6:.2f}" fill="{color}" fill-opacity="0.6"/>')

    n = 160
    x = np.linspace(6, 894, n)
    melody = 0.55 + 0.18 * np.sin(x / 140) + 0.09 * np.sin(x / 55 + 0.7)
    melody[70:76] -= 0.28   # octave jump down
    melody[71:] += 0.0
    melody[120:126] += 0.22  # octave jump up
    y = 40 + 460 * (1 - np.clip(melody, 0.05, 0.95))
    segs = []
    seg_x, seg_y = [x[0]], [y[0]]
    for i in range(1, n):
        if abs(y[i] - y[i - 1]) > 60:
            segs.append((seg_x, seg_y)); seg_x, seg_y = [], []
        seg_x.append(x[i]); seg_y.append(y[i])
    segs.append((seg_x, seg_y))
    paths = "".join(
        f'<path d="M {" L ".join(f"{a:.1f},{b:.1f}" for a,b in zip(sx, sy))}" fill="none" stroke="{ACCENTS["pitch"]}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
        for sx, sy in segs if len(sx) > 1
    )
    notes = ["C3", "G3", "C4", "G4", "C5"]
    yticks = "".join(
        f'<text x="908" y="{40+460*(1-p):.1f}" font-family="\'JetBrains Mono\',monospace" font-size="15" fill="{MUTED}">{lab}</text>'
        for p, lab in zip(np.linspace(0.08, 0.92, len(notes)), notes)
    )
    return f"""
<svg viewBox="0 0 960 540" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
  {''.join(cells)}
  <rect x="0" y="40" width="900" height="460" fill="none" stroke="{BORDER}" stroke-width="1.5"/>
  {paths}
  {yticks}
  <text x="450" y="518" text-anchor="middle" font-family="'JetBrains Mono',monospace" font-size="17" fill="{MUTED}">time &#8594;</text>
  <text x="16" y="24" font-family="'JetBrains Mono',monospace" font-size="15" fill="{INK_DIM}" font-weight="600">green = estimated pitch &#8226; jumps often mean the tracker lost the line, not the singer</text>
</svg>"""


# ================================================================== RHYTHM ===
def svg_rhythm():
    rng = np.random.default_rng(21)
    n = 260
    x = np.linspace(10, 890, n)
    base = np.abs(np.sin(x / 33)) * 0.5 + np.abs(np.sin(x / 71 + 0.4)) * 0.3
    base += rng.normal(0, 0.05, n)
    base = smooth(np.clip(base, 0, None), 3)
    base = base / base.max()
    peaks = []
    for i in range(2, n - 2):
        if base[i] > 0.32 and base[i] >= base[i - 1] and base[i] >= base[i + 1]:
            peaks.append(i)
    onsets = [x[i] for i in peaks]
    beats = onsets[::3]
    y0 = 470
    curve_y = y0 - base * 300
    curve_path = "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in zip(x, curve_y))
    onset_ticks = "".join(
        f'<line x1="{ox:.1f}" y1="{y0}" x2="{ox:.1f}" y2="{y0-270}" stroke="{ACCENTS["spec"]}" stroke-width="2.4" stroke-opacity="0.85"/>'
        for ox in onsets
    )
    beat_ticks = "".join(
        f'<line x1="{bx:.1f}" y1="{y0-270}" x2="{bx:.1f}" y2="{y0-330}" stroke="{ACCENTS["tempo"]}" stroke-width="5" stroke-linecap="round"/>'
        for bx in beats
    )
    return f"""
<svg viewBox="0 0 900 540" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
  {"".join(f'<line x1="0" y1="{gy}" x2="900" y2="{gy}" stroke="{GRIDLN}" stroke-width="1"/>' for gy in np.linspace(80, 470, 5))}
  <path d="{curve_path}" fill="none" stroke="{INK_DIM}" stroke-width="2.6"/>
  {onset_ticks}
  {beat_ticks}
  <text x="16" y="38" font-family="'JetBrains Mono',monospace" font-size="16" fill="{INK_DIM}" font-weight="600">onset strength</text>
  <g>
    <line x1="620" y1="70" x2="650" y2="70" stroke="{ACCENTS['spec']}" stroke-width="4"/>
    <text x="658" y="75" font-family="'JetBrains Mono',monospace" font-size="16" fill="{ACCENTS['spec']}" font-weight="600">onsets</text>
    <line x1="620" y1="98" x2="650" y2="98" stroke="{ACCENTS['tempo']}" stroke-width="5"/>
    <text x="658" y="103" font-family="'JetBrains Mono',monospace" font-size="16" fill="{ACCENTS['tempo']}" font-weight="600">beats</text>
  </g>
  <text x="450" y="512" text-anchor="middle" font-family="'JetBrains Mono',monospace" font-size="17" fill="{MUTED}">time &#8594;</text>
</svg>"""


# ================================================================ TEMPOGRAM ===
def svg_tempogram():
    rng = np.random.default_rng(5)
    cols, rows = 64, 34
    t = np.linspace(0, 1, cols)
    grid = rng.normal(0, 0.05, (rows, cols))
    main_row = 12 + 1.2 * np.sin(t * 5)
    half_row = main_row * 2
    for j in range(cols):
        for i in range(rows):
            grid[i, j] += 1.0 * np.exp(-((i - main_row[j]) ** 2) / (2 * 1.0 ** 2))
            if half_row[j] < rows:
                grid[i, j] += 0.35 * np.exp(-((i - half_row[j]) ** 2) / (2 * 1.0 ** 2))
    grid = np.clip(grid, 0, None); grid /= grid.max()
    cw, ch = 900 / cols, 460 / rows
    cells = []
    for i in range(rows):
        for j in range(cols):
            color = ramp(BLUES, grid[i, j] ** 0.8)
            cells.append(f'<rect x="{j*cw:.2f}" y="{(rows-1-i)*ch+40:.2f}" width="{cw+0.6:.2f}" height="{ch+0.6:.2f}" fill="{color}"/>')
    main_line_y = [40 + (rows - 1 - main_row[j]) * ch + ch / 2 for j in range(cols)]
    xs = [j * cw + cw / 2 for j in range(cols)]
    dot_path = "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in zip(xs, main_line_y))
    labels = ["40", "60", "90", "180", "360"]
    yticks = "".join(
        f'<text x="908" y="{40+460*(1-p):.1f}" font-family="\'JetBrains Mono\',monospace" font-size="15" fill="{MUTED}">{lab}</text>'
        for p, lab in zip(np.linspace(0.1, 0.9, len(labels)), labels)
    )
    return f"""
<svg viewBox="0 0 960 540" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
  {''.join(cells)}
  <rect x="0" y="40" width="900" height="460" fill="none" stroke="{BORDER}" stroke-width="1.5"/>
  <path d="{dot_path}" fill="none" stroke="{ACCENTS['spec']}" stroke-width="2" stroke-dasharray="2 5" opacity="0.9"/>
  {yticks}
  <text x="932" y="26" font-family="'JetBrains Mono',monospace" font-size="14" fill="{MUTED}">BPM</text>
  <text x="450" y="518" text-anchor="middle" font-family="'JetBrains Mono',monospace" font-size="17" fill="{MUTED}">time &#8594;</text>
  <text x="16" y="24" font-family="'JetBrains Mono',monospace" font-size="15" fill="{INK_DIM}" font-weight="600">bright band = the pulse &#8226; faint band above it = the same pulse, doubled</text>
</svg>"""


# ================================================================ STRUCTURE ===
def svg_structure():
    # Matches the app's own axes: x and y are both time, origin (0 s) at the
    # LOWER-LEFT, increasing right and UP -- so the main diagonal runs from
    # bottom-left to top-right, and a repeat above the diagonal mirrors one
    # below it.
    n = 42
    rng = np.random.default_rng(9)
    R = rng.uniform(0, 0.12, (n, n))
    blocks = [(0, 12), (12, 22), (22, 30), (30, 42)]
    for a, b in blocks:
        R[a:b, a:b] += rng.uniform(0.35, 0.55, (b - a, b - a))
    # a repeat: section 1 (0-12) resembles section 3 (22-30)
    for i in range(0, 8):
        for j in range(22, 30):
            v = 0.55 + rng.uniform(-0.05, 0.05)
            R[i, j] = v; R[j, i] = v
    R = (R + R.T) / 2
    np.fill_diagonal(R, 0)
    R = np.clip(R, 0, 1)

    x0, y0, size = 40, 40, 460
    cw = ch = size / n

    def cell_xy(row, col):
        """Pixel top-left for data cell (row, col); row 0 is the OLDEST time
        and sits at the bottom, so increasing row moves the cell upward."""
        return x0 + col * cw, y0 + (n - 1 - row) * ch

    def centre(row_lo, row_hi, col_lo, col_hi):
        cx, _ = cell_xy(0, (col_lo + col_hi - 1) / 2)
        _, cy = cell_xy((row_lo + row_hi - 1) / 2, 0)
        return cx + cw / 2, cy + ch / 2

    cells = []
    for i in range(n):
        for j in range(n):
            v = 0 if i == j else R[i, j]
            color = ramp(BLUES, v)
            px, py = cell_xy(i, j)
            cells.append(f'<rect x="{px:.2f}" y="{py:.2f}" width="{cw+0.5:.2f}" height="{ch+0.5:.2f}" fill="{color}"/>')

    b1x, b1y = centre(*blocks[0], *blocks[0])
    b3x, b3y = centre(*blocks[2], *blocks[2])
    rx, ry = centre(0, 8, 22, 30)           # the off-diagonal repeat patch

    return f"""
<svg viewBox="0 0 560 540" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
  {''.join(cells)}
  <rect x="{x0}" y="{y0}" width="{size}" height="{size}" fill="none" stroke="{BORDER}" stroke-width="1.5"/>
  <line x1="{x0}" y1="{y0+size}" x2="{x0+size}" y2="{y0}" stroke="{ACCENTS['struct']}" stroke-width="1.5" stroke-dasharray="3 4" opacity="0.55"/>
  <text x="{x0}" y="522" font-family="'JetBrains Mono',monospace" font-size="16" fill="{MUTED}">0 s &#8594; time</text>
  <text x="26" y="{y0+size-8:.1f}" font-family="'JetBrains Mono',monospace" font-size="16" fill="{MUTED}" transform="rotate(-90 26 {y0+size-8:.1f})">0 s &#8594; time</text>
  <text x="{b1x:.1f}" y="{b1y+5:.1f}" text-anchor="middle" font-family="'JetBrains Mono',monospace" font-size="14" fill="{SURFACE}" font-weight="700">block</text>
  <text x="{b3x:.1f}" y="{b3y+5:.1f}" text-anchor="middle" font-family="'JetBrains Mono',monospace" font-size="14" fill="{SURFACE}" font-weight="700">block</text>
  <text x="{rx+cw*4+12:.1f}" y="{ry+4:.1f}" font-family="'JetBrains Mono',monospace" font-size="14" fill="{ACCENTS['struct']}" font-weight="700">&#8592; repeat</text>
</svg>"""


# =================================================================== LAYERS ===
def svg_layers():
    rng = np.random.default_rng(13)
    n = 220
    x = np.linspace(20, 880, n)
    lines = []
    for k, (freq, amp, dy) in enumerate([(70, 26, 0), (46, 18, -34), (95, 14, 30)]):
        y = 130 + dy + amp * np.sin((x - 20) / freq + k)
        path = "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in zip(x, y))
        op = 1.0 if k == 0 else 0.55
        w = 5 if k == 0 else 3
        lines.append(f'<path d="{path}" fill="none" stroke="{ACCENTS["layers"]}" stroke-width="{w}" stroke-opacity="{op}" stroke-linecap="round"/>')

    spikes = sorted(rng.choice(range(20, n - 20), size=26, replace=False))
    spike_lines = []
    for i in spikes:
        h = rng.uniform(50, 180)
        spike_lines.append(f'<line x1="{x[i]:.1f}" y1="{430}" x2="{x[i]:.1f}" y2="{430-h:.1f}" stroke="{ACCENTS["spec"]}" stroke-width="3.4" stroke-linecap="round" stroke-opacity="0.9"/>')

    share = 0.63
    bar_w = 860
    return f"""
<svg viewBox="0 0 900 540" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
  <rect x="20" y="20" width="860" height="200" rx="10" fill="{ACCENTS['layers']}" fill-opacity="0.08"/>
  {''.join(lines)}
  <text x="36" y="46" font-family="'JetBrains Mono',monospace" font-size="16" fill="{ACCENTS['layers']}" font-weight="700">harmonic &#8226; sustained tones</text>

  <rect x="20" y="250" width="860" height="200" rx="10" fill="{ACCENTS['spec']}" fill-opacity="0.08"/>
  <line x1="20" y1="430" x2="880" y2="430" stroke="{GRIDLN}" stroke-width="1"/>
  {''.join(spike_lines)}
  <text x="36" y="276" font-family="'JetBrains Mono',monospace" font-size="16" fill="{ACCENTS['spec']}" font-weight="700">percussive &#8226; attacks &amp; noise</text>

  <rect x="20" y="486" width="{bar_w}" height="26" rx="6" fill="{GRIDLN}"/>
  <rect x="20" y="486" width="{bar_w*share:.1f}" height="26" rx="6" fill="{ACCENTS['layers']}"/>
  <rect x="{20+bar_w*share:.1f}" y="486" width="{bar_w*(1-share):.1f}" height="26" rx="6" fill="{ACCENTS['spec']}" fill-opacity="0.75"/>
  <text x="30" y="504" font-family="'JetBrains Mono',monospace" font-size="14" fill="{SURFACE}" font-weight="700">63% harmonic</text>
  <text x="{20+bar_w-10:.1f}" y="504" text-anchor="end" font-family="'JetBrains Mono',monospace" font-size="14" fill="{SURFACE}" font-weight="700">37% percussive</text>
</svg>"""


SVG_BUILDERS = {
    "wave": svg_waveform,
    "spec": svg_spectrogram,
    "pitch": svg_pitch,
    "rhythm": svg_rhythm,
    "tempo": svg_tempogram,
    "struct": svg_structure,
    "layers": svg_layers,
}

# ---------------------------------------------------------------- content ---
TILES = [
    dict(key="wave", num="01", tab="Waveform",
         title="Waveform", tagline="Loudness and phrasing, moment by moment.",
         what="Air pressure over time. At this zoom it shows loudness and phrasing &#8212; not pitch.",
         how="The filled shape is the amplitude envelope; the orange line is smoothed loudness (RMS) in decibels below the loudest moment.",
         listen="Phrase boundaries, dynamic swells, breaths and silences."),
    dict(key="spec", num="02", tab="Spectrogram",
         title="Spectrogram", tagline="Every frequency, frame by frame.",
         what="Cuts the sound into short frames and shows how much energy sits at each frequency in each one.",
         how="Bright horizontal bands are sustained tones and their harmonics; bright vertical lines are attacks.",
         listen="Timbral brightness, harmonic stacking, tonal vs. noisy texture."),
    dict(key="pitch", num="03", tab="Pitch",
         title="Pitch", tagline="The melody, tracked frame by frame.",
         what="pYIN estimates the fundamental frequency in every frame, plus a confidence that a pitched sound is present.",
         how="The line traces estimated pitch in notes and cents over a note-labelled spectrogram; histograms show the pitch set used.",
         listen="Melodic contour and intonation &#8212; octave jumps usually mean the tracker slipped, not the performer."),
    dict(key="rhythm", num="04", tab="Rhythm",
         title="Rhythm", tagline="Where the pulse begins, and where it lands.",
         what="Onsets mark moments where something new begins; beats are the pulse tracked from them.",
         how="Grey curve is onset strength; orange ticks are onsets; green ticks are the tracked beats.",
         listen="Whether a click track on the beats matches the pulse you feel &#8212; steady meter vs. free rhythm."),
    dict(key="tempo", num="05", tab="Tempogram",
         title="Tempogram", tagline="A spectrogram, but for rhythm.",
         what="At every moment, shows how strongly the onsets repeat at every possible tempo.",
         how="Bright horizontal bands are steady pulses; a fainter band at double or half tempo is the same pulse, counted differently.",
         listen="Whether the pulse holds steady through the excerpt, speeds up, or drifts."),
    dict(key="struct", num="06", tab="Structure",
         title="Structure", tagline="Every moment, compared to every other.",
         what="A self-similarity matrix compares each moment of the recording with every other moment.",
         how="Stripes parallel to the diagonal are passages that return later at the same speed; blocks are internally homogeneous sections.",
         listen="Repetition and form &#8212; verses, refrains, or a phrase that comes back minutes later."),
    dict(key="layers", num="07", tab="Layers",
         title="Layers", tagline="Sustained tone, separated from attack.",
         what="Harmonic/percussive separation (HPSS) splits the spectrogram into held tones and transient attacks.",
         how="The harmonic layer is smooth along time; the percussive layer is smooth along frequency. A share reports the split.",
         listen="Melody apart from accompaniment, or a voice apart from drums &#8212; play each layer on its own."),
]

CSS = f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 1600px; height: 900px; overflow: hidden; background: {CREAM}; }}
body {{
  font-family: 'DM Sans', 'Segoe UI', sans-serif;
  color: {INK};
  background-image:
    radial-gradient(circle at 4% 8%, rgba(24,20,15,0.045), transparent 40%),
    radial-gradient(circle at 96% 92%, rgba(24,20,15,0.04), transparent 42%);
}}
.tile {{ width: 1600px; height: 900px; padding: 56px 64px 44px; display: flex; flex-direction: column; position: relative; }}
.rule {{ position:absolute; left:0; top:0; width:100%; height:10px; background: var(--accent); }}

.eyebrow {{ font-family:'JetBrains Mono', monospace; font-size:16px; letter-spacing:0.14em; text-transform:uppercase; color: var(--accent); font-weight:600; display:flex; align-items:center; gap:14px; }}
.eyebrow .num {{ font-size:16px; background: var(--accent); color:{SURFACE}; padding:3px 10px; border-radius:5px; }}
h1 {{ font-family:'Bricolage Grotesque', 'DM Sans', sans-serif; font-weight:700; font-size:64px; letter-spacing:-0.01em; margin-top:10px; color:{INK}; }}
.tagline {{ font-size:23px; color:{INK_DIM}; margin-top:6px; font-weight:500; max-width:1100px; }}

.body {{ flex:1; display:flex; gap:44px; margin-top:30px; min-height:0; }}
.visual {{ flex: 1.42; background:{SURFACE}; border:1.5px solid {BORDER}; border-radius:18px; padding:26px 30px 18px; display:flex; align-items:center; justify-content:center; box-shadow: 0 1px 0 rgba(24,20,15,0.03); min-width:0; overflow:hidden; }}
.visual svg {{ width:100%; height:100%; }}

.textcol {{ flex:1; display:flex; flex-direction:column; gap:22px; min-width:0; }}
.block {{ display:flex; gap:16px; }}
.dot {{ flex:0 0 14px; width:14px; height:14px; border-radius:50%; background: var(--accent); margin-top:7px; }}
.block h3 {{ font-family:'JetBrains Mono', monospace; font-size:15px; letter-spacing:0.09em; text-transform:uppercase; color: var(--accent); font-weight:700; margin-bottom:6px; }}
.block p {{ font-size:20px; line-height:1.42; color:{INK}; font-weight:400; }}

.placeholder {{ margin-top:26px; border:2px dashed {BORDER}; border-radius:14px; padding:16px 22px; display:flex; align-items:center; gap:14px; background: rgba(24,20,15,0.025); }}
.placeholder .icon {{ flex:0 0 auto; width:34px; height:34px; border-radius:8px; border:2px dashed var(--accent); display:flex; align-items:center; justify-content:center; color:var(--accent); font-family:'JetBrains Mono',monospace; font-size:18px; font-weight:700; }}
.placeholder .txt {{ font-family:'JetBrains Mono', monospace; font-size:15px; color:{MUTED}; }}
.placeholder .txt b {{ color:{INK_DIM}; }}

.footer {{ margin-top:26px; display:flex; justify-content:space-between; align-items:center; font-family:'JetBrains Mono', monospace; font-size:14px; color:{MUTED}; letter-spacing:0.04em; }}
.footer .brand {{ display:flex; align-items:center; gap:10px; }}
.footer .swatch {{ width:10px; height:10px; border-radius:50%; background: var(--accent); }}
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title} tile</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700;800&family=DM+Sans:wght@400;500;600&family=JetBrains+Mono:wght@500;600;700&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<div class="tile" style="--accent:{accent}">
  <div class="rule"></div>
  <div class="eyebrow"><span class="num">{num}</span> HEARING THE ARCHIVE &nbsp;&middot;&nbsp; SIGNAL ANALYSIS</div>
  <h1>{title}</h1>
  <div class="tagline">{tagline}</div>

  <div class="body">
    <div class="visual">{svg}</div>
    <div class="textcol">
      <div class="block"><div class="dot"></div><div><h3>What it shows</h3><p>{what}</p></div></div>
      <div class="block"><div class="dot"></div><div><h3>How to read it</h3><p>{how}</p></div></div>
      <div class="block"><div class="dot"></div><div><h3>Listen &amp; look for</h3><p>{listen}</p></div></div>
      <div class="placeholder">
        <div class="icon">+</div>
        <div class="txt">Add a PNG screenshot from the <b>{tab}</b> tab of the app here.</div>
      </div>
    </div>
  </div>

  <div class="footer">
    <div class="brand"><span class="swatch"></span> Hearing the archive &middot; PARADISEC excerpts &middot; librosa</div>
    <div>{num} / 07</div>
  </div>
</div>
</body>
</html>"""

for t in TILES:
    svg = SVG_BUILDERS[t["key"]]()
    html = TEMPLATE.format(css=CSS, accent=ACCENTS[t["key"]], num=t["num"], title=t["title"],
                            tagline=t["tagline"], svg=svg, what=t["what"], how=t["how"],
                            listen=t["listen"], tab=t["tab"])
    path = OUT / f"{t['num']}_{t['key']}.html"
    path.write_text(html)
    print(path)
