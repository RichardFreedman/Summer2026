import os
import json
from collections import Counter

import streamlit as st
import streamlit.components.v1 as components
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import networkx as nx
import plotly.express as px
from pyvis.network import Network

from langchain_openai import ChatOpenAI
from recommender import (
    OPENAI_MODEL,
    load_dataframe,
    enrich_dataframe,
    score_all_genre_fits,
    build_playlist,
)
from supergenres import (
    SUPERGENRE_CACHE,
    SUPERGENRES,
    SELECTABLE_SUPERGENRES,
    song_supergenres,
    apply_supergenre_preference,
)

# GENRE_MODE (from .env / st.secrets, loaded by recommender.py):
#   "supergenre" (default) - pick super-genres from a dropdown; deterministic,
#                            no live LLM calls, fast enough for a workshop.
#   "llm"                  - free-text genres scored per song by OpenAI (cached).
GENRE_MODE = os.environ.get("GENRE_MODE", "supergenre").strip().lower()
if GENRE_MODE not in ("supergenre", "llm"):
    GENRE_MODE = "supergenre"

st.set_page_config(page_title="Melbourne Moods", page_icon="🎵", layout="wide")


# ---------------------------------------------------------------------------
# Cached startup — runs once per server session
# ---------------------------------------------------------------------------

class LazyLLM:
    """Builds the OpenAI client only when something actually calls it, so
    the default super-genre mode runs from the cache files with no key."""

    def __init__(self):
        self._llm = None

    def invoke(self, *args, **kwargs):
        if self._llm is None:
            if not os.environ.get("OPENAI_API_KEY"):
                raise RuntimeError(
                    "This request needs OpenAI (a tag or genre is not in the cache) "
                    "but OPENAI_API_KEY is not set."
                )
            self._llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0)
        return self._llm.invoke(*args, **kwargs)


@st.cache_resource(show_spinner=False)
def load_enriched_df():
    with st.spinner("Starting up — loading songs and enriching with tags (first run only)..."):
        llm = LazyLLM()
        df  = load_dataframe()
        df  = enrich_dataframe(df, llm)
    return df, llm


# ---------------------------------------------------------------------------
# Journey chart
# ---------------------------------------------------------------------------

MAX_TITLE_CHARS = 30


def plot_journey(playlist, current_valence, current_energy, desired_valence, desired_energy):
    fig, ax = plt.subplots(figsize=(8, 6))

    for x, y, label in [
        (0.25, 0.75, "Stressed / Anxious"),
        (0.75, 0.75, "Excited / Happy"),
        (0.25, 0.25, "Sad / Depressed"),
        (0.75, 0.25, "Calm / Relaxed"),
    ]:
        ax.text(x, y, label, ha="center", va="center",
                fontsize=9, color="gray", alpha=0.5)

    ax.plot(playlist["target_valence"], playlist["target_energy"],
            linestyle="--", color="lightblue", linewidth=1.5, label="Target path", zorder=2)

    for i in range(len(playlist) - 1):
        x0, y0 = playlist.iloc[i]["valence"],   playlist.iloc[i]["energy"]
        x1, y1 = playlist.iloc[i+1]["valence"], playlist.iloc[i+1]["energy"]
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color="royalblue", lw=1.2, alpha=0.5))

    ax.scatter(playlist["valence"], playlist["energy"],
               s=100, color="royalblue", zorder=5, label="Songs")
    for _, row in playlist.iterrows():
        title = row["title"]
        if len(title) > MAX_TITLE_CHARS:
            title = title[:MAX_TITLE_CHARS - 1].rstrip() + "…"
        # Point labels inward near the edges so they stay inside the axes.
        right_side = row["valence"] > 0.7
        top_side   = row["energy"]  > 0.9
        ax.annotate(f"{int(row['step'])}. {title}",
                    (row["valence"], row["energy"]),
                    textcoords="offset points",
                    xytext=(-6 if right_side else 6, -10 if top_side else 6),
                    ha="right" if right_side else "left",
                    va="top" if top_side else "bottom",
                    fontsize=8)

    ax.scatter([current_valence], [current_energy],
               s=200, color="red", marker="*", zorder=6, label="You are here")
    ax.scatter([desired_valence], [desired_energy],
               s=200, color="green", marker="*", zorder=6, label="Where you want to be")

    ax.axvline(0.5, linestyle=":", color="gray", alpha=0.4)
    ax.axhline(0.5, linestyle=":", color="gray", alpha=0.4)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Valence  (Unpleasant → Pleasant)")
    ax.set_ylabel("Energy  (Calm → Energized)")
    ax.set_title("Your Emotional Journey")
    ax.legend(loc="upper left", fontsize=8)
    plt.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Emotion scatter plot (library overview)
# ---------------------------------------------------------------------------

def plot_scatter(df):
    emotions  = sorted(df["dominant_emotion"].unique())
    cmap      = plt.colormaps["tab20"].resampled(max(len(emotions), 1))
    color_map = {emo: cmap(i) for i, emo in enumerate(emotions)}

    fig, ax = plt.subplots(figsize=(13, 8))
    for emo, grp in df.groupby("dominant_emotion"):
        ax.scatter(grp["valence"], grp["energy"],
                   s=60, color=color_map[emo], label=f"{emo} ({len(grp)})",
                   zorder=5, alpha=0.75, edgecolors="white", linewidths=0.4)

    for x, y, label in [
        (0.15, 0.88, "Stressed / Anxious"),
        (0.85, 0.88, "Excited / Happy"),
        (0.15, 0.12, "Sad / Depressed"),
        (0.85, 0.12, "Calm / Relaxed"),
    ]:
        ax.text(x, y, label, ha="center", va="center",
                fontsize=9, color="gray", alpha=0.55,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.5, ec="none"))

    ax.axvline(0.5, linestyle=":", color="gray", alpha=0.35)
    ax.axhline(0.5, linestyle=":", color="gray", alpha=0.35)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Valence  (Unpleasant → Pleasant)", fontsize=11)
    ax.set_ylabel("Energy  (Calm → Energized)", fontsize=11)
    ax.set_title(f"Song Library — {len(df)} songs coloured by dominant emotion", fontsize=13)
    ax.legend(title="Dominant emotion", loc="upper left", fontsize=8,
              bbox_to_anchor=(1.01, 1), borderaxespad=0, framealpha=0.9)
    plt.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Sidebar helpers
# ---------------------------------------------------------------------------

def quadrant_label(v, e):
    if v < 0.5 and e > 0.5:
        return "Stressed / Anxious"
    elif v >= 0.5 and e > 0.5:
        return "Excited / Happy"
    elif v < 0.5 and e <= 0.5:
        return "Sad / Depressed"
    else:
        return "Calm / Relaxed"


# ---------------------------------------------------------------------------
# Network / heatmap helpers (Part 1c port from recommender.ipynb)
#
# enrich_dataframe() (recommender.py) doesn't add `all_tags` / `supergenre` —
# those only exist in the notebook (cells 13 and 15). Reconstructed here from
# the same cache files the notebook uses, so no recommender.py changes and no
# live API calls in the common case (falls back to the same GPT mapping call
# as the notebook only for genuinely new, uncached tags).
# ---------------------------------------------------------------------------

QUADRANTS = ["Stressed / Anxious", "Excited / Happy", "Sad / Depressed", "Calm / Relaxed"]
MIN_TAG_FREQ = 4


def _csv_genres(row):
    val = row.get("genres", None)
    if not val or isinstance(val, float):
        return []
    return [g.strip().lower() for g in str(val).split(",") if g.strip()]


def split_genres(val):
    if not val or isinstance(val, float):
        return []
    return [g.strip() for g in str(val).split(",") if g.strip()]


@st.cache_data(show_spinner=False)
def add_supergenre_column(df, _llm):
    df = df.copy()
    song_tags_cache = {}
    if os.path.exists("song_tags_cache.json"):
        with open("song_tags_cache.json") as f:
            song_tags_cache = json.load(f)

    def merged_tags(row):
        csv_tags    = _csv_genres(row)
        lastfm_tags = song_tags_cache.get(f"{row['title']}|||{row['artist']}", [])
        return list(dict.fromkeys(csv_tags + lastfm_tags))

    df["all_tags"] = df.apply(lambda r: ",".join(merged_tags(r)), axis=1)

    supergenre_map = {}
    if os.path.exists(SUPERGENRE_CACHE):
        with open(SUPERGENRE_CACHE) as f:
            supergenre_map = json.load(f)

    unique_tags = sorted({t for tags in df["all_tags"].str.split(",") for t in tags if t})
    missing = [t for t in unique_tags if t not in supergenre_map]
    if missing:
        prompt = (
            "Map each of the following music genre/mood tags to exactly one of these "
            "super-genre categories: " + ", ".join(SUPERGENRES) + ".\n"
            "Return ONLY a valid JSON object mapping each tag string to one category "
            "string (no extra text).\n"
            "Tags: " + json.dumps(missing)
        )
        text = _llm.invoke(prompt).content
        if "```" in text:
            parts = text.split("```")
            text = parts[1] if len(parts) >= 2 else parts[0]
            if text.startswith("json"):
                text = text[4:]
        supergenre_map.update(json.loads(text.strip()))
        with open(SUPERGENRE_CACHE, "w") as f:
            json.dump(supergenre_map, f, indent=2)

    df["supergenre"] = df["all_tags"].apply(
        lambda s: supergenre_map.get(s.split(",")[0], "Other") if s else "Other"
    )
    # Every super-genre a song touches (any tag), used for preference filtering.
    df["supergenres"] = df["all_tags"].apply(lambda s: song_supergenres(s, supergenre_map))
    return df


@st.cache_data(show_spinner=False)
def build_genre_zone_network(df):
    """Super-genre -> emotional-zone bipartite graph (port of notebook cell 26)."""
    sg_zone_counts = Counter()
    for _, row in df.iterrows():
        quadrant = quadrant_label(row["valence"], row["energy"])
        sg_zone_counts[(row["supergenre"], quadrant)] += 1

    G = nx.Graph()
    G.add_nodes_from(QUADRANTS, kind="zone")
    for (supergenre, quadrant), weight in sg_zone_counts.items():
        if weight >= 2:
            G.add_node(supergenre, kind="genre")
            G.add_edge(supergenre, quadrant, weight=weight)
    return G


@st.cache_data(show_spinner=False)
def build_supergenre_emotion_network(df):
    """Super-genre -> discrete-emotion bipartite graph (port of notebook cell 30)."""
    supergenre_emotion_counts = Counter()
    for _, row in df.iterrows():
        for emotion, _weight in row["top_emotions"]:
            supergenre_emotion_counts[(row["supergenre"], emotion)] += 1

    G = nx.Graph()
    for (supergenre, emotion), weight in supergenre_emotion_counts.items():
        if weight >= 4:
            G.add_node(supergenre, kind="genre")
            G.add_node(emotion, kind="emotion")
            G.add_edge(supergenre, emotion, weight=weight)
    return G


@st.cache_data(show_spinner=False)
def build_frequent_tags(df):
    """Individual tags appearing on >= MIN_TAG_FREQ songs (port of notebook cell 23)."""
    tag_song_freq = Counter()
    for _, row in df.iterrows():
        for tag in set(split_genres(row.get("all_tags"))):
            tag_song_freq[tag] += 1
    return {t for t, c in tag_song_freq.items() if c >= MIN_TAG_FREQ}


@st.cache_data(show_spinner=False)
def build_genre_zone_network_detailed(df, frequent_tags):
    """Individual-tag -> emotional-zone bipartite graph (port of notebook cell 23)."""
    genre_zone_counts = {}
    for _, row in df.iterrows():
        quadrant = quadrant_label(row["valence"], row["energy"])
        for genre in split_genres(row.get("all_tags")):
            if genre not in frequent_tags:
                continue
            key = (genre, quadrant)
            genre_zone_counts[key] = genre_zone_counts.get(key, 0) + 1

    G = nx.Graph()
    G.add_nodes_from(QUADRANTS, kind="zone")
    for (genre, quadrant), weight in genre_zone_counts.items():
        if weight >= 2:
            G.add_node(genre, kind="genre")
            G.add_edge(genre, quadrant, weight=weight)
    return G


@st.cache_data(show_spinner=False)
def build_tag_emotion_network(df, frequent_tags):
    """Individual-tag -> discrete-emotion bipartite graph (port of notebook cell 33)."""
    tag_emotion_counts = Counter()
    for _, row in df.iterrows():
        tags = set(split_genres(row.get("all_tags"))) & frequent_tags
        for tag in tags:
            for emotion, _weight in row["top_emotions"]:
                tag_emotion_counts[(tag, emotion)] += 1

    G = nx.Graph()
    for (tag, emotion), weight in tag_emotion_counts.items():
        if weight >= 2:
            G.add_node(tag, kind="genre")
            G.add_node(emotion, kind="emotion")
            G.add_edge(tag, emotion, weight=weight)
    return G


@st.cache_data(show_spinner=False)
def build_heatmap_data(df):
    """Super-genre x emotion count matrix (port of notebook cell 36)."""
    supergenre_emotion_counts = Counter()
    for _, row in df.iterrows():
        for emotion, _weight in row["top_emotions"]:
            supergenre_emotion_counts[(row["supergenre"], emotion)] += 1

    sg_degree, emo_degree = {}, {}
    for (sg, emo), weight in supergenre_emotion_counts.items():
        if weight >= 4:
            sg_degree.setdefault(sg, set()).add(emo)
            emo_degree.setdefault(emo, set()).add(sg)

    supergenres = sorted(sg for sg, emos in sg_degree.items() if len(emos) >= 3)
    emotions    = sorted(emo for emo, sgs in emo_degree.items() if len(sgs) >= 3)

    matrix = np.array([
        [supergenre_emotion_counts.get((sg, emo), 0) for emo in emotions]
        for sg in supergenres
    ])
    return supergenres, emotions, matrix


def render_pyvis_html(net, physics_enabled=True):
    """Generate standalone HTML for a pyvis Network and patch in fixes pyvis's
    default template is missing:
      - a tooltip CSS override, without which multi-line hover tooltips render
        as a single unbounded line that runs off the visible canvas
      - a re-fit of the camera once physics settles. The template never calls
        network.fit() after stabilization, so the view stays centered on the
        nodes' initial random pre-physics positions while forceAtlas2Based /
        repulsion spreads them out — on a sparse graph the settled layout ends
        up mostly off-screen.
      - if physics_enabled is False, physics stays on just long enough for the
        layout to organise itself (same ~5s window as the fit polling) and is
        then switched off, so nodes stay put and can be dragged individually
        without the rest of the graph reacting."""
    html_str = net.generate_html()
    html_str = html_str.replace(
        "</head>",
        "<style>div.vis-tooltip { white-space: pre-wrap; max-width: 280px; }</style></head>",
    )
    freeze_after_settle = "false" if physics_enabled else "true"
    html_str = html_str.replace(
        "</body>",
        "<script>"
        "(function() {"
        "  var count = 0;"
        "  var timer = setInterval(function() {"
        "    network.fit();"
        "    count++;"
        "    if (count > 20) {"
        "      clearInterval(timer);"
        f"      if ({freeze_after_settle}) {{ network.setOptions({{physics: {{enabled: false}}}}); }}"
        "    }"
        "  }, 250);"
        "})();"
        "</script></body>",
    )
    return html_str


# ---------------------------------------------------------------------------
# Library count bar charts
# ---------------------------------------------------------------------------

BAR_COLOUR = "#4a6fa5"


def count_bar_chart(counts, x_label):
    """Horizontal single-series bar chart, largest at the top, values labelled."""
    counts = counts.sort_values(ascending=True)
    fig = px.bar(
        x=counts.values, y=counts.index, orientation="h", text=counts.values,
        labels={"x": x_label, "y": ""},
    )
    fig.update_traces(
        marker_color=BAR_COLOUR, marker_line_width=0, textposition="outside",
        hovertemplate="%{y}: %{x} songs<extra></extra>",
    )
    fig.update_layout(
        height=max(260, 32 * len(counts) + 80), margin=dict(l=10, r=40, t=10, b=40),
        bargap=0.35, showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.2)", zeroline=False),
        yaxis=dict(showgrid=False),
    )
    return fig


@st.cache_data(show_spinner=False)
def library_counts(df):
    supergenre_counts = pd.Series(
        Counter(sg for sgs in df["supergenres"] for sg in sgs)
    ).drop("Other", errors="ignore")
    emotion_counts  = df["dominant_emotion"].value_counts()
    quadrant_counts = df.apply(lambda r: quadrant_label(r["valence"], r["energy"]), axis=1).value_counts()
    return supergenre_counts, emotion_counts, quadrant_counts


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------

df_base, llm = load_enriched_df()
df_base = add_supergenre_column(df_base, llm)

st.title("Melbourne Moods")
st.caption("Emotion-regulated playlists using the iso principle from music therapy.")

# --- Sidebar ---
with st.sidebar:
    st.header("How are you feeling?")

    st.subheader("Right now")
    cur_v = st.slider("Valence (unpleasant → pleasant)", 0.0, 1.0, 0.23, 0.01, key="cur_v")
    cur_e = st.slider("Energy (calm → energized)",       0.0, 1.0, 0.10, 0.01, key="cur_e")
    st.caption(f"**{quadrant_label(cur_v, cur_e)}**")

    st.subheader("Where you want to be")
    des_v = st.slider("Valence (unpleasant → pleasant)", 0.0, 1.0, 0.75, 0.01, key="des_v")
    des_e = st.slider("Energy (calm → energized)",       0.0, 1.0, 0.82, 0.01, key="des_e")
    st.caption(f"**{quadrant_label(des_v, des_e)}**")

    st.divider()
    st.subheader("Genre preference")
    if GENRE_MODE == "llm":
        genre_input = st.text_input(
            "Enter genres separated by commas (optional)",
            placeholder="e.g. indie folk, jazz",
        )
        genre_preferences = [g.strip() for g in genre_input.split(",") if g.strip()] if genre_input else []
    else:
        genre_preferences = st.multiselect(
            "Pick one or more genres (optional)",
            SELECTABLE_SUPERGENRES,
            placeholder="Any genre",
        )

    st.divider()
    st.subheader("Playlist length")
    n_steps = st.slider("Number of songs", 3, 15, 10)

    generate = st.button("Generate playlist", type="primary", use_container_width=True)

# --- Main area ---
tab_playlist, tab_scatter, tab_genre_network, tab_emotion_network, tab_heatmap, tab_counts = st.tabs([
    "Playlist", "Song library", "Genre network", "Emotion network", "Genre × Emotion", "Library counts"
])

with tab_playlist:
    if not generate:
        st.info("Set your mood in the sidebar and click **Generate playlist**.")
    else:
        df = df_base.copy()

        genre_label = " + ".join(genre_preferences) if genre_preferences else None
        show_fit = False

        if genre_preferences and GENRE_MODE == "llm":
            # Per-song genre fit scored by OpenAI (cached to file after first run)
            genre_scores = []
            with st.spinner(f"Scoring genre fit for: {genre_label}..."):
                for genre in genre_preferences:
                    df = score_all_genre_fits(df, genre, llm)
                    genre_scores.append(df["genre_fit"].values.copy())
            df["genre_fit"] = np.mean(genre_scores, axis=0)
            show_fit = True
        elif genre_preferences:
            # Deterministic: keep only songs in the chosen super-genres. If that
            # leaves too few for a journey, prefer them instead of requiring them.
            df, hard = apply_supergenre_preference(df, genre_preferences, min_songs=2 * n_steps)
            if hard:
                genre_label = None   # already filtered; no genre term in the distance
            else:
                st.info(
                    f"Only {int(df['genre_fit'].sum())} songs match {genre_label}; "
                    "the playlist will favour them but also draw on other genres."
                )

        playlist = build_playlist(
            df, cur_v, cur_e, des_v, des_e,
            n_steps=n_steps,
            genre_request=genre_label,
        )

        col_list, col_chart = st.columns([1, 1], gap="large")

        with col_list:
            st.subheader(f"Your {n_steps}-song journey")
            for _, row in playlist.iterrows():
                with st.container():
                    st.markdown(f"**{int(row['step'])}.  {row['title']}**  \n*{row['artist']}*")
                    meta = f"valence {row['valence']}  ·  energy {row['energy']}"
                    if show_fit:
                        meta += f"  ·  genre fit {row['genre_fit']:.2f}"
                    st.caption(meta)

        with col_chart:
            st.subheader("Emotional journey")
            fig = plot_journey(playlist, cur_v, cur_e, des_v, des_e)
            st.pyplot(fig)
            plt.close(fig)

with tab_scatter:
    st.subheader("Song library — coloured by dominant emotion")
    fig2 = plot_scatter(df_base)
    st.pyplot(fig2)
    plt.close(fig2)

with tab_genre_network:
    genre_view = st.radio(
        "View", ["Super-genre", "Individual tags"],
        horizontal=True, key="genre_network_view", label_visibility="collapsed",
    )

    if genre_view == "Super-genre":
        st.markdown(
            "Which broad genres in the library — Rock, Pop, Hip Hop/Rap, and so on — show up "
            "in each of the four emotional quadrants, and how strongly. Hover a node to see "
            "the exact breakdown; drag nodes around, the layout will settle again."
        )

        G1b = build_genre_zone_network(df_base)
        supergenre_nodes = [n for n, d in G1b.nodes(data=True) if d["kind"] == "genre"]

        net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="black",
                      notebook=False, cdn_resources="in_line")

        for zone in QUADRANTS:
            top5 = sorted(G1b[zone].items(), key=lambda kv: kv[1]["weight"], reverse=True)[:5]
            tooltip = f"{zone}\nTop super-genres:\n" + "\n".join(
                f"  {g}: {d['weight']}" for g, d in top5
            )
            net.add_node(zone, label=zone, size=50, color="#fd8d3c", title=tooltip, shape="dot")

        for sg in supergenre_nodes:
            conns = sorted(G1b[sg].items(), key=lambda kv: kv[1]["weight"], reverse=True)
            tooltip = f"{sg}\nConnects to:\n" + "\n".join(
                f"  {z}: {d['weight']}" for z, d in conns
            )
            net.add_node(sg, label=sg, size=30, color="#6baed6", title=tooltip, shape="dot")

        for u, v, d in G1b.edges(data=True):
            net.add_edge(u, v, value=d["weight"] / 2, title=f"weight: {d['weight']}")

        net.set_options("""
        {
          "physics": {
            "enabled": true,
            "solver": "forceAtlas2Based",
            "forceAtlas2Based": {
              "gravitationalConstant": -50,
              "centralGravity": 0.01,
              "springLength": 120,
              "springConstant": 0.08
            },
            "stabilization": {"iterations": 150}
          }
        }
        """)

        physics_on = st.toggle("Physics", value=True, key="genre_sg_physics")
        components.html(render_pyvis_html(net, physics_enabled=physics_on), height=650)
        st.caption("Edge thickness shows how many songs in that genre land in that emotional zone.")

    else:
        frequent_tags = build_frequent_tags(df_base)
        st.markdown(
            f"The same relationship at the individual-tag level — every genre/mood tag "
            f"appearing on at least {MIN_TAG_FREQ} songs in the library ({len(frequent_tags)} "
            "tags), rather than the clustered super-genres above. Denser, but shows exactly "
            "which specific tags — not just broad genres — drive each emotional quadrant."
        )

        G1 = build_genre_zone_network_detailed(df_base, frequent_tags)
        genre_nodes = [n for n, d in G1.nodes(data=True) if d["kind"] == "genre"]

        net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="black",
                      notebook=False, cdn_resources="in_line")

        for zone in QUADRANTS:
            top5 = sorted(G1[zone].items(), key=lambda kv: kv[1]["weight"], reverse=True)[:5]
            tooltip = f"{zone}\nTop genres:\n" + "\n".join(
                f"  {g}: {d['weight']}" for g, d in top5
            )
            net.add_node(zone, label=zone, size=40, color="#fd8d3c", title=tooltip, shape="dot")

        for genre in genre_nodes:
            conns = sorted(G1[genre].items(), key=lambda kv: kv[1]["weight"], reverse=True)
            tooltip = f"{genre}\nConnects to:\n" + "\n".join(
                f"  {z}: {d['weight']}" for z, d in conns
            )
            net.add_node(genre, label=genre, size=15, color="#6baed6", title=tooltip, shape="dot")

        for u, v, d in G1.edges(data=True):
            net.add_edge(u, v, value=d["weight"] / 2, title=f"weight: {d['weight']}")

        net.set_options("""
        {
          "physics": {
            "enabled": true,
            "solver": "forceAtlas2Based",
            "forceAtlas2Based": {
              "gravitationalConstant": -50,
              "centralGravity": 0.01,
              "springLength": 100,
              "springConstant": 0.08
            },
            "stabilization": {"iterations": 150}
          }
        }
        """)

        physics_on = st.toggle("Physics", value=True, key="genre_tag_physics")
        components.html(render_pyvis_html(net, physics_enabled=physics_on), height=650)
        st.caption(
            f"{len(genre_nodes)} individual tags shown (appearing on ≥ {MIN_TAG_FREQ} "
            "songs); edge thickness shows how many songs with that tag land in that zone."
        )

with tab_emotion_network:
    emotion_view = st.radio(
        "View", ["Super-genre", "Individual tags"],
        horizontal=True, key="emotion_network_view", label_visibility="collapsed",
    )

    if emotion_view == "Super-genre":
        st.markdown(
            "Which discrete emotions — joy, nostalgia, rebellion, and so on — are most "
            "associated with each broad genre in the library. Hover a node to see the exact "
            "breakdown."
        )

        G3 = build_supergenre_emotion_network(df_base)
        genre_nodes_g3   = [n for n, d in G3.nodes(data=True) if d["kind"] == "genre"]
        emotion_nodes_g3 = [n for n, d in G3.nodes(data=True) if d["kind"] == "emotion"]

        net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="black",
                      notebook=False, cdn_resources="in_line")

        for emotion in emotion_nodes_g3:
            top3 = sorted(G3[emotion].items(), key=lambda kv: kv[1]["weight"], reverse=True)[:3]
            tooltip = f"{emotion}\nTop super-genres:\n" + "\n".join(
                f"  {sg}: {d['weight']}" for sg, d in top3
            )
            net.add_node(emotion, label=emotion, size=25, color="#fd8d3c", title=tooltip, shape="dot")

        for sg in genre_nodes_g3:
            top3 = sorted(G3[sg].items(), key=lambda kv: kv[1]["weight"], reverse=True)[:3]
            tooltip = f"{sg}\nTop emotions:\n" + "\n".join(
                f"  {emo}: {d['weight']}" for emo, d in top3
            )
            net.add_node(sg, label=sg, size=35, color="#6baed6", title=tooltip, shape="dot")

        for u, v, d in G3.edges(data=True):
            net.add_edge(u, v, value=d["weight"] / 2, title=f"weight: {d['weight']}")

        net.set_options("""
        {
          "physics": {
            "enabled": true,
            "solver": "forceAtlas2Based",
            "forceAtlas2Based": {
              "gravitationalConstant": -50,
              "centralGravity": 0.01,
              "springLength": 120,
              "springConstant": 0.08
            },
            "stabilization": {"iterations": 150}
          }
        }
        """)

        physics_on = st.toggle("Physics", value=True, key="emotion_sg_physics")
        components.html(render_pyvis_html(net, physics_enabled=physics_on), height=650)
        st.caption(
            "This network illustrates the semantic gap: the same super-genre can carry very "
            "different emotional textures, which is why genre labels alone are insufficient "
            "for emotion regulation."
        )

    else:
        frequent_tags = build_frequent_tags(df_base)
        st.markdown(
            f"The same relationship at the individual-tag level — every genre/mood tag "
            f"appearing on at least {MIN_TAG_FREQ} songs, paired with discrete emotions, "
            "rather than the clustered super-genres above. Much denser, so it uses stronger "
            "node repulsion to spread the layout out."
        )

        G4 = build_tag_emotion_network(df_base, frequent_tags)
        genre_nodes_g4   = [n for n, d in G4.nodes(data=True) if d["kind"] == "genre"]
        emotion_nodes_g4 = [n for n, d in G4.nodes(data=True) if d["kind"] == "emotion"]

        net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="black",
                      notebook=False, cdn_resources="in_line")

        for emotion in emotion_nodes_g4:
            top3 = sorted(G4[emotion].items(), key=lambda kv: kv[1]["weight"], reverse=True)[:3]
            tooltip = f"{emotion}\nTop genre tags:\n" + "\n".join(
                f"  {tag}: {d['weight']}" for tag, d in top3
            )
            net.add_node(emotion, label=emotion, size=25, color="#fd8d3c", title=tooltip, shape="dot")

        for tag in genre_nodes_g4:
            top3 = sorted(G4[tag].items(), key=lambda kv: kv[1]["weight"], reverse=True)[:3]
            tooltip = f"{tag}\nTop emotions:\n" + "\n".join(
                f"  {emo}: {d['weight']}" for emo, d in top3
            )
            net.add_node(tag, label=tag, size=15, color="#6baed6", title=tooltip, shape="dot")

        for u, v, d in G4.edges(data=True):
            net.add_edge(u, v, value=d["weight"] / 2, title=f"weight: {d['weight']}")

        net.set_options("""
        {
          "physics": {
            "enabled": true,
            "solver": "repulsion",
            "repulsion": {
              "nodeDistance": 150,
              "springLength": 200,
              "springConstant": 0.01
            },
            "stabilization": {"iterations": 200}
          }
        }
        """)

        physics_on = st.toggle("Physics", value=True, key="emotion_tag_physics")
        components.html(render_pyvis_html(net, physics_enabled=physics_on), height=650)
        st.caption(
            f"{len(genre_nodes_g4)} genre tags, {len(emotion_nodes_g4)} emotions, "
            f"{G4.number_of_edges()} edges (weight ≥ 2)."
        )

with tab_heatmap:
    st.markdown(
        "How song counts for each super-genre break down across discrete emotions — "
        "useful for spotting which genres carry which emotional signals most strongly."
    )

    heatmap_supergenres, heatmap_emotions, matrix = build_heatmap_data(df_base)

    fig3 = px.imshow(
        matrix,
        x=heatmap_emotions,
        y=heatmap_supergenres,
        color_continuous_scale="YlOrRd",
        text_auto=True,
        labels=dict(x="Emotion", y="Super-genre", color="Songs"),
    )
    fig3.update_traces(
        hovertemplate="Super-genre: %{y}<br>Emotion: %{x}<br>Song count: %{z}<extra></extra>",
    )
    fig3.update_layout(title="Super-genre × Emotion — Song Counts", xaxis_tickangle=-45)
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Emotional profile by super-genre (normalised)")
    normalised_matrix = matrix / matrix.sum(axis=1, keepdims=True)
    fig4 = px.imshow(
        normalised_matrix,
        x=heatmap_emotions,
        y=heatmap_supergenres,
        color_continuous_scale="YlOrRd",
        text_auto=".0%",
        labels=dict(x="Emotion", y="Super-genre", color="Share"),
    )
    fig4.update_traces(
        hovertemplate="Super-genre: %{y}<br>Emotion: %{x}<br>Share of songs: %{z:.1%}<extra></extra>",
    )
    fig4.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig4, use_container_width=True)

    st.markdown(
        "The normalised version above divides each row by its own total, making "
        "lower-volume super-genres like Jazz and Folk/Country comparable to Rock despite "
        "having far fewer songs in the library."
    )

with tab_counts:
    supergenre_counts, emotion_counts, quadrant_counts = library_counts(df_base)
    n_songs = len(df_base)

    st.subheader("Songs per super-genre")
    st.caption(
        f"A song counts towards every super-genre any of its tags maps to, so the bars "
        f"sum to more than the {n_songs} songs in the library. This is what the genre "
        "dropdown filters on. The \"Other\" bucket is omitted."
    )
    st.plotly_chart(count_bar_chart(supergenre_counts, "Songs"), use_container_width=True)

    st.subheader("Songs per dominant emotion")
    st.caption("Each song's single strongest emotion from its tag scores.")
    st.plotly_chart(count_bar_chart(emotion_counts, "Songs"), use_container_width=True)

    st.subheader("Songs per emotional zone")
    st.caption("Quadrant of the valence × energy space each song's Spotify features place it in.")
    st.plotly_chart(count_bar_chart(quadrant_counts, "Songs"), use_container_width=True)
