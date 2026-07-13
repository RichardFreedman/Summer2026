
import contextlib
import io
import json
import re
import tempfile
from pathlib import Path

import streamlit as st
from jsonschema import Draft202012Validator
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

import postprocess
from preprocess import preprocess, make_batches

HERE = Path(__file__).parent
BUNDLE = HERE / ".." / "bundle"
DATA = HERE / ".." / "data" / "Grainger_Catalog_Other_Composers.txt"

st.set_page_config(page_title="Grainger -> EMu parser demo", layout="wide")



# Cached loading; loads all the things in the context bundle and the demo dataset TXT file (Grainger's Collection of Music by Other Composers)


@st.cache_data
def load_bundle() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8")
            for p in sorted(BUNDLE.iterdir()) if p.is_file()}


@st.cache_data
def load_schema() -> dict:
    return json.loads((BUNDLE / "output_schema.json").read_text(encoding="utf-8"))


@st.cache_data
def load_entries():
    text = DATA.read_text(encoding="utf-8")
    entries = preprocess(text)
    return entries


@st.cache_data
def load_batches(entries, batch_size: int = 5):
    return make_batches(entries, batch_size)


def build_system_prompt(bundle: dict[str, str]) -> str:
    """Semantic rules, then the JSON files appended with delimiters"""
    parts = [bundle["system_prompt.md"]]
    for name in ("field_mapping.json", "output_schema.json", "worked_examples.json"):
        parts.append(f"\n\n----- BEGIN {name} -----\n{bundle[name]}\n----- END {name} -----")
    return "".join(parts)


# LLM call + validation


def extract_json(raw: str):
    """Parse the LLM output"""
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.S)
    return json.loads(s)


def validate_records(data, schema) -> list[str]:
    """Returns violations of output_schema.json"""
    validator = Draft202012Validator(schema)
    errors = []
    for err in validator.iter_errors(data):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"{loc}: {err.message[:300]}")
    return errors


def run_batch(llm: ChatOpenAI, system_prompt: str, batch_text: str, schema: dict):
    """Parses one batch of entries; on failure, tries to correct itself once"""
    user_msg = ("Convert the following catalogue entries into EMu-ready "
                "structured metadata (a JSON array conforming to "
                "output_schema.json):\n\n" + batch_text)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]
    attempts = []
    for attempt in (1, 2):
        raw = llm.invoke(messages).content
        try:
            data = extract_json(raw)
            errors = validate_records(data, schema)
        except json.JSONDecodeError as e:
            data, errors = None, [f"response was not valid JSON: {e}"]
        attempts.append({"attempt": attempt, "raw": raw, "errors": errors})
        if data is not None and not errors:
            return data, attempts
        # corrective retry: feed the errors back once
        messages.append(HumanMessage(content=(
            "Your previous response failed validation against "
            "output_schema.json with these errors:\n- " + "\n- ".join(errors)
            + "\nReturn the corrected full JSON array only.")))
    return data, attempts


# Post-processor


def run_postprocessor(argv: list[str]):
    """Calls postprocess.main(argv); returns output + exit code"""
    out_io, err_io = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out_io), contextlib.redirect_stderr(err_io):
            code = postprocess.main(argv)
    except SystemExit as e:  # load_config / load_records use sys.exit(str)
        code = e.code if isinstance(e.code, int) else 1
        if isinstance(e.code, str):
            err_io.write(e.code + "\n")
    except Exception as e:
        code = 1
        err_io.write(f"unhandled error: {e!r}\n")
    return code, out_io.getvalue(), err_io.getvalue()


def _save_upload(upload, directory: Path) -> Path:
    """saves an upload and returns its path for CLI args"""
    p = directory / upload.name
    p.write_bytes(upload.getvalue())
    return p


# UI


st.title("Grainger catalogue → EMu structured metadata (demo)")
st.caption("Tab 1: LLM; Parses entries into intermediate EMu-like JSON. Tab 2: Manual review + deterministic postprocessing of intermediate JSON to EMu import files")

with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("OpenAI API key", type="password",
                            help="Only kept in this session's memory.")
    model = st.selectbox("Model", ["gpt-5-mini", "gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini"])
    batch_size = st.slider("Entries per LLM call", 1, 10, 5,
                           help="Parent and '+' child entries always stay together regardless.")

bundle = load_bundle()
schema = load_schema()
units = load_entries()
batches = load_batches(units, batch_size)
entries = [e for b in batches for e in b.entries]

if "results" not in st.session_state:
    st.session_state.results = {}  

tab_parse, tab_post = st.tabs(["1 · LLM Parser (TXT > JSON)", "2 · Post-processor (JSON > EMu)"])

# Parser tab

with tab_parse:
    c1, c2, c3 = st.columns(3)
    c1.metric("Catalogue entries", len(entries))
    c2.metric("Batches", len(batches))
    c3.metric("Entries with + parts", sum(1 for e in entries
                                        if any(l.lstrip().startswith("+") for l in e.lines)))

    idx = st.number_input("Batch #", min_value=0, max_value=len(batches) - 1, value=0)
    batch = batches[int(idx)]
    st.write("**Entries in this batch:** " + ", ".join(f"`{n}`" for n in batch.numbers))

    tab_in, tab_out = st.tabs(["Batch input", "Parsed records"])
    with tab_in:
        st.code(batch.text, language=None) 

    # button is grayed out until you enter an api key in the sidebar
    run = st.button("Parse this batch", type="primary", disabled=not api_key)
    if not api_key:
        st.info("Enter an OpenAI API key in the sidebar to run the parser.")

    if run:
        llm = ChatOpenAI(model=model, temperature=0, api_key=api_key)
        with st.spinner(f"Parsing batch {idx} with {model}…"):
            try:
                data, attempts = run_batch(llm, build_system_prompt(bundle), batch.text, schema)
            except Exception as e:
                st.error(f"LLM call failed: {e}")
                data, attempts = None, []
        for a in attempts:
            if a["errors"]:
                st.warning(f"Attempt {a['attempt']}: " + "; ".join(a["errors"][:5]))
        if data is not None and attempts and not attempts[-1]["errors"]:
            st.success(f"{len(data)} record(s) parsed and validated against output_schema.json (attempt {attempts[-1]['attempt']}).")
            st.session_state.results[int(idx)] = data
        elif data is not None:
            st.error("Response still fails schema validation after retry—records shown below are NOT valid. Do not load into EMu.")
            st.session_state.results[int(idx)] = data

    with tab_out:
        records = st.session_state.results.get(int(idx))
        if not records:
            st.write("No parse yet for this batch.")
        else:
            # display review flags
            flags = [{"object_number": r.get("object_number"), "reason": f.get("reason"), "note": f.get("detail")} for r in records for f in (r.get("review_flags") or [])]
            st.subheader(f"review_flags ({len(flags)})—possible errors to manually review")
            if flags:
                st.dataframe(flags, width=True)
            else:
                st.write("None raised.")
            st.subheader("Records (intermediate JSON)")
            st.json(records, expanded=False)

    if st.session_state.results:
        combined = [r for i in sorted(st.session_state.results) for r in st.session_state.results[i]]
        st.download_button(
            f"Download all parsed records ({len(combined)}) as JSON",
            json.dumps(combined, ensure_ascii=False, indent=2),
            file_name="grainger_intermediate_records.json",
            mime="application/json",
        )

# Postprocessor tab

with tab_post:
    st.subheader("Deterministic post-processing (JSON → EMu import files)")

    combined = [r for i in sorted(st.session_state.results)
                for r in st.session_state.results[i]]
    src = st.radio("Records source",
                   [f"Parsed records from this session ({len(combined)})",
                    "Upload intermediate records JSON"],
                   horizontal=True)
    upload_mode = src.startswith("Upload")
    up_records = st.file_uploader("Intermediate records JSON", type=["json"],
                                  disabled=not upload_mode)

    col1, col2 = st.columns(2)
    up_corr = col1.file_uploader("--corrections · completed curator_review.csv",
                                 type=["csv"])
    up_part = col2.file_uploader("--parties-decisions · completed parties_review.csv",
                                 type=["csv"])
    up_cfg = st.file_uploader("--config · emu_columns.json "
                              "(default: the one next to the app)", type=["json"])

    col3, col4 = st.columns(2)
    allow_unv = col3.checkbox("--allow-unverified",
                              help="Emit DRAFT_ import files even while 'Verify' "
                                   "columns are unconfirmed in the config.")
    outdir_name = col4.text_input("--out · output directory", "emu_out")

    with st.expander("--init-config · generate a fresh emu_columns.json template"):
        if st.button("Generate template"):
            tdir = Path(tempfile.mkdtemp(prefix="emu_cfg_"))
            cfg_path = tdir / "emu_columns.json"
            code, out, err = run_postprocessor(["--init-config", "--config", str(cfg_path)])
            if code == 0:
                st.download_button("Download emu_columns.json",
                                   cfg_path.read_bytes(),
                                   file_name="emu_columns.json",
                                   mime="application/json")
            else:
                st.error(err or out)

    have_records = bool(up_records) if upload_mode else bool(combined)
    if not have_records:
        st.info("Parse some batches in tab 1 or upload a records JSON to enable the run.")

    if st.button("Run post-processor", type="primary", disabled=not have_records):
        tdir = Path(tempfile.mkdtemp(prefix="pp_in_"))
        if upload_mode:
            records_path = _save_upload(up_records, tdir)
        else:
            records_path = tdir / "records_from_session.json"
            records_path.write_text(json.dumps(combined, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
        cfg_path = _save_upload(up_cfg, tdir) if up_cfg else HERE / "emu_columns.json"
        out_dir = Path(outdir_name)
        if not out_dir.is_absolute():
            out_dir = HERE / out_dir

        argv = [str(records_path), "--config", str(cfg_path), "--out", str(out_dir)]
        if up_corr:
            argv += ["--corrections", str(_save_upload(up_corr, tdir))]
        if up_part:
            argv += ["--parties-decisions", str(_save_upload(up_part, tdir))]
        if allow_unv:
            argv += ["--allow-unverified"]

        with st.spinner("Running post-processor…"):
            code, out, err = run_postprocessor(argv)
        st.session_state.pp_run = {"code": code, "stdout": out, "stderr": err,
                                   "outdir": str(out_dir), "argv": argv}

    pp = st.session_state.get("pp_run")
    if pp:
        st.code("postprocess.py " + " ".join(pp["argv"]), language=None)
        if pp["code"] == 0:
            st.success("Exit 0 — import files written.")
        elif pp["code"] == 2:
            st.warning("Exit 2 — blocked by unconfirmed 'Verify' columns. Review files "
                       "were still written; confirm columns in emu_columns.json or use "
                       "--allow-unverified for DRAFT files.")
        else:
            st.error(f"Exit {pp['code']} — run failed.")
        if pp["stdout"]:
            st.code(pp["stdout"], language=None)
        if pp["stderr"]:
            st.warning(pp["stderr"])

        out_dir = Path(pp["outdir"])
        if out_dir.exists():
            st.subheader("Outputs")
            for f in sorted(out_dir.iterdir()):
                if f.suffix not in (".tsv", ".csv", ".md"):
                    continue
                dcol, pcol = st.columns([1, 3])
                dcol.download_button(f"Download {f.name}", f.read_bytes(),
                                     file_name=f.name, key=f"dl_{f.name}")
                with pcol.expander(f"Preview {f.name}"):
                    if f.suffix == ".md":
                        st.markdown(f.read_text(encoding="utf-8"))
                    else:
                        import pandas as pd
                        sep = "\t" if f.suffix == ".tsv" else ","
                        try:
                            st.dataframe(pd.read_csv(f, sep=sep, dtype=str).fillna(""),
                                         width=True)
                        except Exception:
                            st.code(f.read_text(encoding="utf-8")[:5000], language=None)
