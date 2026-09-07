"""Where the app gets its OpenAI credentials from.

In the workshop deployment the key is supplied by the server (an environment
variable set from `deploy/grainger/.env`), so participants never handle one.
`st.secrets` is checked as well so the Streamlit Community Cloud build keeps
working unchanged.
"""

import os

import streamlit as st

MISSING_KEY_MESSAGE = (
    "No OpenAI API key is configured. Set `OPENAI_API_KEY` in the environment "
    "(or in `.streamlit/secrets.toml`) before starting the app."
)


def get_openai_key() -> str:
    """Returns the configured OpenAI API key, or an empty string if there is none."""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    try:
        return str(st.secrets["OPENAI_API_KEY"]).strip()
    except Exception:
        # No secrets.toml, or no such entry in it.
        return ""
