import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

from langchain_ollama import ChatOllama
from recommender import (
    OLLAMA_MODEL,
    load_dataframe,
    enrich_dataframe,
    score_all_genre_fits,
    build_playlist,
)

st.set_page_config(page_title="MoodRec", page_icon="🎵", layout="wide")


# ---------------------------------------------------------------------------
# Cached startup — runs once per server session
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def load_enriched_df():
    with st.spinner("Starting up — loading songs and enriching with tags (first run only)..."):
        llm = ChatOllama(model=OLLAMA_MODEL, temperature=0)
        df  = load_dataframe()
        df  = enrich_dataframe(df, llm)
    return df, llm


# ---------------------------------------------------------------------------
# Journey chart
# ---------------------------------------------------------------------------

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
        ax.annotate(f"{int(row['step'])}. {row['title']}",
                    (row["valence"], row["energy"]),
                    textcoords="offset points", xytext=(6, 6), fontsize=8)

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
# Main UI
# ---------------------------------------------------------------------------

df_base, llm = load_enriched_df()

st.title("MoodRec")
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
    st.subheader("Genre / mood preference")
    genre_input = st.text_input(
        "Enter genres separated by commas (optional)",
        placeholder="e.g. indie folk, jazz",
    )
    genre_preferences = [g.strip() for g in genre_input.split(",") if g.strip()] if genre_input else []

    st.divider()
    st.subheader("Playlist length")
    n_steps = st.slider("Number of songs", 3, 15, 10)

    generate = st.button("Generate playlist", type="primary", use_container_width=True)

# --- Main area ---
tab_playlist, tab_scatter = st.tabs(["Playlist", "Song library"])

with tab_playlist:
    if not generate:
        st.info("Set your mood in the sidebar and click **Generate playlist**.")
    else:
        df = df_base.copy()

        # Genre scoring (cached to file — fast on repeat runs)
        if genre_preferences:
            genre_scores = []
            with st.spinner(f"Scoring genre fit for: {', '.join(genre_preferences)}..."):
                for genre in genre_preferences:
                    df = score_all_genre_fits(df, genre, llm)
                    genre_scores.append(df["genre_fit"].values.copy())
            df["genre_fit"] = np.mean(genre_scores, axis=0)
            genre_label = " + ".join(genre_preferences)
        else:
            genre_label = None

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
                    if genre_label:
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
